> 学习目标：掌握如何为计算昂贵的 Skill 设计渐进式测试，并在真实数据上只做完成性验收。

# 第 8 章：渐进测试模式与真实数据验收

## 8.1 什么场景需要渐进测试？

当 Skill 满足以下特征时，全量回归测试成本过高：

- 单次运行需要 GPU 和数小时
- 真实数据集大、标注稀缺
- 小修改即可导致明显回归

渐进测试模式（`test-skill --mode gradual`）把测试分成 4 级，从快到慢、从合成到真实，逐级放行。这种分层设计受 darwin-skill 启发，但已内化为 skillPrism 的 `--mode gradual` CLI。

## 8.2 四级 benchmark 设计

### Level 0：单元测试

使用 `skillprism.testing.mock_data` 生成最小数据，检查：

- 输出文件存在
- 输出形状正确
- 无异常报错

```yaml
# benchmarks/bio-spatial-deconvolution-cell2location/registry.yaml
benchmarks:
  c2l_level0_smoke:
    skill: bio-spatial-deconvolution-cell2location
    level: 0
    task: deconvolution
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
    skill: bio-spatial-deconvolution-cell2location
    level: 1
    task: deconvolution
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
    skill: bio-spatial-deconvolution-cell2location
    level: 2
    task: deconvolution
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
    skill: bio-spatial-deconvolution-cell2location
    level: 3
    real_data: true
    requires_gpu: true
    task: deconvolution
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

## 8.4 真实数据只做完成性检查

`compare_suite` 会把 benchmark 分成 `mock` 和 `real_data` 两个 bucket：

- mock：正常数值回归比较
- real_data：只检查 `_all_pass` 是否为 true

这避免了在真实数据上设定过于严格、容易波动的阈值。

## 8.5 本章小结

- 渐进测试模式通过 4 级测试降低昂贵 Skill 的回归测试成本
- 每级用 `level` 字段标记，suite 可以组合不同级别
- 真实数据 benchmark 用 `real_data: true` 标记，只做完成性验收
- `test-skill --mode gradual` CLI 自动 ratchet 基线、失败即停
