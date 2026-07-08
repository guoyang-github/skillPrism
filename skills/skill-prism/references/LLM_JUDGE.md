# skill-prism LLM Judge 参考

> 本文件是 `skills/skill-prism/SKILL.md` 的附属参考。复制 `skill-prism` Skill 时，应同时复制本文件。

## Agent 决策规则

1. 若配置了 `SKILLPRISM_LLM_JUDGE_COMMAND` 或 `skill_rubric_types.yaml` 中 `llm_judge.command`，使用 `evaluate-skill --llm-judge`。
2. 否则 Agent 自己生成 `.skillprism_llm_judgments.json`，再使用 `evaluate-skill --llm-judgments .skillprism_llm_judgments.json`。

## Judgments 文件格式

```json
{
  "judges": [
    {
      "dimension": "D2",
      "scores": [4, 5],
      "reasons": ["Clear examples.", "Well structured."],
      "aggregated_score": 4,
      "aggregate": "median",
      "model": "moonshot-v1-8k",
      "temperature": 0.2,
      "prompt_version": "1.0"
    }
  ]
}
```

- `dimension`: D2 / D5 / D6 / D8
- `scores` / `reasons`: 每个独立 judge 的结果，长度一致
- `aggregated_score`: 1–5 的整数
- `aggregate`: `median` / `mean` / `min` / `max`
- `model` / `temperature` / `prompt_version`: 可复现性元数据（Agent 生成文件时必须带上）

## 辅助脚本

不想手写上述流程时，可直接运行仓库中的辅助脚本：

```bash
export OPENAI_API_KEY=<your-key>
export OPENAI_BASE_URL=https://api.moonshot.cn/v1
export OPENAI_MODEL=moonshot-v1-8k

python scripts/generate_llm_judgments.py skills/my-skill \
    --dimensions D2 D5 \
    --count 2 \
    --aggregate median \
    --output .skillprism_llm_judgments.json
```

脚本位置：`scripts/generate_llm_judgments.py`。

## Prompt 模板

### System prompt

```text
You are an expert reviewer evaluating an AI agent SKILL.md file.
Respond with ONLY a JSON object containing exactly two keys:
"score" (integer 1-5) and "reason" (concise explanation).
Do not add markdown fences or explanations outside the JSON.
```

### User prompt

```text
You are an expert reviewer evaluating a SKILL.md file for an AI agent skill.

Evaluate the following SKILL.md for dimension {dimension} ({focus}).
The rule-based engine gave it a score of {engine_score}/5.

Return a JSON object with exactly two keys:
  "score": an integer from 1 to 5,
  "reason": a concise explanation (one sentence).

SKILL.md content:
---
{content[:8000]}
---
```

各维度 `focus`：

- **D2**: `documentation clarity and completeness: structure, examples, input/output descriptions, tables, version notes, and pitfalls/troubleshooting`
- **D5**: `domain accuracy: whether references/citations, parameters, recommended practices, and caution notes are present and plausible for the skill's domain`
- **D6**: `LLM callability: description quality, keywords, when-to-use guidance, and tool selection clarity`
- **D8**: `maintainability: versioning, organization, and update practices`

## 外部 judge 命令接口

外部命令从 stdin 接收上述 user prompt，stdout 返回：

```json
{"score": 4, "reason": "Concise explanation."}
```

退出码 0 表示成功。

## 配置项

`skill_rubric_types.yaml`：

```yaml
llm_judge:
  enabled: false
  # command: python examples/editor_wrappers/openai_compatible_judge.py
  n_judges: 2
  aggregate: median
  weight: 0.3
  # Reproducibility fields
  model: moonshot-v1-8k
  temperature: 0.2
  prompt_version: "1.0"
  system_prompt: "You are an expert reviewer..."
  prompts:
    D2: "Evaluate the following SKILL.md for dimension {dimension} ({focus}). Engine score: {engine_score}/5.\n{content}"
```
