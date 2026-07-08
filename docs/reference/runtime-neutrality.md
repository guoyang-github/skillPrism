> Runtime neutrality 确保 SKILL.md 不会被绑定到某个特定 Agent 或运行时（如 Claude Code、Cursor、Codex）。

# Runtime Neutrality

## 为什么重要

一个好的 skill 应该能在不同 Agent、不同环境中运行。如果 SKILL.md 里写死了：

- "在 Claude Code 中..."
- "~/\.claude/skills/..."
- "npx skills add ..."
- "Cursor only"

那么这个 skill 就丧失了可迁移性。

## 红灯信号

`evaluate-skill` 默认扫描以下 runtime-specific 措辞：

| 类别 | 红灯示例 |
|---|---|
| 平台绑定 | "在 Claude Code"、"Cursor only"、"Codex 中" |
| 路径绑定 | "~/\.claude/skills/..." |
| 安装命令绑定 | "npx skills add"、"/plugin install" |
| badge 绑定 | "Claude Code Skill"、"Cursor Only" |
| 工具调用绑定 | 钉死的工具调用前缀 |

## 绿灯改写

| 红灯措辞 | 绿灯改写 |
|---|---|
| "在 Claude Code 中运行..." | "运行..." |
| "~/\.claude/skills/my-skill" | "<skill-install-dir>/my-skill" |
| "npx skills add my-skill" | "按你的 Agent 方式安装本 skill" |

## 输出

扫描结果会显示在 scorecard 中：

```text
Runtime neutrality: 0 warnings
```

如果有命中：

```text
Runtime neutrality: 2 warnings
  - "在 Claude Code" found at line 12
  - "~/\.claude/skills/" found at line 25
```

## 对优化策略的影响

如果 runtime 红灯命中数 > 0，`improve-skill --suggest` 会把它作为 P0 优先级策略：

```text
P0 · runtime_drift
- Trigger: Runtime-specific wording detected
- Action: Replace runtime-specific wording with runtime-neutral alternatives
```
