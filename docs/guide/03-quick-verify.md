# 随堂抽查：test-prompts 效果验证

> 这一篇回答：不建 benchmark、不准备金标准，怎么快速知道一个 skill「实际用起来有没有用」？

## 这是什么：给 skill 做「随堂抽查」

test-prompts 效果抽查是**综合评估的第三块**（默认的「全面评估」已经包含它，见 [给技能打分](./02-evaluate.md)；这一篇把机制讲透，也方便你单独补做）：你（通过 Agent）写 2–3 条有代表性的真实使用 prompt，让 Agent 分别带着 skill 和不带 skill 各跑一遍，再让第三个独立 Agent 当裁判对比打分。整个机制**零基建**——不需要 registry、不需要 task spec、不需要金标准文件，产物只有两个放在 `artifacts/<skill>/` 下的 JSON。

它和日常打分回答的是两个不同的问题：

- **打分（Rubric 九维度）看说明书**：SKILL.md 写得清不清楚、结构完不完整、有没有安全隐患——评的是文档本身。
- **抽查看真实使用中的行为**：一个真实用户丢过来一句人话，带着这个 skill 的 Agent 是不是比不带时做得更好——会不会主动澄清、会不会优雅报错、产出是不是真符合期望。

一句话：打分告诉你「教练手册写得好不好」，抽查告诉你「学员照着手册上场，打得过没手册的对手吗」。

综合评估里这一步会自动发生；以下时机值得**单独再补做一轮**：

- **skill 刚写好**：先拿抽查信号，再决定要不要投入建 benchmark；
- **改了 SKILL.md 之后**：复跑一轮，对比前后 pass_rate 看改动是否真的改善了使用行为；
- **评估分数和使用体感对不上时**：Rubric 分高但用户说不好用（或反之），抽查是最快的仲裁手段。

!!! note "缺了验证文件也能评分"
    没有验证文件时（比如只跑了快速模式），`evaluate-skill` 照常评估，D6/D8 不加不减，报告里只是没有验证摘要。抽查是加分信号，不是准入门槛。

## 完整走一遍：csv-summary-skill 抽查全流程

下面用 `skills/csv-summary-skill` 贯穿五个步骤。每一步都按「你要做什么 → 对 Agent 怎么说 → 得到什么 → 注意什么」展开。先给个总览：

| 步骤 | 谁做 | 产物 |
|---|---|---|
| 1. 写三条 test-prompts | 你下指令，Agent 撰写 | `artifacts/csv-summary-skill/test-prompts.json` |
| 2. with / without 各跑一遍 | Agent 起两个独立子 Agent 执行 | 每条 prompt 两份输出记录 |
| 3. 裁判对比打分 | Agent 起第三个独立子 Agent 做 judge | 每条的 `improvement_score` 和 `passed` |
| 4. 写验证文件 | Agent 汇总 | `artifacts/csv-summary-skill/prompts_verification.json` |
| 5. 评估自动消费 | 引擎 | 报告附验证摘要，D6/D8 按 pass_rate ±1 |

你真正要动手的只有第 1 步的「下指令」和第 5 步的「跑评估」，中间三步都是 Agent 按协议自动完成。

### 第 1 步：写三条 test-prompts

**你要做什么**：给 skill 写三条代表性 prompt，覆盖 trigger（真实需求语言，看是否触发并按工作流执行）、ambiguous（故意含糊，看澄清行为）、boundary（边界/失败场景，看风险防护）三种场景，存到 `artifacts/csv-summary-skill/test-prompts.json`。

**对 Agent 说**：

> "给 csv-summary-skill 写三条 test-prompts：trigger、ambiguous、boundary 各一条。每条要有具体场景和**行为可核对**的期望——是否澄清、是否按 SKILL.md 工作流走、是否防护边界；不要写数值结果校验（那是 benchmark 的事），也不要写 'Use this skill to ...' 这种话。"

**得到什么**：

```json
// artifacts/csv-summary-skill/test-prompts.json
[
  {
    "id": 1,
    "scenario": "trigger",
    "prompt": "帮我把这个季度的销售数据捋一捋，看看哪些品类在拖后腿。",
    "expected": "按 SKILL.md 的工作流组织分析（先描述性统计，再品类对比）；主动询问数据位置；可用小样演示关键步骤；不编造数据结论。"
  },
  {
    "id": 2,
    "scenario": "ambiguous",
    "prompt": "帮我看看 data/sales.csv。",
    "expected": "主动澄清「看看」指什么（统计摘要 / 异常检查 / 可视化建议），不擅自假设直接开跑。"
  },
  {
    "id": 3,
    "scenario": "boundary",
    "prompt": "对一个空 CSV 文件（只有表头、没有数据行）做统计摘要。",
    "expected": "不崩溃；明确指出数据为空，给出可读的报错信息或一份标注为空数据的摘要。"
  }
]
```

**注意**：

- 文件默认位置是 `artifacts/<skill>/test-prompts.json`（项目根目录下，skill 源树保持只读），可用 `--prompts-dir` 覆盖。
- 如果这个文件不存在，`evaluate-skill` 会**自动生成 3 条占位模板**（trigger / ambiguous / boundary）并在报告里给出 ⚠️ 占位符警告。占位模板只是兜底，看到警告就必须让 Agent 按上面的标准重写正式版（原因见下文「prompt 写法红线」）。
- 不想让引擎自动生成占位模板，加 `--no-generate-prompts`。

### 第 2 步：with / without 两个独立子 Agent 各跑一遍

**你要做什么**：让 Agent 对每条 prompt 各起**两个独立子 Agent** 执行：一个环境里 skill 在可发现路径下（with-skill），一个把 skill 临时移出可发现路径（without-skill），两边执行同一条 prompt，各自记录执行过程和输出。

**对 Agent 说**：

> "按验证协议跑一遍 test-prompts：每条 prompt 用带 skill 和不带 skill 两个独立子 Agent 各执行一次，两边不要共享上下文，把执行过程和输出都记下来。trigger 那条用轻量执行——小样数据、方案加关键步骤即可，不要跑完整重计算。"

**得到什么**：每条 prompt 两份执行记录。两边都真实启动并执行了关键步骤（trigger 类允许小样数据/方案级演示，不要求产出最终结果文件），`eval_mode` 记 `full_test`；实在无法真实执行（缺依赖、缺环境），允许降级为 `dry_run`（凭推测填写），但这是降级，不是常态。

**注意**：

- 验证的是**行为**不是**结果**：记录里要能看出 Agent 的做事方式（澄清没有、按什么流程、怎么防护），不需要校验产出数值——数值正确性是 benchmark 的事。
- 两个子 Agent 必须相互独立、不得共享推理上下文，否则「不带 skill」那一边会沾染「带 skill」的思路，对比失效。
- without-skill 的构造方式：把 skill 临时移出可发现路径（如 `.claude/skills/csv-summary-skill/`），或换一个不含该 skill 的干净目录执行；跑完记得移回去。
- 全程**不得修改被测 skill**；中间文件只写 `artifacts/csv-summary-skill/`。

### 第 3 步：第三个子 Agent 当裁判

**你要做什么**：再起**第三个独立子 Agent** 做 judge，把同一条 prompt 的 expected、without 输出、with 输出一起交给它，让它对比打分。

**Agent 用的裁判提示词**（协议原文，照用即可）：

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

**得到什么**：每条 prompt 一个 `improvement_score`（0.0–1.0）和一个 `passed`（true/false）。`improvement_score` 衡量 skill 的**边际贡献**——with 比 without 好多少；`passed` 只看 with-skill 的**行为**是否满足 expected。

### 第 4 步：得到 prompts_verification.json

**你要做什么**：什么都不用做——Agent 会把上面三步的结果汇总写入 `artifacts/csv-summary-skill/prompts_verification.json`。

**得到什么**：

```json
// artifacts/csv-summary-skill/prompts_verification.json
{
  "skill": "csv-summary-skill",
  "results": [
    {
      "prompt_id": 1,
      "prompt": "帮我把这个季度的销售数据捋一捋，看看哪些品类在拖后腿。",
      "expected": "按 SKILL.md 的工作流组织分析（先描述性统计，再品类对比）；主动询问数据位置；可用小样演示关键步骤；不编造数据结论。",
      "without_skill_output": "直接对小样跑了 pandas describe()，没有品类对比，也没有按任何工作流组织。",
      "with_skill_output": "先询问数据位置，用小样演示：按 SKILL.md 工作流先出描述性统计，再按品类分组对比，指出拖后腿品类。",
      "improvement_score": 1.0,
      "passed": true,
      "eval_mode": "full_test"
    },
    {
      "prompt_id": 2,
      "prompt": "帮我看看 data/sales.csv。",
      "expected": "主动澄清「看看」指什么（统计摘要 / 异常检查 / 可视化建议），不擅自假设直接开跑。",
      "without_skill_output": "直接跑了 describe()。",
      "with_skill_output": "先反问用户想做统计摘要还是异常检查。",
      "improvement_score": 1.0,
      "passed": true,
      "eval_mode": "full_test"
    },
    {
      "prompt_id": 3,
      "prompt": "对一个空 CSV 文件（只有表头、没有数据行）做统计摘要。",
      "expected": "不崩溃；明确指出数据为空，给出可读的报错信息或一份标注为空数据的摘要。",
      "without_skill_output": "pandas 抛 EmptyDataError，堆栈直接抛给用户。",
      "with_skill_output": "捕获空数据，输出『文件无数据行，无法生成摘要』。",
      "improvement_score": 1.0,
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

字段含义：

| 字段 | 说明 |
|---|---|
| `improvement_score` | 0.0–1.0，judge 给出的边际贡献分 |
| `passed` | with-skill 输出是否满足 expected |
| `eval_mode` | `full_test`（真实执行）/ `dry_run`（未执行、凭推测填写） |
| `summary.pass_rate` | 通过比例（`passed / total`），D6/D8 加减分就看它 |
| `summary.dry_run_ratio` | `dry_run` 结果占比；> 30% 时 `dry_run_warning` 为 `true` |

### 第 5 步：下一次 evaluate-skill 自动生效

**你要做什么**：像平常一样跑评估，不需要任何新参数。

```bash
evaluate-skill skills/csv-summary-skill --detailed
```

引擎自动发现 `artifacts/csv-summary-skill/prompts_verification.json`（也可显式指定 `--prompts-verification <path>`），在报告里附上验证摘要表，并据此调整 D6/D8：

| pass_rate | D6 / D8 调整 |
|---|---|
| ≥ 90% | 各 **+1**（上限 5） |
| 50% – 90% | 不加不减 |
| < 50% | 各 **-1**（下限 1） |

**得到什么**：报告末尾多出一段验证摘要：

```text
### Test-Prompts Verification
| Prompt | Passed | Improvement | Mode |
|---|---|---|---|
| 1 | PASS | 1.00 | full_test |
| 2 | PASS | 1.00 | full_test |
| 3 | PASS | 1.00 | full_test |

**Pass rate**: 100%
**Dry-run ratio**: 0%
```

**注意**：如果 `dry_run_ratio > 30%`，报告会告警 `⚠️ Warning: dry-run ratio > 30%; measured performance score may be unreliable.`——大部分 prompt 只是「纸上谈兵」，此时的 D8 加减分不可信，应该想办法提高 `full_test` 比例。

## 四个最容易搞混的问题

这四个问题是抽查机制被误解的重灾区，逐一说清。

### 在哪个环节用？

**评估环节（`evaluate-skill`），不是 `test-skill`，也不是 benchmark。** 抽查的产物是评估报告的加分证据，不是测试门禁。

引擎在这个机制里的角色很克制：检查 `test-prompts.json` 是否存在、数量是否足够，以及消费 `prompts_verification.json` 做加减分——**引擎从不执行 prompt**。执行 prompt、起子 Agent、当裁判，全是 Agent 按协议做的事。

### 需要先建 benchmark 吗？

**完全不需要。** 抽查与 benchmark 体系零依赖：不读 `benchmarks/<skill>/registry.yaml`，不需要 task spec，不需要金标准数据，不需要 metric 定义。两个 JSON 文件就是全部基建。

定位上它是 benchmark 的**轻量替代 / 前置探针**：先用零基建抽查拿到「这个 skill 到底有没有用」的信号；信号好、skill 值得长期投入，再为它建正式 benchmark 考题。顺序不要反——给一个没有抽查信号的 skill 先建全套 benchmark，大概率是浪费。

### 为什么必须 with / without 两边都跑？

**因为抽查测的是 skill 的边际贡献，不是模型的裸能力。** 底层模型本身可能本来就会做 CSV 摘要——如果只看 with-skill 一边跑得好，你无法区分这是 skill 的功劳还是模型的基线水平。without-skill 基线就是用来扣除模型裸能力的：judge 对比两边，只有「带了 skill 明显更好」才算数。

两条硬规则：

- 两个子 Agent **不得共享上下文**，否则 without 那一边会被污染；
- 无法真实执行时可以降级为 `dry_run`，但占比 **> 30% 引擎告警「分数不可信」**——能跑就必须 `full_test`。

### 需要准备测试数据吗？

**不需要正式的数据体系**（没有 dataset 注册、没有数据版本管理）。三条 prompt 的数据问题有三条出路，按省事程度排：

1. **让 Agent 随手造小样数据**。test-prompts 没有金标准对比，数据只要「有」不要「准」——trigger 那条用轻量执行，两个子 Agent 各自造一份几行的小样、演示关键步骤就够，不用跑完整分析。
2. **设计天然不需要数据的 prompt**。ambiguous 那条故意不给文件（「帮我看看 data/sales.csv」重在澄清行为，文件在不在都行）；boundary 那条用一个空文件，随手 `touch` 就有。
3. **dry_run 降级**。实在跑不了（缺重型依赖、要 GPU），允许凭推测填写，记住 30% 告警线即可。

四个问题一张表收个尾：

| 问题 | 答案 |
|---|---|
| 在哪个环节用？ | `evaluate-skill`（评估），引擎只检查存在性、消费验证文件，从不执行 prompt |
| 需要 benchmark 吗？ | 完全不需要，与 benchmark 体系零依赖；是 benchmark 的轻量前置 |
| 必须 with / without 吗？ | 必须，这是核心设计：测 skill 的边际贡献；两子 Agent 不得共享上下文 |
| 需要测试数据吗？ | 不需要正式数据体系：Agent 造小样 / 设计无数据 prompt / dry_run 降级 |

## 和 benchmark level 0 smoke 的分工

两者都是「便宜的快速检查」，但检查的完全不是一个东西：

| 维度 | test-prompts 抽查 | benchmark level 0 smoke |
|---|---|---|
| 所属环节 | `evaluate-skill`（评估） | `test-skill`（测试） |
| 回答的问题 | 这个 skill 实际用起来**有没有用**、行为得不得体 | 产出**符不符合客观期望**、会不会一跑就崩 |
| 对照基准 | without-skill 基线 + LLM 裁判 | 金标准 + metric 阈值 |
| 基建成本 | 零：两个 JSON 文件 | registry + task spec + 数据 + metric 定义 |
| 谁执行 | Agent 的两个独立子 Agent | 引擎执行 `--code`，或直接消费已产出的结果 |
| 谁判分 | 第三个子 Agent（LLM 裁判） | 引擎确定性 metric |
| 能考察什么 | **过程行为**：会不会澄清、会不会优雅报错、有没有擅自假设 | **最终产物**：数值对不对、结构符不符合、文件存不存在 |
| 结果去向 | D6/D8 ±1，评估报告附摘要 | CI 门禁 / 回归基线 |

打个比方：**smoke 是开机自检**——灯亮不亮、数值对不对，全是客观指标；**test-prompts 是试驾员评价**——开起来顺不顺、遇到沟坎（含糊需求、空文件）会不会好好处理，评的是行为质量。一辆车既要过自检，也要经得起试驾。

推荐的使用顺序：

1. **先零基建抽查**：skill 刚写好就做一次全面评估（含抽查），拿到「有没有用」的信号；
2. **值得投入再建 benchmark**：抽查信号好、skill 要长期维护，再建正式考题（见 [构建 benchmark 案例](../cases/bio-benchmark-walkthrough.md)）；
3. **成熟后各管一段**：smoke 管数值——进 CI，每次必过；抽查管行为——定期复核，尤其是改了 SKILL.md 之后。

## prompt 写法红线

抽查质量七分靠 prompt 写法。红线有三条：

**红线一：期望必须是「行为可核对」的。** expected 写的是裁判能从执行过程记录逐条核对的行为清单（是否澄清、按没按 SKILL.md 工作流、有没有防护边界），而不是「正确完成任务」这种没法判的话。

**红线二：禁止数值结果校验。** 「输出文件存在」「cluster 数在 5–15 之间」这类写法会把抽查变成 benchmark——逼两个子 Agent 跑完整重计算，耗时且越权。结果正确性（数值、结构、文件内容）一律交给 benchmark 的金标准 + metric；抽查只看做事方式。

**红线三：禁止 "Use the X skill to ..." 元指令。** prompt 要模拟真实用户说话——真实用户不知道 skill 的存在，只会描述自己的需求。元指令写法等于开卷考试，测不出 skill 被自然触发时的表现。

| ❌ 错误写法 | ✅ 正确写法 |
|---|---|
| "Use the csv-summary-skill to summarize a CSV file." | "帮我把这个季度的销售数据捋一捋，看看哪些品类在拖后腿。" |
| "Use this skill with an ambiguous input." | "帮我看看 data/sales.csv。" |
| expected: "out/summary.csv 存在，包含 mean/min/max" | expected: "按 SKILL.md 工作流组织（先描述统计再品类对比）；主动询问数据位置；不编造结论" |
| expected: "The skill should work correctly." | expected: "不崩溃；识别输入为空，给出明确报错或回退" |

!!! warning "占位符警告不是装饰品"
    引擎自动生成的占位模板恰恰就是元指令形式（形如 `"Use the csv-summary-skill skill to ... under normal conditions."`），并附带警告：
    `⚠️ Auto-generated template prompts are placeholders only. Have the agent author real prompts per references/PROMPTS_VERIFICATION.md.`
    看到这条警告，就让 Agent 按上面的红线重写正式版——拿占位模板跑抽查，等于用开卷考题测闭卷能力，结果没有意义。

协议的完整细节（三个独立子 Agent 的约束、judge 提示词原文、所有规则）以 `skills/skill-prism/references/PROMPTS_VERIFICATION.md` 为权威；两个交换文件的完整 schema 见 [交换文件参考](../reference/exchange-files.md)。

## 下一步

- 抽查发现 skill 没用？先改进 SKILL.md，再复跑抽查对比前后信号——见 [改进与迭代闭环](./08-production-loop.md)。
- 想给 skill 建正式考题：见 [bio benchmark 全流程案例](../cases/bio-benchmark-walkthrough.md)。
- 想看一个 skill 从创建、抽查到建 benchmark 的完整生命周期：见 [csv-summary 全周期案例](../cases/csv-summary-full-cycle.md)。
- 评估维度 D6/D8 的定义与权重：见 [Rubric 参考](../reference/rubric.md) 与 [指标参考](../reference/metrics.md)。
