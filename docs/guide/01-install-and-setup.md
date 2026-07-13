# 安装与初始设置

> 本篇带你完成一次性准备工作：装好 skillPrism、把 meta skill 交给 Agent、弄清项目里每个目录的用途、知道配置文件在哪。
> 整个过程约 10 分钟，之后日常使用只需要和 Agent 说话。

本篇按顺序讲四件事：

1. **安装四步**——pip 安装、可选依赖、把 meta skill 交给 Agent、验证；
2. **项目目录结构**——`skills/`、`benchmarks/`、`reports/`、`artifacts/` 各放什么；
3. **使用方式**——为什么你全程只需要和 Agent 说话；
4. **配置**——`skill_rubric_types.yaml` 和常用环境变量。

## 安装：四步搞定

### 第 1 步：安装 skillPrism 本体

环境要求：Python ≥ 3.9，建议在干净的 virtualenv 或 conda 环境中安装，避免污染系统 Python：

```bash
python -m venv .venv
source .venv/bin/activate    # Windows 用 .venv\Scripts\activate
```

在仓库根目录执行安装：

```bash
pip install -e .
```

安装完成后，你得到 `skillprism` Python 包和 7 个命令行工具：

| 命令 | 干什么 |
|---|---|
| `evaluate-skill` | 给 SKILL.md 打分 |
| `test-skill` | 跑 benchmark 考试 |
| `build-skill-test` | 注册新考题 |
| `improve-skill` | 改进说明书并记录基线 |
| `skill-pipeline` | 把评估→考试→改进串成完整流水线 |
| `skill-ci` | CI 质量门禁 |
| `skill-gradual` | 由易到难的分级测试 |

验证本体是否装好：

```bash
evaluate-skill --help
```

看到帮助信息即成功。各命令的完整参数见 [CLI 参考](../reference/cli.md)，日常使用中你不需要亲自敲它们（见下文「你只需和 Agent 说话」）。

!!! note "要参与 skillPrism 本身的开发？"
    改用 `pip install -e ".[dev]"`，会额外安装 pytest、ruff、mkdocs 等开发工具。普通使用者不需要。

### 第 2 步：按需安装可选依赖

本体只依赖 PyYAML，非常轻。以下场景需要额外组件：

| extra | 包含 | 什么时候需要 |
|---|---|---|
| `[benchmark]` | pandas、numpy、scipy | 要跑数据分析类 benchmark（如聚类、统计摘要） |
| `[all]` | 以上全部 + 机器学习指标、安全扫描、开发工具 | 不确定先装哪个时就装它 |

```bash
# 跑数据分析类 benchmark
pip install -e ".[benchmark]"

# 全部可选组件
pip install -e ".[all]"
```

暂时用不上可以跳过，以后随时补装；缺依赖时命令会明确提示该装哪个 extra。

### 第 3 步：把 meta skill 交给 Agent

`skills/skill-prism/` 是一个特殊的 skill（meta skill）：它不是给引擎读的，而是**给 Agent 读的说明书**，教 Agent 把你的自然语言请求翻译成 skillPrism 命令。把它放到你的 Agent 能读到的地方：

| 你用的 Agent | 怎么做 |
|---|---|
| **Claude Code** | 复制整个目录到 `.claude/skills/skill-prism/`，之后每个会话自动加载 |
| **Kimi 等 LLM 客户端** | 把 `skills/skill-prism/SKILL.md` 的内容作为 system prompt 或上下文文件粘贴给 Agent |
| **自定义 Agent** | 在 Agent 的 prompt 中拼接 `SKILL.md` 的文本 |
| **MCP / Tool Server** | 把 `SKILL.md` 作为工具描述（tool description）注册，让 LLM 决定何时调用 |
| **不用 Agent、纯命令行** | 不需要加载任何文件，直接照着 [CLI 参考](../reference/cli.md) 敲命令即可 |

Claude Code 的具体操作：

```bash
mkdir -p .claude/skills
cp -r skills/skill-prism .claude/skills/skill-prism
```

也可以用软链接，避免两处内容不同步：

```bash
mkdir -p .claude/skills
ln -s ../../skills/skill-prism .claude/skills/skill-prism
```

!!! note "复制整个目录，不只是一个文件"
    `skill-prism/` 里除了 `SKILL.md` 还有 `references/`（Agent 交互规范、LLM 评委协议等），`SKILL.md` 会引用它们。只复制单个文件会丢掉这些配套文档。

!!! tip "两个目录各司其职"
    `.claude/skills/` 是给 Agent 看的入口；`skills/<skill>/` 是你维护的技能资产，供评估和改进使用。业务 skill 也可以复制一份到 `.claude/skills/` 让 Agent 直接调用，但它的工作目录仍保留在 `skills/<skill>/`。

加载完成后，Agent 就掌握了"你说什么 → 调哪个命令"的映射。例如你说"评估这个 skill"，它会去运行 `evaluate-skill`；你说"跑完整流水线"，它会去运行 `skill-pipeline`。SKILL.md 约 540 行，会占用少量上下文窗口，通常可以接受。

### 第 4 步：验证安装

不用敲命令——直接对 Agent 说一句：

> "帮我检查一下 skillPrism 装好了没有，给 skills 里的技能打个分试试。"

Agent 会自己运行评估并把结果讲给你听。能看到总分、等级和每个维度的得分，说明安装、meta skill、Agent 调用全链路都通了。

如果报错，直接把报错信息贴给 Agent，让它按提示处理——最常见的原因是缺可选依赖，回到第 2 步补装对应的 extra 即可。

不想通过 Agent，也可以手动验证（任意一个已存在的技能目录都行）：

```bash
evaluate-skill skills/my-skill --no-generate-prompts
```

!!! tip "配置就这些"
    没有账号、没有密钥、没有服务器。skillPrism 完全在你的电脑上运行，不会把数据发到任何地方。只有你主动配置 LLM 评委或外部 Agent（见下文「配置」）时，才会产生外部调用。

## 项目目录结构

用 skillPrism 管理技能，你的项目目录大致长这样：

```text
你的项目/
├── skills/                       # 技能资产：每个技能一个文件夹
│   ├── skill-prism/              # meta skill（给 Agent 的"翻译官"）
│   └── my-skill/
│       └── SKILL.md              # 技能说明书（被打分、被改进的就是它）
├── benchmarks/                   # 考题库：每个技能一套考题
│   └── my-skill/
│       ├── registry.yaml         # 考题登记表（考什么、怎么判分）
│       ├── tasks/                # 任务定义（每个任务一个 yaml）
│       ├── data/                 # 考题用的输入数据
│       └── expected/             # 标准答案
├── reports/                      # 报告输出（scorecard、质量报告）
└── artifacts/                    # 生成物：评估/考试/改进的过程记录
    └── my-skill/
        ├── test-prompts.json           # 测试 prompts
        ├── llm_judgments.json          # LLM 评委打分结果
        ├── prompts_verification.json   # prompts 验证结果
        ├── history.jsonl               # 评分历史（每次评估追加一行）
        └── baseline/                   # 改进基线快照
```

记住三个要点就够了：

- **`skills/` 是你的资产**——精心维护的说明书和代码，评估和改进的对象。
- **`benchmarks/` 是考试区**——题目、数据、标准答案、判分规则都在这里，与说明书分开管理。
- **`reports/` 和 `artifacts/` 是输出区**——所有自动生成的报告和历史记录都往这里放。

`benchmarks/<skill>/` 下四个部分的分工：

| 部分 | 作用 |
|---|---|
| `registry.yaml` | 考题登记表：有哪些考题、关联哪个任务、用什么指标判分 |
| `tasks/` | 任务定义：每个任务一个 yaml，描述要 Agent 做什么 |
| `data/` | 考题用的输入数据（真实数据或固定随机种子生成的模拟数据） |
| `expected/` | 标准答案：判卷的对照基准，质量直接决定考试的意义 |

`artifacts/<skill>/` 下各文件的来历：

| 文件 | 什么时候产生 |
|---|---|
| `test-prompts.json` | 评估时检查；缺失会自动生成占位模板，正式版由 Agent 撰写 |
| `llm_judgments.json` | 你或 Agent 启用 LLM 评委复核后写入 |
| `prompts_verification.json` | Agent 完成 prompts 验证后写入 |
| `history.jsonl` | 每次评估自动追加一条成绩记录 |
| `baseline/` | 开始一轮改进前记录的基线快照 |

!!! warning "生成物一律不写进 skill 树"
    上述所有引擎生成物默认写入项目根的 `artifacts/<skill>/`，**永远不会**出现在 `skills/<skill>/` 里。这样 `skills/` 目录可以随时整体打包、分享或提交，不夹带任何过程文件。

## 还没有技能？

skillPrism 评估的是**已经存在**的技能。如果你手上还没有任何技能，先创建一个最小的练手：

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

然后就可以对它打分了（[下一篇](./02-evaluate.md)）。一个真实可用的技能通常还会带 `examples/`（示例代码）、`scripts/`（脚本）等资产，评分时会鼓励这些；但打分这一步，有 `SKILL.md` 就能开始。仓库的 `templates/` 目录里有更完整的技能模板（`templates/skill_standard/`），写正式技能时可以直接参考。

## 你只需和 Agent 说话

这是使用 skillPrism 唯一需要记住的原则：**你全程用自然语言和 Agent 对话，命令行由 Agent 在背后调用**。skillPrism 引擎负责测量——打分、判卷、对比、回滚，全部是确定的、可重复的机械工作，它自己不调用 LLM，也不会猜你的意图。动脑的部分——读懂你的话、编辑说明书、回答主观问题——由 Agent 完成，而且改任何文件之前都会先向你说明计划、征得同意。所以本文档里出现的命令只是让你知道背后发生了什么；不方便用 Agent 时，你也可以直接照敲。

## 配置

### skill_rubric_types.yaml

项目根目录的 `skill_rubric_types.yaml` 是评分配置文件，定义了：

- 九个维度的权重和等级阈值（A/B/C/D 的分数线）
- skill 类型注册表：不同类型技能的 frontmatter 要求与检查项
- LLM 评委、外部编辑器等可选组件的参数（评委数量、聚合方式、混合权重等）

日常用默认值即可；想调权重、改等级线或接入外部命令时再动它，例如：

```yaml
# skill_rubric_types.yaml（节选）
llm_judge:
  enabled: false        # 是否默认启用 LLM 评委
  n_judges: 2           # 独立评委数量
  aggregate: median     # 多评委聚合方式
  weight: 0.3           # 评委分与机器分混合时的权重
```

完整字段说明见 [配置参考](../reference/config.md)。

### 常用环境变量

| 变量 | 一句话作用 |
|---|---|
| `SKILLPRISM_EDITOR_COMMAND` | `improve-skill` 改写说明书时调用的外部编辑器命令 |
| `SKILLPRISM_LLM_JUDGE_COMMAND` | `--llm-judge` 时调用的外部评委命令 |
| `SKILLPRISM_AGENT_COMMAND` | benchmark 执行时调用的外部 Agent 命令 |
| `SKILLPRISM_AGENT_PASS_THROUGH_ENV` | 允许透传给外部 Agent 的环境变量名列表（逗号分隔的凭据白名单） |

用法示例：

```bash
export SKILLPRISM_LLM_JUDGE_COMMAND="python examples/editor_wrappers/openai_compatible_judge.py"
export SKILLPRISM_AGENT_COMMAND="python examples/editor_wrappers/agent_caller.py"
# 外部 Agent 需要 API key 时，显式放行变量名（默认不透传任何额外环境变量）
export SKILLPRISM_AGENT_PASS_THROUGH_ENV="OPENAI_API_KEY,OPENAI_BASE_URL"
```

四个变量都可以不配：不配时，评估、考试、改进闭环全部照常工作；LLM 相关的增强（评委复核、自动改写）由你的 Agent 用自己的模型代劳。

!!! note "为什么默认不透传环境变量"
    调用外部 Agent 命令时，引擎只提供最小环境（PATH、HOME 等），不会把整个 shell 环境——包括你的密钥——塞给子进程。需要凭据时，用 `SKILLPRISM_AGENT_PASS_THROUGH_ENV` 显式点名放行。

## 下一步

- 装好就来打第一个分：[给技能打分](./02-evaluate.md)
- 想看完整流程实例：[CSV 摘要技能全流程](../cases/csv-summary-full-cycle.md)
- 命令与参数速查：[CLI 参考](../reference/cli.md)
- 遇到问题：[常见问题](../reference/faq.md)
