> 本文描述 skillPrism 的当前体系结构：Agent 侧统一为单一 `skill-prism` 入口，LLM 能力通过 Agent 交互或外部命令实现；核心引擎保持确定性、CI 友好。

# skillPrism 架构设计：统一 Agent 入口与可选 LLM 增强层

## 1. 核心原则

> **Agent 是 LLM 调用方，引擎只做测量。**

- 引擎默认不调用 LLM。
- Agent 理解用户意图，按需调用 LLM 或外部命令，生成结构化结果。
- 引擎通过 CLI 参数消费这些结果，与确定性评分 blended。

## 2. 总体结构

```text
┌─────────────────────────────────────────────────────────────┐
│                         User                                │
│                 (natural language intent)                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                      Agent                                  │
│  (Claude / Cursor / GPT / human-in-the-loop)                │
│  Loads: skills/skill-prism/SKILL.md                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
          ┌────────────┼────────────┬────────────────┐
          │            │            │                │
          ▼            ▼            ▼                ▼
   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐
   │  Engine  │  │  Engine  │  │  Agent   │  │  Optional    │
   │  CLI     │  │  CLI     │  │  LLM     │  │  Reporter    │
   │ evaluate │  │ improve  │  │ Judge    │  │ Visual Card  │
   └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘
        │             │             │                │
        ▼             ▼             ▼                ▼
   deterministic  .skillprism   .skillprism      result-card.html
   scorecard      _history      _llm_judgments   / .png
                  .jsonl        .json
```

## 3. 三层职责

| 层级 | 职责 | 是否调用 LLM | 代表实体 |
|---|---|---|---|
| **Agent 层** | 理解用户意图，翻译为命令；按需调用 LLM 生成验证结果 | ✅ 可以 | `skills/skill-prism/SKILL.md` |
| **交换层** | 结构化文件，承载验证结果和历史，供引擎消费 | ❌ 不调用 | `artifacts/<skill>/history.jsonl`、`artifacts/<skill>/llm_judgments.json`、`artifacts/<skill>/prompts_verification.json` |
| **引擎层** | 确定性评分、benchmark、回归、报告生成、优化策略 | ❌ 不调用 | `evaluate-skill`、`test-skill`、`improve-skill`、`skill-pipeline`、`skill-ci` |

## 4. 统一 Agent 入口：`skill-prism`

`skills/skill-prism/SKILL.md` 是 Agent 的唯一主接口。

它教会 Agent：
1. 如何把自然语言意图映射到引擎 CLI 命令。
2. 何时需要调用 LLM 或外部命令生成结构化验证文件。
3. 何时需要用户确认（人在回路）。

### 意图表示例

| 自然语言意图 | Agent 执行动作 |
|---|---|
| "评估这个 skill" | `evaluate-skill <skill>` |
| "跑 benchmark" | `test-skill --skill <skill> --task <task>` |
| "用代码跑 benchmark" | `test-skill --skill <skill> --task <task> --code <code>` |
| "渐进测试" | `test-skill --mode gradual --skill <skill> --registry <registry>` |
| "优化这个 skill" | `improve-skill <skill> --record-baseline --suggest --judge` |
| "查看优化历史" | `improve-skill <skill> --history` |
| "探索性重写" | `improve-skill <skill> --explore-rewrite --apply` |
| "跑完整流水线" | `skill-pipeline --intent "run full quality pipeline"` |
| "再深入看看可读性和准确性" | `evaluate-skill <skill> --llm-judge --llm-judge-count 3` |
| "验证 test-prompts" | `evaluate-skill <skill> --prompts-verification artifacts/<skill>/prompts_verification.json` |

## 5. 引擎核心能力

### 5.1 evaluate-skill

默认启用：
- 9 维度 rubric 评分
- 规则增强检查（模糊词、AI 腔、失败模式编码、检查点标记、体积膨胀）
- SkillLens 高风险黑名单检查
- Runtime neutrality 红灯扫描
- test-prompts.json 存在性检查；缺失时自动生成 3 个 prompts
- 安全扫描
- 记录基线到 `artifacts/<skill>/history.jsonl`

可选启用：
- `--llm-judge`：调用外部 LLM judge 命令，默认 2 个独立评委
- `--prompts-verification`：消费 Agent 生成的 prompts 验证结果
- `--run-smoke`、`--run-deps`

### 5.2 improve-skill

默认流程：
1. `--record-baseline`：记录当前 scorecard 和 benchmark
2. `--suggest`：输出最弱维度、相关簇、P0-P3 优化策略
3. Agent 或外部 editor 编辑 SKILL.md（单轮单维度约束）
4. `--judge`：对比 baseline，决定 keep / revert / human-decide
5. `--apply`：应用决策
6. `--history`：查看 `artifacts/<skill>/history.jsonl`

异常处理：
- 不在 git 仓库时自动 `git init`
- `git revert` 失败时尝试 stash fallback
- SKILL.md 体积 > 150% baseline 时自动 revert
- 自动记录时间戳备份

### 5.3 test-skill

- `--mode single`：单次 benchmark
- `--mode gradual`：level 0→3 失败优先渐进测试
- `--mode quick`：level 0 + level 1 快速 gate

## 6. 结构化交换文件

### 6.1 `artifacts/<skill>/history.jsonl`

每行一条 JSON，记录每次 evaluate / improve 尝试。

```json
{
  "timestamp": "2026-06-22T12:00:00Z",
  "skill": "skills/my-skill",
  "commit_or_backup": "a1b2c3d",
  "old_score": 72.3,
  "new_score": 78.5,
  "status": "keep",
  "dimension": "D3",
  "note": "Added if-then fallback tables",
  "eval_mode": "static"
}
```

### 6.2 `artifacts/<skill>/llm_judgments.json`

多评委 LLM judge 结果。

```json
{
  "skill": "skills/my-skill",
  "generated_at": "2026-06-22T12:00:00Z",
  "judges": [
    {"dimension": "D2", "judge_id": "judge_1", "score": 4, "reason": "..."},
    {"dimension": "D2", "judge_id": "judge_2", "score": 3, "reason": "..."}
  ],
  "aggregate": {
    "D2": {"score": 4, "method": "median"}
  }
}
```

### 6.3 `artifacts/<skill>/prompts_verification.json`

test-prompts 验证结果，包含 `eval_mode`（full_test / dry_run）和 dry_run 比例。

```json
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

## 7. 新增 darwin-skill 最佳实践

skillPrism 已吸收 darwin-skill / SkillLens 验证过的机制：

| 能力 | 状态 |
|---|---|
| 9 维 rubric + meta-skill 维度 | ✅ 已实现 |
| 失败模式编码检查 | ✅ 默认启用 |
| 可执行具体性（模糊词黑名单） | ✅ 默认启用 |
| 高风险行动黑名单 | ✅ SkillLens 检查 |
| 多评委 LLM judge（默认 n=2） | ✅ 可选启用（`--llm-judge`） |
| 干跑比例控制（>30% 告警） | ✅ 默认启用 |
| P0-P3 优化策略库 | ✅ `--suggest` |
| 维度相关簇分析 | ✅ `--suggest` |
| 探索性重写 | ✅ `--explore-rewrite` |
| Runtime 红灯扫描 | ✅ 默认启用 |
| 实验历史 JSONL | ✅ 默认记录 |
| 视觉成果卡片 | ✅ 可选 reporter |
| 单轮单维度约束 | ✅ 默认启用 |

## 8. 推荐文件结构

```text
skills/
└── skill-prism/
    └── SKILL.md                  # 统一 Agent 入口

<skill-path>/
├── SKILL.md
└── .skillprism_baseline/         # baseline 与备份
    ├── SKILL.md
    ├── SKILL.md.bak.<timestamp>
    └── optimization_result.json

artifacts/<skill>/                # 生成物（gitignored），skill 树保持只读
├── test-prompts.json
├── llm_judgments.json            # 可选
├── prompts_verification.json     # 可选
└── history.jsonl                 # 优化历史
```

## 9. 总结

> **skillPrism 以 `skill-prism` 作为唯一 Agent 入口，引擎保持确定性测量，LLM 能力通过 Agent 或外部命令可选接入。通过结构化文件交换结果，系统既保持 CI 友好，又支持人在回路的高质量 Skill 优化。**
