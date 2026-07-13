# Test-Prompts 验证（功能概述）

> `test-prompts.json` 列出 2-3 个能代表 skill 能力的 prompts。验证这些 prompts 可以衡量 SKILL.md 作为"教练"的有效性。
>
> 本文只描述**引擎侧**的功能与消费方式。Agent 如何执行 with/without 对比并生成验证文件的协议，权威文档是随 skill 复制的 `skills/skill-prism/references/PROMPTS_VERIFICATION.md`，两侧不复述。

## test-prompts.json 格式

每条 prompt 必须是**具体场景 + 行为可核对的期望**——expected 写的是 judge 能从执行过程记录直接核对的行为清单（是否澄清、是否按 SKILL.md 工作流、是否防护边界），**不校验数值结果**（结果正确性归 benchmark）；禁止 "Use this skill to ..." 这类元指令写法（规范见 `skills/skill-prism/references/PROMPTS_VERIFICATION.md` Step 1）：

```json
[
  {
    "id": 1,
    "scenario": "trigger",
    "prompt": "我有一管 PBMC 的单细胞数据，想看看里面有哪些细胞群。",
    "expected": "按 SKILL.md 工作流组织分析（QC→归一化→聚类）；主动询问数据位置和格式；可用小样演示关键步骤；不编造聚类结果。"
  }
]
```

`evaluate-skill` 默认会在 `test-prompts.json` 缺失时自动生成 3 个 prompts（trigger、ambiguous、boundary），写入 `artifacts/<skill>/test-prompts.json`（可用 `--prompts-dir` 覆盖）。**自动生成的是通用占位模板**，引擎会给出 ⚠️ 占位符警告；正式版应由 Agent 按协议撰写（规范见 `skills/skill-prism/references/PROMPTS_VERIFICATION.md`）。

## 验证方式

### 默认：存在性检查

`evaluate-skill` 默认检查 `test-prompts.json` 是否存在、数量是否足够。

### 完整验证：消费 prompts_verification.json

Agent 按协议执行 with/without 对比后，把结果写入 `artifacts/<skill>/prompts_verification.json`。引擎**不执行** prompt，只消费该文件：未传参数时自动发现默认路径，也可显式指定：

```bash
evaluate-skill skills/my-skill --prompts-verification artifacts/my-skill/prompts_verification.json
```

每条结果的 `eval_mode` 标记执行方式：

- `full_test`：真实执行了代码或 LLM 调用
- `dry_run`：只检查了输出结构或 prompt 本身，没有真实执行

### summary schema

```json
// artifacts/<skill>/prompts_verification.json（摘要部分）
{
  "skill": "skills/my-skill",
  "results": [ ... ],
  "summary": {
    "total": 3,
    "passed": 3,
    "pass_rate": 1.0,
    "dry_run_ratio": 0.0,
    "dry_run_warning": false
  }
}
```

- `pass_rate`：通过比例（`passed / total`）。
- `dry_run_ratio`：`dry_run` 结果占比。
- `dry_run_warning`：`dry_run_ratio > 30%` 时为 `true`，评估报告发出警告：

```text
⚠️ Warning: dry-run ratio > 30%; measured performance score may be unreliable.
```

这意味着大部分 prompts 只是"纸上谈兵"，没有真实验证 skill 的执行效果，此时应增加 `full_test` 比例。

## 与 D6/D8 评分的关系

Test-prompts 验证属于 `evaluate-skill` 的可选能力，影响 D6 "LLM callability" 和 D8 "measured performance" 的评分证据：`pass_rate < 50%` 时 D6/D8 减 1 分，`pass_rate ≥ 90%` 时加 1 分，报告中附验证摘要。
