---

name: skill-prism
description: >-
  Unified Agent interface for skillPrism. Translates natural-language intents
  into the five core commands: evaluate-skill, test-skill, build-skill-test,
  improve-skill, and skill-pipeline. The engine itself never calls LLMs; Agent
  handles all LLM interactions when needed.
tool_type: meta
keywords:
  - skillprism
  - evaluate
  - test
  - build-skill-test
  - improve
  - pipeline
  - quality
---

> **设计说明**：本 Skill 是 skillPrism 的**唯一 Agent 接口**。
> skillPrism 是一个测量 AI agent skill 质量的框架：评估 SKILL.md 好不好、测试生成的代码跑不跑得通、帮助改进 SKILL.md。
> 本文件教会 Agent 如何理解用户意图并调用 skillPrism 引擎命令。
>
> **配套规范（必须加载）**：加载本文件时，**必须同时加载** [`references/AGENT_GUIDE.md`](references/AGENT_GUIDE.md)。它定义了 Agent 在调用 skillPrism 时的交互行为规范：开场说明计划、编辑前征求同意、展示 diff、失败恢复、最终报告格式等。
>
> **安全红线（即使未加载 AGENT_GUIDE 也必须遵守）**：
> - 编辑目标 SKILL.md 前，必须先说明打算改什么并等用户批准。
> - `--apply`（真正 keep/revert、写文件）只在用户明确确认后才使用；默认 dry-run。
> - 涉及代码资产（`scripts/`、`examples/`、`requirements.txt`）修改时，默认需人工确认，不能自动执行。
> - D5（领域准确性）与 D9（安全扫描）的 critical/high 发现必须人工处理。

# skill-prism: Unified Agent Interface

## What skillPrism Does

skillPrism measures the quality of an AI agent skill. A skill has two parts:

1. **SKILL.md**: the instruction document that teaches an Agent how to do something.
2. **Generated code or direct result**: the executable artifact or output an Agent produces after reading SKILL.md.

skillPrism answers three questions:

| Question | Command | Measures |
|---|---|---|
| Is the SKILL.md good? | `evaluate-skill` | Documentation, executability, safety, etc. |
| Does the skill actually work? | `test-skill` | Correctness on data, regression, robustness |
| How do I make it better? | `improve-skill` | Edits SKILL.md/code and judges the change |

## Core Principle

> **The skillPrism engine never calls an LLM. The Agent is the executor and the LLM caller.**
>
> - The engine provides deterministic measurement.
> - The Agent generates code, produces results, spawns sub-agents, calls LLM judges, and verifies prompts when asked.
> - Results are exchanged through structured files so the engine can consume them.

---

## Quick Intent Map

| User says | Agent runs |
|---|---|
| "Evaluate this skill" | `evaluate-skill skills/<skill>` |
| "Score all skills" | `evaluate-skill --all --skills-dir ./skills` |
| "Test this skill" | `test-skill --skill <skill> --task <task>` |
| "Run all benchmarks" | `test-skill --skill <skill> --registry benchmarks/<skill>/registry.yaml` |
| "Build a benchmark" | `build-skill-test --id ... --skill <skill> --task <task> --input ... --expected-path ...` |
| "Improve this skill" | `improve-skill skills/<skill> --record-baseline --suggest` |
| "Judge my edit" | `improve-skill skills/<skill> --judge --apply` |
| "Run full pipeline" | `skill-pipeline --intent "run full quality pipeline"` |
| "CI gate" | `skill-ci --skill <skill>` |

### Natural-language variants

The table above shows canonical phrases. Agent should also recognize these synonyms and word orders:

| User says | Interpreted intent | Command to run |
|---|---|---|
| "跑一下 benchmark" / "run benchmarks" / "benchmark this skill" | Test skill against registry | `test-skill --skill <skill> --registry benchmarks/<skill>/registry.yaml` |
| "给所有 skills 打分" / "score everything" / "grade all skills" | Evaluate all skills | `evaluate-skill --all --skills-dir ./skills` |
| "评估一下 skill-prism" / "evaluate skill-prism" | Evaluate single skill | `evaluate-skill skills/skill-prism` |
| "生成测试用例" / "generate prompts" / "create test prompts" | Generate test prompts | `evaluate-skill --skill <skill> --output <dir>/report.md` (prompts written beside the report, not in the skill tree) |
| "看看有没有 regress" / "check regression" / "ratchet check" | Evaluate with ratchet | `evaluate-skill --ratchet --output docs/SKILL_SCORECARD.md` |
| "CI 检查" / "run CI gate" / "static gate" | CI gate | `skill-ci --skill <skill>` |
| "优化 skill-prism" / "improve skill-prism" / "fix the failing dimension" | Improve skill | `improve-skill skills/<skill> --record-baseline --suggest` |
| "完整流水线" / "full pipeline" / "quality check everything" | Full pipeline | `skill-pipeline --intent "run full quality pipeline" --skills-dir ./skills --benchmark-registry benchmarks/<skill>/registry.yaml` |

---

## Core Intents

### 1. Evaluate a skill

**User says**: "Evaluate this skill", "Score this skill", "Check this SKILL.md"

**Default command** (when user does not specify extra requirements):

```bash
evaluate-skill skills/my-skill
```

**How to choose parameters from natural language**:

| User intent clue | Parameter to add | Example user phrase |
|---|---|---|
| "详细", "告诉我哪里扣分", "定位短板" | `--detailed` | "详细评估一下这个 skill" |
| "可执行", "跑一下示例", "smoke" | `--run-smoke` | "检查一下这个 skill 能不能跑" |
| "依赖", "环境", "安装" | `--run-deps` | "看看依赖能不能装" |
| "所有 skill", "批量", "打分" | `--all --skills-dir ./skills` | "给所有 skills 打个分" |
| "LLM judge", "主观维度", "第二意见" | `--llm-judge` 或 `--llm-judgments` | "用 LLM judge 再看看" |
| "对比 baseline", "别 regress" | `--ratchet` | "评估一下有没有 regress" |
| "输出报告", "生成 scorecard" | `--output docs/SKILL_SCORECARD.md` | "生成一份 scorecard" |
| "追踪历史", "趋势" | `--output-history docs/score_history.jsonl` | "记录到历史里" |

**Common combinations**:

```bash
# 默认：快速确定性评分
evaluate-skill skills/my-skill

# 详细评估
evaluate-skill skills/my-skill --detailed

# 检查可执行性和依赖
evaluate-skill skills/my-skill --run-smoke --run-deps

# 批量评估并生成报告
evaluate-skill --all --skills-dir ./skills --output docs/SKILL_SCORECARD.md

# 主观维度用 LLM judge（需要配置外部 judge 命令）
evaluate-skill skills/my-skill --llm-judge

# Agent 已生成 judgments 文件，引擎直接消费（无需配置外部命令）
evaluate-skill skills/my-skill --llm-judgments .skillprism_llm_judgments.json

# 完整 CI 前检查
evaluate-skill skills/my-skill --detailed --run-smoke --run-deps --ratchet
```

**Side effects and output directory**:

- By default, `evaluate-skill` does **not** modify the skill source tree.
- If `--output <path>` is provided, auto-generated `test-prompts.json` is written next to the report (in the same directory as `--output`), not inside the skill directory.
- If you explicitly want prompts inside the skill tree, run without `--output`.
- Use `--no-generate-prompts` to skip prompt generation entirely.

**Key parameters**:

| Parameter | Purpose |
|---|---|
| `--detailed` | Per-dimension evidence and suggestions |
| `--all` | Evaluate all skills under `--skills-dir` |
| `--skills-dir <path>` | Skills root directory (default: `./skills`) |
| `--run-smoke` | Run example smoke tests |
| `--allow-exec` | Execute skill-shipped example code (sandboxed). Off by default; safe to enable for **trusted/internal** skills to get the real D3 signal. Keep off for untrusted skill sources. |
| `--run-deps` | Check dependency reproducibility |
| `--llm-judge` | Enable LLM judge for subjective dimensions |
| `--llm-judge-count N` | Number of judges (default: 2) |
| `--llm-judgments <path>` | Consume pre-computed judgments generated by the Agent |
| `--prompts-verification <path>` | Consume pre-computed prompt verification |
| `--output-history <path>` | Append result to JSONL trend file |
| `--ratchet` | Fail if score regresses vs baseline |
| `--output <path>` | Write scorecard/report |
| `--verbose` / `-v` | Print detailed progress |

**Agent decision rule for LLM judge**:

- If `SKILLPRISM_LLM_JUDGE_COMMAND` or `skill_rubric_types.yaml` 中 `llm_judge.command` 有值，使用 `--llm-judge`。引擎会通过子进程调用该外部 judge 命令。
- 否则，Agent 自己生成 `.skillprism_llm_judgments.json`，再使用 `--llm-judgments <file>`。
- 两种路径对用户请求表现一致："用 LLM judge 再看看"。

**路径 A：Agent 生成 judgments 文件**

- 默认评估 **D2 和 D5**（可选 D6、D8）。
- 每个维度调用 **2 个独立 judge**，每次调用必须是独立子 agent / 独立 LLM 请求，不能共享推理上下文。
- 必须使用 [`references/LLM_JUDGE.md`](references/LLM_JUDGE.md) 中的 prompt 模板，不得修改 JSON 输出要求。
- 用 `mean` 聚合 2 个分数，写入 `.skillprism_llm_judgments.json`。
- 文件格式见 [`references/LLM_JUDGE.md`](references/LLM_JUDGE.md)。

**路径 B：外部 judge 命令**

- 外部命令从 stdin 接收引擎构造的 user prompt，stdout 返回 `{"score": int, "reason": str}`，退出码 0 表示成功。
- 配置方式：
  - 环境变量：`export SKILLPRISM_LLM_JUDGE_COMMAND="python path/to/judge.py"`
  - 或 `skill_rubric_types.yaml`：`llm_judge.command`
- 启用：`evaluate-skill skills/<skill> --llm-judge --llm-judge-count 2`
- 完整接口规范和 prompt 模板见 [`references/LLM_JUDGE.md`](references/LLM_JUDGE.md)。

---

### 2. Test a skill

**User says**: "Test this skill", "Run the benchmark", "Does the code work?"

The primary purpose of `test-skill` is to verify that a **skill works as part of an Agent's capabilities**. The skill is the thing being tested; the Agent is the executor that selects and invokes it.

**Important**: By default `test-skill` runs in **verify-only mode**. It does **not** execute any code and does **not** call an LLM. It only checks whether the expected output file already exists and satisfies the metrics. Therefore, **you must produce the output before calling `test-skill`**, unless an external agent command is configured.

**Execution mode selection**:

| Mode | Trigger | Who produces the result |
|---|---|---|
| **Verify-only (default)** | No `SKILLPRISM_AGENT_COMMAND`, no `--code` | Current Agent / sub-agent |
| **External agent** | `SKILLPRISM_AGENT_COMMAND` is set | External command invoked by the engine |
| **Code** | `--code <path>` | Engine executes the provided code |

Use `--verify-only` to force verify-only mode even when `SKILLPRISM_AGENT_COMMAND` is set.

---

#### Default workflow: Agent/sub-agent produces the result, engine verifies

```bash
test-skill --skill my-skill --task csv_summary
```

**What the Agent must do before running the command above**:

```text
当前 Agent（已加载 skill-prism + target skills）：
  1. 读取 task spec: benchmarks/my-skill/tasks/csv_summary.yaml
  2. 拿到 input path、output path 和 task prompt
  3. （推荐）创建子 agent：只保留 skill 能力，不保留当前任务推理上下文
  4. 子 agent 看到 task prompt，识别并调用合适的 skill
  5. 子 agent 生成结果文件到 task-spec 指定的 output path
  6. 当前 Agent 运行：test-skill --skill my-skill --task csv_summary
  7. skillPrism 评估结果并报告 PASS/FAIL
```

This is the recommended mode because:
- It tests whether the Agent can correctly select and invoke the right skill.
- The Agent can retry, iterate, and debug before finalizing the output.
- The engine stays deterministic and does not call LLMs.

> When spawning sub-agents or reporting results to the user, follow the conventions in [`references/AGENT_GUIDE.md`](references/AGENT_GUIDE.md): explain the plan, ask before editing files, show diffs, and recover from failures gracefully.

---

#### Code workflow: Agent/sub-agent produces code, engine executes and verifies

If you want the Agent to produce **executable code** instead of the final result, and let the engine run it:

```text
当前 Agent（已加载 skill-prism + target skills）：
  1. 读取 task spec: benchmarks/my-skill/tasks/csv_summary.yaml
  2. 拿到 input path、output path 和 task prompt
  3. （推荐）创建子 agent：只保留 skill 能力，不保留当前任务推理上下文
  4. 子 agent 看到 task prompt，识别并调用合适的 skill
  5. 子 agent 生成可执行代码文件，例如 sample_skill_code.py
  6. 当前 Agent 运行：test-skill --skill my-skill --task csv_summary --code sample_skill_code.py
  7. skillPrism 执行代码并评估产出，报告 PASS/FAIL
```

Use this when:
- The task is easier to express as code than as a direct result.
- You want a reproducible artifact for CI.
- You want to test the skill's code-generation capability rather than its end-to-end reasoning.

> **Code source does not matter.** `--code` accepts any executable file: Agent-generated, user-written, checked into version control, or produced by an external generator. The engine only checks that the file exists and executes it.

---

#### External agent workflow: engine invokes an external agent command

If `SKILLPRISM_AGENT_COMMAND` is configured, the engine itself invokes the external command to produce the result:

```bash
export SKILLPRISM_AGENT_COMMAND="python examples/editor_wrappers/agent_caller.py"
test-skill --skill my-skill --task csv_summary
```

**What happens**:

```text
1. 引擎读取 task spec
2. 引擎构造 task prompt
3. 引擎调用 SKILLPRISM_AGENT_COMMAND，通过 stdin 传入 prompt
4. 外部 agent 读取 SKILLPRISM_INPUT_PATH，生成结果到 SKILLPRISM_OUTPUT_PATH
5. 引擎评估 output 并报告 PASS/FAIL
```

Use this when:
- You want a clean separation between the measuring engine and the executing agent.
- The current Agent context should not be polluted with task-specific reasoning.
- You have a dedicated agent process or LLM wrapper.

Use `--verify-only` to skip the external agent and verify an existing output even when `SKILLPRISM_AGENT_COMMAND` is set.

---

#### How to choose parameters from natural language

| User intent clue | Parameter to add | Example user phrase |
|---|---|---|
| "所有 benchmark", "跑一遍" | `--registry <path>` | "跑一下这个 skill 的所有 benchmark" |
| "用代码", "让 Agent 写代码" | `--code <path>` | "让 Agent 生成代码来跑" |
| "外部 agent", "用另一个 agent 跑" | 配置 `SKILLPRISM_AGENT_COMMAND` | "让外部 agent 执行这个 benchmark" |
| "快速", "quick", "先快速验证" | `--mode quick` | "快速验证一下" |
| "渐进", "逐步", "从简单到复杂" | `--mode gradual` | "从简单到复杂逐步测试" |
| "只跑 level N", "第 N 级" | `--level N` | "只跑 level 2" |
| "最高到 level N" | `--max-level N` | "测到 level 2 就够了" |
| "只跑 smoke", "轻量验证" | `--suite smoke` | "只跑 smoke 测试" |
| "GPU", "显卡" | `--gpu` | "用 GPU 跑" |

---

#### Common combinations

```bash
# 默认：验证 Agent/子 Agent 已生成的结果（必须先产生输出）
test-skill --skill my-skill --task csv_summary

# 跑 registry 里所有 benchmarks（均验证已生成结果）
test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml

# Agent/子 Agent 已生成代码，由引擎执行并验证
test-skill --skill my-skill --task csv_summary --code sample_skill_code.py

# 配置外部 agent 命令后，由引擎调用外部 agent 执行
export SKILLPRISM_AGENT_COMMAND="python examples/editor_wrappers/agent_caller.py"
test-skill --skill my-skill --task csv_summary

# 即使配置了外部 agent，也强制只验证现有输出
test-skill --skill my-skill --task csv_summary --verify-only

# 快速 gate
test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml --mode quick

# 渐进测试到 level 2
test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml --mode gradual --max-level 2

# 只跑 smoke suite
test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml --suite smoke
```

---

#### Key parameters

| Parameter | Purpose |
|---|---|
| `--skill <name>` | Skill name |
| `--task <id>` | Task id (uses task spec in `benchmarks/<skill>/tasks/<task>.yaml`) |
| `--code <path>` | Pre-generated skill code (engine will execute it) |
| `--registry <path>` | Benchmark registry YAML (canonical: `benchmarks/<skill>/registry.yaml`) |
| `--mode single/gradual/quick` | Testing mode |
| `--level N` | Run only benchmarks at this level (single mode) |
| `--max-level N` | Highest level for gradual mode |
| `--suite <name>` | Run only benchmarks in this suite |
| `--output-dir <path>` | Directory for test artifacts |
| `--gpu` / `--no-gpu` | Override GPU availability |
| `--verify-only` | Verify existing output (default: True; disable with `--code` or `SKILLPRISM_AGENT_COMMAND`) |

---

#### What it does

- Discovers the task spec (`benchmarks/<skill>/tasks/<task>.yaml`)
- Generates the agent prompt from the task spec (no SKILL.md leakage)
- In verify-only mode: checks the existing output against the metrics defined in the registry entry
- With `--code`: executes the provided code and evaluates the produced output
- With `SKILLPRISM_AGENT_COMMAND`: invokes the external agent command to produce the output, then evaluates it
- Compares output against expected / baseline

**Metrics**:

- Public metric functions are registered via `@metric("id")` in `skillprism/benchmark/metrics.py`.
- A per-registry `metrics.py` (beside `registry.yaml`) can add private or skill-specific metrics.
- Metrics and expected output are declared in the benchmark entry inside `benchmarks/<skill>/registry.yaml`, not in the task spec.

**Restrictions**:
- `--code` implies engine execution unless `--verify-only` is explicitly set (which is an error).
- `--verify-only` explicitly set ignores `SKILLPRISM_AGENT_COMMAND`.
- `--verify-only` and `--code` are mutually exclusive.
- In verify-only mode, the output file must already exist; otherwise the benchmark fails immediately.

---

### 3. Build a benchmark

**User says**: "Build a benchmark", "Register a test", "Add this case to the benchmark registry"

**Default command** (when user only names the benchmark):

```bash
build-skill-test \
  --id csv_summary_sales \
  --name "CSV Summary: Sales" \
  --skill my-skill \
  --task csv_summary \
  --input data/level1/input.csv \
  --expected-path expected/level1/expected.csv \
  --registry benchmarks/my-skill/registry.yaml
```

> 示例：`examples/benchmark_minimal/benchmarks/document-demo/registry.yaml`

**How to choose parameters from natural language**:

| User intent clue | Parameter to add | Example user phrase |
|---|---|---|
| "task spec 在别处" | `--task-spec <path>` | "task spec 放在别的目录" |
| "定义指标" | `--metric id:type:args` | "行数至少 8 行" |
| "level N" | `--level N` | "这是一个 level 2 的 benchmark" |
| "加入 smoke/gradual suite" | `--suite <name>` | "加到 smoke suite" |
| "需要 GPU" | `--gpu` | "这个 benchmark 需要 GPU" |
| "真实数据" | `--real-data` | "用真实数据，只检查完成" |
| "自动生成金标准" | `--generate-expected` | "帮我生成 expected output" |

**Key parameters**:

| Parameter | Purpose |
|---|---|
| `--id` | Benchmark unique id |
| `--name` | Human-readable name |
| `--skill` | Skill this benchmark tests |
| `--task` | Task id |
| `--task-spec` | Path to task spec YAML relative to the registry directory (default: `tasks/<task>.yaml`) |
| `--input` | Input data path (relative to registry directory) |
| `--expected-path` | Golden output path (relative to registry directory) |
| `--metric id:type:args` | Metric threshold to store in the registry entry |
| `--level` | Difficulty level (0-3) |
| `--suite` | Add to suite (repeatable) |
| `--registry` | Registry file to append to (canonical: `benchmarks/<skill>/registry.yaml`) |
| `--generate-expected` | Auto-generate expected for simple CSV cases |
| `--gpu` | Mark as requiring GPU |
| `--real-data` | Mark as real-data completion check |

---

### 4. Improve a skill

**User says**: "Improve this skill", "Optimize this skill", "Fix the failing dimension"

**Default workflow**:

```bash
# Step 1: record baseline
improve-skill skills/my-skill --record-baseline

# Step 2: get optimization strategy
improve-skill skills/my-skill --suggest

# Step 3: edit SKILL.md (manually or auto-edit)
# Manual: edit skills/my-skill/SKILL.md, then:
improve-skill skills/my-skill --judge --apply

# Auto: let editor edit for you
improve-skill skills/my-skill --auto-edit --max-rounds 3 --apply
```

**How to choose parameters from natural language**:

| User intent clue | Parameter to add | Example user phrase |
|---|---|---|
| "记录 baseline" | `--record-baseline` | "先记录 baseline" |
| "哪里最弱", "给建议" | `--suggest` | "这个 skill 哪里最弱？" |
| "自动改", "帮我改" | `--auto-edit` | "自动帮我优化" |
| "最多改 N 轮" | `--max-rounds N` | "自动改 3 轮" |
| "改完判断" | `--judge` | "judge 一下这次改动" |
| "确认保留" | `--apply` | "确认保留这次改动" |
| "带 benchmark" | `--benchmark-registry <path>` | "优化时跑 benchmark gate" |
| "用代码跑 benchmark" | `--code <path>` | "用这份代码跑 benchmark gate" |
| "允许改代码" | `--edit-code` | "也可以改代码" |
| "最低提升" | `--min-gain <float>` | "至少提升 1 分才保留" |
| "遇到回滚停止" | `--stop-on-regression` | "如果改差了立刻停" |
| "查看历史" | `--history` | "看看优化历史" |
| "重写", "瓶颈" | `--explore-rewrite` | "好像到瓶颈了，重写试试" |
| "LLM judge" / "第二意见" | `--llm-judge` 或 `--llm-judgments` | "优化时用 LLM judge 看看" |

**Key parameters**:

| Parameter | Purpose |
|---|---|
| `--record-baseline` | Save current scorecard/benchmark as baseline |
| `--suggest` | Print weakest dimension and strategy |
| `--auto-edit` | Autonomously edit SKILL.md using configured editor |
| `--max-rounds N` | Max auto-edit rounds |
| `--judge` | Compare current vs baseline and decide keep/revert |
| `--apply` | Actually execute the decision (default is dry-run) |
| `--min-gain <float>` | Minimum score gain to keep edit |
| `--stop-on-regression` | Stop auto-edit if an edit is reverted |
| `--benchmark-registry <path>` | Enable benchmark gate |
| `--benchmark-output-dir <path>` | Directory for benchmark artifacts |
| `--code <path>` | Code to use during benchmark gate |
| `--edit-code` | Allow editor to modify code assets |
| `--clear-baseline` | Remove stored baseline |
| `--history` | Show optimization history |
| `--explore-rewrite` | Exploratory rewrite of SKILL.md |
| `--show-diff` / `--no-show-diff` | Show/hide diff in output |
| `--editor-command`, `--editor-model`, `--judge-model` | Override editor/judge |
| `--llm-judge` | Enable LLM judge for subjective dimensions during optimization |
| `--llm-judge-command` | Override LLM judge command |
| `--llm-judgments <path>` | Consume pre-computed judgments generated by the Agent |

**Agent decision rule for LLM judge**:

- If `SKILLPRISM_LLM_JUDGE_COMMAND` or config `llm_judge.command` is available, use `--llm-judge`.
- Otherwise, the Agent generates `.skillprism_llm_judgments.json` itself and uses `--llm-judgments <file>`.
- 完整 prompt 模板、外部 judge 命令接口和配置项见 [`references/LLM_JUDGE.md`](references/LLM_JUDGE.md)。
- This works the same as in `evaluate-skill`.

**What it does**:

- Records baseline scorecard + benchmark results in `.skillprism_history.jsonl`
- Suggests P0-P3 optimization strategies
- Edits SKILL.md / code (Agent or external editor), constrained to one dimension per round
- Re-evaluates and re-tests
- Judges whether the change is keep / revert / human-decide
- Applies only with explicit `--apply`
- Auto-git-init if not in a repo; uses file backup fallback when git unavailable

### Judge Logic for improve-skill

When `--judge` runs, the engine compares **baseline** vs **current**:

| Condition | Decision |
|---|---|
| Score increased, benchmark passed, no guard failed | **keep** |
| Score decreased, or benchmark failed, or any guard failed | **revert** |
| Score unchanged but a key dimension improved | **human-decide** |
| Security score (D9) decreased | **revert** |

The final apply requires `--apply` or human confirmation.

---

### 5. Run full pipeline

**User says**: "Run the full pipeline", "Quality check everything", "Find the worst skill"

**Default command**:

```bash
skill-pipeline --intent "run full quality pipeline" \
  --skills-dir ./skills \
  --benchmark-registry benchmarks/<skill>/registry.yaml \
  --output docs/SKILL_QUALITY_REPORT.md
```

**How to choose parameters from natural language**:

| User intent clue | `--intent` value | Additional parameters |
|---|---|---|
| "完整流水线", "质量检查" | `"run full quality pipeline"` | `--benchmark-registry <path>` |
| "给所有 skill 打分" | `"evaluate all skills"` | `--skills-dir ./skills` |
| "找出最差的" | `"improve skills"` | `--apply --max-rounds 3` |
| "渐进测试所有 skill" | `"run gradual pipeline"` | `--benchmark-registry <path> --max-level N` |
| "生成报告" | any | `--output docs/SKILL_QUALITY_REPORT.md` |
| "跑 smoke" | any | `--run-smoke` |

**Common combinations**:

```bash
# 完整质量流水线
skill-pipeline --intent "run full quality pipeline" \
  --skills-dir ./skills \
  --benchmark-registry benchmarks/<skill>/registry.yaml \
  --output docs/SKILL_QUALITY_REPORT.md

# 批量评估
skill-pipeline --intent "evaluate all skills" --skills-dir ./skills

# 批量渐进测试
skill-pipeline --intent "run gradual pipeline" \
  --skills-dir ./skills \
  --benchmark-registry benchmarks/<skill>/registry.yaml \
  --max-level 2

# 自动优化所有 skill
skill-pipeline --intent "improve skills" \
  --skills-dir ./skills \
  --apply --max-rounds 3
```

**Key parameters**:

| Parameter | Purpose |
|---|---|
| `--intent <text>` | Natural language intent (required) |
| `--skills-dir <path>` | Skills root directory |
| `--benchmark-registry <path>` | Benchmark registry YAML |
| `--benchmark-suite <name>` | Run only this suite |
| `--benchmark-output-dir <path>` | Directory for benchmark outputs |
| `--benchmark-baseline-dir <path>` | Directory for benchmark baselines |
| `--output <path>` | Combined report output |
| `--run-smoke` | Run smoke tests |
| `--apply` | Auto-apply optimization decisions |
| `--max-rounds N` | Max optimization rounds |
| `--max-level N` | Max gradual level |
| `--no-ratchet` | Do not ratchet baselines forward |

---

### 6. CI gate

**User says**: "CI gate", "Run CI checks", "Static gate"

**Default command**:

```bash
# Static checks only (default)
skill-ci --skill my-skill
```

**How to choose parameters from natural language**:

| User intent clue | Parameter to add | Example user phrase |
|---|---|---|
| "跑 benchmark" | `--run-benchmark --code <path>` | "CI 里也跑 benchmark" |
| "对比 baseline" | `--baseline <path>` | "检查有没有 regress" |
| "regress 就失败" | `--stop-on-regression` | "有 regression 就挂" |
| "更新 baseline" | `--ratchet` | "通过就更新 baseline" |
| "只跑某个 suite" | `--suite <name>` | "只跑 smoke suite" |
| "只跑 level N" | `--level N` | "只跑 level 1" |
| "跳过 smoke" | `--no-smoke` | "跳过 smoke 快点" |
| "跳过依赖检查" | `--no-deps` | "不检查依赖" |

**Common combinations**:

```bash
# 默认静态 CI 门控
skill-ci --skill my-skill

# 含 benchmark 的完整 CI
skill-ci --skill my-skill \
  --registry benchmarks/<skill>/registry.yaml \
  --run-benchmark --code sample_skill_code.py \
  --baseline baselines/my-skill.yaml \
  --stop-on-regression
```

**Key parameters**:

| Parameter | Purpose |
|---|---|
| `--skill <name>` | Skill name or path (required) |
| `--registry <path>` | Benchmark registry YAML |
| `--baseline <path>` | Baseline results YAML for regression comparison |
| `--output-dir <path>` | CI artifacts directory |
| `--output-format <fmt>` | `yaml` / `json` / `markdown` |
| `--suite <name>` | Run only this suite |
| `--level N` | Run only this level |
| `--run-benchmark` | Also run dynamic benchmarks (requires `--code`) |
| `--code <path>` | Code for dynamic benchmarks |
| `--ratchet` | Update baseline on success |
| `--stop-on-regression` | Fail on regression |
| `--no-smoke` | Skip smoke tests |
| `--no-deps` | Skip dependency checks |
| `--deps-dry-run` | Run pip/conda dry-run installs |

---

## Standard Agent Workflow

### For a new skill

```bash
# 1. Evaluate
evaluate-skill skills/my-skill

# 2. Define a task spec for the benchmark
#    benchmarks/my-skill/tasks/csv_summary.yaml

# 3. Register a benchmark
build-skill-test \
  --id csv_summary_sales \
  --skill my-skill \
  --task csv_summary \
  --input data/level1/input.csv \
  --expected-path expected/level1/expected.csv \
  --registry benchmarks/my-skill/registry.yaml

# 4. Test with Agent/sub-agent-produced output (default verify-only)
#    Make sure the output file at the task-spec output path already exists.
test-skill --skill my-skill --task csv_summary

# 5. Or test with an external agent command configured via SKILLPRISM_AGENT_COMMAND
test-skill --skill my-skill --task csv_summary

# 6. Or test with code generated by the Agent/sub-agent and executed by the engine
test-skill --skill my-skill --task csv_summary --code sample_skill_code.py

# 6. Improve if needed
improve-skill skills/my-skill --record-baseline --suggest
# edit skills/my-skill/SKILL.md
improve-skill skills/my-skill --judge --apply
```

---

## Code Generation Rule

**skillPrism never calls an LLM directly, unless configured to invoke an external agent command.**

- In verify-only mode: the Agent or sub-agent produces the result; skillPrism only evaluates it.
- With `SKILLPRISM_AGENT_COMMAND`: skillPrism invokes the configured external command; the command may use an LLM, but the engine itself does not.
- With `--code`: the user or Agent writes code; skillPrism executes it and evaluates the output.
- The engine only measures results; it is not a code generator or an Agent.

---

## Output Artifacts

| Artifact | When produced | Purpose |
|---|---|---|
| `scorecard.md` | `evaluate-skill --output` | Human-readable report |
| `test-prompts.json` | `evaluate-skill` (when prompts are generated) | Test prompts for the skill |
| `.skillprism_baseline/` | `improve-skill --record-baseline` | Baseline for comparison |
| `.skillprism_history.jsonl` | every evaluate/improve run | Optimization history |
| `.skillprism_llm_judgments.json` | Agent LLM judge | Structured LLM opinions |
| `.skillprism_prompts_verification.json` | Agent prompts verification | Structured prompt results |
| `ci-output/` | `test-skill`, `skill-ci` | Test artifacts |

---

## When NOT to Use skillPrism

- If you only need to run arbitrary Python code, use `python` directly.
- If you want the engine to generate code for you, skillPrism is not the tool; generate code with an Agent or external generator first, then test it here.
- If you need non-deterministic creative output without measurement, skillPrism adds no value.

---

## Common Agent Mistakes and Corrections

1. **Confusing `evaluate-skill` with `test-skill`**
   - `evaluate-skill` measures the **SKILL.md** quality (static rubric).
   - `test-skill` measures whether the skill **works on data** (dynamic benchmark).
   - If the user asks "does it work?", use `test-skill`. If "is the doc good?", use `evaluate-skill`.

2. **Passing `--skill` as a flag to `evaluate-skill`**
   - `evaluate-skill` takes the skill path as a positional argument: `evaluate-skill skills/my-skill`.
   - `test-skill` and `skill-ci` take `--skill <name>` because they may also need `--task` or `--registry`.

3. **Running `test-skill` without producing output first**
   - `test-skill` defaults to verify-only mode. The output file must already exist.
   - Recovery: spawn a sub-agent to generate the output, or use `--code <path>` to let the engine execute skill-generated code.

4. **Forgetting `--apply` with `improve-skill`**
   - `--judge`, `--auto-edit`, and `--record-baseline` are dry-run by default.
   - Use `--apply` only after showing the user the planned change and receiving explicit approval.

5. **Using outdated command names**
   - Correct: `evaluate-skill`, `test-skill`, `improve-skill`, `skill-pipeline`, `skill-ci`.
   - Do **not** use `evaluate-skill-rubric` or `run-skill-benchmark`; those names are obsolete.

6. **Writing artifacts into the skill tree**
   - Use `--output` to redirect scorecards, reports, and generated prompts to a separate directory.
   - Keep the skill source tree read-only unless explicitly editing SKILL.md or code assets.

## References

- `docs/getting-started/index.md`: Human-facing getting-started guide.
- `docs/getting-started/cli-cheatsheet.md`: One-page CLI and natural-language reference.
- `docs/tutorial/04-building-your-first-benchmark.md`: Building benchmarks in the new task-spec architecture.
- `docs/reference/skill-prism-architecture.md`: Architecture design document.
- `docs/reference/agent-command.md`: External agent command details.
- `references/LLM_JUDGE.md`: LLM judge details.
- `docs/reference/natural-language-interaction.md`: Natural-language interaction best practices.
- `docs/reference/test-prompts-verification.md`: Prompt verification details.
