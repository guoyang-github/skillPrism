# 安装与环境

## 环境要求

- Python >= 3.9
- 建议在一个干净的 virtual environment 或 conda env 中安装

## 安装 skillPrism

在仓库根目录执行：

```bash
pip install -e ".[dev]"
```

这会安装：

- `skillprism` Python 包
- 全部 7 个 CLI 命令：`evaluate-skill`、`test-skill`、`build-skill-test`、`improve-skill`、`skill-pipeline`、`skill-ci`、`skill-gradual`
- 开发依赖：`pytest`、`ruff`、`mkdocs`、`mkdocs-material`

## 验证安装

```bash
evaluate-skill --help
test-skill --help
```

看到帮助信息即安装成功。

## 开发工具

```bash
# 运行测试
make test

# 代码风格检查
make lint

# 构建文档站点
make docs-build

# 本地预览文档
make docs-serve
```

## 可选依赖

- 跑 clustering/deconvolution benchmark 需要 `scanpy`、`scipy`、`numpy`、`pandas`。
- 跑 LLM-as-judge 需要配置外部 judge 命令（skillPrism 不内置 LLM 调用）。

## 环境变量

| 变量 | 作用 | 示例 |
|---|---|---|
| `SKILLPRISM_LLM_JUDGE_COMMAND` | `--llm-judge` 时调用的外部 judge 命令 | `export SKILLPRISM_LLM_JUDGE_COMMAND="python examples/editor_wrappers/openai_compatible_judge.py"` |
| `SKILLPRISM_AGENT_COMMAND` | benchmark 执行时调用的外部 agent 命令 | `export SKILLPRISM_AGENT_COMMAND="python examples/editor_wrappers/agent_caller.py"` |

## 相关阅读

- Skill 概念、三种使用方式与 Agent 集成（加载 meta skill、意图映射、完整交互示例）已移到 [快速入门首页](./index.md)。
- 构建第一个 Benchmark：[构建你的第一个 Benchmark](../tutorial/04-building-your-first-benchmark.md)
- 命令速查：[CLI 与自然语言速查表](./cli-cheatsheet.md)

## 下一步

[评估一个 Skill](./evaluate.md)
