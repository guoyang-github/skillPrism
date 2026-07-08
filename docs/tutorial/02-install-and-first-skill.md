# 第 2 章：安装与第一个 Skill

> 学习目标：安装 skillPrism，用模板创建第一个 Skill，并跑通 Rubric 评估。

## 2.1 安装

```bash
cd /path/to/Skills_Validation
pip install -e ".[dev]"
```

安装后检查 CLI：

```bash
evaluate-skill --help
improve-skill --help
test-skill --mode single --help
```

## 2.2 创建第一个 Skill

skillPrism 为不同 Skill 类型提供了模板。这里我们使用分析型（analysis）模板：

```bash
mkdir -p skills/my-first-analysis
cp -r templates/analysis/* skills/my-first-analysis/
```

目录结构如下：

```text
skills/my-first-analysis/
├── SKILL.md
├── examples/
│   └── minimal_example.py
├── requirements.txt
└── tests/
    └── test_smoke.py
```

## 2.3 修改 frontmatter

打开 `skills/my-first-analysis/SKILL.md`，把 frontmatter 改成：

```yaml
---
name: my-first-analysis
description: >-
  A minimal analysis skill for learning skillPrism.
tool_type: python
primary_tool: pandas
languages:
  - python
keywords:
  - pandas
  - csv
  - summary
---
```

## 2.4 评估它

```bash
evaluate-skill skills/my-first-analysis --detailed
```

你会看到类似输出：

```text
## my-first-analysis

- **路径**: `skills/my-first-analysis`
- **Skill 类型**: `analysis`
- **Rubric 总分**: 39.4 / 100
- **等级**: D

| 维度 | 名称 | 得分 | 证据 | 优化建议 |
|---|---|---|---|---|
| D1 | 目录与元数据规范 | 3/5 | ... | ... |
| D2 | 文档可理解性 | 2/5 | ... | ... |
| D4 | 工具依赖可复现 | 1/5 | ... | 缺少版本兼容性说明 |
```

如果改用仓库自带的 `templates/analysis` 模板，分数会高很多：

```text
## analysis

- **路径**: `templates/analysis`
- **Skill 类型**: `analysis`
- **Rubric 总分**: 86.0 / 100
- **等级**: B
```

!!! tip "提示"
    第一次评估分数低是正常的。Skill 模板只提供了结构，你需要根据实际场景填充内容。

## 2.5 常见错误

- **无法 import skillprism**：确认已执行 `pip install -e ".[dev]"`，且 import 名为全小写 `skillprism`。
- **SKILL.md 不存在**：skillPrism 只认 `SKILL.md` 文件，大小写敏感。

## 2.6 本章小结

- `pip install -e ".[dev]"` 安装 CLI。
- 用 `templates/analysis` 等模板快速创建 Skill。
- `evaluate-skill <skill-dir> --detailed` 查看详细评分。

## 练习

1. 用 `templates/cmd` 或 `templates/api` 创建第二个 Skill。
2. 对比两个 Skill 的评分差异。
