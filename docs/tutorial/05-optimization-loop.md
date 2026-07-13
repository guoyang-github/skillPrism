> 学习目标：掌握 baseline → 编辑 → judge → keep/revert 的完整优化流程，并理解哪些环节需要 LLM。

# 第 5 章：优化循环实战

## 5.1 优化循环概览

skillPrism 的优化循环只有四步：

```text
记录 baseline → 识别短板 → 编辑 + judge → 应用或回滚
```

| 步骤 | 命令 | 是否需要 LLM |
|---|---|---|
| 记录 baseline | `improve-skill --record-baseline` | 否 |
| 识别短板 | `improve-skill --suggest` | 否 |
| 编辑 SKILL.md | 手动 或 `--auto-edit` | **手动不需要；`--auto-edit 需要`** |
| Judge | `improve-skill --judge` | 否 |
| 应用/回滚 | `improve-skill --apply` | 否 |

!!! tip "核心原则"
    **skillPrism 引擎不调用 LLM。** 所有需要 LLM 的环节（如自动生成编辑、主观维度复核、prompts 验证）都由 Agent 或外部 editor 完成，引擎只负责测量和决策。

## 5.2 自然语言交互方式（Agent 场景）

如果你已经加载了 `skills/skill-prism/SKILL.md`，可以直接对 Agent 说：

- "帮我优化一下这个 skill"
- "这个 skill 哪里最弱？"
- "这个 skill 还能怎么改进？"
- "按建议改一下，然后 judge"
- "如果改得不好就回滚"
- "看看这个 skill 之前的优化记录"

Agent 会翻译成引擎命令：

```text
用户：帮我优化一下这个 skill
Agent：
  1. improve-skill skills/my-first-analysis --record-baseline
  2. improve-skill skills/my-first-analysis --suggest
  3. （Agent 自己编辑 SKILL.md，或调用外部 editor）
  4. improve-skill skills/my-first-analysis --judge
  5. improve-skill skills/my-first-analysis --apply
```

## 5.3 哪些环节需要 LLM？

| 环节 | 是否需要 LLM | 说明 |
|---|---|---|
| 评估（`evaluate-skill`） | 可选 | 默认是确定性规则评分；主观维度可附加 `--llm-judge` |
| 识别短板（`--suggest`） | 否 | 纯规则分析 |
| 编辑 SKILL.md（手动） | 否 | 人自己改 |
| 编辑 SKILL.md（`--auto-edit`） | **是** | 调用外部 editor 命令，通常是 LLM |
| Judge（`--judge`） | 否 | 纯规则对比 baseline |
| Benchmark 代码生成 | **是** | 由 Agent/LLM 生成 `--code` 代码 |
| Prompts 验证 | 可选 | 由 Agent/LLM 生成并验证 test-prompts |

!!! note "用户不需要说 LLM 术语"
    你只要说"帮我优化"，Agent 会自己判断是否需要调用 LLM。你不需要说"用 LLM judge"或"auto-edit"。

## 5.4 记录 Baseline

```bash
improve-skill skills/my-first-analysis --record-baseline
```

这会保存当前 `SKILL.md` 的 Rubric 分数、benchmark 结果到 `artifacts/<skill>/baseline/`，并写入 `artifacts/<skill>/history.jsonl`。

## 5.5 识别短板

```bash
improve-skill skills/my-first-analysis --suggest
```

输出示例：

```text
Current score: 39.4 / 100 (Grade D)
Weakest dimension: D4 环境/依赖可复现性 = 1/5

### Optimization Strategy (P0-P3)
P1 · structure: Structural dimensions (D1-D4) are the weakest
- Action: Reorganize workflow into linear steps; add frontmatter trigger words; add checkpoints

### Dimension Cluster Analysis
Weakest dimension: D4
Cluster: Structure cluster
Related dimensions in the same cluster:
- D2: 2/5
- D3: 2/5
```

## 5.6 手动编辑并 Judge

编辑 `skills/my-first-analysis/SKILL.md`，例如添加 `requirements.txt` 和版本说明。

然后 dry-run：

```bash
improve-skill skills/my-first-analysis --judge
```

你会看到：

```text
SKILL.md diff (baseline → current):
--- SKILL.md (baseline)
+++ SKILL.md (current)
@@ -25,6 +25,10 @@

 ## Outputs

+## Version Compatibility
+
+Compatible with Python 3.9+ and pandas>=2.0.
+
 The output is a summary DataFrame.

 Current: 45.8 / 100 (Grade D)
 Baseline: 39.4 / 100
 Delta: +6.4
 Decision: KEEP (Rubric score improved)
```

确认后 apply：

```bash
improve-skill skills/my-first-analysis --apply
```

!!! warning "先 judge 再 apply"
    `--judge` 默认是 dry-run，不会修改文件。只有 `--apply` 才会真正 keep/revert。

## 5.7 自动优化

配置 editor 命令后，Agent 或外部 LLM 可以自动编辑：

```bash
export SKILLPRISM_EDITOR_COMMAND="python examples/editor_wrappers/openai_editor.py"

improve-skill skills/my-first-analysis \
    --auto-edit --apply --max-rounds 3
```

如果想在遇到回滚时立即停止：

```bash
improve-skill skills/my-first-analysis \
    --auto-edit --apply --max-rounds 5 --stop-on-regression
```

!!! tip "自动优化时引擎在做什么？"
    引擎不编辑。它只是：
    1. 调用你配置的 `SKILLPRISM_EDITOR_COMMAND` 生成新 SKILL.md
    2. 重新评估
    3. 对比 baseline，决定 keep 还是 revert
    4. 只有 `--apply` 时才真正写回文件

## 5.8 编辑代码资产

默认 `--auto-edit` 只改 `SKILL.md`。如果需要同时修改 `scripts/`、`examples/`、`requirements.txt`：

```bash
improve-skill skills/my-first-analysis \
    --auto-edit --apply --edit-code --max-rounds 3
```

开启 `--edit-code` 后，优化器会在编辑前记录代码资产快照，回滚时自动恢复。

## 5.9 探索性重写

当普通优化连续触顶时，可以尝试从头重写 SKILL.md：

```bash
improve-skill skills/my-first-analysis --explore-rewrite --apply
```

这会：
1. 备份当前最优版本到 `artifacts/<skill>/baseline/SKILL.md.stash`
2. 调用 editor 从头重写
3. judge 重写版
4. 如果更好则保留，否则恢复 stash

## 5.10 查看优化历史

```bash
improve-skill skills/my-first-analysis --history
```

输出：

```text
| Timestamp           | Status | Dim | Old | New | Δ   | Note                          | Mode   |
|---------------------|--------|-----|-----|-----|-----|-------------------------------|--------|
| 2026-06-22 12:00:00 | baseline | all | 39.4 | 39.4 | +0.0 | baseline evaluation           | static |
| 2026-06-22 12:05:00 | keep   | D4  | 39.4 | 45.8 | +6.4 | Added version compatibility   | static |
```

## 5.11 参数速查表

| 参数 | 作用 |
|---|---|
| `--record-baseline` | 保存当前状态作为 baseline |
| `--suggest` | 输出最弱维度、相关簇、P0-P3 优化策略 |
| `--judge` | dry-run 评估当前改动 |
| `--apply` | 应用 judge 决策（keep/revert） |
| `--auto-edit` | 调用外部 editor 自动编辑 SKILL.md |
| `--edit-code` | 允许同时编辑代码资产（scripts/、examples/ 等） |
| `--max-rounds N` | 自动优化最大轮数 |
| `--stop-on-regression` | 遇到回滚立即停止 |
| `--explore-rewrite` | 探索性重写，跳出局部最优 |
| `--history` | 查看优化历史 |
| `--min-gain X` | 最小可接受分数提升 |
| `--allow-regression X` | 允许最大分数下降 |
| `--benchmark-registry PATH` | 指定 benchmark registry |
| `--ratchet` | 启用 ratchet 模式，只接受严格提升 |

## 5.12 本章小结

- `--record-baseline` 保存当前状态。
- `--suggest` 指出最弱维度、相关簇和 P0-P3 策略。
- `--judge` 评估编辑，dry-run 默认不修改文件。
- `--apply` 真正执行 keep/revert。
- `--auto-edit` 让 editor（通常是 LLM）自动改写。
- `--explore-rewrite` 用于 hill-climbing 触顶时跳出局部最优。
- `--history` 查看 `artifacts/<skill>/history.jsonl`。
- **引擎不调用 LLM；LLM 只出现在 `--auto-edit` 和 Agent 生成的环节中。**

## 5.13 练习

1. 手动改进 `my-first-analysis` 的 D4，使其分数提升。
2. 用 `--auto-edit` 跑一轮优化，观察 judge 输出。
3. 用 `--output-json` 导出 judge 结果，查看 `diff` 字段。
4. 故意改差 SKILL.md，观察 `--judge` 如何建议 revert。
