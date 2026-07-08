# 第 6 章：质量流水线与 CI

> 学习目标：把评估、Benchmark、优化整合成一条可重复运行的流水线，并接入 CI。

## 6.1 运行完整流水线

```bash
skill-pipeline --intent "run full quality pipeline" \
    --skills-dir ./skills \
    --benchmark-registry benchmarks/<skill>/registry.yaml \
    --output docs/SKILL_QUALITY_REPORT.md \
    --run-smoke
```

这条命令会：

1. 评估所有 skill 的 Rubric 分数。
2. 运行每个 skill 的 benchmark。
3. 对比基线，识别 regression。
4. 找出最差 skill。
5. 生成合并报告。

## 6.2 支持的意图

| 意图 | 行为 |
|---|---|
| `evaluate all skills` | 只跑 Rubric |
| `run benchmarks` | 只跑 Benchmark |
| `run full quality pipeline` | Rubric + Benchmark + 报告 |
| `optimize skills` | 完整流水线 + 为最差 skill 记录 baseline |
| `run gradual pipeline` | 跑 level 0→3 渐进测试 |

## 6.3 GitHub Actions 接入

项目已提供 `.github/workflows/skill-rubric-ci.yaml`。复制到目标仓库后，它会在 PR 修改 `skills/**`、`skillprism/**`、`tests/**` 时自动触发。

典型的 CI 步骤：

```yaml
- name: Install
  run: pip install -e ".[dev]"

- name: Lint & Test
  run: |
    make lint
    make test

- name: Evaluate skills
  run: |
    evaluate-skill --all --skills-dir ./skills \
      --output docs/SKILL_SCORECARD.md --run-smoke
```

## 6.4 pre-commit

```bash
pre-commit install
make lint
make test
```

## 6.5 本章小结

- `skill-pipeline` 把多个步骤整合成一条命令。
- CI 可以在每次 PR 时自动跑评估和测试。
- 定期审计可以生成历史评分卡，追踪 skill 质量趋势。

## 练习

1. 在本地跑一遍 `skill-pipeline --intent "run full quality pipeline"`。
2. 查看生成的 `docs/SKILL_QUALITY_REPORT.md`，找出最差 skill。
