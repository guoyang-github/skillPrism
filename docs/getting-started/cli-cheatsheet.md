# CLI 与自然语言速查表

> 一页纸掌握 skillPrism 所有命令：你想做什么、对 Agent 怎么说、对应 CLI 是什么、关键参数怎么用。

---

## 自然语言 → CLI 命令

如果你已经加载了 `skills/skill-prism/SKILL.md`，直接像对同事一样说话，Agent 会翻译成下面的 CLI。同一功能在不同阶段，你可以问得更具体。

### 评估（evaluate-skill）

| 你想做什么 | 对 Agent 这样说 | 对应 CLI |
|---|---|---|
| 看整体质量 | "这个 skill 的 SKILL.md 写得怎么样？" | `evaluate-skill skills/<skill>` |
| 定位短板 | "给这个 skill 打个分，告诉我哪里扣分最多" | `evaluate-skill skills/<skill> --detailed` |
| 检查文档细节 | "检查一下有没有模糊 wording 或安全隐患" | `evaluate-skill skills/<skill> --detailed` |
| 批量打分 | "给所有 skills 打个分" | `evaluate-skill --all --skills-dir ./skills` |
| 主观维度第二意见 | "再深入看看可读性和领域准确性" | `evaluate-skill skills/<skill> --llm-judge` |

### 测试（test-skill）

| 你想做什么 | 对 Agent 这样说 | 对应 CLI |
|---|---|---|
| 验证 Agent 已生成的结果 | "测一下这个 skill 能不能做 CSV 摘要" | `test-skill --skill <skill> --registry benchmarks/<skill>/registry.yaml --task <task>` |
| 跑 registry 里所有 benchmarks | "跑一下这个 skill 的所有 benchmark" | `test-skill --skill <skill> --registry benchmarks/<skill>/registry.yaml` |
| 用预生成代码验证 | "用这份代码跑一下 benchmark" | `test-skill --skill <skill> --registry benchmarks/<skill>/registry.yaml --task <task> --code ...` |
| 外部 agent 执行 | "让外部 agent 跑这个 benchmark" | 配置 `SKILLPRISM_AGENT_COMMAND` 后运行 `test-skill --skill <skill> --registry benchmarks/<skill>/registry.yaml --task <task>` |
| Agent 已生成结果，只评估 | "结果我已经生成了，帮我检查一下" | `test-skill --skill <skill> --registry benchmarks/<skill>/registry.yaml --task <task>` |
| 快速 gate | "先快速验证一下，别跑太重的数据" | `test-skill --mode quick --skill <skill> --registry benchmarks/<skill>/registry.yaml` |
| 渐进放行 | "从简单到复杂逐步测试这个 skill" | `test-skill --mode gradual --skill <skill> --registry benchmarks/<skill>/registry.yaml` |
| 只跑 smoke | "只跑 smoke 测试，看看核心路径会不会崩溃" | `test-skill --mode single --suite smoke --skill <skill> --registry benchmarks/<skill>/registry.yaml` |

### 改进（improve-skill）

| 你想做什么 | 对 Agent 这样说 | 对应 CLI |
|---|---|---|
| 记录 baseline | "先记录这个 skill 的 baseline" | `improve-skill skills/<skill> --record-baseline` |
| 诊断短板 | "这个 skill 哪里最弱？给我优化建议" | `improve-skill skills/<skill> --suggest` |
| 单维度改进 | "按 P1 结构策略先改 D1，其他别动" | 手动/Agent 编辑 + `improve-skill skills/<skill> --judge` |
| 判断改动 | "改完 judge 一下，看看要不要保留" | `improve-skill skills/<skill> --judge` |
| 应用决策 | "确认保留这次改动" | `improve-skill skills/<skill> --apply` |
| 自动迭代 | "自动帮我改到不能改为止" | `improve-skill skills/<skill> --auto-edit --apply --max-rounds 5` |
| 突围重写 | "这个 skill 好像到瓶颈了，换个思路重写试试" | `improve-skill skills/<skill> --explore-rewrite --apply` |
| 复盘历史 | "看看这个 skill 之前的优化记录" | `improve-skill skills/<skill> --history` |

### 流水线 / CI

| 你想做什么 | 对 Agent 这样说 | 对应 CLI |
|---|---|---|
| 完整质量流水线 | "跑完整质量流水线" | `skill-pipeline --intent "run full quality pipeline"` |
| 批量评估 | "给所有 skills 打个分" | `skill-pipeline --intent "evaluate all skills"` |
| 找最差 skill | "哪个 skill 最差？帮我准备优化" | `skill-pipeline --intent "improve skills"` |
| 批量渐进测试 | "对所有 skill 做渐进测试" | `skill-pipeline --intent "run gradual pipeline"` |
| CI 门控 | "接入 CI" / "跑 CI 门控" | `skill-ci --skill <skill>` |

---

## 全局常用参数

| 参数 | 作用 | 适用命令 |
|---|---|---|
| `--skills-dir` | 指定 skills 根目录 | `evaluate-skill`, `skill-pipeline` |
| `--config` | 指定 `skill_rubric_types.yaml` | `evaluate-skill`, `improve-skill` |
| `--output` | 输出报告路径 | `evaluate-skill`, `skill-pipeline` |
| `--verbose` / `-v` | 打印详细评分过程 | 所有 |
| `--apply` | 真正执行 keep/revert，否则 dry-run | `improve-skill` |
| `--ratchet` | 分数不 regress | `evaluate-skill`, `improve-skill` |

---

## `evaluate-skill`

回答：**SKILL.md 写得怎么样？**

| 参数 | 作用 | 常用场景 |
|---|---|---|
| `--detailed` | 输出每维度证据与建议 | 日常评估 |
| `--all` | 批量评估 `--skills-dir` 下所有 skill | 生成 scorecard |
| `--run-smoke` | 运行示例/代码冒烟测试 | 验证可执行性 |
| `--run-deps` | 检查依赖是否可安装 | CI / 可复现性 |
| `--llm-judge` | 主观维度第二意见 | D2/D5 需要更细判断 |
| `--llm-judge-count N` | 评委数量（默认 2） | 提高主观评分稳定性 |
| `--prompts-dir <path>` | test-prompts.json 读写目录（默认 skill 目录；与 `--output` 解耦） | 多 skill 项目隔离产物 |
| `--no-generate-prompts` | 不自动生成 test-prompts.json | 只读评估 |
| `--output-history <path>` | 写入全局趋势 JSONL | 追踪历史变化 |

```bash
# 最常用的两种用法
evaluate-skill skills/my-skill --detailed

evaluate-skill --all --skills-dir ./skills \
    --output reports/SKILL_SCORECARD.md \
    --run-smoke --run-deps
```

> - `--all` 批量评估会**自动跳过 `skill-prism` 元 skill**（它是 Agent harness，不是被测 skill）。
> - 未传 `--prompts-verification` 时，引擎自动尝试 `{skill}/.skillprism_prompts_verification.json`。
> - 生成物按 skill 隔离到 `artifacts/<skill>/`，跨 skill 汇总放 `reports/`。

---

## `test-skill`

回答：**这个 skill 能不能完成指定任务？**

| 参数 | 作用 | 常用场景 |
|---|---|---|
| `--skill <skill>` | skill 名 | 必填 |
| `--task <task>` | task id | 必填 |
| `--code <path>` | 要执行的生成代码文件（引擎会执行它） | Agent 生成代码而非结果时 |
| `--results` | 强制只验证现有输出（忽略 `SKILLPRISM_AGENT_COMMAND`） | 已生成结果且要跳过外部 agent 时 |
| `--registry <path>` | benchmark 注册表 YAML | 跑 registry 内 benchmarks |
| `--mode single` | 跑单个或某 level/suite 的 benchmark | 日常验证 |
| `--mode gradual` | level 0 → max-level 逐级放行 | 发布前完整验证 |
| `--mode quick` | level 0 + level 1 快速 gate | PR / 快速检查 |
| `--level N` | single 模式下只跑某一级 | 单独调试 |
| `--max-level N` | gradual 模式下最高级 | 控制成本 |
| `--suite <name>` | 只跑某 suite | 跑 smoke / regression |
| `--output-dir <path>` | 测试产物目录 | 保存中间结果 |
| `--results` | 跳过执行，只评估已存在的输出 | 默认开启 |

```bash
# 默认：验证 Agent 已生成的结果
test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml --task csv_summary

# 跑 registry 里的所有 benchmarks（验证已生成结果）
test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml

# 用预生成代码验证（引擎执行）
test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml --task csv_summary --code sample_skill_code.py

# 配置外部 agent 命令后，由引擎调用外部 agent
export SKILLPRISM_AGENT_COMMAND="python examples/editor_wrappers/agent_caller.py"
test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml --task csv_summary

# Agent 已生成结果，只评估（与默认等价）
test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml --task csv_summary

# 渐进测试到 level 2
test-skill --mode gradual --skill my-skill \
    --registry benchmarks/my-skill/registry.yaml --max-level 2
```

---

## `improve-skill`

回答：**怎么改更好？改完要不要保留？**

| 参数 | 作用 | 常用场景 |
|---|---|---|
| `--record-baseline` | 记录当前 Rubric/benchmark 作为基线 | 优化第一步 |
| `--suggest` | 打印最弱维度与策略建议 | 决定改哪里 |
| `--judge` | 对比 baseline，决定 keep/revert | 编辑后评估 |
| `--apply` | 真正执行 keep/revert | 确认决策后 |
| `--auto-edit` | 调用外部 editor 自动改 SKILL.md | 自动优化 |
| `--max-rounds N` | 自动优化最大轮数 | 控制成本 |
| `--min-gain <float>` | 最低分数提升才保留（默认 1.0） | 过滤微提升 |
| `--stop-on-regression` | 遇到回滚立即停止 | 保守自动优化 |
| `--explore-rewrite` | 探索性重写 SKILL.md | 跳出局部最优 |
| `--history` | 查看优化历史 | 复盘 |
| `--benchmark-registry <path>` | 启用 benchmark gate | 需要验证代码时 |
| `--edit-code` | 允许 editor 修改代码资产 | 默认只改 SKILL.md |

```bash
# 手动优化循环
improve-skill skills/my-skill --record-baseline
improve-skill skills/my-skill --suggest
# 编辑 skills/my-skill/SKILL.md
improve-skill skills/my-skill --judge --apply

# 自动优化 3 轮
improve-skill skills/my-skill --auto-edit --apply --max-rounds 3

# 带 benchmark gate 的优化
improve-skill skills/my-skill --judge --apply \
    --benchmark-registry benchmarks/my-skill/registry.yaml
```

---

## `skill-pipeline`

回答：**完整质量流程怎么跑？**

| 参数 | 作用 | 常用场景 |
|---|---|---|
| `--intent <text>` | 自然语言意图 | 必填 |
| `--skills-dir` | skills 根目录 | 批量 |
| `--benchmark-registry <path>` | benchmark 注册表 | 含 benchmark 的意图 |
| `--output <path>` | 统一质量报告 | 生成报告 |
| `--run-smoke` | 同时跑 smoke test | 完整检查 |

```bash
skill-pipeline --intent "run full quality pipeline" \
    --skills-dir ./skills \
    --benchmark-registry benchmarks/my-skill/registry.yaml \
    --output docs/SKILL_QUALITY_REPORT.md --run-smoke
```

---

## `skill-ci`

回答：**CI 门控怎么配？**

默认只跑静态检查（Rubric、smoke、依赖、安全），不调用 LLM。

| 参数 | 作用 | 常用场景 |
|---|---|---|
| `--skill <skill>` | 目标 skill | 必填 |
| `--registry <path>` | benchmark 注册表 | CI |
| `--output-dir <path>` | CI 产物目录 | CI |
| `--run-benchmark` | 同时运行动态 benchmark（需 `--code`） | 完整 CI |
| `--code <path>` | 预生成的 skill 代码 | `--run-benchmark` 时必需 |
| `--baseline <path>` | 基线结果 YAML | 回归门控 |
| `--stop-on-regression` | benchmark 退化即失败 | 严格 CI |
| `--ratchet` | 通过时更新基线 | 自动 ratchet |
| `--no-smoke` | 跳过 smoke test | 快速 CI |
| `--no-deps` | 跳过依赖检查 | 快速 CI |

```bash
# 默认静态 CI 门控
skill-ci --skill my-skill

# 含 benchmark 的完整 CI
skill-ci --skill my-skill \
    --run-benchmark --code sample_skill_code.py \
    --baseline baselines/my-skill.yaml \
    --stop-on-regression
```

---

## `build-skill-test`

回答：**怎么构造新的 benchmark 任务？**

```bash
build-skill-test \
    --id <id> --name "..." --skill <skill> --task <task> \
    --task-spec tasks/<task>.yaml \
    --input data/<dataset-or-task>/input.<ext> --expected-path expected/<expected-file> \
    --metric <id:type:args> --registry benchmarks/<skill>/registry.yaml
```

> - `--skill` 表示这个 benchmark 测试哪个 skill。
> - `--task` 引用 task spec id；task spec 文件放在 `benchmarks/<skill>/tasks/<task>.yaml`。
> - `--task-spec`、`--input`、`--expected-path` 均相对注册表目录解析。
> - `--metric` 定义该 benchmark 的指标，格式为 `id:type:args`。
> - `--registry` 是 per-skill 注册表路径（必填）。

---

## 更多细节

- 每个命令的完整参数：`evaluate-skill --help`、`test-skill --help`、`improve-skill --help` 等。
- 自然语言交互的完整话术：[自然语言操作手册](../reference/operational-playbook.md)。
- 架构设计：[skillPrism 架构设计](../reference/skill-prism-architecture.md)。
