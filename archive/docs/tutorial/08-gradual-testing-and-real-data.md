> 学习目标：掌握如何为计算昂贵的 Skill 设计渐进式测试，并在真实数据上只做完成性验收。

# 第 8 章：渐进测试模式与真实数据验收

## 8.1 什么场景需要渐进测试？

当 Skill 满足以下特征时，全量回归测试成本过高：

- 单次运行需要 GPU 和数小时
- 真实数据集大、标注稀缺
- 小修改即可导致明显回归

渐进测试模式（`test-skill --mode gradual`）把测试分成 4 级，从快到慢、从合成到真实，逐级放行。这种失败优先的分层设计已内化为 skillPrism 的 `--mode gradual` CLI。

## 8.2 四级 benchmark 设计

四级的定位（完整定义见 [测试一个 Skill](../getting-started/test.md)）：

| 级别 | 名称 | 典型数据 | 关注点 |
|---|---|---|---|
| 0 | unit | 最小合成数据 | 输出格式、边界条件 |
| 1 | component | 小合成数据 | 与 golden 输出对比 |
| 2 | integration | 中合成数据 | 稳定性、相关性 |
| 3 | release | 真实数据 | 完成性、资源需求 |

下面以 cell2location 示例（`examples/benchmark_cell2location/`）说明各级的 registry 写法。
每个 benchmark 条目中，`name` 是人类可读标签（输出报告里显示），`task_spec` 是 task spec
相对 registry 目录的路径（省略时默认 `tasks/<task>.yaml`）。

### Level 0：单元测试

使用 `skillprism.testing.mock_data` 生成最小数据，检查：

- 输出文件存在
- 输出形状正确
- 无异常报错

```yaml
# examples/benchmark_cell2location/benchmarks/bio-spatial-deconvolution-cell2location/registry.yaml
benchmarks:
  c2l_level0_smoke:
    name: "Level 0: tiny smoke test"
    skill: bio-spatial-deconvolution-cell2location
    level: 0
    task: deconvolution
    task_spec: tasks/deconvolution.yaml
    input:
      path: data/tiny
    expected:
      path: expected/tiny_proportions.csv
    metrics:
      - id: n_spots
        type: exact
        expected: 10
```

### Level 1：组件回归

加入 golden 输出，开始数值比较：

```yaml
  c2l_level1_small:
    name: "Level 1: small mock regression"
    skill: bio-spatial-deconvolution-cell2location
    level: 1
    task: deconvolution
    task_spec: tasks/deconvolution.yaml
    input:
      path: data/small
    expected:
      path: expected/small_proportions.csv
    metrics:
      - id: mean_rmse
        type: max
        threshold: 0.45
```

### Level 2：集成测试

更大规模合成数据，检查稳定性：

```yaml
  c2l_level2_medium:
    name: "Level 2: medium mock integration"
    skill: bio-spatial-deconvolution-cell2location
    level: 2
    task: deconvolution
    task_spec: tasks/deconvolution.yaml
    input:
      path: data/medium
    expected:
      path: expected/medium_proportions.csv
    metrics:
      - id: min_pearson
        type: min
        threshold: 0.30
```

### Level 3：真实数据验收

标记 `real_data: true` 和 `requires_gpu: true`，只检查完成：

```yaml
  c2l_level3_real_data:
    name: "Level 3: real Visium acceptance"
    skill: bio-spatial-deconvolution-cell2location
    level: 3
    real_data: true
    requires_gpu: true
    task: deconvolution
    task_spec: tasks/deconvolution.yaml
    input:
      path: data/real_visium
    expected:
      path: expected/real_proportions.csv
```

## 8.3 运行渐进测试流水线

```bash
test-skill --mode gradual \
    --skill bio-spatial-deconvolution-cell2location \
    --registry examples/benchmark_cell2location/benchmarks/bio-spatial-deconvolution-cell2location/registry.yaml \
    --max-level 2
```

输出示例：

```text
=== Gradual stage 0: unit ===
[PASS] Level 0: tiny smoke test
=== Gradual stage 1: component ===
[PASS] Level 1: small mock regression
=== Gradual stage 2: integration ===
[PASS] Level 2: medium mock integration

Overall: PASS
```

### Ratchet 基线与落盘位置

渐进流水线从 level 0 跑到 `--max-level`，每一级是一个 stage：

- **先失败，后通过**：某级失败时流水线立即停止，不浪费后续昂贵 stage 的资源。
- **ratchet（默认开启）**：某级全部通过时，把该级结果写入该级的 baseline，防止后续回退；
  可用 `--no-ratchet` 关闭。
- 每级 baseline 默认落盘在
  `artifacts/<skill>/ci/gradual/.baselines/<skill>/gradual_baseline_level<N>.yaml`
  （带 `--suite` 时文件名为 `gradual_baseline_level<N>_<suite>.yaml`），
  在 skill 源码树之外，不污染仓库。
- GPU-only benchmark（`requires_gpu: true`）在无 GPU 环境自动跳过。

## 8.4 真实数据只做完成性检查

`compare_suite` 会把 benchmark 分成 `mock` 和 `real_data` 两个 bucket：

- mock：正常数值回归比较
- real_data：只检查 `_all_pass` 是否为 true

这避免了在真实数据上设定过于严格、容易波动的阈值。

## 8.5 CI 集成

`skill-ci` 支持 `--level`，可以在 CI 里只跑某一级的 benchmark 作为门禁：

```bash
skill-ci \
  --skill my-skill \
  --registry benchmarks/my-skill/registry.yaml \
  --level 0
```

`--level` 与 `--suite` 可以组合；回归默认使 CI 失败（`--no-stop-on-regression` 可关闭）。

## 8.6 本章小结

- 渐进测试模式通过 4 级测试降低昂贵 Skill 的回归测试成本
- 每级用 `level` 字段标记，suite 可以组合不同级别
- 真实数据 benchmark 用 `real_data: true` 标记，只做完成性验收
- `test-skill --mode gradual` 逐级放行、失败即停，通过后自动 ratchet 该级基线到
  `artifacts/<skill>/ci/gradual/.baselines/<skill>/gradual_baseline_level<N>.yaml`
- `skill-ci --level` 可把单级测试接进 CI 门禁
