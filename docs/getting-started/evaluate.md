# 评估一个 Skill

> `evaluate-skill` 回答：SKILL.md 作为文档/教练质量如何？

## 自然语言交互方式（Agent 场景）

`evaluate-skill` 回答的是：**SKILL.md 作为一份"教练文档"够不够好？**

你可以直接问：

- "这个 skill 的 SKILL.md 写得怎么样？" → 完整 9 维度评分
- "给这个 skill 打个分，告诉我哪里扣分最多" → 快速定位短板
- "检查一下这份文档有没有模糊 wording 或安全隐患" → 规则增强 + 安全扫描
- "这个 skill 的说明清楚吗？示例够不够用？" → D2 可读性重点
- "再深入看看可读性和领域准确性" → 主观维度第二意见

Agent 会翻译成：

```bash
evaluate-skill skills/my-skill
# 或
evaluate-skill skills/my-skill --detailed
# 主观维度需要第二意见时
evaluate-skill skills/my-skill --llm-judge
```

如果 Agent 觉得可读性、结构、领域准确性这类主观维度需要再深入判断，它会自己调用外部 LLM 做第二意见。你只要像对同事说话一样提需求，不用说什么"LLM judge"。

## 默认评估（确定性）

```bash
evaluate-skill skills/my-skill
```

默认包含：

- 9 维度规则评分
- **规则增强检查**：模糊词、AI 腔废话、失败模式编码、检查点标记、体积膨胀
- SkillLens 检查
- test-prompts.json 存在性检查；缺失时自动生成 3 个 prompts
- **runtime neutrality 红灯扫描**
- 安全扫描
- 将基线写入 `.skillprism_history.jsonl`

## 完整评估（可选增强）

默认评估对客观维度已经足够。如果你或 Agent 希望主观维度（D2 可读性、D5 领域准确性）有第二意见，可以启用多评委打分：

```bash
# 主观维度第二意见（默认 2 个独立评委）
evaluate-skill skills/my-skill --llm-judge

# 更多评委
evaluate-skill skills/my-skill \
  --llm-judge \
  --llm-judge-count 3 \
  --llm-judge-aggregate median

# 验证 test-prompts
evaluate-skill skills/my-skill --prompts-verification .skillprism_prompts_verification.json

# 同时启用 smoke 和依赖检查
evaluate-skill skills/my-skill --run-smoke --run-deps

# 不自动生成 prompts
evaluate-skill skills/my-skill --no-generate-prompts
```

## 输出报告

```bash
evaluate-skill skills/my-skill --output docs/scorecard.md --detailed
```

## 评估消费的结构化文件

当 Agent 完成主观维度复核或 prompts 验证后，会生成以下文件：

- `.skillprism_llm_judgments.json`：多评委评分结果
- `.skillprism_prompts_verification.json`：prompts 验证结果
- `.skillprism_history.jsonl`：优化历史

引擎通过 `--llm-judgments` 和 `--prompts-verification` 参数消费它们。
