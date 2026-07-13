# 给技能打分（评估）

> 先分清两件事：**打分**（评估，`evaluate-skill`）看的是 `SKILL.md` 这份说明书本身——就像评一份菜谱写得清不清楚；**考试**（benchmark，`test-skill`）看的是照着做出来的结果——就像尝炒出来的菜。菜谱写得漂亮不等于菜好吃，所以两件事都要做，而且标准顺序是**先打分、后建考题**：打分不需要准备任何数据，先把说明书上的明显问题修干净，再投入精力去设计考题。本篇只讲打分；建考题见 [构建考题](./04-build-benchmark.md)，考试见 [运行考试](./05-run-benchmark.md)。

| | 打分（本篇） | 考试（后续章节） |
|---|---|---|
| 看什么 | 说明书本身的质量 | 照做之后产出的结果 |
| 需要什么 | 只要 `skills/<skill>/` 目录 | 考题、数据、标准答案 |
| 多久出结果 | 几分钟（快速模式几秒） | 取决于考题规模 |
| 能单独做吗 | 随时能，零准备 | 需要先建好考题 |
| 命令 | `evaluate-skill` | `test-skill` |

## 对 Agent 怎么说

你只管提需求，Agent 会把它翻译成 `evaluate-skill` 调用：

| 你说 | Agent 做 |
|---|---|
| "全面评估一下 my-skill。" | 综合评估：机器评分 + AI 评委复核 + test-prompts 出题实测，一份三合一成绩单（默认方式） |
| "赶时间，快速打个分。" | 只做机器九维评分，几秒出结果 |
| "这个 skill 哪里扣分最多？" | 评分 + 按扣分排序的短板清单 |
| "检查一下这份说明书有没有措辞模糊或安全隐患。" | 规则增强检查 + 安全扫描 |
| "把所有技能都评一遍，出个总报告。" | 批量评估 + 生成 scorecard |

默认的**综合评估**是一串编排好的动作，Agent 按序完成：

1. **备题**：检查 `artifacts/<skill>/test-prompts.json`——缺失或只是占位模板时，Agent 按真实使用场景撰写 2–3 条正式 prompt，**先拿给你看、你确认后**才写入；
2. **实测**：每条 prompt 由"带 skill"和"不带 skill"两个独立子 Agent 各做一遍，第三个子 Agent 当裁判对比打分，产出 `prompts_verification.json`（机制详见 [随堂抽查](./03-quick-verify.md)）；
3. **评委**：Agent 对 D2/D5 等主观维度各请两位独立评委打分，产出 `llm_judgments.json`；
4. **汇总**：引擎运行 `evaluate-skill skills/my-skill --detailed`，自动发现并消费上面两个文件，合成一份成绩单。

整个过程不改你的 `skills/` 目录，写入的东西都在 `artifacts/<skill>/` 下。因为要做实测和评委复核，一次综合评估大约几分钟、消耗一些大模型额度。赶时间就说"快速打个分"——只跑机器检查：

```bash
evaluate-skill skills/my-skill
```

快速模式下如果 `test-prompts.json` 还不存在，引擎会自动生成占位模板并在报告里给出 ⚠️ 警告——占位模板没有测试价值，下次综合评估时 Agent 会撰写正式版。

## 九个维度，各管一摊

skillPrism 从九个角度给说明书打分，每个角度有固定权重（越重要占比越高）：

| 维度 | 白话解释 | 权重 |
|---|---|---|
| D1 结构规范 | 文件齐不齐、格式对不对、元数据写没写 | 10% |
| D2 讲得清不清楚 | 说明书写得明不明白，有没有例子、有没有常见错误提示 | 15% |
| D3 能不能执行 | 给的代码示例语法对不对、能不能跑 | 18% |
| D4 环境可复现 | 依赖写清楚没有，换台机器还能不能装出来 | 12% |
| D5 领域准确性 | 专业内容靠不靠谱，概念用对没有 | 15% |
| D6 AI 可调用性 | AI 容不容易读懂并照做，有没有模棱两可的话 | 10% |
| D7 性能与稳健 | 有没有考虑超时、大数据量、异常情况 | 8% |
| D8 可维护性 | 结构清不清晰，以后好不好改 | 4% |
| D9 安全可信 | 有没有危险操作（删库、强推）且不加警告 | 8% |

每个维度打 1–5 分，按权重加权后换算成 100 分制，再折算成等级。每个维度的具体检查项见 [Rubric 参考](../reference/rubric.md)。

成绩单顶部会显示引擎识别出的 **Skill 类型**（来自 frontmatter 的 `tool_type` 等字段）。类型决定了部分检查项的适用规则，如果识别得不对，先在 `SKILL.md` 的 frontmatter 里把 `tool_type` 写准确。

!!! tip "权重可以调，但先别急着调"
    九个权重定义在项目根的 `skill_rubric_types.yaml` 里，可以按你的业务偏好修改（例如安全敏感的场景调高 D9）。但默认权重已经过校准，建议先用默认权重跑一段时间，确有必要再改——改了权重，历史分数就不可直接对比了。

## 看懂成绩单

一次默认评估给你四样东西：

- **总分**：九个维度按权重加权的百分制分数；
- **等级**：A（≥90）/ B（≥75）/ C（≥60）/ D（<60）；
- **每维得分**：1–5 分，一眼看出哪项强、哪项弱；
- **扣分点**：每个扣分项的具体原因和证据，附改进建议。

输出大致长这样：

```markdown
## my-skill

- **路径**: `skills/my-skill`
- **Skill 类型**: `python`
- **Rubric 总分**: 78.3 / 100
- **等级**: B

| 维度 | 名称 | 得分 | 证据 | 优化建议 |
|---|---|---|---|---|
| D1 | 目录与元数据规范 | 5/5 | frontmatter 完整 | - |
| D3 | 可执行性/正确性 | 3/5 | 示例缺少 import | 补充完整可运行示例 |
| D4 | 环境/依赖可复现 | 2/5 | 未找到 requirements.txt | 添加依赖声明 |
```

!!! note "默认评估还做了什么"
    除了九维评分，一次默认运行还包括：规则增强检查（模糊词、AI 腔废话、失败模式编码、检查点标记、体积膨胀）、SkillLens 检查、runtime 红灯扫描、安全扫描、`test-prompts.json` 存在性检查（缺失时生成占位模板并警告），最后把本次成绩写入 `artifacts/<skill>/history.jsonl`。

    因此成绩单里除了维度表，还可能看到这些区块：**安全发现**（危险操作清单）、**SkillLens 报告**、**runtime 红灯**、**规则增强检查**、**LLM Judge Contributions**（启用评委时）。它们都以证据列表的形式呈现，按严重程度处理即可。

**看扣分点比看总分更重要。** 扣分都在"缺文件、缺示例"这类地方，补起来很快；扣分落在"领域准确性"上，才需要认真对待。

分数低也不等于技能差。机器检查看的是"表面规范"：一份内容很好但格式不规范的说明书也会得低分，而一份堆满关键词的空洞说明书可能得高分。所以解读成绩单的正确姿势是——**先看扣分点分布，再看总分**：

- 扣分集中在 D1/D3/D4（缺文件、示例跑不通、缺依赖声明）：格式问题，补起来快，补完分数立竿见影；
- 扣分集中在 D2/D5（讲不清楚、专业内容存疑）：实质问题，需要认真改，建议配合 [AI 评委](#ai)或人工复核确认。

!!! warning "分数可以骗，能力骗不了"
    默认评分是静态启发式：数标题、查关键词、验语法、扫危险操作。它快、免费、结果可复现，但只看"表面功夫"——一份说明书可以靠堆关键词拿到高分。所以关键技能要结合 [AI 评委](#ai)或人工复核；并且分数高不等于技能好用，最终要靠 benchmark 考试验证实际效果（见 [生产闭环](./08-production-loop.md)）。

## 诊断短板

光知道分数低不够，要知道**为什么**低。这时用详细模式：

> 你说："这个技能哪里最弱？把扣分细节展开给我看。"

背后对应：

```bash
evaluate-skill skills/my-skill --detailed
```

你得到一张按维度展开的问题清单：哪一行措辞模糊、哪个示例有语法错误、缺哪个文件，每条都带证据和改进建议。输出大致长这样：

```markdown
### 详细说明

**D4 环境/依赖可复现** — 得分 2/5
- 证据：
  - 未找到 requirements.txt 或 environment.yml
  - SKILL.md 提到 scanpy 但未声明版本
- 建议：
  - 添加 requirements.txt 并锁定关键依赖版本
```

需要注意：**不是每个扣分点都值得修**——比如"性能稳健性"对一个一次性脚本可能无所谓。诊断完之后，对 Agent 说"按这份清单给我优化建议"，就自然进入改进环节（见后续章节）。

还有两个按需开启的深度检查（默认关闭，因为更慢、且要求依赖可安装）：

```bash
# smoke test：真的把示例跑一遍，看能不能执行
# 依赖检查：真的装一遍依赖，看环境能不能复现
evaluate-skill skills/my-skill --detailed --run-smoke --run-deps
```

说明书里带可执行示例、或准备发布关键技能时，值得加跑一次。

## 评估会动哪些文件

综合评估只往 `artifacts/<skill>/` 下写东西，绝不碰你的 `skills/` 目录：

| 文件 | 行为 |
|---|---|
| `artifacts/<skill>/test-prompts.json` | 缺失或为占位模板时，由 Agent 撰写正式版（写前经你确认） |
| `artifacts/<skill>/prompts_verification.json` | 实测产物：每条 prompt 的 with/without 输出与裁判打分 |
| `artifacts/<skill>/llm_judgments.json` | 评委产物：主观维度的评委打分与理由 |
| `artifacts/<skill>/history.jsonl` | 每次评估追加一条成绩记录，用于画质量曲线 |

快速模式（裸 `evaluate-skill`）下如果 `test-prompts.json` 缺失，引擎会自动生成 3 条占位模板并给出 ⚠️ 警告——占位模板没有测试价值，下次综合评估时 Agent 会替换为正式版。想完全禁止自动生成，加 `--no-generate-prompts`。

## AI 评委

**作用**：D2（讲得清不清楚）、D5（领域准确性）这类主观维度，机器规则只能粗判。AI 评委请大模型当第二位评委：默认 2 个独立评委各自打 1–5 分，按 median 聚合后与机器分混合（评委分权重默认 0.3）。除 D2/D5 外，D6、D8 也可以接受评委意见。

**综合评估默认就包含评委**，走 Agent 路径：Agent 自己调用模型生成 `artifacts/<skill>/llm_judgments.json`，引擎自动发现并消费，无需任何配置。快速模式（裸 `evaluate-skill`）不含评委；想单独补做，就说"请评委复核一下主观维度"。

也可以改用外部命令做评委（比如想用固定模型保证可复现性）：

```bash
export SKILLPRISM_LLM_JUDGE_COMMAND="python examples/editor_wrappers/openai_compatible_judge.py"
evaluate-skill skills/my-skill --llm-judge
```

没配置就直接传 `--llm-judge` 时，引擎会给出警告并退回纯机器评分，不会报错中断。

**成本提示**：每次复核都会调用外部大模型，按 token 计费；评委越多越贵（`--llm-judge-count` 可增减，默认 2 个通常足够；聚合方式 `--llm-judge-aggregate` 默认 median，对个别评委的极端打分不敏感）。

想要更多评委提高稳定性时：

```bash
evaluate-skill skills/my-skill --llm-judge --llm-judge-count 3 --llm-judge-aggregate median
```

> 你说："发布前请 LLM 评委复核一下可读性和领域准确性。"

评委生效后，成绩单里会多出一段评委贡献：

```markdown
### LLM Judge Contributions
- **D2**: scores=[4, 5], aggregate=median → 4/5
- **D5**: scores=[3, 4], aggregate=median → 3/5
```

机器分和评委分歧较大时（比如机器给 5 分、评委给 2 分），以评委意见为线索人工复核——这正是开评委的价值所在。

!!! note "可复现性"
    评委结果会记录所用模型、温度、prompt 版本等元数据（见 `llm_judgments.json`）。同一份说明书、同一套配置，复核结果应该大致稳定；如果两次复核波动很大，先检查评委模型或 prompt 是否变过，再怀疑说明书本身。

judgments 文件的 schema、聚合口径与引擎侧契约细节见 [交换文件参考](../reference/exchange-files.md)。

## 批量打分与报告

技能多了，一次评全部。`--all` 需要和 `--skills-dir` 搭配，告诉引擎去哪里发现技能：

> 你说："给所有技能做个体检，按分数排个名。"

背后对应：

```bash
evaluate-skill --all --skills-dir ./skills --output reports/SKILL_SCORECARD.md
```

你得到 `reports/SKILL_SCORECARD.md`——所有技能按九维得分和总分列出的总表：

```markdown
| Skill | Type | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 | D9 | Score | Grade |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| csv-summary | python | 5 | 4 | 4 | 4 | 4 | 4 | 3 | 4 | 5 | 82.6 | B |
| cell-annotation | python | 4 | 3 | 3 | 2 | 4 | 3 | 3 | 3 | 4 | 63.1 | C |
```

两点需要知道：

- `--all` 会**自动跳过 `skill-prism` 自身**——它是给 Agent 的 meta skill，不是被测对象；
- 每个技能的成绩同时记入各自的 `artifacts/<skill>/history.jsonl`，定期跑一次就能看到每个技能的质量曲线。

只想给单个技能留一份详细存档时，用 `--output` 指定文件：

```bash
evaluate-skill skills/my-skill --detailed --output artifacts/my-skill/scorecard.md
```

!!! tip "批量报告是最便宜的质量看板"
    定期跑批量评估、把 scorecard 提交到仓库，团队协作中谁的质量在退步一目了然。它是纯 Markdown 表格，可以直接 git diff 对比两次体检的变化。想进一步做成每次提交自动检查的门禁，见 [生产闭环](./08-production-loop.md)。

## 常见追问

**评估会改我的 SKILL.md 吗？**
不会。评估是只读操作，只在 `artifacts/<skill>/` 下写历史记录和占位 prompts。改说明书是改进环节的事，而且每次改动前 Agent 都会先征求你同意。

**一定要配置大模型（LLM）吗？**
不用额外配置。通过 Agent 操作时，Agent 自己就是大模型——AI 评委、出题实测、自动改写说明书都由它完成。只有抛开 Agent、只用纯命令行跑引擎时，才退化为只做机器检查。

**历史成绩在哪看？**
每次评估都追加到 `artifacts/<skill>/history.jsonl`（一行一条 JSON 记录）。想看趋势，直接对 Agent 说"把 my-skill 最近几次的分数变化整理给我看"即可。

**能评估不在 `skills/` 目录下的技能吗？**
能。`evaluate-skill` 接受任意路径，`evaluate-skill /path/to/some-skill` 即可。放在 `skills/` 下只是为了让批量评估（`--all`）能自动发现它。

**分数多少算合格？**
看用途：内部工具类技能 C 级以上通常够用；要发布给团队或对外使用的关键技能，建议冲到 B 级以上并加一次 LLM 评委复核。等级线（A/B/C 分别 90/75/60）可以在 `skill_rubric_types.yaml` 里调整。

## 下一步

- 建考题：[构建考题](./04-build-benchmark.md)；跑考试：[运行考试](./05-run-benchmark.md)
- 想看完整流程实例：[CSV 摘要技能全流程](../cases/csv-summary-full-cycle.md)
- 九个维度的检查细则：[Rubric 参考](../reference/rubric.md)
- 评委文件等结构化产物的格式：[交换文件参考](../reference/exchange-files.md)
- 命令与参数速查：[CLI 参考](../reference/cli.md)
- 把评估和改进串成日常闭环：[生产闭环](./08-production-loop.md)
