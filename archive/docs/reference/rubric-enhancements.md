> Rubric 规则增强把 SkillLens 等研究中验证过的质量信号（模糊词、失败模式编码、检查点标记等）变成可执行的默认检查。

# Rubric 规则增强

skillPrism 在 9 维 rubric 基础上，增加了一组规则增强检查。这些检查默认启用，不需要额外参数。

## 检查项

| 检查项 | 触发条件 | 影响维度 | 严重程度 |
|---|---|---|---|
| 模糊词黑名单 | 出现"建议"、"可以考虑"、"根据情况"、"灵活把握"、"视情况而定"等 | D2、D5 | warning / error |
| AI 腔废话 | 出现"说白了"、"换句话说"、"首先/其次/综上"等 | D2、D7 | warning |
| 失败模式编码 | 没有显式 "如果 X 失败 → Y"、fallback、else 等 | D3 | error |
| 检查点显性标记 | 没有 🔴/🛑/CHECKPOINT/STOP 等标记 | D4 | error |
| 体积控制 | SKILL.md 大小超过 baseline 的 150% | D8 | error |
| 结尾空话尾巴 | description 以"灵活应用"、"根据情况判断"等结尾 | D1 | error |

## 输出示例

在 scorecard 中会显示：

```markdown
### Quality Issues

⚠️ **D2**: found 3 vague wording occurrence(s)
🔴 **D3**: no explicit failure-mode encoding found
🔴 **D4**: no explicit checkpoint markers found

**Suggested penalty**: -5 points
```

## 与 Rubric 评分的关系

规则增强检查不会直接覆盖 LLM judge 或人工评分，而是：

1. 作为具体扣分证据追加到对应维度。
2. 在 `--suggest` 中影响 P0-P3 策略排序。
3. 在 `--judge` 时作为 guard 触发 revert（如体积膨胀）。

## 如何临时禁用

目前规则增强是默认行为，无法通过 CLI 单独禁用。如果你认为某项检查过于严格，
只能在 `SKILL.md` 中避免触发该检查的措辞。

> 注意：`--no-generate-prompts` 只控制 test-prompts 的自动生成，与规则增强检查无关。
