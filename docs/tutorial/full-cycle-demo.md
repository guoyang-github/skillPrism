# skillPrism 全周期 Skill 评估优化 Demo

> 以**自然语言交互**为主线，展示一个 Agent（加载 `skills/skill-prism/SKILL.md`）
> 如何驱动 skillPrism 引擎完成「评估 → 测试 → 优化 → 回滚 → CI 门控 → 趋势追踪」全周期。
> 引擎实际执行的 CLI 在每步以 `▶` 标注，输出为示意（数值经脱敏/简化）。
>
> 示例 skill：`data-summary`（analysis 型，从 CSV 生成汇总统计）。

---

## 0. 角色与边界

| 角色 | 职责 | 是否调用 LLM |
|---|---|---|
| **用户** | 自然语言下指令、审批每一轮编辑 | — |
| **Agent** | 读 SKILL.md，把意图映射为引擎命令；用自己的 LLM 编辑 SKILL.md；展示 diff/分数；失败恢复 | ✅ 由 Agent 决定 |
| **skillPrism 引擎** | Rubric 评分、benchmark 运行、回归判断、keep/revert、git 提交/回滚 | ❌ 不调用 |

**安全红线**（SKILL.md 内联）：编辑 SKILL.md 前征求同意；`--apply` 只在用户确认后用；
代码资产修改需人工确认；D5/D9 的 critical/high 发现需人工处理。

---

## 1. 安装与准备

```bash
pip install /path/to/Skills_Validation          # 引擎（仅 pyyaml 依赖）
cp -r skills/skill-prism ~/.claude/skills/      # 把 Agent 入口装进你的 Agent
```

项目结构（用户侧）：
```
my-project/
├── skills/
│   └── data-summary/
│       ├── SKILL.md            # 待评估/优化的 skill
│       └── examples/
│           └── minimal_example.py
├── benchmarks/
│   └── data-summary/
│       ├── registry.yaml       # 后面用 build-skill-test 生成
│       └── tasks/
│           └── table.yaml
└── data/counts.csv
```

---

## 2. 首次评估：看现状

**用户**：评估一下 data-summary 这个 skill，要详细。

**Agent**：好的，我先跑 Rubric 静态评估（含 D9 安全扫描），加上冒烟测试和依赖检查。
不会改任何文件。

▶ `evaluate-skill skills/data-summary --detailed --run-smoke --run-deps --verbose`

```
Evaluating data-summary...
  detected type: analysis
Current: 47.2 / 100 (Grade 2)

| 维度 | 分 | 说明 |
|---|---|---|
| D1 结构与元数据 | 3/5 | 缺 keywords、license |
| D2 文档可理解性   | 2/5 | 无 Pitfalls/Troubleshooting；hedge 词 3 处 |
| D3 可执行性       | 3/5 | examples 有语法错误 |
| D4 环境可复现     | 1/5 | 无 requirements.txt |
| D5 领域准确性     | 3/5 | 统计方法描述偏旧 |
| D6 LLM 可调用性   | 3/5 | 输入输出表不完整 |
| D7 性能/稳健性    | 4/5 | — |
| D8 可维护性       | 4/5 | — |
| D9 安全与可信     | 5/5 | 无高危命令 |

Smoke: 1 example skipped (pass --allow-exec to execute)
Deps:   pip dry-run: 2 packages resolved; no requirements.txt pinned
```

**Agent 解读**：总分 47.2/100，Grade 2。最弱是 **D4（环境可复现，1/5）**——没有 `requirements.txt`，
依赖未锁版本；其次是 D2（文档，2/5）和 D3（可执行性，3/5，示例有语法错误）。
冒烟测试的示例执行默认关闭（沙箱已就位，可信场景可加 `--allow-exec` 开启真实 D3 信号）。

> **注**：`--run-smoke` 默认只做语法/边界检查；执行 skill 自带示例代码需 `--allow-exec`（沙箱内执行）。

---

## 3. 构建 benchmark：建立客观测试

**用户**：给它建个测试，用 counts.csv。

**Agent**：我用 `build-skill-test` 建一个 table 型 benchmark：以 `data/counts.csv` 为输入，
期望输出行数 ≥ 2。金标准由我现场生成。

▶ `build-skill-test --id counts_summary --name "Counts Summary" --skill-type analysis --task table --dataset-source data/counts.csv --expected-path benchmarks/data-summary/expected/counts_summary.csv --metric row_count:min:2 --generate-expected --registry benchmarks/data-summary/registry.yaml`

**用户**：用代码跑一下。

**Agent**：跑 single 模式，用你提供的 `sample_code.py` 作为 skill 生成代码，沙箱内执行。

▶ `test-skill --mode single --skill data-summary --registry benchmarks/data-summary/registry.yaml --code examples/data-summary/sample_skill_code.py`

```
[PASS] Counts Summary: row_count=3 (≥2)  _all_pass=True
```

**Agent**：benchmark 通过。客观测试基线已建立。

---

## 4. 记录 baseline + 识别短板

**用户**：优化它。

**Agent**：按 SKILL.md 工作流，我先记录 baseline（当前 SKILL.md + Rubric 分数，无 LLM 调用），
再获取改进建议。**每轮编辑前我会说明计划并等你批准，编辑后展示 diff 和分数变化。**

▶ `improve-skill skills/data-summary --record-baseline`

```
Baseline recorded: score=47.2, historical_best=47.2
  → artifacts/data-summary/baseline/baseline.json (原子写 + .bak)
```

▶ `improve-skill skills/data-summary --suggest`

```
Current score: 47.2 / 100 (Grade 2)
Weakest dimension: D4 环境/依赖可复现 = 1/5
Evidence: no requirements.txt found
Suggestion: 新增 requirements.txt 并固定版本；在 SKILL.md 标注 Python/包版本兼容性。
```

**Agent**：最弱维度 D4。我打算：① 新增 `requirements.txt`（固定 pandas/numpy 版本）；
② 在 SKILL.md 加一节「Version Compatibility」。这两项是文档/配置资产，不动业务代码。
**可以吗？**

**用户**：可以，做。

---

## 5. 第一轮优化（手动编辑流，人在回路）

**Agent**：（用自己的 LLM 编辑 SKILL.md 与新增 requirements.txt）

▶ 引擎行为：Agent 直接写文件；引擎不参与编辑。

**Agent**：改完了，diff 如下（baseline → current）：

```diff
+ ## Version Compatibility
+ Compatible with Python 3.9+ and pandas>=2.0,<3.0, numpy>=1.24,<2.0.
+ See `requirements.txt` for pinned versions.
```

**用户**：看看效果。

**Agent**：先 dry-run 评判（不真正保留/回滚）。

▶ `improve-skill skills/data-summary --judge --benchmark-registry benchmarks/data-summary/registry.yaml`

```
Current: 58.6 / 100 (Grade 3)   Baseline: 47.2   Delta: +11.4
Dimension changes: D4: +3 (1→4)  D2: +1 (2→3)
Benchmark gate: counts_summary PASS
Guards: All anti-pattern guards passed.
Decision: KEEP (Rubric score improved)
(dry-run: pass --apply to actually keep or revert)
```

**Agent**：D4 1→4、D2 2→3，总分 +11.4，benchmark 未 regress，guard 全过。
**保留这次改动吗？**

**用户**：保留。

▶ `improve-skill skills/data-summary --judge --benchmark-registry benchmarks/data-summary/registry.yaml --apply`

```
Edit kept and baseline updated.   [git commit: keep improved SKILL.md (score 58.6)]
```

**Agent**：已保留并提交，新 baseline = 58.6。进入下一轮还是停？

---

## 6. 第二轮起：用 --auto-edit 自动闭环

**用户**：继续自动优化 3 轮。

**Agent**：我配置一个 editor 命令（OpenAI 兼容 wrapper），让引擎自动「识别最弱维度 → 调 editor →
写入 → judge → 保留/回滚」闭环 3 轮。每轮保留的版本成为下轮 baseline。回归默认即停（`--no-stop-on-regression` 可关）。

▶ `export SKILLPRISM_EDITOR_COMMAND="python examples/editor_wrappers/openai_compatible_editor.py"`

▶ `improve-skill skills/data-summary --auto-edit --apply --max-rounds 3 --benchmark-registry benchmarks/data-summary/registry.yaml`

```
=== Auto-edit round 1/3 ===
Invoking skill editor to improve dimension D2...
Decision: KEEP (Rubric score improved)   58.6 → 63.1
=== Auto-edit round 2/3 ===
Invoking skill editor to improve dimension D6...
Decision: KEEP   63.1 → 66.8
=== Auto-edit round 3/3 ===
Invoking skill editor to improve dimension D5...
Decision: REVERT (No improvement, delta -0.4 < min_gain 1.0)
Edit reverted. Stopping auto-edit loop.   (--stop-on-regression default on)
```

**Agent**：3 轮里 2 轮保留（58.6→63.1→66.8），第 3 轮 D5 改动未达 `min_gain` 且略 regress，
**自动回滚**到第 2 轮版本，循环停止。当前 baseline = 66.8。

> **回滚正确性**：引擎用 `git checkout HEAD -- SKILL.md` 丢弃未提交的候选编辑，HEAD 不变、
> 工作区干净，不会像旧版 `git revert HEAD` 那样回滚错对象。

---

## 7. 失败恢复：guard block 与回滚

**用户**：刚才第 3 轮为什么直接回滚了？

**Agent**：判定 REVERT 的原因写在这里：
`No improvement (delta -0.4 < min_gain 1.0)`。引擎在 `apply=True` 下自动还原 SKILL.md 到
本轮 baseline（第 2 轮版本），并 `record_attempt` 写历史。如果是 guard block（如多维度同改、
bloat、`git reset --hard` 出现在可执行脚本），同样自动回滚并记录违规。

**用户**：如果我不小心把 SKILL.md 改坏了，能恢复吗？

**Agent**：能。`artifacts/data-summary/baseline/SKILL.md.bak.*` 有滚动备份（保留最近 5 份），
`load_baseline` 主文件损坏时自动回退 `.bak`。也可以 `git log` 看每次 keep 的提交。

---

## 8. 渐进测试（失败优先）

**用户**：跑渐进测试，先便宜的。

**Agent**：渐进模式按 level 0→3 逐级跑，首失败即停，ratchet 逐级保护。

▶ `test-skill --mode gradual --skill data-summary --registry benchmarks/data-summary/registry.yaml --max-level 2`

```
=== Gradual stage 0: smoke ===   PASS
=== Gradual stage 1: unit ===    PASS
=== Gradual stage 2: integration === PASS
Gradual pipeline passed through level 2.
```

> baseline 写在 `artifacts/data-summary/ci/gradual/.baselines/data-summary/`（不污染 skill 源码树）。

---

## 9. CI 门控 + ratchet

**用户**：把它接进 CI，别让质量退化。

**Agent**：用 `skill-ci` 做门控：静态评估 + benchmark + 回归对比 + ratchet。
回归默认 fail CI（`--no-stop-on-regression` 可关）。

▶ `skill-ci --skill data-summary --registry benchmarks/data-summary/registry.yaml --baseline baselines/data-summary.yaml --run-benchmark --code examples/data-summary/sample_skill_code.py --ratchet --output-format markdown`

```
Rubric:    66.8 / 100 (Grade 3)
Benchmark: counts_summary PASS
Regression: all_pass=True
_all_pass: True   → exit 0
Ratchet:   66.8 ≥ historical best 66.8 → baseline updated.
```

**退化场景**（某次改动把 D4 改回 1/5）：

```
Rubric:    55.1 / 100
Regression: D4 regressed; counts_summary still PASS but rubric dropped
_all_pass: False  → exit 1   (CI fail, 阻止合并)
```

> ratchet 真相源当前为本地 `artifacts/<skill>/baseline/baseline.json`（原子写 + flock）。
> 接 Langfuse 后可迁服务端（见 `docs/reference/langfuse-integration.md` §9）。

---

## 10. 历史趋势 + 统一报告

**用户**：给我一份全项目 skills 的质量报告和历史趋势。

**Agent**：批量评估，写 scorecard + 历史 jsonl。

▶ `evaluate-skill --all --skills-dir ./skills --output docs/SKILL_SCORECARD.md --output-history docs/skill_history.jsonl --run-smoke --verbose`

或者一站式流水线（评估 + benchmark + 找最差 skill + 给下一步优化命令）：

▶ `skill-pipeline --intent "run full quality pipeline" --skills-dir ./skills --benchmark-registry benchmarks/data-summary/registry.yaml --output docs/SKILL_QUALITY_REPORT.md --run-smoke`

```
Rubric scorecard → docs/SKILL_QUALITY_REPORT.md
Worst skill: data-summary (66.8)  ← 已不是最差，本轮优化生效
Next optimize command:
  improve-skill skills/<worst> --record-baseline --benchmark-registry ...
```

---

## 11. （可选）LLM-as-judge 主观维度

**用户**：D2 文档、D5 领域准确性这些主观维度，让 LLM 也评一下。

**Agent**：配置 judge 命令，引擎分数与 LLM 分数按权重混合（默认 LLM 占 30%）。
outlier（与引擎偏差 >2）会被丢弃并打印 warning，不再静默。

▶ `export SKILLPRISM_LLM_JUDGE_COMMAND="python examples/editor_wrappers/openai_compatible_judge.py"`

▶ `evaluate-skill skills/data-summary --detailed --llm-judge`

```
D2: engine=3, LLM=4 → blended 3.3/5  (LLM judges: [4,4] aggregate=4)
D5: engine=3, LLM=3 → blended 3.0/5
```

> judge wrapper 解析失败时 `exit(1)`（不再静默吐 3 分），引擎走重试路径。

---

## 12. 闭环图

```
        自然语言意图
            │
            ▼
    ┌───────────────┐  审批检查点
    │  Agent(SKILL) │ ────────► 用户确认
    └───────┬───────┘
            │ 引擎命令
            ▼
   ┌────────────────────────────────────────┐
   │ skillPrism 引擎（无 LLM）              │
   │  evaluate ─ benchmark ─ improve ─ ci   │
   │   │           │           │        │   │
   │   ▼           ▼           ▼        ▼   │
   │ Rubric     runner     judge/revert  gate│
   │  分数      指标       keep/revert   ratchet
   └────────────────────────────────────────┘
            │
            ▼
   scorecard / history.jsonl / git commits
   （+ Langfuse trace/score，可选观测层）
```

---

## 13. 最佳实践要点（本 demo 体现）

| 要点 | 体现 |
|---|---|
| 引擎不调 LLM | 评分/回归/keep-revert 全确定性；LLM 只在 editor/judge 外挂 |
| 默认 dry-run | `--judge` 不带 `--apply` 只出决策，不改文件 |
| 人在回路 | 每轮编辑前征求同意、编辑后展示 diff，`--apply` 需用户确认 |
| 回归默认 fail CI | `skill-ci` 默认 `stop_on_regression=True` |
| 沙箱执行 | `--code` 与 `--allow-exec` 的示例执行在 rlimits+最小 env+timeout 沙箱内 |
| 状态原子 + 锁 | baseline 原子写 + `.bak` 回退 + flock 串行化 |
| 渐进失败优先 | gradual level 0→3 首失败即停，baseline 不污染 skill 源码树 |
| 可观测可接 | 自然语言闭环不变，Langfuse 作为可选观测层外挂 |

---

## 14. 常见意图速查

| 用户说 | Agent 跑（引擎命令） | 是否需确认 |
|---|---|---|
| "评估 X" | `evaluate-skill skills/X --detailed` | 否 |
| "评估所有 skills" | `evaluate-skill --all --skills-dir ./skills --output docs/SKILL_SCORECARD.md` | 否 |
| "给它建测试" | `build-skill-test --id ... --task table ...` | 否 |
| "用代码测试 X" | `test-skill --mode single --skill X --registry ... --code ...` | 否 |
| "优化 X" | `improve-skill skills/X --record-baseline` → `--suggest` → 编辑 → `--judge [--apply]` | **是**（每轮） |
| "自动优化 3 轮" | `improve-skill skills/X --auto-edit --apply --max-rounds 3` | **是**（授权 auto-edit） |
| "跑渐进测试" | `test-skill --mode gradual --skill X --registry ... --max-level 2` | 否 |
| "接 CI 别退化" | `skill-ci --skill X --registry ... --baseline ... --ratchet` | 否 |
| "跑质量流水线" | `skill-pipeline --intent "run full quality pipeline" ...` | 否 |

---

## 附录：环境变量速查

| 变量 | 作用 |
|---|---|
| `SKILLPRISM_EDITOR_COMMAND` | `--auto-edit` 调的外部 editor（stdin prompt → stdout Markdown） |
| `SKILLPRISM_LLM_JUDGE_COMMAND` | `--llm-judge` 调的外部 judge（stdin prompt → stdout `{score,reason}` JSON） |
| `SKILLPRISM_AGENT_COMMAND` | `test-skill` 的外部 agent 模式 |
| `SKILLPRISM_AGENT_PASS_THROUGH_ENV` | Agent 子进程透传的凭据 env（逗号分隔，默认不透） |
| `SKILLPRISM_OBSERVABILITY=langfuse` | 启用 Langfuse 观测层（可选，见集成方案） |
| `SKILLPRISM_TRACE_ON_FAIL=1` | CI 只在 fail 时建完整 trace |
| `SKILLPRISM_RATCHET_SOURCE=auto\|local` | ratchet 真相源（auto=服务端优先本地兜底） |
