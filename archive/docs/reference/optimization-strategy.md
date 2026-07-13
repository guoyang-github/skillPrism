# 优化策略与维度簇

skillPrism 的优化策略库按 P0-P3 优先级组织建议；
维度相关簇分析帮助识别会一起变动的维度，避免无效的单维度编辑。

## 优先级

| 优先级 | 触发条件 | 建议动作 |
|---|---|---|
| P0 | Runtime-specific 措辞命中红灯扫描 | 替换为 runtime-neutral 措辞 |
| P0 | test-prompts 验证失败或 with-skill 比 without-skill 更差 | 修复核心指令，减少过度约束 |
| P0 | D9 安全维度 ≤ 2 | 添加高风险操作黑名单 |
| P1 | 结构维度（D1-D4）最低 | 重组 workflow、补充 frontmatter、添加检查点 |
| P2 | 具体性维度（D3、D5）最低 | 补充参数、示例、输入/输出格式、异常处理表 |
| P2 | 无显式失败模式编码 | 添加 if-then 三段式 fallback 表 |
| P3 | 可读性维度（D2、D7、D8）最低 | 拆分段落、去重、加 TL;DR |
| P3 | SKILL.md 体积 > 130% baseline | 精简冗余内容 |

## 使用

```bash
improve-skill skills/my-skill --suggest
```

输出会按优先级列出当前适用的策略。

## 维度相关簇

> 维度相关簇分析：某些 rubric 维度在优化时会一起变动，识别这些簇可以避免无效的单维度编辑。

### 为什么需要相关簇

在优化 SKILL.md 时，修一个维度可能带动其他维度一起涨。例如：

- 补充 if-then fallback 表（D3）时，通常也会让文档更清晰（D2）、依赖说明更完整（D4）。
- 添加具体参数示例（D5）时，LLM callability（D6）往往也会提升。

如果不知道这些相关性，可能会重复优化，或者错过一次编辑带来的复合收益。

### 默认簇定义

| 簇 | 维度 | 说明 |
|---|---|---|
| 结构簇 | D1、D2、D3、D4 | frontmatter、workflow、失败模式、检查点 |
| 执行簇 | D3、D5、D6 | 可执行性、具体性、LLM 调用能力 |
| 维护簇 | D7、D8、D9 | 可读性、可维护性、安全性 |

簇定义见 `skillprism/dimension_clusters.py` 的 `CLUSTERS`。

### 在 `--suggest` 中查看

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

### 簇对优化策略的影响

- 如果最弱维度在结构簇，优先使用 P1 "structure" 策略。
- 如果最弱维度在执行簇，优先使用 P2 "specificity" 或 "failure_mode_encoding" 策略。
- 如果相关簇中多个维度都低，一次更全面的重写可能比多轮单维度编辑更高效。
