# LLM Judge（引擎侧参考）

> `evaluate-skill` 默认使用确定性规则评分。对于主观维度（D2 文档、D5 领域准确性），可以启用 LLM judge 作为第二意见。
>
> 本文只描述**引擎侧**的行为与配置。Agent 如何生成 judgments 文件的协议（prompt 模板、决策规则、聚合口径），权威文档是随 skill 复制的 `skills/skill-prism/references/LLM_JUDGE.md`，两侧不复述。

## 设计原则

- **引擎不直接依赖 LLM provider**：LLM judge 通过外部命令（stdin/stdout 契约）或 Agent 预先生成的 judgments 文件接入，引擎本身保持 provider 无关。
- **可选**：不启用时，评分完全确定性。
- **多评委**：默认 2 个独立评委，可按需增减。

## 两种接入方式

| 方式 | 谁来调 LLM | 引擎入口 |
|---|---|---|
| 外部 judge 命令 | 引擎通过子进程调用配置的命令 | `evaluate-skill --llm-judge` |
| 预生成 judgments 文件 | Agent 或外部脚本自行调用 LLM，写 `artifacts/<skill>/llm_judgments.json` | 引擎自动发现该文件，也可显式 `--llm-judgments <file>` |

Agent 侧选择哪条路径、如何构造 judge prompt，见 `skills/skill-prism/references/LLM_JUDGE.md`。

## 外部 judge 命令配置

二选一：

```bash
# 方式一：环境变量
export SKILLPRISM_LLM_JUDGE_COMMAND="python examples/editor_wrappers/openai_compatible_judge.py"
evaluate-skill skills/my-skill --llm-judge --llm-judge-count 3
```

```yaml
# 方式二：skill_rubric_types.yaml
llm_judge:
  enabled: false
  # command: python examples/editor_wrappers/openai_compatible_judge.py
  n_judges: 2
  aggregate: median
  weight: 0.3
  # 可复现性字段
  model: moonshot-v1-8k
  temperature: 0.2
  prompt_version: "1.0"
  system_prompt: "You are an expert reviewer..."
  prompts:
    D2: "Evaluate the following SKILL.md for dimension {dimension} ({focus}). Engine score: {engine_score}/5.\n{content}"
```

示例命令实现见 `examples/editor_wrappers/openai_compatible_judge.py`。

## 命令接口契约

Judge 命令从 stdin 接收 prompt 文本，stdout 返回单个 JSON 对象，退出码 0 表示成功：

```json
{"score": 4, "reason": "Concise explanation."}
```

- `score`：1–5 的整数。
- `reason`：一句话理由。

## judgments 文件格式

`artifacts/<skill>/llm_judgments.json` 的 schema（与 `skills/skill-prism/references/LLM_JUDGE.md` 一致）：

```json
{
  "judges": [
    {
      "dimension": "D2",
      "scores": [4, 5],
      "reasons": ["Clear examples.", "Well structured."],
      "aggregated_score": 4,
      "aggregate": "mean",
      "model": "moonshot-v1-8k",
      "temperature": 0.2,
      "prompt_version": "1.0"
    }
  ]
}
```

- `dimension`：D2 / D5 / D6 / D8。
- `scores` / `reasons`：每个独立 judge 的结果，长度一致。
- `aggregated_score`：1–5 的整数。
- `aggregate`：`median` / `mean` / `min` / `max`。Agent 生成文件时按 `mean` 聚合（与 `skills/skill-prism/SKILL.md` 一致）；引擎外部 judge 路径的默认聚合方式由 `skill_rubric_types.yaml` 的 `llm_judge.aggregate` 决定（默认 `median`）。
- `model` / `temperature` / `prompt_version`：可复现性元数据。

引擎消费：

```bash
evaluate-skill skills/my-skill --llm-judgments artifacts/my-skill/llm_judgments.json
```

**辅助脚本**：仓库提供 `scripts/generate_llm_judgments.py`，把"调 LLM → 聚合 → 写文件"的流程自动化（仅在 skillPrism 仓库内可用）：

```bash
export OPENAI_API_KEY=<your-key>
export OPENAI_BASE_URL=https://api.moonshot.cn/v1
export OPENAI_MODEL=moonshot-v1-8k

python scripts/generate_llm_judgments.py skills/my-skill \
    --dimensions D2 D5 \
    --count 2 \
    --aggregate mean
```

默认输出 `artifacts/my-skill/llm_judgments.json`（`--output` 可覆盖），引擎自动发现该文件。聚合口径以 `skills/skill-prism/references/LLM_JUDGE.md` 为准。

## 实现位置

- `skillprism/llm_judge.py`：`LLMJudge` 类、结果解析、多评委聚合、分数混合。
- `skillprism/evaluate_skill_rubric.py`：读取 `--llm-judgments` 并应用到 D2/D5/D6/D8。
- `scripts/generate_llm_judgments.py`：生成 judgments 文件的参考实现（仅仓库内可用）。
- `examples/editor_wrappers/openai_compatible_judge.py`：单条 judge 命令的参考实现。
