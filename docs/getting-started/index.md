# 快速入门

> 本节带你用 10 分钟理解 skillPrism 的四个核心命令：**评估（evaluate）**、**测试（test）**、**改进（improve）**、**流水线（pipeline）**。

## 核心概念

skillPrism 回答三个问题：

| 问题 | 命令 | 说明 |
|---|---|---|
| SKILL.md 好不好？ | `evaluate-skill` | 9 维度规则评分 + 规则增强 + SkillLens + runtime 红灯扫描 + smoke + 依赖 + 安全 |
| 生成的代码跑不跑得通？ | `test-skill` | 单次 benchmark / 渐进分级测试 / 快速 gate |
| 怎么改更好？ | `improve-skill` | 记录 baseline → 查看 P0-P3 策略 → 单维度编辑 → judge → apply |

`skill-pipeline` 把上面三步串成一条完整工作流，`skill-ci` 用于 CI 门控。

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

## 手册目录

- [🙌 手把手教程](./hands-on.md)（新手推荐）
- [安装与环境](./install.md)
- [评估一个 Skill](./evaluate.md)
- [测试一个 Skill](./test.md)
- [改进一个 Skill](./improve.md)
- [运行完整流水线](./pipeline.md)
- [CI 集成](./ci.md)
- [CLI 与自然语言速查表](./cli-cheatsheet.md)

## 重要原则

> **skillPrism 引擎不调用 LLM，Agent 是 LLM 调用方。**
>
> - 评估默认是确定性规则评分。
> - 测试需要 `--code`，代码由 Agent/LLM 或用户自己生成。
> - 改进的编辑可以由 Agent 或外部 editor 完成，引擎只做 judge。
> - 主观维度复核、prompts 验证、视觉成果卡片等由 Agent 或可选 reporter 完成。
