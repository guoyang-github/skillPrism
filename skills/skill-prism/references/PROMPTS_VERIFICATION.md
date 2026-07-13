# Test-Prompts Verification Protocol

引擎**不执行** prompt，只消费结果。本协议规定 Agent 如何通过「带 skill / 不带 skill」对比，产出引擎可消费的验证文件，用于 D8（measured performance）评分。

**职责边界**：本机制只验证**行为质量**——真实用户语言下，带 skill 的 Agent 是否更会澄清、更遵循 SKILL.md 工作流、更能防护边界。产出物的**结果正确性**（数值、结构、文件内容 vs 金标准）由 benchmark（`test-skill`）负责，**不在此校验**。

涉及两个文件，默认都放在 `artifacts/<skill>/`（项目根目录下，skill 树保持只读）：

| 文件 | 作用 | 谁写 |
|---|---|---|
| `test-prompts.json` | 2–3 条代表性 prompt | Agent 撰写（引擎模板仅为兜底占位） |
| `prompts_verification.json` | with/without 执行与评判结果 | Agent 按本协议生成 |

## Step 1：撰写 test-prompts.json

要求：**具体场景 + 行为可核对的期望**。expected 是 judge 能从执行过程记录直接核对的行为清单（是否澄清、是否按 SKILL.md 工作流、是否防护边界），**禁止结果数值校验**（"文件存在""数值在某区间""结构比对"——那是 benchmark 的职责）；禁止 "Use the X skill to ..." 这类元指令。覆盖三种场景：

```json
[
  {
    "id": 1,
    "scenario": "trigger",
    "prompt": "我有一管 PBMC 的单细胞数据，想看看里面有哪些细胞群。",
    "expected": "按 SKILL.md 工作流组织分析（QC→归一化→聚类）；主动询问数据位置和格式；可用小样演示关键步骤；不编造聚类结果。"
  },
  {
    "id": 2,
    "scenario": "ambiguous",
    "prompt": "帮我分析一下这个单细胞数据。",
    "expected": "主动澄清分析目标（聚类/注释/差异表达），不擅自假设。"
  },
  {
    "id": 3,
    "scenario": "boundary",
    "prompt": "对空矩阵文件跑聚类。",
    "expected": "不崩溃；按 SKILL.md 的 failure-mode 给出明确报错或回退。"
  }
]
```

三种场景的分工：`trigger` 验触发与工作流遵循（真实需求语言，不带 skill 名）；`ambiguous` 验澄清行为；`boundary` 验风险识别与优雅处理。

## Step 2：执行 with / without

对每条 prompt 各起**两个独立子 agent**（不得共享上下文）：

- **with-skill 子 agent**：被测 skill 在可发现路径（如 `.claude/skills/<skill>`）下，执行 prompt，记录执行过程和输出。
- **without-skill 子 agent**：相同环境但**不含**被测 skill（临时移出或换干净目录），执行同一 prompt，记录执行过程和输出。

**轻量执行**：trigger 类 prompt 允许用小样数据、或「方案 + 关键步骤演示」后终止——验证的是做事方式是否符合 skill 指引，**不要求跑完整重计算、不要求产出最终结果文件**。真实启动并执行了关键步骤即记 `full_test`。

## Step 3：评判

起**第三个独立子 agent** 做 judge，对比两份输出与 expected：

```text
You are judging whether a skill improves task outcomes.
Prompt: {prompt}
Expected: {expected}
Output WITHOUT skill: {without_skill_output}
Output WITH skill: {with_skill_output}

Judge ONLY process behavior: whether the with-skill agent followed the skill's
guidance (workflow, tool choice, clarification, risk handling). Do NOT judge
numeric correctness of outputs — result correctness belongs to benchmarks.

Score improvement_score from 0.0 to 1.0:
- 1.0: with-skill behavior fully meets expected; without-skill does not
- 0.5: with-skill partially better
- 0.0: no improvement or with-skill is worse
Set passed=true iff the with-skill behavior meets the expected criteria.
Return only JSON: {"improvement_score": 0.0, "passed": false, "reason": "..."}
```

## Step 4：写 prompts_verification.json

写到 `artifacts/<skill>/prompts_verification.json`，schema：

| 字段 | 说明 |
|---|---|
| `prompt_id` / `prompt` / `expected` | 来自 test-prompts.json |
| `without_skill_output` / `with_skill_output` | Step 2 记录（可截断） |
| `improvement_score` | 0.0–1.0，judge 给出 |
| `passed` | bool，with-skill 输出是否满足 expected |
| `eval_mode` | `full_test`（真实执行）/ `dry_run`（未执行、凭推测填写） |

```json
{
  "skill": "<skill-name>",
  "results": [
    {
      "prompt_id": 1,
      "prompt": "...",
      "without_skill_output": "...",
      "with_skill_output": "...",
      "expected": "...",
      "improvement_score": 1.0,
      "passed": true,
      "eval_mode": "full_test"
    }
  ]
}
```

`dry_run` 是降级模式：无法真实执行时允许填写，但 **dry_run 占比 > 30% 时引擎报警**，D8 分数不可信。能跑就必须 `full_test`。

## Step 5：引擎消费

```bash
# 自动发现 artifacts/<skill>/prompts_verification.json（无需参数）
evaluate-skill skills/<skill>

# 或显式指定
evaluate-skill skills/<skill> --prompts-verification artifacts/<skill>/prompts_verification.json
```

引擎行为：pass_rate < 50% → D6/D8 减 1 分；≥ 90% → 加 1 分；报告附验证摘要表。

## 规则

- expected 只写**行为可核对项**；结果正确性（数值、文件内容、结构 vs 金标准）由 benchmark 负责，写进 test-prompts 属于越权。
- trigger 类允许**轻量执行**（小样数据 / 方案 + 关键步骤演示）；真实启动并执行了关键步骤即记 `full_test`，不要求产出最终结果文件。
- 三个子 agent（with / without / judge）必须相互独立，不得共享推理上下文。
- 执行与评判全程**不得修改被测 skill**。
- 中间文件只写 `artifacts/<skill>/`，不写 skill 树。
