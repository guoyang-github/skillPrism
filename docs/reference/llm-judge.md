# LLM Judge

> `evaluate-skill` 默认使用确定性规则评分。对于主观维度（D2 文档、D5 领域准确性），可以启用 LLM judge 作为第二意见。
>
> 对 Agent 用户来说，直接说"再帮我看看可读性和领域准确性"即可，Agent 会自己决定是否启用；本页面向需要手动配置或自定义 judge 命令的用户。

## 设计原则

- **引擎不调用 LLM**：LLM judge 由 Agent 或外部脚本调用，结果以结构化文件写回。
- **可选**：不启用时，评分完全确定性。
- **多评委**：默认 2 个独立评委，可按需增减。

## 谁来控制生成 judgments？

**Agent 自己决定。**

当用户表达"再用 LLM 看看可读性/领域准确性"等主观维度评估意图时，Agent 按以下逻辑选择路径：

1. 检查环境是否配置了 `SKILLPRISM_LLM_JUDGE_COMMAND` 或 `skill_rubric_types.yaml` 中 `llm_judge.command`。
2. **如果已配置**：直接调用 `evaluate-skill --llm-judge`。
3. **如果未配置**：Agent 自己调用 LLM 生成 `artifacts/<skill>/llm_judgments.json`（引擎自动发现，也可显式 `--llm-judgments <file>`）。

第二种方式不需要用户配置任何外部命令，是 Agent 自包含的 fallback。

## 使用方式

### 方式一：Agent 生成 judgments 文件（推荐）

Agent 直接调用 LLM，生成 `artifacts/<skill>/llm_judgments.json`，然后让引擎消费。此方式不需要配置 `SKILLPRISM_LLM_JUDGE_COMMAND`。

**Agent 工作流**：

```text
1. 读取 skills/my-skill/SKILL.md
2. 为 D2 / D5 构造 judge prompt
3. 对每个维度独立调用 2 次 LLM（不通过引擎）
4. 解析每个返回的 {"score": int, "reason": str}
5. 按 median/mean/min/max 聚合
6. 写入 artifacts/<skill>/llm_judgments.json
7. 调用 evaluate-skill（引擎自动发现该文件）
```

**文件格式**：

```json
{
  "judges": [
    {
      "dimension": "D2",
      "scores": [4, 5],
      "reasons": ["Clear examples.", "Well structured."],
      "aggregated_score": 4,
      "aggregate": "median"
    }
  ]
}
```

**引擎消费**：

```bash
evaluate-skill skills/my-skill --llm-judgments artifacts/my-skill/llm_judgments.json
```

**辅助脚本**：

仓库提供了 `scripts/generate_llm_judgments.py`，把上述流程自动化：

```bash
export OPENAI_API_KEY=<your-key>
export OPENAI_BASE_URL=https://api.moonshot.cn/v1
export OPENAI_MODEL=moonshot-v1-8k

python scripts/generate_llm_judgments.py skills/my-skill \
    --dimensions D2 D5 \
    --count 2 \
    --aggregate median
```

默认输出 `artifacts/my-skill/llm_judgments.json`（`--output` 可覆盖），引擎自动发现该文件。

### 方式二：引擎直接调用外部 judge

```bash
export SKILLPRISM_LLM_JUDGE_COMMAND="python examples/editor_wrappers/openai_compatible_judge.py"
evaluate-skill skills/my-skill --llm-judge --llm-judge-count 3
```

此方式需要配置外部命令。示例命令见 `examples/editor_wrappers/openai_compatible_judge.py`。

## 配置

在 `skill_rubric_types.yaml` 中：

```yaml
llm_judge:
  enabled: false
  # command: python examples/editor_wrappers/openai_compatible_judge.py
  n_judges: 2
  aggregate: median
  weight: 0.3
```

## Judge 命令接口

Judge 命令从 stdin 接收 prompt，stdout 返回 JSON：

```json
{"score": 4, "reason": "Concise explanation."}
```

## 实现位置

- `skillprism/llm_judge.py`：`LLMJudge` 类、结果解析、多评委聚合、分数混合。
- `skillprism/evaluate_skill_rubric.py`：读取 `--llm-judgments` 并应用到 D2/D5/D6/D8。
- `scripts/generate_llm_judgments.py`：Agent 直接生成 judgments 文件的参考实现。
- `examples/editor_wrappers/openai_compatible_judge.py`：单条 judge 调用的参考实现。
