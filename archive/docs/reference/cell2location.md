# Cell2location 示例完整指南

本指南演示如何为 **空间转录组去卷积（spatial deconvolution）** Skill 构建一套从单元测试到真实数据验收的完整 benchmark 体系，并搭配 渐进测试策略使用。

## 1. 为什么需要分层测试？

cell2location 这类分析型 Skill 具有以下特点：

- 运行时间长（GPU 上可能数小时）
- 依赖真实 Visium 数据，获取和标注成本高
- 代码修改容易引发回归，但全量回归测试代价大

因此采用 **渐进四级测试策略**：

| 级别 | 名称 | 数据规模 | 用途 | 是否评分 |
|------|------|----------|------|----------|
| 0 | Unit | 微小合成数据 | 烟雾测试，验证输出格式 | 是 |
| 1 | Component | 小合成数据 | 与 golden proportions 对比 RMSE | 是 |
| 2 | Integration | 中合成数据 | 检验相关性和稳定性 | 是 |
| 3 | Release | 真实 Visium | 仅检查能否跑通 | 否（completion-only） |

## 2. 示例结构

```text
examples/benchmark_cell2location/
├── SKILL.md                        # Skill 文档
├── benchmarks/
│   └── bio-spatial-deconvolution-cell2location/
│       ├── registry.yaml           # 四级 benchmark 定义
│       ├── tasks/
│       │   └── deconvolution.yaml  # 任务契约（prompt、输入输出格式）
│       ├── data/                   # 输入数据（按级别分子目录）
│       └── expected/               # golden proportions
├── scripts/
│   ├── generate_data.py            # 生成合成数据
│   └── run_c2l.py                  # 示例 skill 代码
└── README.md
```

## 3. 生成数据

```bash
python examples/benchmark_cell2location/scripts/generate_data.py
```

该脚本使用 `skillprism.testing.mock_data.generate_visium_data()` 生成：

- 参考 scRNA-seq 数据（含 `cell_type` 标签）
- Visium-like 空间数据
- 每个 spot 的真实细胞类型比例（保存到 `expected/`）

## 4. 运行 渐进测试流水线

```bash
test-skill --mode gradual \
    --skill bio-spatial-deconvolution-cell2location \
    --registry examples/benchmark_cell2location/benchmarks/bio-spatial-deconvolution-cell2location/registry.yaml \
    --max-level 2
```

渐进测试会依次运行 level 0、1、2。任何一级失败都会立即停止，避免在明显有问题的版本上浪费 level 3 的真实数据运行时间。

## 5. 集成到 CI

使用 `skill-ci`。注意：`skill-ci` **默认只做静态检查**（rubric、smoke、依赖复现、安全扫描，不调用 LLM）；要真正跑 benchmark 必须显式加 `--run-benchmark` 并提供预生成的 skill 代码 `--code`。另外 `skill-ci` 没有 `--mode`，渐进执行请用第 4 节的 `test-skill --mode gradual`；这里用 registry 中真实存在的 suite（`smoke` / `gradual` / `release`）：

```bash
skill-ci \
    --skill bio-spatial-deconvolution-cell2location \
    --registry examples/benchmark_cell2location/benchmarks/bio-spatial-deconvolution-cell2location/registry.yaml \
    --suite smoke \
    --run-benchmark \
    --code examples/benchmark_cell2location/scripts/run_c2l.py \
    --baseline path/to/your/baseline.yaml \
    --ratchet
```

- `--baseline` 接**用户自行管理的对比基线 yaml**（通常由上一次运行的结果保存而来，例如 `test-skill ... --output baselines/c2l.yaml`）；示例仓库本身不附带该文件，需要自己生成。
- `--ratchet` 会在全部通过后把当前结果提升为新的 baseline。

## 6. 真实数据验收

level 3 benchmark 标记为 `real_data: true` 和 `requires_gpu: true`：

```yaml
c2l_level3_real_data:
  real_data: true
  requires_gpu: true
```

在 `compare_suite` 中，真实数据 benchmark 只检查 `_all_pass`（即完成），不参与数值回归比较。这允许在真实数据上只验证「能跑通且输出有效」，而不必追求与合成数据相同的精确阈值。

## 7. 扩展建议

- 为 `scripts/run_c2l.py` 添加 cell2location 真实训练逻辑（替换示例中的 NNLS fallback）
- 调整 `benchmarks/bio-spatial-deconvolution-cell2location/registry.yaml` 中 `mean_rmse`、`min_pearson` 阈值以匹配你的模型精度
- 在真实数据目录 `data/real_visium/` 准备好后，运行 `--max-level 3`
