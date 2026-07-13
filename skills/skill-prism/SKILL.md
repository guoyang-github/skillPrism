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

## Output Location Rules

`<project-root>` 下可同时测多个 skill，生成物一律**按 skill 命名空间隔离**，绝不写进 skill 树。约定：`artifacts/<skill>/` 放该 skill 的全部生成物，`reports/` 放跨 skill 汇总。

| 产物 | 位置 | 控制参数 |
|---|---|---|
| scorecard / report | `artifacts/<skill>/scorecard.md` | `--output` |
| test-prompts.json | `artifacts/<skill>/`（默认） | 自动生成仅兜底；`--prompts-dir` 覆盖落点 |
| LLM judgments | `artifacts/<skill>/llm_judgments.json` | Agent 写 → `--llm-judgments` |
| prompts verification | `artifacts/<skill>/prompts_verification.json` | Agent 写 → `--prompts-verification` |
| optimization history | `artifacts/<skill>/history.jsonl` | `--output-history` |
| benchmark 结果 | `artifacts/<skill>/results.yaml` | `test-skill --output` |
| benchmark baseline | `benchmarks/<skill>/baselines/<name>.yaml` | `--baseline` / `--ratchet` |
| test / CI artifacts | `artifacts/<skill>/ci/` | `--output-dir` |
| 跨 skill 汇总 | `reports/SKILL_SCORECARD.md` | `evaluate-skill --all --output` |

**红线**：

- **绝不**把生成物写进 `skills/skill-prism/`（本 skill 自身文件夹）或目标 skill 源码树，除非本次明确在编辑该 SKILL.md 或其代码资产。
- 生成物默认落 `artifacts/<skill>/`；多 skill 时不要在 CWD 平铺 dot 文件，避免互相覆盖。

---

## Most Common Invocations

按生命周期排序。每行是该环节**最常用的参数组合**（覆盖最常见整体场景，不是裸默认）。一个环节可能有多行，对应不同的常用场景。裸默认见各 Core Intent 节的 **Default**。

| Phase | User says（默认说法） | Most common command |
|---|---|---|
| Evaluate | "评估这个 skill，详细看哪里扣分，主观维度用 LLM judge" | `evaluate-skill skills/<skill> --detailed --llm-judge` |
| Evaluate | "给所有 skill 打分并出报告" | `evaluate-skill --all --skills-dir ./skills --output ./reports/SKILL_SCORECARD.md` |
| Build | "为这个 skill 建 benchmark" | **进入 §2 引导流程**；最终落到 `build-skill-test --id <id> --skill <skill> --task <task> --input data/<level>/... --metric <id:type:args> --suite smoke --suite gradual --registry benchmarks/<skill>/registry.yaml` |
| Test | "用代码跑全部 benchmark" | `test-skill --skill <skill> --registry benchmarks/<skill>/registry.yaml --code <path>` |
| Test | "只评估已产出的结果（results 模式）" | `test-skill --skill <skill> --registry benchmarks/<skill>/registry.yaml` |
| Test | "先跑冒烟" | `test-skill --skill <skill> --registry benchmarks/<skill>/registry.yaml --suite smoke --code <path>` |
| Improve | "优化这个 skill 并判断是否保留" | `improve-skill skills/<skill> --record-baseline --suggest` → 编辑 → `improve-skill skills/<skill> --judge --apply` |
| Improve | "自动改 3 轮" | `improve-skill skills/<skill> --auto-edit --max-rounds 3 --apply` |
| Pipeline | "跑完整质量流水线" | `skill-pipeline --intent "run full quality pipeline" --skills-dir ./skills --benchmark-registry benchmarks/<skill>/registry.yaml --output ./reports/SKILL_QUALITY_REPORT.md` |
| CI | "CI 静态门控" | `skill-ci --skill <skill>` |
| CI | "CI 里也跑 benchmark" | `skill-ci --skill <skill> --registry benchmarks/<skill>/registry.yaml --run-benchmark --code <path>` |

> 没有配置外部 judge 命令时，Agent 自己生成 `artifacts/<skill>/llm_judgments.json`；不传 `--llm-judgments` 时引擎自动发现该文件，对用户说法表现一致。详见各节 decision rule。

---

## Core Intents

### 1. Evaluate a skill

**Default**（用户只说"评估一下"时）：

```bash
evaluate-skill skills/my-skill
```

**参数与意图线索（整合表）**：

| User intent clue | Parameter | Purpose |
|---|---|---|
| "详细"、"哪里扣分"、"定位短板" | `--detailed` | 逐维度证据与改进建议 |
| "可执行"、"跑一下示例"、"smoke" | `--run-smoke` | 运行示例冒烟测试 |
| "允许执行 skill 自带示例" | `--allow-exec` | 沙箱执行 skill 自带示例（仅可信/内部 skill 开启，以获得真实 D3 信号） |
| "依赖"、"环境"、"安装" | `--run-deps` | 检查依赖可复现性 |
| "所有 skill"、"批量"、"打分" | `--all` | 评估 `--skills-dir` 下所有 skill |
| "skill 目录在别处" | `--skills-dir <path>` | Skills 根目录（默认 `./skills`） |
| "LLM judge"、"主观维度"、"第二意见" | `--llm-judge` | 对主观维度启用 LLM judge（外部命令） |
| "judge 次数" | `--llm-judge-count N` | judge 数量（默认 2） |
| "Agent 已生成 judgments" | `--llm-judgments <path>` | 消费 Agent 预生成的 judgments 文件 |
| "已验证 prompts"、"验证 prompt 效果" | `--prompts-verification <path>` | 消费 prompt 验证结果（不传则自动发现 `artifacts/<skill>/prompts_verification.json`）；执行流程见 [`references/PROMPTS_VERIFICATION.md`](references/PROMPTS_VERIFICATION.md) |
| "对比 baseline"、"别 regress" | `--ratchet` | 分数退步即失败 |
| "输出报告"、"生成 scorecard" | `--output <path>` | 写 scorecard/report（单 skill 建议 `artifacts/<skill>/scorecard.md`；跨 skill 汇总用 `reports/`） |
| "追踪历史"、"趋势" | `--output-history <path>` | 追加到 JSONL 趋势文件（建议 `artifacts/<skill>/history.jsonl`） |
| "不要生成 test prompts" | `--no-generate-prompts` | 跳过 prompt 生成 |
| "prompts 放指定目录" | `--prompts-dir <path>` | test-prompts.json 读写目录（默认 `artifacts/<skill>/`；传 skill 目录才写进 skill 树） |
| "看进度" | `--verbose` / `-v` | 打印详细进度 |

**Common combinations**（本环节最常用场景）：

```bash
# 默认：快速确定性评分
evaluate-skill skills/my-skill

# 详细评估 + 主观维度 LLM judge
evaluate-skill skills/my-skill --detailed --llm-judge

# 批量评估并生成报告
evaluate-skill --all --skills-dir ./skills --output ./reports/SKILL_SCORECARD.md

# Agent 已生成 judgments 文件，引擎直接消费（无需配置外部命令）
evaluate-skill skills/my-skill --llm-judgments artifacts/my-skill/llm_judgments.json

# CI 前完整检查
evaluate-skill skills/my-skill --detailed --run-smoke --run-deps --ratchet
```

**Side effects and output directory**:

- 默认 `evaluate-skill` **不**修改 skill 源码树。
- `test-prompts.json` 默认写 `artifacts/<skill>/`（与 `--output` 解耦）；`--prompts-dir` 覆盖落点，传 skill 目录才会写进 skill 树。
- 自动生成的 template prompts 只是占位符（报告带 ⚠️ 标记）；正式 prompt 由 Agent 按 [`references/PROMPTS_VERIFICATION.md`](references/PROMPTS_VERIFICATION.md) 撰写。
- `--output` 只管 scorecard/report 路径，不再影响 prompt 落点。
- 用 `--no-generate-prompts` 完全跳过 prompt 生成（缺失时报告提示按协议创建）。

**Agent decision rule for LLM judge**:

- 若 `SKILLPRISM_LLM_JUDGE_COMMAND` 或 `skill_rubric_types.yaml` 中 `llm_judge.command` 有值，用 `--llm-judge`，引擎通过子进程调用外部 judge 命令。
- 否则，Agent 自己生成 `artifacts/<skill>/llm_judgments.json`（引擎自动发现，也可显式 `--llm-judgments <file>`）。
- 两条路径对用户请求表现一致："用 LLM judge 再看看"。

**路径 A：Agent 生成 judgments 文件**

- 默认评估 **D2 和 D5**（可选 D6、D8）。
- 每个维度调用 **2 个独立 judge**，每次必须是独立子 agent / 独立 LLM 请求，不能共享推理上下文。
- 必须使用 [`references/LLM_JUDGE.md`](references/LLM_JUDGE.md) 中的 prompt 模板，不得修改 JSON 输出要求。
- 用 `mean` 聚合 2 个分数，写入 `artifacts/<skill>/llm_judgments.json`。

**路径 B：外部 judge 命令**

- 外部命令从 stdin 接收引擎构造的 user prompt，stdout 返回 `{"score": int, "reason": str}`，退出码 0 表示成功。
- 配置：环境变量 `export SKILLPRISM_LLM_JUDGE_COMMAND="python path/to/judge.py"`，或 `skill_rubric_types.yaml` 的 `llm_judge.command`。
- 启用：`evaluate-skill skills/<skill> --llm-judge --llm-judge-count 2`。
- 完整接口规范与 prompt 模板见 [`references/LLM_JUDGE.md`](references/LLM_JUDGE.md)。

**Agent prompts verification（D8 实测）**:

- 用户说"验证 prompt 效果"、"带不带 skill 差多少"时，按 [`references/PROMPTS_VERIFICATION.md`](references/PROMPTS_VERIFICATION.md) 执行：每条 prompt 起 with/without 两个独立子 agent 执行，第三个 judge 子 agent 打分。
- 结果写 `artifacts/<skill>/prompts_verification.json`；`evaluate-skill` 不传 `--prompts-verification` 时自动发现该文件。
- 能真实执行就必须 `full_test`；`dry_run` 占比 > 30% 引擎会报警。

---

### 2. Build a benchmark（引导流程）

> **前提**：`build-skill-test` **只把一条 benchmark 写进 `benchmarks/<skill>/registry.yaml`**。
> 它**不**创建目录、**不**写 task spec、**不**生成/复制数据（`--generate-expected` 仅对 csv 做简单拷贝）、**不**写 `metrics.py`、**不**写执行代码。
> 这些都要在调用前由 Agent 与用户一起准备好。因此"帮我建个 benchmark"不是一句话能完成的——Agent 按下面流程**逐步引导**用户。

下面是可以**照抄执行**的 runbook。每步给你三块：**Agent 说**（复制给用户的话术）、**收集/判断**（这一步在要什么、怎么分支）、**落地**（复制运行的命令或写入的文件）。
全程遵循 [`references/AGENT_GUIDE.md`](references/AGENT_GUIDE.md)：写文件前先展示并获确认，不编造不安全默认。

占位符：`<skill>` 技能名，`<task>` 任务 id，`<fmt>` 格式（`csv`/`h5ad`/`markdown`/`directory`），`<id>` benchmark id。所有相对路径都相对 `benchmarks/<skill>/`。

---

**Step 0 — 定界**

Agent 说：
> "我来为 `<skill>` 建 benchmark。先确认两件事：① skill 名是 `<skill>` 吗？② benchmark 目录用 `benchmarks/<skill>/` 可以吗？确认后我建目录骨架。"

落地（用户确认后）：
```bash
mkdir -p benchmarks/<skill>/{tasks,data,expected}
```

---

**Step 1 — Task spec**

Agent 说：
> "定义任务契约。请给我：任务描述一句话、输入格式（csv/h5ad/markdown/directory）、输出格式。输入占位符我叫 `{input}`、输出叫 `{output}`，可以吗？若输出是 h5ad，要比较的标签列名是什么（设 `label_column`）？若是 csv，有哪些必需列（设 `required_columns`）？我起草后给你看完整 YAML 再写入。"

落地（确认后写 `benchmarks/<skill>/tasks/<task>.yaml`）：
```yaml
id: <task>
skill: <skill>
name: <Human name>
description: <what this task verifies>
# 仅 h5ad 需要比较标签列时加：label_column: <col>
prompt: |
  ## 角色
  <role>
  ## 任务
  <one-line task>
  ## 输入
  - 文件路径：{input}
  - 格式：<fmt>
  ## 输出要求
  - 文件路径：{output}
  - 格式：<fmt>
input:
  format: <fmt>
  path: "{input}"
output:
  format: <fmt>
  path: "{output}"
```
> 占位符 `{input}`/`{output}` 的名字自由取，但必须和 `input.path`/`output.path` 一致；引擎会把它们解析成同名全局变量注入 `--code` 脚本。

---

**Step 2 — 数据**

Agent 说：
> "准备输入数据，放 `benchmarks/<skill>/data/<level>/`。数据来源三选一：A 你已有文件（给我路径）；B 用库内置数据集（如 `scanpy.datasets.pbmc3k_processed`）；C 我写脚本合成（用 `skillprism.testing.mock_data` 或 `scripts/generate_data.py`，固定 seed 可复现）。你选哪个？规模多大？我先做成 level 0（极小，冒烟）和 level 1（小，回归）两份，生成后给你看 shape/前几行再确认。"

落地分支：
- A：`cp <user-file> benchmarks/<skill>/data/level1/`
- B：在 registry 条目用 `dataset: {source: <builtin>, type: builtin}`（Step 6 处理），此处无需落文件。
- C：写并运行 `scripts/generate_data.py`，产物落到 `data/level0/`、`data/level1/`，固定 `random_state`。

---

**Step 3 — Expected（可选，先判断）**

Agent 说：
> "这条 benchmark 要不要和『金标准』对比？"
> - 不要（只检查输出自身是否合理）→ 跳过 expected，Step 4 选自洽性 metric。
> - 要（比对一致性）→ 金标准从哪来：A 你已有文件；B 我写参考实现生成。生成后放 `benchmarks/<skill>/expected/`，并和金标准的细胞/行顺序保持一致（按位置对齐比较）。"

落地（仅"要"时）：A `cp <gold> benchmarks/<skill>/expected/`；B 写参考实现生成到 `expected/<file>`。

---

**Step 4 — Metrics**

Agent 说：
> "选指标。先复用内置，不够再写私有。我列一下当前可用内置 metric，你挑；阈值我提议默认，你确认。"

落地（发现内置）：
```bash
python -c "from skillprism.benchmark.metrics import list_metrics; print(list_metrics())"
```

落地（需私有 metric 时写 `benchmarks/<skill>/metrics.py`，随 registry 自动加载；签名固定）：
```python
from skillprism.benchmark.metrics import metric

@metric("my_metric")                 # id 供 registry 引用
def my_metric(actual_path, expected_path, task_spec):
    # 返回一个单值。无需 expected 时忽略 expected_path；需要但缺失时返回 None（判失败）。
    ...
```
> metric 是**单值判断**：函数算一个数，registry 里用 `type/threshold` 判定。自洽性指标（无 expected）：`n_clusters`、`row_count`、`has_required_columns`；一致性指标（需 expected）：`ari`、`nmi`、`mean_rmse`、私有 `*_accuracy`。

---

**Step 5 — 执行方式**

Agent 说：
> "输出由谁产出？三选一：① `--code <path>`：引擎在沙箱里执行被测代码（最适合 CI/回归）；② agent 模式：配置 `SKILLPRISM_AGENT_COMMAND`，引擎调外部 agent；③ results 模式：只评估已存在的输出（Agent 已产出结果）。你选哪个？选①的话我现在起草 `sample_skill_code.py`。"

落地（选①时写 `sample_skill_code.py`，全局变量名 = Step 1 占位符）：
```python
# 全局变量 input / output 由引擎从 task spec 占位符注入
...  # 读 input，写 output
```

---

**Step 6 — 注册（此时才调 build-skill-test）**

Agent 说：
> "我把上面收集到的值注册进 `benchmarks/<skill>/registry.yaml`。拟用 id=`<id>`、level=`<0|1|2|3>`、suite 加 `smoke` 和 `gradual`。注册命令如下，确认后我执行，并给你看生成的条目。"

落地：
```bash
build-skill-test \
  --id <id> --name "<name>" \
  --skill <skill> --task <task> \
  --task-spec tasks/<task>.yaml \
  --level <0|1|2|3> \
  --input data/<level>/... \
  `# 仅 Step 3 要金标准时加：` [--expected-path expected/<file>] \
  --metric <id:type:args> [--metric ...] \
  --suite smoke --suite gradual \
  --registry benchmarks/<skill>/registry.yaml
```
> `--metric` 的 `type`：`min`/`max`/`range`/`exact`/`tolerance`。例：`row_count:min:8`、`ari:min:0.4`、`n_clusters:range:3:12`。

---

**Step 7 — 验证**

Agent 说：
> "先跑冒烟，再跑渐进。失败我带你回到对应步骤修。"

落地：
```bash
# 冒烟
test-skill --skill <skill> --registry benchmarks/<skill>/registry.yaml --suite smoke --code <path>
# 渐进（level 0 → 1）
test-skill --skill <skill> --registry benchmarks/<skill>/registry.yaml --suite gradual --code <path>
```

---

**一页信息收集表（Agent 开场可一次性贴出，逐项打勾）**

| 项 | 谁来填 | 示例 |
|---|---|---|
| skill 名 | 用户必填 | `<skill>` |
| task id | 用户必填 | `<task>` |
| 输入/输出格式 | 用户必填 | `h5ad` → `h5ad` |
| 输入数据来源 | 用户必填 | A 文件 / B builtin / C 合成 |
| 是否对比金标准 | 用户必填 | 是 / 否 |
| metrics 与阈值 | Agent 提议，用户确认 | `ari:min:0.4` |
| level / suite | Agent 提议，用户确认 | level0+1；smoke+gradual |
| 执行方式 | 用户必填 | `--code` / agent / results |

**用户必须提供的最少信息**（Agent 不得编造不安全默认）：skill 名、task id、输入/输出格式、输入数据、是否做金标准对比、执行方式。
**Agent 可提议但须确认的默认**：level 0/1 划分、suite 名（smoke/gradual/release）、`cache_dir`、默认阈值、占位符名（`{input}`/`{output}`）。

**参数对照（收集到的答案如何映射到 `build-skill-test`）**：

| User intent clue | Parameter | Purpose |
|---|---|---|
| （直接指定） | `--id` | Benchmark 唯一 id |
| （直接指定） | `--name` | 人类可读名称 |
| （直接指定） | `--skill` | 关联的 skill 名 |
| （直接指定） | `--task` | Task id |
| "task spec 在别处" | `--task-spec <path>` | task spec 路径（相对 registry 目录，默认 `tasks/<task>.yaml`） |
| "level N" | `--level N` | 难度等级 0–3 |
| （直接指定） | `--input <path>` | 输入数据路径（相对 registry 目录） |
| "有金标准" | `--expected-path <path>` | 金标准路径（相对 registry 目录） |
| "定义指标" | `--metric id:type:args` | 指标阈值（可重复；type ∈ min/max/range/exact/tolerance） |
| "加入 smoke/gradual suite" | `--suite <name>` | 加入 suite（可重复） |
| （直接指定） | `--registry <path>` | 注册表文件（必填；约定 `benchmarks/<skill>/registry.yaml`） |
| "自动生成金标准" | `--generate-expected` | 仅对 csv 做简单拷贝 |
| "需要 GPU" | `--gpu` | 标记需要 GPU |
| "真实数据" | `--real-data` | 真实数据，completion-only |

---

### 3. Test a skill

The primary purpose of `test-skill` is to verify that a **skill works as part of an Agent's capabilities**. The skill is the thing being tested; the Agent is the executor that selects and invokes it.

**Important**: By default `test-skill` runs in **results mode**. It does **not** execute any code and does **not** call an LLM. It only checks whether the expected output already exists and satisfies the metrics. Therefore, **you must produce the output before calling `test-skill`**, unless `--code` or an external agent command is configured.

**Default**（用户只说"跑一下"，验证已产出结果）：

```bash
test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml
```

**Execution mode selection**:

| Mode | Trigger | Who produces the result |
|---|---|---|
| **Results (default)** | No `SKILLPRISM_AGENT_COMMAND`, no `--code` | Current Agent / sub-agent 已产出 |
| **External agent** | `SKILLPRISM_AGENT_COMMAND` is set | External command invoked by the engine |
| **Code** | `--code <path>` | Engine executes the provided code |

Use `--results` to force results mode even when `SKILLPRISM_AGENT_COMMAND` is set.

#### Default workflow: Agent/sub-agent produces the result, engine evaluates (results mode)

```text
当前 Agent（已加载 skill-prism + target skills）：
  1. 读取 task spec: benchmarks/my-skill/tasks/csv_summary.yaml
  2. 拿到 input path、output path 和 task prompt
  3. （推荐）创建子 agent：只保留 skill 能力，不保留当前任务推理上下文
  4. 子 agent 看到 task prompt，识别并调用合适的 skill
  5. 子 agent 生成结果文件到 task-spec 指定的 output path
  6. 当前 Agent 运行：test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml
  7. skillPrism 评估结果并报告 PASS/FAIL
```

推荐原因：测试 Agent 能否正确选择并调用 skill；Agent 可在定稿前重试/迭代/排错；引擎保持确定性、不调 LLM。

#### Code workflow: `--code <path>`

```text
1-4 同上
5. 子 agent 生成可执行代码文件，例如 sample_skill_code.py
6. 当前 Agent 运行：test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml --code sample_skill_code.py
7. skillPrism 在沙箱中执行代码并评估产出，报告 PASS/FAIL
```

适用：任务更适合表达为代码；需要可复现的 CI 产物；想测 skill 的代码生成能力。
> **代码来源无关**：`--code` 接受任何可执行文件——Agent 生成、用户手写、纳入版本管理、外部生成器产出。引擎只检查文件存在并执行它。

#### External agent workflow

```bash
export SKILLPRISM_AGENT_COMMAND="python examples/editor_wrappers/agent_caller.py"
test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml
```

引擎构造 task prompt，通过 stdin 传给外部命令；外部命令读 `SKILLPRISM_INPUT_PATH`，写结果到 `SKILLPRISM_OUTPUT_PATH`；引擎评估。用 `--results` 可在已配置外部 agent 时仍只评估现有输出。

**参数与意图线索（整合表）**：

| User intent clue | Parameter | Purpose |
|---|---|---|
| （直接指定） | `--skill <name>` | Skill 名 |
| "跑某个 task" | `--task <id>` | Task id（用 `benchmarks/<skill>/tasks/<task>.yaml`） |
| "用代码跑"、"让 Agent 写代码" | `--code <path>` | 引擎执行该代码并评估产出 |
| "跑全部 benchmark" | `--registry <path>` | 注册表 YAML（约定 `benchmarks/<skill>/registry.yaml`） |
| "渐进"、"从简单到复杂" | `--mode single/gradual/quick` | 测试模式（默认 single） |
| "只跑 level N" | `--level N` | 仅跑该 level（single 模式） |
| "最高到 level N" | `--max-level N` | gradual 模式最高 level |
| "只跑 smoke"、"轻量验证" | `--suite <name>` | 仅跑该 suite |
| "强制只评估已有结果" | `--results` | results 模式；忽略 `SKILLPRISM_AGENT_COMMAND` |
| "产物目录" | `--output-dir <path>` | test artifacts 目录（默认 `ci-output/test`） |
| "写出完整结果" | `--output <path>` | single 模式写全量结果到文件 |
| "GPU" | `--gpu` / `--no-gpu` | 覆盖 GPU 可用性 |

**Common combinations**（本环节最常用场景）：

```bash
# 默认：results 模式，评估 Agent/子 Agent 已生成的结果（必须先有输出）
test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml

# 用代码跑全部 benchmark
test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml --code sample_skill_code.py

# 只跑 smoke suite
test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml --suite smoke --code sample_skill_code.py

# 渐进测试到 level 2
test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml --mode gradual --max-level 2 --code sample_skill_code.py

# 即使配置了外部 agent，也强制只评估现有输出
test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml --results
```

**Restrictions**:

- `--code` 表示引擎执行；显式 `--results` 与 `--code` 互斥（同时使用报错）。
- 显式 `--results` 忽略 `SKILLPRISM_AGENT_COMMAND`。
- results 模式下输出文件必须已存在，否则该 benchmark 立即失败。

**Metrics**:

- 公共 metric 用 `@metric("id")` 注册在 `skillprism/benchmark/metrics.py`；registry 同级 `metrics.py` 可加私有 metric。
- metric 与 expected 声明在 `benchmarks/<skill>/registry.yaml` 的 benchmark 条目里，**不在** task spec 里。

---

### 4. Improve a skill

**Default workflow**:

```bash
# Step 1: record baseline
improve-skill skills/my-skill --record-baseline

# Step 2: get optimization strategy
improve-skill skills/my-skill --suggest

# Step 3: edit SKILL.md (manual or auto), then judge + apply
improve-skill skills/my-skill --judge --apply
# or: improve-skill skills/my-skill --auto-edit --max-rounds 3 --apply
```

**参数与意图线索（整合表）**：

| User intent clue | Parameter | Purpose |
|---|---|---|
| "记录 baseline" | `--record-baseline` | 保存当前 scorecard/benchmark 为 baseline |
| "哪里最弱"、"给建议" | `--suggest` | 打印最弱维度与 P0–P3 策略 |
| "自动改"、"帮我改" | `--auto-edit` | 用配置的 editor 自动改 SKILL.md |
| "最多改 N 轮" | `--max-rounds N` | 自动编辑最大轮数 |
| "改完判断" | `--judge` | 对比 baseline 与当前，决定 keep/revert |
| "确认保留" | `--apply` | 真正执行决定（默认 dry-run） |
| "最低提升" | `--min-gain <float>` | 至少提升多少才保留 |
| "遇到回滚停止" | `--stop-on-regression` | 自动编辑若被回滚则停 |
| "带 benchmark" | `--benchmark-registry <path>` | 优化时跑 benchmark gate |
| "benchmark 产物目录" | `--benchmark-output-dir <path>` | benchmark artifacts 目录 |
| "用代码跑 benchmark" | `--code <path>` | benchmark gate 用这份代码 |
| "允许改代码" | `--edit-code` | 允许 editor 改代码资产 |
| "查看历史" | `--history` | 看优化历史 |
| "清掉 baseline" | `--clear-baseline` | 删除已存 baseline |
| "重写"、"瓶颈" | `--explore-rewrite` | 探索性重写 SKILL.md |
| "显示/隐藏 diff" | `--show-diff` / `--no-show-diff` | 输出中是否显示 diff |
| "换 editor/judge" | `--editor-command` / `--editor-model` / `--judge-model` | 覆盖 editor/judge |
| "LLM judge" / "第二意见" | `--llm-judge` | 优化时对主观维度启用 LLM judge |
| "换 judge 命令" | `--llm-judge-command` | 覆盖 LLM judge 命令 |
| "Agent 已生成 judgments" | `--llm-judgments <path>` | 消费 Agent 预生成的 judgments |

**Agent decision rule for LLM judge**: 与 `evaluate-skill` 相同——有外部 judge 命令用 `--llm-judge`，否则 Agent 生成 `artifacts/<skill>/llm_judgments.json`（引擎自动发现，也可显式 `--llm-judgments <file>`）。模板与接口见 [`references/LLM_JUDGE.md`](references/LLM_JUDGE.md)。

**What it does**:

- 在 `artifacts/<skill>/history.jsonl` 记录 baseline scorecard + benchmark 结果
- 给出 P0–P3 优化策略
- 编辑 SKILL.md / 代码（Agent 或外部 editor），每轮限一个维度
- 重新评估与测试
- 判断 keep / revert / human-decide
- 仅在显式 `--apply` 时落地
- 非 git 仓库自动 git-init；git 不可用则用文件备份回退

**Judge Logic for improve-skill**:

`--judge` 对比 **baseline** vs **current**：

| Condition | Decision |
|---|---|
| Score increased, benchmark passed, no guard failed | **keep** |
| Score decreased, or benchmark failed, or any guard failed | **revert** |
| Score unchanged but a key dimension improved | **human-decide** |
| Security score (D9) decreased | **revert** |

最终 apply 需要 `--apply` 或人工确认。

---

### 5. Run full pipeline

**Default**:

```bash
skill-pipeline --intent "run full quality pipeline" \
  --skills-dir ./skills \
  --benchmark-registry benchmarks/<skill>/registry.yaml \
  --output ./reports/SKILL_QUALITY_REPORT.md
```

**参数与意图线索（整合表）**：

| User intent clue | Parameter | Purpose |
|---|---|---|
| （必填） | `--intent <text>` | 自然语言意图 |
| "完整流水线"、"质量检查" | `--intent "run full quality pipeline"` | 评估 + 测试 + 优化全流程 |
| "给所有 skill 打分" | `--intent "evaluate all skills"` | 批量评估 |
| "找出最差的并优化" | `--intent "improve skills"` | 批量优化（配 `--apply --max-rounds`） |
| "渐进测试所有 skill" | `--intent "run gradual pipeline"` | 渐进测试 |
| "skill 目录" | `--skills-dir <path>` | Skills 根目录 |
| "带 benchmark" | `--benchmark-registry <path>` | benchmark 注册表 |
| "只跑某 suite" | `--benchmark-suite <name>` | 仅跑该 suite |
| "benchmark 产物目录" | `--benchmark-output-dir <path>` | benchmark 输出目录 |
| "baseline 目录" | `--benchmark-baseline-dir <path>` | baseline 目录 |
| "生成报告" | `--output <path>` | 合并报告输出（默认落 `./reports/`） |
| "跑 smoke" | `--run-smoke` | 跑冒烟测试 |
| "自动应用" | `--apply` | 自动应用优化决定 |
| "优化轮数" | `--max-rounds N` | 最大优化轮数 |
| "最高 level" | `--max-level N` | gradual 最高 level |
| "不推进 baseline" | `--no-ratchet` | 不 ratchet baseline |

**Common combinations**（本环节最常用场景）：

```bash
# 完整质量流水线
skill-pipeline --intent "run full quality pipeline" \
  --skills-dir ./skills \
  --benchmark-registry benchmarks/<skill>/registry.yaml \
  --output ./reports/SKILL_QUALITY_REPORT.md

# 批量评估
skill-pipeline --intent "evaluate all skills" --skills-dir ./skills

# 批量渐进测试到 level 2
skill-pipeline --intent "run gradual pipeline" \
  --skills-dir ./skills \
  --benchmark-registry benchmarks/<skill>/registry.yaml \
  --max-level 2
```

---

### 6. CI gate

**Default**（静态检查）：

```bash
skill-ci --skill my-skill
```

**参数与意图线索（整合表）**：

| User intent clue | Parameter | Purpose |
|---|---|---|
| （必填） | `--skill <name>` | Skill 名或路径 |
| "跑 benchmark" | `--run-benchmark` | 也跑动态 benchmark（需 `--code`） |
| "用代码跑" | `--code <path>` | 动态 benchmark 用代码 |
| "注册表" | `--registry <path>` | benchmark 注册表 YAML |
| "对比 baseline" | `--baseline <path>` | 回归对比的 baseline（`benchmarks/<skill>/baselines/<name>.yaml`） |
| "regress 不要挂" | `--no-stop-on-regression` | 不因 benchmark 回归而失败（默认：回归即失败） |
| "更新 baseline" | `--ratchet` | 通过则更新 baseline |
| "只跑某 suite" | `--suite <name>` | 仅跑该 suite |
| "只跑 level N" | `--level N` | 仅跑该 level |
| "产物目录" | `--output-dir <path>` | CI artifacts 目录（默认 `ci-output`） |
| "报告格式" | `--output-format <fmt>` | `yaml` / `json` / `markdown` |
| "指定 config" | `--config <path>` | skill_rubric_types.yaml 路径 |
| "跳过 smoke" | `--no-smoke` | 跳过冒烟测试 |
| "跳过依赖检查" | `--no-deps` | 跳过依赖检查 |
| "依赖 dry-run" | `--deps-dry-run` | pip/conda dry-run |

**Common combinations**（本环节最常用场景）：

```bash
# 默认静态 CI 门控
skill-ci --skill my-skill

# 含 benchmark 的完整 CI（回归即失败）
skill-ci --skill my-skill \
  --registry benchmarks/<skill>/registry.yaml \
  --run-benchmark --code sample_skill_code.py \
  --baseline benchmarks/<skill>/baselines/initial.yaml
```

---

## Standard Agent Workflow

```bash
# 1. Evaluate（含 LLM judge 看主观维度）
evaluate-skill skills/my-skill --detailed --llm-judge

# 2. Build a benchmark（按 §2 引导流程，准备好 task spec / 数据 / expected / metrics / 代码）
#    最终注册：
build-skill-test \
  --id csv_summary_sales \
  --skill my-skill \
  --task csv_summary \
  --input data/level1/input.csv \
  --expected-path expected/level1/expected.csv \
  --registry benchmarks/my-skill/registry.yaml

# 3. Test —— results 模式：评估 Agent/子 Agent 已生成的结果（必须先有输出）
test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml

# 4. Test —— 或用引擎执行 Agent/子 Agent 生成的代码
test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml --code sample_skill_code.py

# 5. Improve if needed
improve-skill skills/my-skill --record-baseline --suggest
# edit skills/my-skill/SKILL.md（先说明改动并获用户批准）
improve-skill skills/my-skill --judge --apply
```

---

## Code Generation Rule

**skillPrism never calls an LLM directly, unless configured to invoke an external agent command.**

- results 模式：Agent 或子 agent 产出结果，skillPrism 只评估。
- `SKILLPRISM_AGENT_COMMAND`：skillPrism 调用配置的外部命令；该命令内部可用 LLM，但引擎本身不调。
- `--code`：用户或 Agent 写代码，skillPrism 在沙箱中执行并评估产出。
- 引擎只测量结果，不是代码生成器，也不是 Agent。

---

## Output Artifacts

| Artifact | Default location | When produced |
|---|---|---|
| scorecard / report | `artifacts/<skill>/scorecard.md` | `evaluate-skill --output` |
| `test-prompts.json` | `artifacts/<skill>/`（默认） | `evaluate-skill` 自动生成（template 兜底）；Agent 按协议撰写 |
| baseline | `benchmarks/<skill>/baselines/<name>.yaml` | `improve-skill --record-baseline` / `--ratchet` |
| history | `artifacts/<skill>/history.jsonl` | 每次 evaluate/improve（`--output-history`） |
| LLM judgments | `artifacts/<skill>/llm_judgments.json` | Agent LLM judge（`--llm-judgments` 消费） |
| prompts verification | `artifacts/<skill>/prompts_verification.json` | Agent 按 PROMPTS_VERIFICATION 协议执行（自动发现或 `--prompts-verification` 消费） |
| test / CI artifacts | `artifacts/<skill>/ci/` | `test-skill` / `skill-ci --output-dir` |

---

## When NOT to Use skillPrism

- 只想跑任意 Python 代码，直接用 `python`。
- 想让引擎替你生成代码——skillPrism 不是这个工具；先用 Agent 或外部生成器产出，再来这里测。
- 需要不可测量的非确定性创意输出，skillPrism 没有价值。

---

## Common Agent Mistakes and Corrections

1. **混淆 `evaluate-skill` 与 `test-skill`**
   - `evaluate-skill` 测 **SKILL.md** 质量（静态 rubric）。
   - `test-skill` 测 skill **在数据上是否 work**（动态 benchmark）。
   - 用户问"能不能跑"用 `test-skill`；问"文档好不好"用 `evaluate-skill`。

2. **把 `--skill` 当 flag 传给 `evaluate-skill`**
   - `evaluate-skill` 用位置参数：`evaluate-skill skills/my-skill`。
   - `test-skill`、`skill-ci` 用 `--skill <name>`（还可能需要 `--task` / `--registry`）。

3. **没先产出结果就跑 `test-skill`**
   - `test-skill` 默认 results 模式，输出文件必须已存在。
   - 恢复：派子 agent 生成输出，或用 `--code <path>` 让引擎执行 skill 生成的代码。

4. **`improve-skill` 忘了 `--apply`**
   - `--judge`、`--auto-edit`、`--record-baseline` 默认 dry-run。
   - 展示计划改动并获用户明确批准后，才用 `--apply`。

5. **用过时命令名**
   - 正确：`evaluate-skill`、`test-skill`、`build-skill-test`、`improve-skill`、`skill-pipeline`、`skill-ci`。
   - **不要**用 `evaluate-skill-rubric`、`run-skill-benchmark`、`--verify-only`（已改名为 `--results`）；这些已废弃。

6. **把产物写进 skill 树或 skill-prism 文件夹**
   - 生成物按 skill 放 `artifacts/<skill>/`：scorecard 用 `--output`，test-prompts.json 默认已落此处（`--prompts-dir` 仅覆盖），artifacts 用 `--output-dir`；跨 skill 汇总放 `reports/`。
   - baseline 放 `benchmarks/<skill>/baselines/`。
   - **绝不**写进 `skills/skill-prism/`；目标 skill 源码树保持只读，除非明确在编辑其 SKILL.md 或代码资产。

7. **把"建 benchmark"当成一条命令**
   - `build-skill-test` 只写 registry 条目；目录、task spec、数据、expected、metrics、代码要先按 §2 引导流程准备好。

## References

- `references/AGENT_GUIDE.md`: Agent 调用 skillPrism 时的交互行为规范（必须加载）。
- `references/LLM_JUDGE.md`: LLM judge 的 prompt 模板、外部 judge 命令接口与配置。
- `references/PROMPTS_VERIFICATION.md`: test-prompts 撰写规范与 with/without 验证执行协议（D8 实测）。
