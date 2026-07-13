---
name: skill-prism
description: >-
  用自然语言评估、测试、优化 AI Agent skill（SKILL.md）的质量。当用户说"评估/打个分/
  体检一下这个 skill"、"哪里写得不好"、"建/跑 benchmark、出考题、测一下"、"优化/改进
  这个 skill"、"出质量报告"、"接入 CI 检查"时触发。能力覆盖：rubric 九维评分、LLM 评委、
  test-prompts 带/不带 skill 实测、benchmark 金标准对比判分、基线对比与自动回滚的改进闭环。
  Maps natural-language requests to evaluate-skill, test-skill, build-skill-test,
  improve-skill, skill-pipeline, skill-ci — use whenever the user wants to score,
  benchmark, or improve an agent skill.
tool_type: meta
keywords:
  - skillprism
  - evaluate
  - score
  - test
  - benchmark
  - improve
  - optimize
  - pipeline
  - quality
  - 评估
  - 打分
  - 考题
  - 优化
  - 质量报告
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

# skill-prism：统一 Agent 接口

## skillPrism 做什么

skillPrism 衡量一个 AI agent skill 的质量。一个 skill 由两部分组成：

1. **SKILL.md**：教会 Agent 如何做事的指令文档。
2. **生成的代码或直接结果**：Agent 读完 SKILL.md 后产出的可执行产物或输出。

skillPrism 回答三个问题：

| 问题 | 命令 | 衡量内容 |
|---|---|---|
| SKILL.md 写得好不好？ | `evaluate-skill` | 文档质量、可执行性、安全性等 |
| 这个 skill 真的能跑通吗？ | `test-skill` | 数据正确性、回归、鲁棒性 |
| 怎么让它变得更好？ | `improve-skill` | 修改 SKILL.md/代码并评判改动 |

## 核心原则

> **skillPrism 引擎永不调用 LLM。Agent 是执行者，也是 LLM 的调用方。**
>
> - 引擎提供确定性的度量。
> - Agent 负责生成代码、产出结果、派生子 agent、调用 LLM judge、按协议验证 prompts。
> - 双方通过结构化文件交换结果，供引擎消费。

---

## 产物位置规则

`<project-root>` 下可同时测多个 skill，生成物一律**按 skill 命名空间隔离**，绝不写进 skill 树。约定：`artifacts/<skill>/` 放该 skill 的全部生成物，`reports/` 放跨 skill 汇总。

| 产物 | 位置 | 何时产生 | 控制参数 |
|---|---|---|---|
| scorecard / report | `artifacts/<skill>/scorecard.md` | `evaluate-skill --output` | `--output` |
| test-prompts.json | `artifacts/<skill>/`（默认） | `evaluate-skill` 自动生成（template 兜底）；Agent 按协议撰写 | `--prompts-dir` 覆盖落点 |
| LLM judgments | `artifacts/<skill>/llm_judgments.json` | Agent LLM judge | `--llm-judgments`（不传自动发现） |
| prompts verification | `artifacts/<skill>/prompts_verification.json` | Agent 按 PROMPTS_VERIFICATION 协议执行 | `--prompts-verification`（不传自动发现） |
| optimization history | `artifacts/<skill>/history.jsonl` | **每次 evaluate/improve 自动写入** | 无需参数（`--output-history` 是另一个全局 JSONL） |
| benchmark 结果 | `artifacts/<skill>/results.yaml` | `test-skill --output` | `--output` |
| scorecard baseline | `artifacts/<skill>/baseline/` | `improve-skill --record-baseline` | `--record-baseline` / `--clear-baseline` |
| benchmark baseline | `benchmarks/<skill>/baselines/<name>.yaml` | `skill-ci --ratchet` 通过时更新 | `--baseline` / `--ratchet` |
| test / CI artifacts | `artifacts/<skill>/ci/` | `test-skill`（gradual）/ `skill-ci` | `--output-dir` |
| 跨 skill 汇总 | `reports/SKILL_SCORECARD.md` | `evaluate-skill --all --output` | `--output` |

**红线**：

- **绝不**把生成物写进 `skills/skill-prism/`（本 skill 自身文件夹）或目标 skill 源码树，除非本次明确在编辑该 SKILL.md 或其代码资产。
- 生成物默认落 `artifacts/<skill>/`；多 skill 时不要在 CWD 平铺 dot 文件，避免互相覆盖。

---

## 最常用调用方式

按生命周期排序。每行是该环节**最常用的参数组合**（覆盖最常见整体场景，不是裸默认）。一个环节可能有多行，对应不同的常用场景。裸默认见各 Core Intent 节的 **默认**。

| 环节 | 用户说法（常用场景） | 最常用命令 |
|---|---|---|
| Evaluate | "全面评估一下这个 skill：打分、评委复核、出题实测一次做完" | **综合评估流程**（§1）：备/写正式 test-prompts（展示确认）→ with/without 实测 → 生成 `artifacts/<skill>/llm_judgments.json` → `evaluate-skill skills/<skill> --detailed`（引擎自动消费两个产物） |
| Evaluate | "赶时间，快速打个分" | `evaluate-skill skills/<skill>` |
| Evaluate | "把 skills 下所有 skill 都评一遍，出一份汇总报告" | `evaluate-skill --all --skills-dir ./skills --output ./reports/SKILL_SCORECARD.md` |
| Build | "我想给这个 skill 建一套 benchmark，以后每次改动都能回归验证" | **进入 §2 引导流程**；最终落到 `build-skill-test --id <id> --skill <skill> --task <task> --input data/<level>/... --metric <id:type:args> --suite smoke --suite gradual --registry benchmarks/<skill>/registry.yaml` |
| Test | "结果文件已经生成好了，帮我测测达不达标" | `test-skill --skill <skill> --registry benchmarks/<skill>/registry.yaml` |
| Test | "我写好了执行代码，帮我把 benchmark 全部跑一遍" | `test-skill --skill <skill> --registry benchmarks/<skill>/registry.yaml --code <path>` |
| Test | "先跑个冒烟，快速确认基本能通" | `test-skill --skill <skill> --registry benchmarks/<skill>/registry.yaml --suite smoke --code <path>` |
| Improve | "帮我优化这个 skill：先记下现状，改完对比一下要不要保留" | `improve-skill skills/<skill> --record-baseline --suggest` → 编辑 → `improve-skill skills/<skill> --judge --apply` |
| Improve | "让它自己优化几轮，退步就停" | `improve-skill skills/<skill> --auto-edit --max-rounds 3 --apply` |
| Pipeline | "把评估、benchmark、优化整条流水线跑一遍" | `skill-pipeline --intent "run full quality pipeline" --skills-dir ./skills --benchmark-registry benchmarks/<skill>/registry.yaml --output ./reports/SKILL_QUALITY_REPORT.md` |
| CI | "在 CI 里加一道 skill 质量门禁" | `skill-ci --skill <skill>` |
| CI | "CI 里除了静态检查，把 benchmark 也一起跑了" | `skill-ci --skill <skill> --registry benchmarks/<skill>/registry.yaml --run-benchmark --code <path>` |

> 综合评估的两个产物（`llm_judgments.json`、`prompts_verification.json`）由 Agent 按协议生成到 `artifacts/<skill>/`，引擎自动发现消费，无需额外参数；已配置外部 judge 命令时，第 ③ 步改在最终评估命令上加 `--llm-judge`。详见 §1 综合评估流程与 LLM judge 决策规则。

---

## 核心意图

### 1. 评估 skill

**默认**（用户说"评估一下"、"打个分"、"体检"时）：按下方**综合评估流程**执行——机器评分 + LLM 评委 + test-prompts 实测一次做完。仅当用户明确说"快速"、"只打个分"、"不要实测/评委"时，退化为纯机器评分：

```bash
evaluate-skill skills/my-skill
```

**参数与意图线索（整合表）**：

| 用户意图线索 | 参数 | 用途 |
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
| "写 test prompts"、"生成测试 prompts" | （Agent 行为，非引擎参数） | 按 [`references/PROMPTS_VERIFICATION.md`](references/PROMPTS_VERIFICATION.md) Step 1 撰写 2–3 条具体 prompt → `artifacts/<skill>/test-prompts.json` |
| "对比 baseline"、"别 regress" | `--ratchet` | 分数退步即失败 |
| "输出报告"、"生成 scorecard" | `--output <path>` | 写 scorecard/report（单 skill 建议 `artifacts/<skill>/scorecard.md`；跨 skill 汇总用 `reports/`） |
| "追踪历史"、"趋势" | `--output-history <path>` | 追加到 JSONL 趋势文件（建议 `artifacts/<skill>/history.jsonl`） |
| "不要生成 test prompts" | `--no-generate-prompts` | 跳过 prompt 生成 |
| "prompts 放指定目录" | `--prompts-dir <path>` | test-prompts.json 读写目录（默认 `artifacts/<skill>/`；传 skill 目录才写进 skill 树） |
| "看进度" | `--verbose` / `-v` | 打印详细进度 |

**常用组合**（本环节最常用场景）：

```bash
# 快速模式：纯机器评分（默认的综合评估流程见下方"综合评估流程"）
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

**综合评估流程**（"评估一下"的默认动作，按序执行）：

1. **备 prompts**：检查 `artifacts/<skill>/test-prompts.json`；缺失或为占位模板（报告带 ⚠️ 警告）时，按 [`references/PROMPTS_VERIFICATION.md`](references/PROMPTS_VERIFICATION.md) Step 1 撰写 2–3 条正式 prompt，**展示给用户确认后**写入。
2. **实测**：按协议 Step 2–4 执行 with/without 验证（每条 prompt 两个独立执行子 agent + 一个 judge 子 agent，互不共享上下文），写 `artifacts/<skill>/prompts_verification.json`。能真实执行必须 `full_test`。
3. **评委**：按下方 LLM judge 决策规则准备 `artifacts/<skill>/llm_judgments.json`（默认 D2/D5，各 2 个独立 judge）；已配置外部 judge 命令时跳过本步，改在第 4 步加 `--llm-judge`。
4. **汇总**：`evaluate-skill skills/<skill> --detailed`——引擎自动发现并消费两个产物，输出三合一成绩单。
5. **解读**：向用户汇报总分/等级、主要扣分点、评委分歧、实测 pass_rate 与带/不带 skill 的差距。

成本：第 2–3 步需起多个子 agent 并调用大模型，耗时几分钟、消耗模型额度；用户赶时间时用"快速打个分"跳过 1–3 步。

**副作用**：

- 默认 `evaluate-skill` **不**修改 skill 源码树；产物落点统一见上方"产物位置规则"表。
- 自动生成的 template prompts 只是占位符（报告带 ⚠️ 标记）；正式 prompt 由 Agent 按 [`references/PROMPTS_VERIFICATION.md`](references/PROMPTS_VERIFICATION.md) 撰写。
- 用 `--no-generate-prompts` 完全跳过 prompt 生成（缺失时报告提示按协议创建）。

**LLM judge 的 Agent 决策规则**：

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

**Agent prompts 行为规则**：

- **撰写**：用户说"写 test prompts"、"生成测试 prompts"时，**或综合评估流程第 1 步发现 prompts 缺失/为占位模板时**，按 [`references/PROMPTS_VERIFICATION.md`](references/PROMPTS_VERIFICATION.md) Step 1 撰写 2–3 条**具体场景 + 行为可核对期望**的 prompt（是否澄清、是否按 SKILL.md 工作流、是否防护边界；**不校验数值结果**——结果正确性归 benchmark），写入 `artifacts/<skill>/test-prompts.json`。写前向用户展示并获确认。
- **看到占位符警告要主动提议**：评估报告带 ⚠️ "template prompts are placeholders" 时，说明当前 prompts 只是引擎兜底模板、无测试价值。Agent 应主动提议："当前 test-prompts 是占位模板，要我按协议撰写正式版吗？"
- **验证（D8 实测）**：用户说"验证 prompt 效果"、"带不带 skill 差多少"时，**或综合评估流程第 2 步**，按协议 Step 2–4 执行：每条 prompt 起 with/without 两个独立子 agent 执行，第三个 judge 子 agent 打分；trigger 类允许小样数据/方案+关键步骤的**轻量执行**，不要求跑完整重计算；judge 只评行为符合度，不评数值正确性。结果写 `artifacts/<skill>/prompts_verification.json`；`evaluate-skill` 不传 `--prompts-verification` 时自动发现该文件。
- 能真实执行就必须 `full_test`；`dry_run` 占比 > 30% 引擎会报警。

---

### 2. 构建 benchmark（引导流程）

> **前提**：`build-skill-test` **只把一条 benchmark 写进 `benchmarks/<skill>/registry.yaml`**。
> 它**不**创建目录、**不**写 task spec、**不**生成/复制数据（`--generate-expected` 仅对 csv 做简单拷贝）、**不**写 `metrics.py`、**不**写执行代码。
> 这些都要在调用前由 Agent 与用户一起准备好。因此"帮我建个 benchmark"不是一句话能完成的——Agent 按下面流程**逐步引导**用户。

完整 runbook 在 [`references/BUILD_BENCHMARK.md`](references/BUILD_BENCHMARK.md)：每步含 **Agent 说**（可复制给用户的话术）、**收集/判断**（要什么、怎么分支）、**落地**（命令或写入文件），必须照其执行。
全程遵循 [`references/AGENT_GUIDE.md`](references/AGENT_GUIDE.md)：写文件前先展示并获确认，不编造不安全默认。

占位符：`<skill>` 技能名，`<task>` 任务 id，`<fmt>` 格式（`csv`/`h5ad`/`markdown`/`directory`），`<id>` benchmark id。所有相对路径都相对 `benchmarks/<skill>/`。

---

**流程概览**：

| 步骤 | 做什么 | 关键产出 |
|---|---|---|
| 0 定界 | 确认 skill 名与 benchmark 目录 | `benchmarks/<skill>/` 目录骨架 |
| 1 Task spec | 定义任务契约（角色/输入/输出/占位符） | `tasks/<task>.yaml` |
| 2 数据 | 输入数据三选一：已有文件 / 内置数据集 / 脚本合成 | `data/<level>/` |
| 3 Expected | 判断是否对比金标准（可跳过） | `expected/<file>` |
| 4 Metrics | 先复用内置，不够写私有 `@metric` | （可选）`metrics.py` |
| 5 执行方式 | `--code` / agent 模式 / results 模式三选一 | （可选）`sample_skill_code.py` |
| 6 注册 | 此时才调 `build-skill-test` 写 registry 条目 | `registry.yaml` 条目 |
| 7 验证 | 先冒烟（smoke）再渐进（gradual），失败回对应步骤修 | PASS |

---

**用户必须提供的最少信息**（Agent 不得编造不安全默认）：skill 名、task id、输入/输出格式、输入数据、是否做金标准对比、执行方式。
**Agent 可提议但须确认的默认**：level 0/1 划分、suite 名（smoke/gradual/release）、`cache_dir`、默认阈值、占位符名（`{input}`/`{output}`）。
**`build-skill-test` 参数对照**见 [`references/BUILD_BENCHMARK.md`](references/BUILD_BENCHMARK.md) 末尾。

---

### 3. 测试 skill

`test-skill` 的核心目的是验证 **skill 作为 Agent 能力的一部分是否真正可用**。被测对象是 skill；Agent 是选择并调用它的执行者。

**重要**：`test-skill` 默认运行在 **results 模式**：**不**执行任何代码、**不**调用 LLM，只检查期望输出是否已存在且满足 metric。因此，**调用 `test-skill` 前必须先产出输出**，除非配置了 `--code` 或外部 agent 命令。

**默认**（用户只说"跑一下"，验证已产出结果）：

```bash
test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml
```

**执行模式选择**：

| 模式 | 触发条件 | 结果由谁产出 |
|---|---|---|
| **Results（默认）** | 无 `SKILLPRISM_AGENT_COMMAND`、无 `--code` | 当前 Agent / 子 agent 已产出 |
| **External agent** | 配置了 `SKILLPRISM_AGENT_COMMAND` | 引擎调用的外部命令 |
| **Code** | `--code <path>` | 引擎执行给定代码 |

即使配置了 `SKILLPRISM_AGENT_COMMAND`，也可用 `--results` 强制 results 模式。

#### 默认工作流：Agent/子 agent 产出结果，引擎评估（results 模式）

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

#### 代码工作流：`--code <path>`

```text
1-4 同上
5. 子 agent 生成可执行代码文件，例如 sample_skill_code.py
6. 当前 Agent 运行：test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml --code sample_skill_code.py
7. skillPrism 在沙箱中执行代码并评估产出，报告 PASS/FAIL
```

适用：任务更适合表达为代码；需要可复现的 CI 产物；想测 skill 的代码生成能力。
> **代码来源无关**：`--code` 接受任何可执行文件——Agent 生成、用户手写、纳入版本管理、外部生成器产出。引擎只检查文件存在并执行它。

#### 外部 agent 工作流

```bash
export SKILLPRISM_AGENT_COMMAND="python examples/editor_wrappers/agent_caller.py"
test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml
```

引擎构造 task prompt，通过 stdin 传给外部命令；外部命令读 `SKILLPRISM_INPUT_PATH`，写结果到 `SKILLPRISM_OUTPUT_PATH`；引擎评估。用 `--results` 可在已配置外部 agent 时仍只评估现有输出。

**参数与意图线索（整合表）**：

| 用户意图线索 | 参数 | 用途 |
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
| "产物目录" | `--output-dir <path>` | test artifacts 目录（默认 `artifacts/<skill>/ci/test`） |
| "写出完整结果" | `--output <path>` | single 模式写全量结果到文件 |
| "GPU" | `--gpu` / `--no-gpu` | 覆盖 GPU 可用性 |

**常用组合**（本环节最常用场景）：

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

**限制**：

- `--code` 表示引擎执行；显式 `--results` 与 `--code` 互斥（同时使用报错）。
- 显式 `--results` 忽略 `SKILLPRISM_AGENT_COMMAND`。
- results 模式下输出文件必须已存在，否则该 benchmark 立即失败。

**指标**：

- 公共 metric 用 `@metric("id")` 注册在 `skillprism/benchmark/metrics.py`；registry 同级 `metrics.py` 可加私有 metric。
- metric 与 expected 声明在 `benchmarks/<skill>/registry.yaml` 的 benchmark 条目里，**不在** task spec 里。

---

### 4. 优化 skill

**默认工作流**：

```bash
# 第 1 步：记录 baseline
improve-skill skills/my-skill --record-baseline

# 第 2 步：获取优化策略
improve-skill skills/my-skill --suggest

# 第 3 步：编辑 SKILL.md（人工或自动），然后判定 + 落地
improve-skill skills/my-skill --judge --apply
# 或：improve-skill skills/my-skill --auto-edit --max-rounds 3 --apply
```

**参数与意图线索（整合表）**：

| 用户意图线索 | 参数 | 用途 |
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

**LLM judge 的 Agent 决策规则**：与 `evaluate-skill` 相同——有外部 judge 命令用 `--llm-judge`，否则 Agent 生成 `artifacts/<skill>/llm_judgments.json`（引擎自动发现，也可显式 `--llm-judgments <file>`）。模板与接口见 [`references/LLM_JUDGE.md`](references/LLM_JUDGE.md)。

**功能说明**：

- 在 `artifacts/<skill>/history.jsonl` 记录 baseline scorecard + benchmark 结果
- 给出 P0–P3 优化策略
- 编辑 SKILL.md / 代码（Agent 或外部 editor），每轮限一个维度
- 重新评估与测试
- 判断 keep / revert / human-decide
- 仅在显式 `--apply` 时落地
- 非 git 仓库自动 git-init；git 不可用则用文件备份回退

**improve-skill 的判定逻辑**：

`--judge` 对比 **baseline** 与 **current**：

| 条件 | 决定 |
|---|---|
| 分数提高、benchmark 通过、无 guard 失败 | **keep** |
| 分数下降，或 benchmark 失败，或任一 guard 失败 | **revert** |
| 分数不变但关键维度有提升 | **human-decide**（交人工决定） |
| 安全分（D9）下降 | **revert** |

最终 apply 需要 `--apply` 或人工确认。

---

### 5. 运行完整流水线

**默认**：

```bash
skill-pipeline --intent "run full quality pipeline" \
  --skills-dir ./skills \
  --benchmark-registry benchmarks/<skill>/registry.yaml \
  --output ./reports/SKILL_QUALITY_REPORT.md
```

**参数与意图线索（整合表）**：

| 用户意图线索 | 参数 | 用途 |
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

**常用组合**（本环节最常用场景）：

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

### 6. CI 门禁

**默认**（静态检查）：

```bash
skill-ci --skill my-skill
```

**参数与意图线索（整合表）**：

| 用户意图线索 | 参数 | 用途 |
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
| "产物目录" | `--output-dir <path>` | CI artifacts 目录（默认 `artifacts/<skill>/ci`） |
| "报告格式" | `--output-format <fmt>` | `yaml` / `json` / `markdown` |
| "指定 config" | `--config <path>` | skill_rubric_types.yaml 路径 |
| "跳过 smoke" | `--no-smoke` | 跳过冒烟测试 |
| "跳过依赖检查" | `--no-deps` | 跳过依赖检查 |
| "依赖 dry-run" | `--deps-dry-run` | pip/conda dry-run |

**常用组合**（本环节最常用场景）：

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

## 什么时候不该用 skillPrism

- 只想跑任意 Python 代码，直接用 `python`。
- 想让引擎替你生成代码——skillPrism 不是这个工具；先用 Agent 或外部生成器产出，再来这里测。
- 需要不可测量的非确定性创意输出，skillPrism 没有价值。

---

## Agent 常见错误与纠正

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

## 参考文档

- `references/AGENT_GUIDE.md`: Agent 调用 skillPrism 时的交互行为规范（必须加载）。
- `references/BUILD_BENCHMARK.md`: 构建 benchmark 的逐步引导 runbook（每步话术、YAML/代码模板、参数对照）。
- `references/LLM_JUDGE.md`: LLM judge 的 prompt 模板、外部 judge 命令接口与配置。
- `references/PROMPTS_VERIFICATION.md`: test-prompts 撰写规范与 with/without 验证执行协议（D8 实测）。
