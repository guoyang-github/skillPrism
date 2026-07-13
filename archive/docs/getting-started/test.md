# 测试一个 Skill

> `test-skill` 回答：Agent 按 SKILL.md 生成的代码，在数据上跑不跑得通？

## 自然语言交互方式（Agent 场景）

不同阶段的测试，用户想问的问题也不一样：

| 你想验证什么 | 对 Agent 说 | 对应模式 |
|---|---|---|
| 代码会不会一跑就崩 | "生成一份最小示例，看看这个 skill 能不能跑起来" | `--mode single --level 0` |
| 输出结构/数值对不对 | "跑一下 level 1，看看基本指标是否达标" | `--mode single --level 1` |
| 先用最便宜的 gate 快速验证 | "先快速验证一下这个 skill，别跑太重的数据" | `--mode quick` |
| 从边界到真实逐步放行 | "从简单到复杂逐步测试这个 skill" | `--mode gradual` |
| 只跑 smoke suite | "只跑 smoke 测试，看看核心路径会不会崩溃" | `--mode single --suite smoke` |

Agent 会：
1. 读取 `SKILL.md`
2. 按任务要求产出结果（自己执行，或生成代码文件如 `examples/minimal_example.py` 交给引擎执行）
3. 调用 `test-skill --skill <skill> --registry benchmarks/<skill>/registry.yaml [--code <path>]` 评估

## 重要前提：三种执行方式

**skillPrism 引擎不生成代码，也不替你执行任务。** 产出结果的途径有三种，`test-skill` 只负责评估：

| 方式 | 谁产出结果 | 何时用 |
|---|---|---|
| **results（默认）** | Agent / 子 Agent 已把结果产出到预期输出路径；引擎跳过执行、直接判分 | 最常用：验证 Agent 刚做完的结果。显式传 `--results` 可强制此方式（忽略 `SKILLPRISM_AGENT_COMMAND`） |
| **`--code`** | 引擎执行你（或 Agent）预先生成的代码文件 | 需要可重复、无人值守的执行 |
| **外部 agent** | 配置 `SKILLPRISM_AGENT_COMMAND` 后，引擎调用该命令产出结果 | 接入线上 agent 做批量执行 |

优先级：`--code` > 显式 `--results` > `SKILLPRISM_AGENT_COMMAND` > 默认 results。手动场景下想跑 `--code`，需自己写好代码文件传入。

> Benchmark 本身（task spec、数据、registry）的构建流程见 [构建你的第一个 Benchmark](../tutorial/04-building-your-first-benchmark.md)。

## Level 0-2 的数据策略

渐进测试中 level 0-2 使用的数据**不是由引擎统一自动生成**，而是由 `benchmarks/<skill>/registry.yaml` 中对应 benchmark 条目的 `input.path`（直接指向数据路径）或 `dataset`（声明来源，引擎按需获取）决定。`dataset` 支持的类型：

| dataset type | 来源 | 是否自动生成 | 典型用途 |
|---|---|---|---|
| `builtin` | Python 表达式，如 `scanpy.datasets.pbmc3k_processed` | 否 | 使用内置真实数据集 |
| `local` | 用户预置目录，如 `data/tiny`、`data/small` | 否 | 用户自己准备的小型合成数据 |
| `url` | 远程文件 | 否 | 按需下载 |
| `synthetic` | 暂未原生支持 | 否 | 可先用 `skillprism.testing.mock_data` 生成再保存为 `local` |

你可以用 `skillprism.testing.mock_data` 中的函数（如 `generate_table_csv`、`generate_anndata`、`generate_visium_data`）先生成合成数据，再注册为 `type: local`。

## 单次测试

```bash
test-skill --skill my-skill \
  --registry benchmarks/my-skill/registry.yaml \
  --code skills/my-skill/examples/minimal_example.py \
  --mode single \
  --level 1
```

## 渐进测试

```bash
test-skill --skill my-skill \
  --registry benchmarks/my-skill/registry.yaml \
  --code skills/my-skill/examples/minimal_example.py \
  --mode gradual \
  --max-level 2
```

渐进测试从 level 0 开始，逐级放行：

| Level | 数据 | 检查内容 |
|---|---|---|
| 0 | 最小数据 + 边界输入 | 是否崩溃、边界行为 |
| 1 | 小数据 | 数值回归 |
| 2 | 中数据 | 稳定性 / 相关性 |
| 3 | 真实数据 | 能否跑通 |

## 快速 Gate

```bash
test-skill --skill my-skill \
  --registry benchmarks/my-skill/registry.yaml \
  --code skills/my-skill/examples/minimal_example.py \
  --mode quick
```

Quick 模式只跑 level 0 + level 1，是最便宜的完整 gate。

## 什么是 Suite？

Suite 在 `benchmarks/<skill>/registry.yaml` 的 `suites` 字段中定义，把多个 benchmark 分组，用于不同场景的快速选择：

```yaml
suites:
  smoke:
    description: Fast smoke tests using tiny synthetic data
    benchmarks:
      - level0_smoke
  gradual:
    description: Failure-mode-first progression from unit to release
    benchmarks:
      - level0_smoke
      - level1_small
      - level2_medium
  release:
    description: Release gate including real-data acceptance
    benchmarks:
      - level0_smoke
      - level1_small
      - level2_medium
      - level3_real_data
```

示例 registry 中常见的三个 suite：

| Suite | 典型范围 | 用途 |
|---|---|---|
| `smoke` | level 0 | 最快验证，检查是否崩溃 |
| `gradual` | level 0 → 2 | 失败优先的渐进验证 |
| `release` | level 0 → 3 | 完整发布门控，含真实数据 |

## 指定 suite

```bash
test-skill --skill my-skill \
  --registry benchmarks/my-skill/registry.yaml \
  --code code.py --suite smoke --mode single
```

`--mode` 和 `--suite` 可以组合：

- `--suite smoke`：只跑 smoke suite 里的 benchmark
- `--suite gradual --mode gradual`：按 gradual suite 逐级跑
- 不指定 suite 时：跑 registry 中所有 `skill` 字段匹配 `--skill` 的 benchmark（可再按 `--task` / `--level` 过滤）
