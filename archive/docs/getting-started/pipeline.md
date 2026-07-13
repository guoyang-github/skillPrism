# 运行完整流水线

> `skill-pipeline` 把"评估 → 测试 → 找最差 → 准备改进"串成一条命令。

## 自然语言交互（Agent 场景）

`skill-pipeline` 回答的是：**批量场景下，整体质量怎么样？下一步该做什么？**

它把"评估 → 测试 → 找最差 → 准备改进"串成一条命令。不同意图对应不同用户目标：

| 你想做什么 | 对 Agent 说 | 对应 `--intent` |
|---|---|---|
| 只看所有 skill 的文档分数 | "给所有 skills 打个分" | `evaluate all skills`（别名：`score all skills`、`评估所有 skills`） |
| 只跑测试并对比基线 | "跑一下所有 benchmark" | `run benchmarks` |
| 完整检查一遍 | "跑完整质量流水线" | `run full quality pipeline` |
| 找出最差的并准备优化 | "哪个 skill 最差？帮我准备优化" | `improve skills`（别名：`optimize skills`） |
| 批量渐进测试 | "对所有 skill 做渐进测试" | `run gradual pipeline` |

Agent 会翻译成对应的 `--intent`。

## 基本用法

```bash
skill-pipeline \
  --intent "run full quality pipeline" \
  --skills-dir ./skills \
  --benchmark-registry benchmarks/my-skill/registry.yaml
```

## 常用参数

| 参数 | 说明 |
|---|---|
| `--skills-dir` | Skill 目录（默认 `./skills`） |
| `--benchmark-registry` | Benchmark 注册表 |
| `--benchmark-suite` | 指定 suite |
| `--max-level` | 渐进测试最大 level |
| `--output` | 综合报告输出路径 |
| `--run-smoke` | 同时跑 smoke test |
| `--apply` | 自动应用优化决策（配合 `improve skills`） |
| `--max-rounds` | 最大优化轮数 |

## 示例输出

```text
Rubric: 78.5 / 100 (Grade C)
Test: PASS
Weakest dimension: D2
Next step: improve-skill skills/my-skill --record-baseline --benchmark-registry benchmarks/my-skill/registry.yaml
```

## 渐进测试流水线

```bash
skill-pipeline \
  --intent "run gradual pipeline" \
  --skills-dir ./skills \
  --benchmark-registry benchmarks/my-skill/registry.yaml \
  --max-level 2
```
