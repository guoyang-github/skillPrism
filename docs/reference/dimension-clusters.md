> 维度相关簇分析受 darwin-skill 启发：某些 rubric 维度在优化时会一起变动，识别这些簇可以避免无效的单维度编辑。

# 维度相关簇分析

## 为什么需要相关簇

在优化 SKILL.md 时，修一个维度可能带动其他维度一起涨。例如：

- 补充 if-then fallback 表（D3）时，通常也会让文档更清晰（D2）、依赖说明更完整（D4）。
- 添加具体参数示例（D5）时，LLM callability（D6）往往也会提升。

如果不知道这些相关性，可能会重复优化，或者错过一次编辑带来的复合收益。

## 默认簇定义

| 簇 | 维度 | 说明 |
|---|---|---|
| 结构簇 | D1、D2、D3、D4 | frontmatter、workflow、失败模式、检查点 |
| 执行簇 | D3、D5、D6 | 可执行性、具体性、LLM 调用能力 |
| 维护簇 | D7、D8、D9 | 可读性、可维护性、安全性 |

## 在 `--suggest` 中查看

```bash
improve-skill skills/my-skill --suggest
```

输出示例：

```text
Weakest dimension: D3 (score 2/5)
Cluster: Execution cluster
Related dimensions in the same cluster:
- D5: 3/5
- D6: 3/5
```

这意味着：优化 D3 时，可以顺带检查 D5 和 D6 是否也能一起提升。

## 对优化策略的影响

- 如果最弱维度在结构簇，优先使用 P1 "structure" 策略。
- 如果最弱维度在执行簇，优先使用 P2 "specificity" 或 "failure_mode_encoding" 策略。
- 如果相关簇中多个维度都低，一次更全面的重写可能比多轮单维度编辑更高效。
