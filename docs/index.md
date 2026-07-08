# skillPrism 文档

> 项目无关、配置驱动的 Skill 质量评估与持续优化体系。

## 四个核心命令

skillPrism 围绕四个动词构建：

| 命令 | 问题 | 默认确定性 |
|---|---|---|
| `evaluate-skill` | SKILL.md 好不好？ | ✅ 是 |
| `test-skill` | 生成的代码跑不跑得通？ | ✅ 是 |
| `improve-skill` | 怎么改更好？ | 编辑用 LLM，judge 确定 |
| `skill-pipeline` | 完整流程怎么跑？ | ✅ 编排确定 |

## 两层文档结构

### 🚀 快速入门

30 分钟跑通核心工作流：

- [快速入门首页](./getting-started/index.md)
- [🙌 手把手教程](./getting-started/hands-on.md)
- [安装与环境](./getting-started/install.md)
- [评估一个 Skill](./getting-started/evaluate.md)
- [测试一个 Skill](./getting-started/test.md)
- [改进一个 Skill](./getting-started/improve.md)
- [运行完整流水线](./getting-started/pipeline.md)
- [CI 集成](./getting-started/ci.md)
- [CLI 与自然语言速查表](./getting-started/cli-cheatsheet.md)
- [书式教程（8 章）](./tutorial/01-why-evaluate-skills.md)

### 📚 深度参考

**核心概念**

- [体系概览](./reference/overview.md)
- [skillPrism 架构设计](./reference/skill-prism-architecture.md)
- [Rubric 与优化框架](./reference/framework.md)

**Rubric 与优化**

- [Rubric 规则增强](./reference/rubric-enhancements.md)
- [优化策略库](./reference/optimization-strategy.md)
- [维度相关簇分析](./reference/dimension-clusters.md)
- [异常与边界处理](./reference/edge-cases.md)
- [实验历史](./reference/experiment-history.md)

**测试与验证**

- [测试构造指南](./reference/benchmark-guide.md)
- [数据构建决策速查表](./reference/data-building-decisions.md)
- [新增测试任务类型](./reference/adding-a-benchmark-task-type.md)
- [渐进测试策略](./reference/gradual-testing.md)
- [LLM Judge](./reference/llm-judge.md)
- [Test-Prompts 验证](./reference/test-prompts-verification.md)
- [Runtime Neutrality](./reference/runtime-neutrality.md)
- [视觉成果卡片](./reference/visual-result-cards.md)

**操作与示例**

- [自然语言操作手册](./reference/operational-playbook.md)
- [cell2location 完整示例](./reference/cell2location.md)
- [API 参考](./reference/api.md)
- [路线图](./reference/roadmap.md)
- [示例报告](./reference/examples/scorecard.md)

## 核心原则

1. **Agent 是 LLM 调用方**：代码生成、主观维度复核、prompts 验证等需要 LLM 的环节由 Agent 完成。
2. **引擎确定性**：评分、测试、回归、回滚默认不调用 LLM。
3. **人在回路**：默认 dry-run，必须 `--apply` 才修改文件。
4. **失败优先**：渐进测试从 level 0 开始，逐级放行到真实数据。

## 本地预览

```bash
make docs-serve
```

然后访问 <http://127.0.0.1:8000>。
