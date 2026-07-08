# 优化策略库

skillPrism 的优化策略库受 darwin-skill 启发，按 P0-P3 优先级组织建议。

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
