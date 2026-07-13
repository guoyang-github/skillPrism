# 渐进测试（Gradual Testing）

> 渐进测试是 skillPrism 为 **计算昂贵、回归代价高** 的 skill 设计的失败优先测试策略。它从最容易失败的轻量级用例开始，逐级放行到真实数据验收。

## 核心思想

1. **先失败，后通过**：每轮优化先跑 level 0 单元测试，只有通过了才跑更贵的集成/释放级测试。
2. **ratchet 基线**：每级通过后将该级结果保存为新的 baseline，防止后续回退。
3. **尽早停止**：一旦某级失败，立刻停止，不浪费资源。
4. **真实数据 completion-only**：真实数据只检查能否跑通，不做数值回归。

## 四级定义

| 级别 | 名称 | 典型数据 | 关注点 |
|---|---|---|---|
| 0 | unit | 最小合成数据 | 输出格式、边界条件 |
| 1 | component | 小合成数据 | 与 golden 输出对比 |
| 2 | integration | 中合成数据 | 稳定性、相关性 |
| 3 | release | 真实数据 | 完成性、资源需求 |

在 `benchmarks/<skill>/registry.yaml` 中通过 `level` 字段标记：

```yaml
benchmarks:
  my_level0:
    level: 0
    task: table
  my_level3_real:
    level: 3
    real_data: true
    requires_gpu: true
```

## CLI

### `test-skill --mode gradual`

```bash
test-skill \
  --skill my-skill \
  --code my_skill_code.py \
  --registry benchmarks/my-skill/registry.yaml \
  --mode gradual \
  --max-level 2
```

### 与改进联动

在 `improve-skill --judge` 中，若某轮编辑导致 benchmark 回归，优化器会回退。结合渐进测试，可在每轮编辑后先跑 level 0 快速 gate。

## CI 集成

`skill-ci` 支持 `--level`：

```bash
skill-ci \
  --skill my-skill \
  --registry benchmarks/my-skill/registry.yaml \
  --level 0
```

## 实现细节

- 每级 baseline 保存在 `artifacts/<skill>/ci/gradual/.baselines/<skill>/gradual_baseline_level<N>.yaml`
- GPU-only benchmark 在无 GPU 环境自动跳过

## 历史说明

渐进测试策略最初受到 [alchaincyf/darwin-skill](https://github.com/alchaincyf/darwin-skill) 的启发，但已在 skillPrism 中实现为第一方能力，用户可见命令为 `test-skill --mode gradual`。
