# skillPrism 文档

> 项目无关、配置驱动的 Skill 质量评估与持续优化体系。

## 六个核心命令

skillPrism 围绕六个动词构建（另有 `skill-gradual`，是 `test-skill --mode gradual` 的便捷封装）：

| 命令 | 问题 | 默认确定性 |
|---|---|---|
| `evaluate-skill` | SKILL.md 好不好？ | ✅ 是 |
| `test-skill` | 生成的代码跑不跑得通？ | ✅ 是 |
| `build-skill-test` | 怎么注册一条 benchmark？ | ✅ 是（只写 registry） |
| `improve-skill` | 怎么改更好？ | 编辑用 LLM，judge 确定 |
| `skill-pipeline` | 完整流程怎么跑？ | ✅ 编排确定 |
| `skill-ci` | CI 里怎么做质量门禁？ | ✅ 是 |

## 三层文档结构

### 🚀 快速入门

约 30 分钟跑通核心工作流：

- [快速入门首页](./getting-started/index.md)
- [🌱 新手操作手册（自然语言全流程）](./getting-started/beginner-handbook.md)
- [安装与环境](./getting-started/install.md)
- [🙌 手把手教程](./getting-started/hands-on.md)
- [评估一个 Skill](./getting-started/evaluate.md)
- [测试一个 Skill](./getting-started/test.md)
- [改进一个 Skill](./getting-started/improve.md)
- [运行完整流水线](./getting-started/pipeline.md)
- [CI 集成](./getting-started/ci.md)
- [CLI 与自然语言速查表](./getting-started/cli-cheatsheet.md)

### 📖 书式教程（深入读物）

- [01 为什么要评估 Skill](./tutorial/01-why-evaluate-skills.md)
- [03 理解 Rubric 九个维度](./tutorial/03-understanding-the-rubric.md)
- [04 构建你的第一个 Benchmark](./tutorial/04-building-your-first-benchmark.md)
- [用 Claude Code 构建生信 Benchmark（手把手）](./tutorial/build-bio-benchmark-with-claude-code.md)
- [08 渐进测试与真实数据](./tutorial/08-gradual-testing-and-real-data.md)
- [本地全周期演示](./tutorial/full-cycle-demo.md)
- [线上 Agent + Langfuse 生产闭环](./tutorial/agent-langfuse-production-loop.md)

### 📚 深度参考

**架构与概念**

- [体系概览（架构唯一权威）](./reference/overview.md)
- [Rubric 与方法论参考](./reference/framework.md)
- [路线图](./reference/roadmap.md)

**Benchmark**

- [Benchmark 全流程指南](./reference/benchmark-guide.md)
- [Metric 参考（唯一权威）](./reference/benchmark-metrics.md)
- [生信类 Benchmark 设计](./reference/benchmark-bioinformatics.md)
- [数据构建决策速查表](./reference/data-building-decisions.md)
- [扩展 benchmark 任务类型](./reference/adding-a-benchmark-task-type.md)
- [cell2location 完整示例](./reference/cell2location.md)

**优化与评分**

- [优化策略与维度簇](./reference/optimization-strategy.md)
- [Rubric 规则增强](./reference/rubric-enhancements.md)
- [Runtime Neutrality](./reference/runtime-neutrality.md)
- [边界情况与 FAQ](./reference/edge-cases.md)

**集成与接口**

- [LLM Judge（引擎侧）](./reference/llm-judge.md)
- [外部 Agent 命令接口](./reference/agent-command.md)
- [Test-Prompts 验证（功能概述）](./reference/test-prompts-verification.md)
- [Langfuse 集成（设计提案）](./reference/langfuse-integration.md)

**其他**

- [视觉成果卡片](./reference/visual-result-cards.md)
- [API 参考](./reference/api.md)

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
