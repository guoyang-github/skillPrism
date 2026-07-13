# 改进一个 Skill

> `improve-skill` 回答：怎么改才能让评估更高、测试通过？

## 自然语言交互方式（Agent 场景）

`improve-skill` 回答的是：**怎么改才能让 SKILL.md 评分更高、生成的代码更稳？**

优化是一个"测量 → 编辑 → 再测量 → 决定保留/回滚"的循环。不同步骤，你问 Agent 的问题也不同：

| 步骤 | 你想做什么 | 对 Agent 说 |
|---|---|---|
| 开始 | 记录当前状态作为 baseline | "先记录这个 skill 的 baseline" |
| 诊断 | 找出最弱维度和策略 | "这个 skill 哪里最弱？给我优化建议" |
| 编辑 | 按建议改 SKILL.md | "按 P1 结构策略先改 D1，其他别动" |
| 评估 | 判断改动是否保留 | "改完 judge 一下，看看要不要保留" |
| 应用 | 真正执行 keep/revert | "确认保留这次改动" |
| 复盘 | 查看历史 | "看看这个 skill 之前的优化记录" |
| 突围 | 局部最优时重写 | "这个 skill 好像到瓶颈了，换个思路重写试试" |

Agent 会按以下流程执行：

```bash
improve-skill skills/my-skill --record-baseline
improve-skill skills/my-skill --suggest
# 编辑 SKILL.md（每轮只改一个维度）
improve-skill skills/my-skill --judge
improve-skill skills/my-skill --apply
```

## Judge 逻辑

`improve-skill --judge` 会对比 baseline 和 current：

| 情况 | 决策 |
|---|---|
| 总分提高 + benchmark 通过 + 无 guard 触发 | keep |
| 总分下降 或 benchmark 失败 或 guard 触发 | revert |
| D9 安全维度下降 | revert（一票否决） |
| SKILL.md 体积 > 150% baseline | revert |
| 其他 | human-decide |

## 非 Agent 场景：自动编辑

```bash
export SKILLPRISM_EDITOR_COMMAND="python scripts/my_llm_editor.py"
improve-skill skills/my-skill --auto-edit --apply --max-rounds 3
```

## 探索性重写

当 hill-climbing 连续触顶时，可以尝试从头重写：

```bash
improve-skill skills/my-skill --explore-rewrite --apply
```

这会备份当前最优版本、调用 editor 从头重写并 judge；更好则保留，否则恢复备份。

## 优化历史

```bash
improve-skill skills/my-skill --history
```

输出 `artifacts/<skill>/history.jsonl` 中的尝试记录：

```text
| Timestamp           | Status   | Dim | Old  | New  | Δ    | Note                        | Mode   |
|---------------------|----------|-----|------|------|------|-----------------------------|--------|
| 2026-06-22 12:00:00 | baseline | all | 39.4 | 39.4 | +0.0 | baseline evaluation         | static |
| 2026-06-22 12:05:00 | keep     | D4  | 39.4 | 45.8 | +6.4 | Added version compatibility | static |
```

## 参数说明

| 参数 | 说明 |
|---|---|
| `--record-baseline` | 记录当前状态作为 baseline |
| `--suggest` | 打印最弱维度、相关簇和 P0-P3 优化策略 |
| `--judge` | 评估当前改动 |
| `--apply` | 应用 judge 决策 |
| `--auto-edit` | 调用外部 editor 自动编辑 |
| `--explore-rewrite` | 探索性重写，跳出局部最优 |
| `--history` | 查看优化历史 |
| `--benchmark-registry` | 指定 benchmark registry |
| `--max-rounds` | 自动编辑最大轮数 |
| `--min-gain` | 最小可接受分数提升（默认 1.0） |
| `--edit-code` | 允许 `--auto-edit` 同时修改代码资产（scripts/、examples/ 等），回滚时自动恢复 |
| `--ratchet` | 只接受不低于历史最优的分数 |
| `--no-stop-on-regression` | 回滚后继续自动编辑（默认：遇到回滚即停止） |
