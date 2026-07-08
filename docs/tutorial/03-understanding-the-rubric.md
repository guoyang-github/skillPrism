# 第 3 章：理解 Rubric 九维度

> 学习目标：理解 D1–D9 每个维度的含义、检查项和提升方向。

## 3.1 分数怎么看

skillPrism 的评分卡通常长这样：

| Skill | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 | D9 | Score | Grade |
|---|---|---|---|---|---|---|---|---|---|---|---|
| my-first-analysis | 3 | 2 | 1 | 1 | 1 | 4 | 1 | 1 | 5 | 39.4 | D |

每个维度满分 5 分，最终分数按权重融合为 0–100 分，再映射到 A/B/C/D 等级。

## 3.2 维度详解

### D1 目录与元数据规范

检查 frontmatter 是否完整：`name`、`description`、`keywords` 等。

提升方法：

- 补全 `tool_type`、`primary_tool`、`languages`。
- 确保 `SKILL.md` 位于 skill 根目录。

### D2 文档可理解性

检查是否包含 `When to Use`、`Inputs`、`Outputs`、`Quick Start` 等章节。

提升方法：

- 用表格描述输入/输出。
- 提供最小可运行示例。

### D3 可执行性/正确性

检查示例代码是否能跑通。

提升方法：

- 使用内置数据集或提供下载脚本。
- 在 `examples/` 放最小示例。

### D4 环境/依赖可复现

检查是否有 `requirements.txt`、`pyproject.toml` 等依赖文件。

提升方法：

- 添加 `requirements.txt` 并写明版本约束。
- 在文档中说明 Python 版本要求。

### D5 领域准确性

检查是否包含参数说明、最佳实践、陷阱提示、参考文献。

提升方法：

- 添加 `Parameters Reference`、`Common Pitfalls`、`References`。

### D6 LLM 可调用性

检查 frontmatter 关键词是否丰富、意图是否清晰。

提升方法：

- 在 `description` 中写明使用场景和返回值。
- 使用关键词列表。

### D7 性能/资源/稳健性

检查是否说明内存、运行时间、大规模数据处理方式。

### D8 可维护性

检查是否有版本说明、作者、更新日志等。

### D9 安全与可信

扫描 `eval`、`exec`、`subprocess`、硬编码密钥等危险模式。

## 3.3 本章小结

- 9 维度覆盖了 Skill 从文档到执行、从领域到安全的完整生命周期。
- 最低分的维度通常是最快能带来总分的提升点。
- D9 低于 3 分是阻塞项，需要优先修复。

## 练习

1. 针对 `my-first-analysis`，找出最低分的两个维度。
2. 在 `SKILL.md` 中补充对应内容，重新评估看分数变化。
