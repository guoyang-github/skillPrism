# 实验历史

skillPrism 默认在每次 `evaluate-skill` 和 `improve-skill` 运行后追加一条记录到：

```
skills/my-skill/.skillprism_history.jsonl
```

## 记录格式

```json
{
  "timestamp": "2026-06-22T12:00:00Z",
  "skill": "skills/my-skill",
  "commit_or_backup": "a1b2c3d",
  "old_score": 72.3,
  "new_score": 78.5,
  "status": "keep",
  "dimension": "D3",
  "note": "Added if-then fallback tables",
  "eval_mode": "static"
}
```

`status` 取值：`baseline`、`keep`、`revert`、`error`、`human-decide`。

## 查看历史

```bash
improve-skill skills/my-skill --history
```

## 用途

- 追踪每次优化尝试的成败
- 识别触顶信号（连续低 Δ）
- 为探索性重写和策略调整提供数据
