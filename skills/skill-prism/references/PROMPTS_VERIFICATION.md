# Test-Prompts Verification Protocol

引擎**不执行** prompt，只消费结果。本协议规定 Agent 如何通过「带 skill / 不带 skill」对比，产出引擎可消费的验证文件，用于 D8（measured performance）评分。

涉及两个文件，默认都放在 `artifacts/<skill>/`（项目根目录下，skill 树保持只读）：

| 文件 | 作用 | 谁写 |
|---|---|---|
| `test-prompts.json` | 2–3 条代表性 prompt | Agent 撰写（引擎模板仅为兜底占位） |
| `prompts_verification.json` | with/without 执行与评判结果 | Agent 按本协议生成 |

## Step 1：撰写 test-prompts.json

要求：**具体输入 + 具体可验证的期望**，禁止 "Use the X skill to ..." 这类元指令。覆盖三种场景：

```json
[
  {
    "id": 1,
    "scenario": "happy path",
    "prompt": "用 pbmc3k 数据做单细胞聚类，输出 h5ad。",
    "expected": "输出文件存在，obs 中含 leiden 列，cluster 数在 5–15 之间。"
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

## Step 2：执行 with / without

对每条 prompt 各起**两个独立子 agent**（不得共享上下文）：

- **with-skill 子 agent**：被测 skill 在可发现路径（如 `.claude/skills/<skill>`）下，执行 prompt，记录完整输出。
- **without-skill 子 agent**：相同环境但**不含**被测 skill（临时移出或换干净目录），执行同一 prompt，记录输出。

两次执行均真实跑完后，`eval_mode` 记 `full_test`。

## Step 3：评判

起**第三个独立子 agent** 做 judge，对比两份输出与 expected：

```text
You are judging whether a skill improves task outcomes.
Prompt: {prompt}
Expected: {expected}
Output WITHOUT skill: {without_skill_output}
Output WITH skill: {with_skill_output}

Score improvement_score from 0.0 to 1.0:
- 1.0: with-skill output fully meets expected; without-skill does not
- 0.5: with-skill partially better
- 0.0: no improvement or with-skill is worse
Set passed=true iff the with-skill output meets the expected criteria.
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

- 三个子 agent（with / without / judge）必须相互独立，不得共享推理上下文。
- 执行与评判全程**不得修改被测 skill**。
- 中间文件只写 `artifacts/<skill>/`，不写 skill 树。
