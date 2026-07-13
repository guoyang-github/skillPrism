# 生物信息类 Skill 的 Benchmark 设计

生物信息分析（单细胞、空间转录组、基因组、蛋白组等）有几个共同特点：数据体量大、依赖版本敏感、算法带随机性、输出格式复杂、且“看起来跑通了”不等于“生物学上正确”。因此，生物信息类 Skill 的 Benchmark 不能只做 smoke 测试，而要覆盖 **结构正确性、生物学合理性、鲁棒性、可复现性** 四个维度。

---

## 1. Benchmark 对生物信息类 Skill 的核心意义

| 意义 | 说明 |
|---|---|
| **动态验证算法契约** | Rubric 只能检查 SKILL.md 写得是否规范；Benchmark 才能确认“输入一个 `.h5ad`，输出确实包含 `leiden` 列、聚类数合理、轮廓系数达标”。 |
| **金标准对比** | 生物分析常有 ground truth（已知细胞比例、已知注释、已知 marker）。Benchmark 通过 `expected` 把输出和金标准对比，例如去卷积的 RMSE / Pearson。 |
| **回归防护** | 修改 prompt、模型或依赖版本后，同一组数据结果是否还稳定？Benchmark 是防止“这次改好了、下次又坏了”的护栏。 |
| **成本分层** | 真实 Visium / 单细胞数据往往大且昂贵。用 `level` 把 Benchmark 分成 unit / component / integration / release，便宜测试先做，贵的真实数据最后做。 |
| **可重复性** | 数据、task spec、expected、metric 都进 Git，任何人在干净环境里都能复现同一评估。 |

---

## 2. 数据配置策略

### 2.1 目录结构

推荐按 **per-skill registry** 组织（以 `examples/benchmark_cell2location/` 为例）：

```text
examples/benchmark_cell2location/
├── benchmarks/<skill>/
│   ├── registry.yaml           # 该 skill 的所有 benchmark + suites
│   ├── tasks/<task>.yaml       # 任务契约（prompt、输入输出格式）
│   ├── data/                   # 输入数据
│   │   ├── tiny/               # Level 0：单元/边界测试
│   │   ├── small/              # Level 1：组件测试
│   │   ├── medium/             # Level 2：集成测试
│   │   └── real_visium/        # Level 3：真实数据验收
│   └── expected/               # 金标准输出
└── scripts/generate_data.py    # 合成数据生成脚本（在 example 根目录，不在 benchmarks/<skill>/ 下）
```

### 2.2 数据来源

| 数据类型 | 适用场景 | 示例 |
|---|---|---|
| **合成数据（synthetic）** | Level 0–2：快速、可控、可验证边界。形状/比例已知，适合 smoke 和回归。 | `examples/benchmark_cell2location/scripts/generate_data.py` |
| **公开内置数据** | Level 1：用社区公认数据集做组件测试。 | `scanpy.datasets.pbmc3k_processed` |
| **真实生产数据** | Level 3：最终验收，但通常只检查 completion / 基础指标，避免跑太久。 | 用户自备 `real_visium/` |

### 2.3 registry 配置示例

参考 `examples/benchmark_cell2location/benchmarks/bio-spatial-deconvolution-cell2location/registry.yaml`：

```yaml
schema_version: "2.0"
cache_dir: ".benchmark_cache"

suites:
  gradual:
    description: Failure-mode-first progression from unit to release
    benchmarks:
      - c2l_level0_smoke
      - c2l_level1_small
      - c2l_level2_medium

benchmarks:
  c2l_level0_smoke:
    name: "Level 0: tiny smoke test"
    skill: bio-spatial-deconvolution-cell2location
    task: deconvolution
    level: 0
    input:
      path: data/tiny          # 相对 registry 目录
      description: 10 spots, 3 cell types; verifies output shape and basic validity
    expected:
      path: expected/tiny_proportions.csv
      format: csv
    metrics:
      - id: n_spots            # 先验形状检查
        type: exact
        expected: 10
      - id: n_cell_types
        type: exact
        expected: 3
```

要点：

- `input` 只给相对路径，**不要在 task spec 里写死绝对路径**。
- `expected` 是金标准，必须人工或脚本生成后 review。
- `expected` **不是必须的**。如果只是想检查输出自身的指标（如 `n_spots == 10`、`n_clusters` 在合理范围），可以省略 `expected`，直接对 actual output 写 metric。
- `metrics` 写在 registry 的 benchmark 条目里；task spec 只保留输入输出格式和 prompt。
- 不要把几个指标值硬塞进 `expected` 文件，再让 metric 去读它；指标值应直接写在 `metrics` 里，或通过私有 metric 从 actual output 计算。
- 用 `description` 字段说明数据的生物学背景（细胞数、spot 数、批次等）。

---

## 3. 必须覆盖的边界与特殊场景

生物信息数据天然有坑，Benchmark 不覆盖边界等于没测。

| 场景 | 设计方法 | metric 示例 |
|---|---|---|
| **空/极小数据** | Level 0 用 10 spots × 3 cell types 的 tiny 数据。 | `n_spots: exact 10` |
| **格式错误/缺失文件** | 故意提供缺少 `spatial.h5ad` 或 `reference.h5ad` 的目录，期望 skill 报错退出。 | `expected_result: fail` + `expected_error` |
| **异常值 / 零表达** | 合成数据里加入全零 spot、缺失值。 | 检查输出是否仍行和为 1，无 NaN |
| **细胞类型不平衡** | 某细胞类型占比极小。 | `min_pearson` 保障稀有类型也能被识别 |
| **随机性控制** | 聚类、降维常带随机种子。 | 用 range / tolerance 指标而非 exact；必要时在 task prompt 里要求固定 seed |
| **资源/超时** | 大数据或 GPU 任务。 | `requires_gpu: true`、`real_data: true`、sandbox timeout |
| **依赖版本差异** | scanpy / anndata 版本变更导致读取行为不同。 | CI 中固定依赖，benchmark 用 lockfile |

### 3.1 负向测试示例

 skillPrism 支持“期望失败”的 benchmark：

```yaml
benchmarks:
  clustering_missing_x_pca:
    skill: bio-single-cell-clustering
    task: clustering
    level: 0
    input:
      path: data/no_pca.h5ad
    expected_result: fail
    expected_error: "X_pca"
    metrics: []
```

这能验证 skill 遇到不合规输入时是否会给出明确错误，而不是静默返回错误结果。

判定逻辑（`skillprism/benchmark/runner.py` 的 `_evaluate_expected_result`）：`expected_result: fail` 时，运行结果必须实际产生**非空** `error`，且 `error` 要匹配 `expected_error` 正则（`re.search`，默认 `.+`）才判 PASS；skill 意外跑通（无 error）会判 FAIL。

### 3.2 真实数据只验收、不严格评分

Level 3 的真实数据往往受样本质量、批次效应影响，不建议用 tight threshold 评判。推荐：

```yaml
c2l_level3_real_data:
  name: "Level 3: real Visium acceptance"
  skill: bio-spatial-deconvolution-cell2location
  task: deconvolution
  level: 3
  real_data: true
  requires_gpu: true
  input:
    path: data/real_visium
  expected:
    path: expected/real_proportions.csv
    format: csv
  metrics:
    - id: n_spots
      type: min
      threshold: 100
    - id: n_cell_types
      type: min
      threshold: 2
```

这里只检查“输出了合理形状的结果”，不检查与金标准的严格相似度，避免真实数据波动导致误判。

---

## 4. Metric 选择建议

生物信息类 Skill 的 metric 通常分三层（完整清单、注册方式与五种比较类型见 [Benchmark Metrics 参考与最佳实践](./benchmark-metrics.md)，该文是 metric 主题的唯一权威源）：

| 层次 | 作用 | 常用 metric |
|---|---|---|
| **结构指标** | 输出格式、维度、列名是否正确 | `n_spots`、`n_cell_types`、`n_clusters`、`has_required_columns`、`row_count` |
| **生物学指标** | 与金标准或先验知识的一致性 | `mean_rmse`、`max_rmse`、`min_pearson`、`mean_pearson`、`ari`、`nmi`、`silhouette_score` |
| **鲁棒性指标** | 输出是否稳定、无异常值 | `largest_cluster_ratio`、`mean_jsd` |

---

## 5. 推荐实施路线图

1. **每个生物 skill 一个 registry**：`benchmarks/<skill>/registry.yaml`。
2. **先写数据生成脚本**：`scripts/generate_data.py` 用确定性 seed 生成 synthetic 数据，确保可复现。
3. **按四级渐进设计**：
   - Level 0：形状、格式、基本存在性（秒级）
   - Level 1：小数据上的生物学正确性（分钟级）
   - Level 2：更大/更复杂数据的稳定性（十分钟级）
   - Level 3：真实数据 completion-only（小时级 / GPU）
4. **把随机性约束写进 prompt**：例如“使用 `random_state=42`”。
5. **真实数据不评分只验收**：`real_data: true` + 宽松 metric。
6. **用 `suites` 组织常用组合**：`smoke`、`gradual`、`release`，方便 CI 快速选择。

---

## 6. 参考示例

- 最小可运行示例：`examples/benchmark_minimal/benchmarks/bio-single-cell-clustering/`
- 完整四级渐进分层示例：`examples/benchmark_cell2location/benchmarks/bio-spatial-deconvolution-cell2location/`
- 通用 metric 注册：`skillprism/benchmark/metrics.py`
