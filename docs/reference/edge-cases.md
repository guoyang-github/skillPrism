> improve-skill 在优化过程中会遇到各种边界情况。skillPrism 内置了 fallback 处理，让优化循环更稳健。

# 异常与边界条件处理

## 自动处理的情况

| 场景 | 行为 |
|---|---|
| 不在 git 仓库 | 自动 `git init` 并提交初始快照 |
| `git revert` 失败 | 先尝试 `git stash`，再回退到 baseline 文件副本 |
| baseline 损坏 | 使用时间戳备份恢复 |
| SKILL.md 找不到 | 记录 error 并退出 |
| SKILL.md 体积 > 150% baseline | 触发 bloat guard，自动 revert |
| 分支已存在 | 自动加 `-2` / `-3` 后缀 |
| 多维度同时大幅变化 | 发出警告，建议下一轮收窄编辑范围 |

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
