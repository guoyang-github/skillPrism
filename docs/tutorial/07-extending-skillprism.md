# 第 7 章：扩展 skillPrism

> 学习目标：学会注册自定义 benchmark 任务、按类型模板创建 Skill，以及向社区贡献。

## 7.1 自定义 Benchmark 任务插件

如果内置任务（`table`、`clustering`、`document`、`deconvolution`）不满足需求，可以写插件。

### Registry 内联方式

创建 `my_plugin.py`：

```python
def run(benchmark, skill, code_path, registry, registry_dir):
    return {"_all_pass": True, "custom_metric": 0.95}
```

在注册表中引用：

```yaml
plugins:
  - my_plugin.run

benchmarks:
  my_custom_bench:
    name: "Custom benchmark"
    task: run
    skills: [my-skill]
```

### Entry point 方式

在 `pyproject.toml` 中注册：

```toml
[project.entry-points."skillprism.benchmark.task"]
my_task = "my_package.benchmarks:my_task"
```

## 7.2 自定义 Skill 模板

复制现有模板并修改：

```bash
cp -r templates/analysis templates/my-domain-analysis
```

修改 `SKILL.md` 中的 frontmatter 和示例代码，使其符合你的领域。

## 7.3 贡献指南

如果你想为 skillPrism 贡献代码：

1. 运行 `make test` 和 `make lint`，确保全部通过。
2. 新功能必须附带测试。
3. 更新相关文档（`docs/` 和 `README.md`）。
4. 提交 Pull Request。

## 7.4 本章小结

- 插件 API 让 skillPrism 可以适应任意 benchmark 类型。
- 模板系统让团队可以沉淀领域最佳实践。
- 贡献前请确保测试和 lint 通过。

## 练习

1. 写一个最简单的自定义 benchmark 插件，返回 `_all_pass: True`。
2. 基于 `templates/api` 创建一个你们团队常用的 API skill 模板。
