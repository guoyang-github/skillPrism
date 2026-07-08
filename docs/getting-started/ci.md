> `skill-ci` 是 skillPrism 的 CI 门控入口，默认只跑静态客观检查，不调用 LLM。

# CI 集成

## 默认行为

```bash
skill-ci --skill my-skill
```

默认包含：

- Rubric 静态评分（含规则增强检查）
- Smoke test
- Dependency reproducibility checks
- Security scan
- Runtime neutrality 红灯扫描

## 可选跑测试

如果你已经在 CI 中预先生成了代码 artifact，可以跑动态测试：

```bash
skill-ci --skill my-skill \
  --run-benchmark \
  --code artifacts/generated_code.py \
  --registry benchmarks/my-skill/registry.yaml
```

## 指定 level 或 suite

```bash
# 只跑 level 0 benchmark
skill-ci --skill my-skill \
  --run-benchmark --code code.py --registry benchmarks/my-skill/registry.yaml --level 0

# 只跑 smoke suite
skill-ci --skill my-skill \
  --run-benchmark --code code.py --registry benchmarks/my-skill/registry.yaml --suite smoke
```

## GitHub Actions 示例

```yaml
name: Skill Quality
on: [push, pull_request]
jobs:
  skill-ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: skill-ci --skill skills/my-skill
```

## CI 不做什么

- 不调用 LLM 生成代码
- 不自动编辑 SKILL.md
- 不跑渐进测试 level 3（除非显式配置）
