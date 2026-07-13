> `test-prompts.json` 列出 2-3 个能代表 skill 能力的 prompts。验证这些 prompts 可以衡量 SKILL.md 作为"教练"的有效性。

# Test-Prompts 验证

## 文件格式

```json
[
  {
    "id": 1,
    "scenario": "happy path",
    "prompt": "Use this skill to summarize sales.csv and return total revenue.",
    "expected": "The skill should compute the sum of the revenue column."
  }
]
```

`evaluate-skill` 默认会在 `test-prompts.json` 缺失时自动生成 3 个 prompts（happy path、ambiguous、boundary）。

## 验证方式

### 默认：存在性检查

`evaluate-skill` 默认检查 `test-prompts.json` 是否存在、数量是否足够。

### 完整验证：Agent 执行 prompts

Agent 对每个 prompt：

1. 不带 skill 执行一次（baseline）
2. 带 skill 执行一次
3. 判断 with skill 是否更好

每个结果都会标记 `eval_mode`：

- `full_test`：真实执行了代码或 LLM 调用
- `dry_run`：只检查了输出结构或 prompt 本身，没有真实执行

结果写入：

```json
// artifacts/<skill>/prompts_verification.json
{
  "skill": "skills/my-skill",
  "results": [
    {
      "prompt_id": 1,
      "prompt": "...",
      "without_skill_output": "...",
      "with_skill_output": "...",
      "expected": "...",
      "improvement_score": 0.8,
      "passed": true,
      "eval_mode": "full_test"
    }
  ],
  "summary": {
    "total": 3,
    "passed": 3,
    "pass_rate": 1.0,
    "dry_run_ratio": 0.0,
    "dry_run_warning": false
  }
}
```

引擎消费：

```bash
evaluate-skill skills/my-skill --prompts-verification artifacts/my-skill/prompts_verification.json
```

## 干跑比例控制

如果 `dry_run_ratio > 30%`，评估报告会发出警告：

```text
⚠️ Warning: dry-run ratio > 30%; measured performance score may be unreliable.
```

这意味着大部分 prompts 只是"纸上谈兵"，没有真实验证 skill 的执行效果。此时应增加 `full_test` 比例。

## 与评估的关系

Test-prompts 验证属于 `evaluate-skill` 的可选能力，影响 D6 "LLM callability" 和 D8 "measured performance" 的评分证据。
