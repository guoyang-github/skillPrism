# 边界情况与 FAQ

> improve-skill 在优化过程中会遇到各种边界情况。skillPrism 内置了 fallback 处理，让优化循环更稳健。

## 自动处理的情况

| 场景 | 行为 |
|---|---|
| 不在 git 仓库 | 自动 `git init` 并提交初始快照；`git init` 失败或没有 git 时改用文件副本兜底 |
| 候选编辑需要回滚（revert） | git 可用时执行 `git checkout HEAD -- SKILL.md` 丢弃未提交改动；git 不可用或 checkout 失败时，用 baseline 文件副本（`artifacts/<skill>/baseline/SKILL.md`）恢复 |
| baseline 损坏 | 自动回退到 `.bak` 副本恢复 |
| SKILL.md 找不到 | 记录 error 并退出 |
| SKILL.md 体积 > 150% baseline | 触发 bloat guard，自动 revert |
| 分支已存在 | 自动加 `-2` / `-3` 后缀 |
| 多维度同时大幅变化 | 发出警告，建议下一轮收窄编辑范围 |

> 注意：回滚机制不涉及 `git stash`。`SKILL.md.stash` 文件只出现在 `--explore-rewrite`（探索性重写）流程中，与常规 keep/revert 无关。

## Bloat Guard

当一次编辑让 `SKILL.md` 体积超过 baseline 的 150% 时：

```text
Bloat guard triggered: SKILL.md size increased to 160% of baseline (>150%)
Reverting edit; reduce SKILL.md size and try again.
```

这防止优化过程中 SKILL.md 无限膨胀。

## 单维度约束

每轮自动编辑默认只改一个维度。如果 judge 后发现多个维度同时变化 ≥2 分：

```text
Warning: multiple dimensions changed significantly ['D2', 'D3']; consider a narrower edit next round.
```

这帮助把分数变化归因到单一变量，便于判断优化是否有效。

## 实验历史

所有尝试（包括 error、revert）都会写入 `artifacts/<skill>/history.jsonl`，方便排查问题。

## FAQ（常见问题）

### Q1：安装后 `skillprism` 无法 import

确认包已正确安装：

```bash
pip install -e ".[dev]"
python -c "import skillprism; print(skillprism.__file__)"
```

### Q2：`--auto-edit` 报错 "no skill editor configured"

需要配置 editor 命令：

```bash
export SKILLPRISM_EDITOR_COMMAND="python examples/editor_wrappers/openai_editor.py"
```

### Q3：Benchmark 因数据文件损坏失败

删除缓存/下载的损坏文件，重新运行。例如：

```bash
rm -f examples/benchmark_minimal/data/pbmc3k_processed.h5ad
```

### Q4：judge 退出码为 1

表示编辑被回滚。检查：

- Rubric 分数是否没有提升（delta < `--min-gain`）
- benchmark 是否 regress
- 是否触发 guard block

### Q5：`--run-deps` 很慢

`pip install --dry-run` 需要解析依赖图。首次慢，后续可缓存；或在 CI 中单独跑。

### Q6：smoke test 运行示例失败

检查示例是否自包含。推荐在示例中使用内置数据集或提供下载脚本。
