# 快速入门

> 本节带你用约 30 分钟理解 skillPrism 的四个核心命令：**评估（evaluate）**、**测试（test）**、**改进（improve）**、**流水线（pipeline）**，并完成 Agent 集成。
>
> 🌱 **完全新手、不想记命令行？** 先看 [新手操作手册](beginner-handbook.md)：用说话的方式驱动 skillPrism 走完全流程。

## 核心概念

skillPrism 回答三个问题：

| 问题 | 命令 | 说明 |
|---|---|---|
| SKILL.md 好不好？ | `evaluate-skill` | 9 维度规则评分 + 规则增强 + SkillLens + runtime 红灯扫描 + smoke + 依赖 + 安全 |
| 生成的代码跑不跑得通？ | `test-skill` | 单次 benchmark / 渐进分级测试 / 快速 gate |
| 怎么改更好？ | `improve-skill` | 记录 baseline → 查看 P0-P3 策略 → 单维度编辑 → judge → apply |

`skill-pipeline` 把上面三步串成一条完整工作流，`skill-ci` 用于 CI 门控。四个命令的对照表见 [文档首页](../index.md)。

## 对 Agent 说的话（按工作流递进）

如果你在用 Agent，只需要加载 `skills/skill-prism/SKILL.md`，然后按阶段说：

**第一步：先看文档质量**
- "这个 skill 的 SKILL.md 写得怎么样？"
- "给这个 skill 打个分，告诉我哪里扣分最多"

**第二步：再看代码能不能跑**
- "这个 skill 生成的代码能跑通吗？"
- "先用最小的数据快速验证一下"
- "从简单到复杂逐步测试这个 skill"

**第三步：定位并改进短板**
- "这个 skill 哪里最弱？给我优化建议"
- "按建议只改最弱维度，改完判断要不要保留"
- "如果改得不好就回滚"

**第四步：批量或完整流程**
- "跑完整质量流水线"
- "所有 skills 里最差的是哪个？帮我准备优化"
- "接入 CI，每次 PR 自动检查"

Agent 会翻译成对应命令。

## Skill 是什么

skillPrism 本身不调用 LLM，也不替你写 Skill。它测量的是**已经存在的 Skill** 或 **Agent 按 Skill 生成的结果**。因此你需要先让 Skill 可被 skillPrism 发现。

一个 Skill 通常是一个目录，至少包含：

```text
skills/my-skill/
├── SKILL.md              # 教 Agent/用户怎么用的说明书
└── examples/             # 可选：示例代码或最小可运行片段
    └── minimal_example.py
```

`SKILL.md` 采用 frontmatter + Markdown 格式：

````markdown
---
name: my-skill
description: 对 CSV 做统计摘要
tool_type: python
keywords: [csv, summary]
---

## 角色
数据分析助手

## 任务
读取 CSV，计算描述性统计，输出 CSV。

## 示例
```python
import pandas as pd
df = pd.read_csv(input_csv)
df.describe().to_csv(output_csv)
```
````

### Skill 放在哪里

skillPrism 默认从当前项目的 `skills/` 目录发现 Skill：

```text
skills/
+-- skill-prism/          # meta skill：教 Agent 如何使用 skillPrism
+-- my-skill/             # 你自己的 Skill
```

`test-skill --skill my-skill` 会根据这个名字去匹配 registry 里的 benchmark 条目，而不是直接读取 `skills/my-skill/SKILL.md`。SKILL.md 是给 Agent（或你自己）看的执行说明。

### 三种使用 Skill 的方式

| 方式 | 谁生成/执行结果 | skillPrism 做什么 | 典型命令 |
|---|---|---|---|
| **Results 模式（默认）** | Agent 或子 Agent 根据 task prompt 生成结果；skillPrism 只评估 | 生成 task prompt、校验输出、计算 metrics | `test-skill --skill my-skill --task csv_summary` |
| **外部 Agent 模式** | 配置的外部 agent 命令生成结果；skillPrism 调用并评估 | 调用 `SKILLPRISM_AGENT_COMMAND`、评估结果 | 配置后 `test-skill --skill my-skill --task csv_summary` |
| **Code 模式** | 你或 Agent 预先把 Skill 写成可执行代码；skillPrism 执行并评估 | 执行代码、评估结果 | `test-skill --skill my-skill --task csv_summary --code sample.py` |

### 没有 Skill 怎么办

如果你还没有 Skill，先创建一个：

```bash
mkdir -p skills/my-skill
cat > skills/my-skill/SKILL.md << 'EOF'
---
name: my-skill
description: 示例 Skill
tool_type: python
---

## 任务
把输入复制到输出。
EOF
```

然后参考[构建你的第一个 Benchmark](../tutorial/04-building-your-first-benchmark.md) 为它建立 benchmark。

## 加载 skill-prism meta skill

`skills/skill-prism/SKILL.md` 是 **meta skill**：它不是给 skillPrism 引擎读取的，而是给 **Agent 读取**的。它教会 Agent 如何把用户的自然语言意图转换成 skillPrism 的 CLI 命令。

`skills/skill-prism/references/AGENT_GUIDE.md` 是配套的 **Agent 交互行为规范**，约定 Agent 在调用 skillPrism 时应该如何开场、何时征求用户同意、如何展示 diff、如何报告结果等。建议把这两个文件一起加载给 Agent。

### 加载方式

取决于你使用的 Agent 框架：

| 场景 | 怎么做 |
|---|---|
| **Claude Code** | 复制到 `.claude/skills/skill-prism.md`，Claude 会自动加载（见下方） |
| **Kimi / 类似 LLM 客户端** | 把 `skills/skill-prism/SKILL.md` 的内容作为 system prompt 或上下文文件上传/粘贴给 Agent |
| **自定义 Agent** | 在 Agent 的 prompt 中拼接 `skills/skill-prism/SKILL.md` 的文本 |
| **MCP / Tool Server** | 把 SKILL.md 作为工具描述（tool description），让 LLM 决定何时调用 |
| **命令行手动使用** | 直接复制 SKILL.md 中的命令到终端执行，不需要"加载" |

#### 方式 A：Claude Code 自动加载（推荐）

Claude Code 支持从项目目录 `.claude/skills/` 自动读取 skill 文件。你可以把 meta skill 放到这里：

```bash
mkdir -p .claude/skills
cp skills/skill-prism/SKILL.md .claude/skills/skill-prism.md
```

也可以创建软链接，避免内容重复：

```bash
mkdir -p .claude/skills
ln -s ../../skills/skill-prism/SKILL.md .claude/skills/skill-prism.md
```

放好后，在 Claude Code 中直接说：

```text
测一下 my-skill 的 csv_summary benchmark
```

Claude 会自动引用 `.claude/skills/skill-prism.md` 中的指令，调用对应的 skillPrism 命令。

**优点**：
- 不需要每次手动粘贴 SKILL.md
- 项目级 skill，任何进入该目录的 Claude 会话都能用
- 与 `skills/` 目录共存，不破坏 skillPrism 自身的目录约定

**注意事项**：
- 文件必须放在 `.claude/skills/` 下且以 `.md` 结尾；Claude Code 才会自动识别。
- **复制整个 `skill-prism/` 目录到 `.claude/skills/skill-prism/`**（`SKILL.md` + `references/`；references 是 LLM judge 与 prompts 验证的协议文档，SKILL.md 会引用）。引擎生成物（test-prompts.json、history.jsonl 等）默认写入项目根的 `artifacts/<skill>/`，不在 skill 树中。
- 如果 skill 文件很大，会占用一部分上下文窗口。skill-prism SKILL.md 约 540 行，通常可接受。
- 同样地，具体业务 Skill 也可以放到 `.claude/skills/`，例如 `.claude/skills/my-skill.md`；但业务 Skill 的工作目录仍建议保留在 `skills/my-skill/`，供 `evaluate-skill` 评估、`improve-skill` 读写 baseline（历史等生成物在项目根的 `artifacts/<skill>/`）。

**两个目录的职责区分**：

| 目录 | 给谁用 | 放什么 |
|---|---|---|
| `.claude/skills/` | Claude Code Agent | 让 Agent 读懂指令的 `.md` skill 文件 |
| `skills/<skill>/` | skillPrism 引擎 | SKILL.md + 代码资产（scripts/、examples/ 等）；引擎生成物（test-prompts.json、baseline、history 等）一律写入项目根的 `artifacts/<skill>/`，不写 skill 树 |

#### 方式 B：手动/system prompt 加载

把 meta skill 喂给 Agent 后，Agent 就学会了下面这套"意图 → 命令"映射。

## Agent 能理解的意图

| 用户说的话 | Agent 会做的事 |
|---|---|
| "评估这个 skill" | `evaluate-skill skills/my-skill` |
| "测一下 my-skill 的 csv_summary 任务" | `test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml --task csv_summary` |
| "用这份代码跑 benchmark" | `test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml --task csv_summary --code sample.py` |
| "让外部 agent 跑 benchmark" | 配置 `SKILLPRISM_AGENT_COMMAND` 后运行 `test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml --task csv_summary` |
| "帮我给 my-skill 建一个 benchmark" | 生成 task spec + 数据 + 调用 `build-skill-test` |
| "改进这个 skill" | `improve-skill skills/my-skill --record-baseline --suggest` |
| "跑完整 pipeline" | `skill-pipeline --intent "run full quality pipeline" --skills-dir ./skills` |

## 完整交互示例

**步骤 1：把 meta skill 加入 Agent 上下文**

```text
[system]
你是一个 skillPrism 助手。请严格按照以下 SKILL.md 的内容，把用户的自然语言请求转换成 skillPrism CLI 命令。
同时遵守 AGENT_GUIDE.md 中的交互规范：开场说明计划、编辑前征求同意、展示 diff、失败时给出修复建议。

--- 以下是 skills/skill-prism/references/AGENT_GUIDE.md 全文 ---
（粘贴 AGENT_GUIDE.md 内容）

--- 以下是 skills/skill-prism/SKILL.md 全文 ---
（粘贴 SKILL.md 内容）
```

**步骤 2：用户用自然语言提出请求**

```text
[user]
帮我为 my-skill 建一个 CSV 摘要的 benchmark，输入是 benchmarks/my-skill/data/sales.csv。
```

**步骤 3：Agent 按 SKILL.md 执行**

Agent 会：
1. 读取 `skills/my-skill/SKILL.md` 判断能力
2. 设计 task spec：`benchmarks/my-skill/tasks/csv_summary.yaml`
3. 生成金标准（如用 pandas.describe）
4. 调用 `build-skill-test`：

```bash
build-skill-test \
  --id csv_summary_sales \
  --name "CSV Summary: Sales" \
  --skill my-skill \
  --task csv_summary \
  --task-spec tasks/csv_summary.yaml \
  --input data/sales.csv \
  --expected-path expected/sales_summary.csv \
  --metric row_count:min:8 \
  --registry benchmarks/my-skill/registry.yaml
```

**步骤 4：Agent 报告结果**

```text
已注册 benchmark `csv_summary_sales`。
你可以说：
- "测一下 my-skill" → 运行 `test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml --task csv_summary`
- "渐进测试" → 运行 `test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml --mode gradual`
```

### 关键点

- **skillPrism 引擎不读 SKILL.md**，它只执行命令。
- **Agent 读 SKILL.md**：`skill-prism` 这个 skill 让 Agent 知道有哪些命令、每个命令解决什么问题。
- **Agent 同时应读 AGENT_GUIDE.md**，以遵循审批检查点、diff 展示、失败恢复等交互规范。
- 如果你想让 Agent 既懂 skillPrism 又懂具体业务 Skill，需要同时把 `skills/skill-prism/SKILL.md`、`skills/skill-prism/references/AGENT_GUIDE.md` 和 `skills/my-skill/SKILL.md` 放入 Agent 上下文。

## 手册目录与重要原则

- 完整手册目录（手把手教程、各命令手册、深度参考）见 [文档首页](../index.md)。
- 核心原则（Agent 是 LLM 调用方、引擎确定性、人在回路、失败优先）见 [文档首页](../index.md) 的"核心原则"一节。
