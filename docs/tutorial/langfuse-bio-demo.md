# Langfuse 集成下的全周期 Skill 评估优化 Demo（生物信息示例）

> **前提**：Langfuse 已自建就位（见 `docs/reference/langfuse-integration.md` §10），
> skillPrism 观测层已实现（`SKILLPRISM_OBSERVABILITY=langfuse`）。
>
> 示例 skill：**`bio-single-cell-clustering`**（analysis 型，scanpy + Leiden 聚类，PBMC 3k 数据）。
> 全程以**自然语言交互**为主线，Agent（加载 `skills/skill-prism/SKILL.md`）驱动引擎，
> 引擎执行以 `▶` 标注，Langfuse 侧产出以 `◇` 标注。

---

## 0. 前提与角色

自建 Langfuse v3 栈（langfuse-web/worker + postgres + clickhouse + redis + minio）已在内网运行，
project = `bio-skills`（对应本仓库），CI service key 已注入。

| 角色 | 职责 | Langfuse 侧 |
|---|---|---|
| 用户 | 自然语言下指令、审批每轮编辑 | — |
| Agent | 意图→引擎命令；编辑 SKILL.md；展示 diff/分数/trace 链接 | — |
| skillPrism 引擎 | Rubric/benchmark/judge/revert/CI（确定性，不调 LLM） | 每次 run 发 trace + score |
| Langfuse（自建） | 可观测/实验/ratchet 真相源 | trace/score/event/experiment |

**安全红线不变**：编辑前征求同意；`--apply` 需确认；D5（领域准确性）/D9 critical 需人工处理。
SKILL.md 正文/代码/绝对路径**从不上送** Langfuse（§4.1 隐私清单）。

---

## 1. 环境配置（自建）

```bash
# 启用观测层 + 自建端点
export SKILLPRISM_OBSERVABILITY=langfuse
export LANGFUSE_HOST=https://langfuse.internal
export LANGFUSE_SECRET=sk-...                      # CI service account
export LANGFUSE_PUBLICKEY=pk-...                    # 标注归属

# CI 采样：高频场景只在 fail 时建完整 trace
export SKILLPRISM_TRACE_ON_FAIL=1

# ratchet 真相源：服务端优先，本地兜底（迁移阶段 R2）
export SKILLPRISM_RATCHET_SOURCE=auto

# editor/judge 外挂（OpenAI 兼容，生物信息领域知识由 LLM 补）
export SKILLPRISM_EDITOR_COMMAND="python examples/editor_wrappers/openai_compatible_editor.py"
export SKILLPRISM_LLM_JUDGE_COMMAND="python examples/editor_wrappers/openai_compatible_judge.py"
```

项目结构：
```
bio-skills/
├── skills/bio-single-cell-clustering/
│   ├── SKILL.md
│   └── examples/minimal_example.py
├── benchmarks/
│   └── bio-single-cell-clustering/
│       ├── registry.yaml          # clustering task
│       └── tasks/
│           └── clustering.yaml
└── .benchmark_cache/pbmc3k_processed.h5ad     # 真实数据
```

---

## 2. 首次评估 → Langfuse Trace

**用户**：评估一下 bio-single-cell-clustering，跑冒烟和依赖检查。

**Agent**：跑 Rubric + smoke + deps。这次每一步都会在 Langfuse 形成一条 trace。

▶ `evaluate-skill skills/bio-single-cell-clustering --detailed --run-smoke --run-deps --verbose`

```
Current: 61.4 / 100 (Grade 3)
D3 可执行性 3/5  D4 环境可复现 2/5  D5 领域准确性 3/5  D2 文档 3/5 ...
Smoke: 1 example skipped (--allow-exec to execute sandboxed)
Deps: scanpy/sklearn resolved; requirements.txt pins incomplete
```

◇ **Langfuse 侧**（trace `evaluate:bio-single-cell-clustering`）：
```
trace evaluate:bio-single-cell-clustering  [metadata: skill_type=analysis, commit=a1b2c3, branch=main]
├─ span D1  score[D1]=3
├─ span D2  score[D2]=3
├─ span D3  score[D3]=3
├─ span D4  score[D4]=2
├─ span D5  score[D5]=3
├─ ... (D6-D9)
└─ score[rubric_total]=61.4
```

**Agent**：总分 61.4。最弱是 **D4（环境可复现 2/5）** 和 **D5（领域准确性 3/5，聚类参数选择/分辨率指导偏旧）**。
trace 链接：`https://langfuse.internal/bio-skills/traces/<id>`，可在 UI 下钻每个维度。

> 上送的只有 skill 名 + 分数 + commit/branch；SKILL.md 正文、`adata.obs` 路径均未上送。

---

## 3. Benchmark → metric scores 落库

**用户**：用 PBMC 3k 跑一下聚类 benchmark。

**Agent**：single 模式，用 skill 生成代码，沙箱执行（rlimits + 最小 env + timeout）。

▶ `test-skill --mode single --skill bio-single-cell-clustering --registry benchmarks/bio-single-cell-clustering/registry.yaml --code examples/benchmark_minimal/sample_skill_code.py`

```
[PASS] pbmc3k_clustering: ari=0.78(≥0.7) nmi=0.81(≥0.7) silhouette=0.42 n_clusters=8 largest_cluster_ratio=0.31
```

◇ **Langfuse 侧**（span `benchmark:pbmc3k_clustering`，挂在评估 trace 下）：
```
span benchmark:pbmc3k_clustering
├─ score[ari]=0.78
├─ score[nmi]=0.81
├─ score[silhouette]=0.42
├─ score[n_clusters]=8
├─ score[largest_cluster_ratio:lower_better]=0.31   ← 方向标注
└─ score[benchmark_pass]=true
```

> `largest_cluster_ratio` 是 lower-better，score name 加 `:lower_better` 后缀，
> 离线分析按方向解读（复用 `regression._is_lower_better`）。

---

## 4. LLM-judge 桥接 + outlier event

**用户**：D5 领域准确性这种主观的，让 LLM 也评。

**Agent**：开 `--llm-judge`。引擎分与 LLM 分按权重混合（默认 LLM 30%）。
每次 judge 结果作为 score 发 Langfuse；outlier（与引擎偏差 >2）丢弃时发 event，不再静默。

▶ `evaluate-skill skills/bio-single-cell-clustering --detailed --llm-judge`

```
D5: engine=3, LLM=4 → blended 3.3/5  (LLM judges: [4,4])
D2: engine=3, LLM=3 → blended 3.0/5
```

◇ **Langfuse 侧**：
```
span D5  score[llm_judge:D5]=4 (comment="参数选择合理，建议补充分辨率选择依据")
        score[D5]=3.3 (blended)
event outlier_dropped  level=warning  payload={dim:D2, llm=1, engine=3, reason:"偏离>2,丢弃"}
```

**Agent**：D5 的 LLM judge 给 4，混合后 3.3。D2 有一票 LLM 给 1（与引擎 3 偏差 >2）被当 outlier 丢弃，
**在 Langfuse 留了 warning event**——以前这种分歧会被静默丢掉，现在可离线统计 LLM 与引擎的分歧分布。

---

## 5. 记录 baseline + Ratchet R1 双写

**用户**：优化它。

**Agent**：先记录 baseline。现在处于 ratchet 迁移 **R1 双写**阶段：本地写 baseline 的同时，
把 `rubric_total` 作为 score 发 Langfuse（ratchet 判定仍读本地）。

▶ `improve-skill skills/bio-single-cell-clustering --record-baseline`

```
Baseline recorded: score=61.4, historical_best=61.4
  → .skillprism_baseline.json (原子写 + .bak) + Langfuse score[rubric_total]=61.4
```

◇ **Langfuse 侧**：
```
score[rubric_total]=61.4  metadata={source=local-mirror, commit=a1b2c3, branch=main, ci_run_id=...}
```

▶ `improve-skill skills/bio-single-cell-clustering --suggest`

```
Weakest dimension: D4 环境/依赖可复现 = 2/5
Suggestion: 固定 scanpy/sklearn/annoy 版本；标注 Python 兼容性。
```

**Agent**：最弱 D4。计划：① 新增 `requirements.txt`（scanpy>=1.9,<2.0 / scikit-learn>=1.3 / numpy<2.0）；
② SKILL.md 加「Environment」与「Version Compatibility」节。**可吗？**

**用户**：做。

---

## 6. 第一轮优化（手动，人在回路）

**Agent**：（用自身 LLM 编辑 SKILL.md + 新增 requirements.txt）

```diff
+ ## Environment
+ Tested on Python 3.10, scanpy 1.9.x, scikit-learn 1.3.x. See `requirements.txt`.
+ ## Version Compatibility
+ numpy<2.0 required (scanpy 1.9 不兼容 numpy 2.0).
```

**用户**：看效果。

▶ `improve-skill skills/bio-single-cell-clustering --judge --benchmark-registry benchmarks/bio-single-cell-clustering/registry.yaml`

```
Current: 70.1 / 100 (Grade 3)   Baseline: 61.4   Delta: +8.7
D4: +2 (2→4)  D2: +1 (3→4)
Benchmark: ari=0.78 PASS (未 regress)
Decision: KEEP (dry-run)
```

**用户**：保留。

▶ `improve-skill skills/bio-single-cell-clustering --judge --benchmark-registry benchmarks/bio-single-cell-clustering/registry.yaml --apply`

◇ **Langfuse 侧**（trace `optimize:bio-single-cell-clustering:round-1`）：
```
span evaluate_candidate  score[rubric_total]=70.1
span benchmark_gate      score[ari]=0.78  score[benchmark_pass]=true
span guards              event[] (无违规)
score[decision]=keep  score[score_delta]=+8.7
```

**Agent**：已保留，baseline = 70.1。下一轮？

---

## 7. 自动闭环多轮 → Experiment

**用户**：自动优化 3 轮，重点攻 D5。

**Agent**：`--auto-edit --max-rounds 3`，每轮 candidate 作为一个 **Experiment run**，
与 baseline 在 Langfuse 逐维度/逐指标对比。回归默认即停。

▶ `improve-skill skills/bio-single-cell-clustering --auto-edit --apply --max-rounds 3 --benchmark-registry benchmarks/bio-single-cell-clustering/registry.yaml`

```
=== round 1/3 === D5  Decision: KEEP  70.1 → 73.5  (ari 0.78→0.81)
=== round 2/3 === D5  Decision: KEEP  73.5 → 75.2  (ari 0.81→0.83)
=== round 3/3 === D6  Decision: REVERT (delta -0.3 < min_gain) → 回滚到 round-2
```

◇ **Langfuse 侧**（Experiment `optimize:bio-single-cell-clustering`）：
```
experiment optimize:bio-single-cell-clustering
├─ run baseline   rubric_total=61.4  ari=0.78
├─ run round-1    rubric_total=70.1  ari=0.78  decision=keep
├─ run round-2    rubric_total=73.5  ari=0.81  decision=keep
├─ run round-3    rubric_total=75.2  ari=0.83  decision=keep
└─ run round-3b   rubric_total=74.9  ari=0.82  decision=revert  ← D6 改动被回滚
```

**Agent**：3 轮里 round-1/2/3 保留（D5 连续提升，ari 0.78→0.83），第 4 次（标 round-3b，攻 D6）
未达 `min_gain` 且略 regress，**自动回滚**到 round-2 版本。当前 baseline = 75.2。
Experiment 视图直接给出每轮 vs baseline 的 diff，**替代了手写 `.skillprism_history.jsonl` 比对**。

---

## 8. keep/revert 决策与 guard event 落库

**用户**：刚才 round-3b 为什么回滚？

**Agent**：引擎判定 `No improvement (delta -0.3 < min_gain 1.0)`，`apply=True` 下自动
`git checkout HEAD -- SKILL.md` 还原，并在 Langfuse 留了决策 score + 原因。

◇ **Langfuse 侧**：
```
score[decision]=revert  score[score_delta]=-0.3  comment="No improvement (delta -0.3 < min_gain 1.0)"
event guard_no_reset_hard  level=info  payload={rule:no_reset_hard, result:pass}  ← D9 策略写入的禁止命令示例未误报
```

> guard 现在只扫 `.sh/.py`，SKILL.md 里「禁止 `git reset --hard`」的示例文本不会误触发 block（见最佳实践改造 P0-5）。

---

## 9. CI 门控 + Ratchet R2/R3 服务端真相源

**用户**：接进 CI，别让质量退化。

**Agent**：`skill-ci` 跑门控。现在 ratchet 已迁到 **R2（读服务端，本地兜底）**：
引擎先查 Langfuse 该 skill 在 `branch=main` 的历史最高 `rubric_total`，有则用服务端值；
查不到/断网则回退本地。`ratchet_source` 字段记录本次用了哪个来源。

▶ `skill-ci --skill bio-single-cell-clustering --registry benchmarks/bio-single-cell-clustering/registry.yaml --baseline baselines/bio-single-cell-clustering.yaml --run-benchmark --code examples/benchmark_minimal/sample_skill_code.py --ratchet`

```
Rubric: 75.2 / 100 (Grade 4)
Benchmark: ari=0.83 PASS
Ratchet: server historical_best=75.2 (source=langfuse)  75.2 ≥ 75.2 → pass
_all_pass: True → exit 0
```

◇ **Langfuse 侧**（trace `ci:bio-single-cell-clustering`，CI 通过只发 score 不建 span 以省存储）：
```
score[ci_pass]=true  score[rubric_total]=75.2  score[benchmark_pass]=true
metadata={ratchet_source=langfuse, ci_run_id=...}
```

**退化场景**（某 PR 把 D5 聚类参数改回旧值，ari 掉到 0.68）：
```
Rubric: 68.9   Benchmark: ari=0.68 (≥0.7? NO → benchmark_fail)
Ratchet: server historical_best=75.2  68.9 < 75.2 → REGRESSION
_all_pass: False → exit 1   CI fail，阻止合并
◇ trace 完整上送（TRACE_ON_FAIL: fail 时建 9 span + metric scores + guard events）
```

> 服务端为真相源后，**两台 CI runner 并行也不再有 `historical_best_score` 的 read-modify-write 竞争**
> （本地 flock 已缓解，服务端聚合彻底消除，见集成方案 §9.3）。

---

## 10. 渐进测试 → level spans

**用户**：跑渐进测试，cell2location 那种四级。

**Agent**：`--mode gradual`，level 0(smoke)→1(unit)→2(integration)→3(release)，首失败即停。

▶ `test-skill --mode gradual --skill bio-single-cell-clustering --registry benchmarks/bio-single-cell-clustering/registry.yaml --max-level 3`

```
=== stage 0: smoke ===        PASS
=== stage 1: unit ===         PASS   (ari=0.83 on subset)
=== stage 2: integration ===  PASS   (full pbmc3k)
=== stage 3: release ===      PASS   (real_data: completion check)
```

◇ **Langfuse 侧**（trace `gradual:bio-single-cell-clustering`）：
```
span level0  score[level0_pass]=true
span level1  score[level1_pass]=true  score[ari]=0.83
span level2  score[level2_pass]=true  score[ari]=0.83
span level3  score[level3_pass]=true  (real_data: completion only)
```

> baseline 写在 `ci-output/gradual/.baselines/bio-single-cell-clustering/`，不污染 skill 源码树（P2-6）。

---

## 11. 反馈闭环：基于历史实验选最弱维度

**用户**：下一步该攻哪个维度？

**Agent**：我不靠本地启发式猜——查 Langfuse 历史 Experiment，看最近 N 轮哪些维度尝试过但无收益。

▶ `skill-pipeline --intent "optimize skills" --skills-dir ./skills --benchmark-registry benchmarks/bio-single-cell-clustering/registry.yaml`

```
Worst skill: bio-single-cell-clustering (75.2)
Langfuse history (last 5 optimize runs):
  D4: improved 2→4 (round-1, 收益 +2)
  D5: improved 3→4 (round-2/3, 收益 +1.7, 近 2 轮收益递减)
  D6: attempted round-3b, reverted (收益 -0.3)  ← 连续 1 次负收益
  D2: flat
Next: D2 (文档) — 3 轮未动过，ROI 最高且低风险。
  → improve-skill skills/bio-single-cell-clustering --suggest  (将聚焦 D2)
```

**Agent**：建议攻 **D2（文档）**——D5 近两轮收益递减、D6 上轮负收益，D2 三轮未动且低风险。
要我按这个开下一轮吗？

> 这是把 `optimization_strategy.py` 的 P0-P3 策略选择从「本地启发式」升级为「基于历史实验的统计选择」（集成方案 §8.3）。

---

## 12. Langfuse UI 可视化（描述）

打开 `https://langfuse.internal/bio-skills`：

- **Traces**：每次 evaluate/ci/improve run 一条，可下钻 9 维 span + benchmark metric + guard event。
- **Scores**：`rubric_total` 时间序列——可见 bio-single-cell-clustering 从 61.4 → 70.1 → 73.5 → 75.2 的爬升曲线，每次 PR 一个点。
- **Experiments**：`optimize:bio-single-cell-clustering` 下各 round 并排对比，每维/每指标 diff 一目了然。
- **Datasets**：`skill:bio-single-cell-clustering:tasks` 镜像了 registry，团队共享。
- **Annotations**：D5 的 LLM-judge 分数与人类评分（可手动注入）并列，用于校准 LLM-judge 权重。

---

## 13. 降级与回退（不阻塞 CI）

**用户**：如果 Langfuse 挂了，CI 还能跑吗？

**Agent**：能。观测层调用全非阻塞：`connect=2s, read=5s` 超时即降级 noop，不抛引擎、不 fail CI。
门控仍以本地引擎结果为准；ratchet 在 R2 阶段服务端不可用时回退本地 baseline。

**断网场景**：
```
[WARN] Langfuse unreachable (timeout),降级 noop — 本次 run 不上送 trace
Ratchet: server query failed → fallback local (source=local)
Rubric: 75.2   _all_pass: True → exit 0   (CI 照常通过)
```

◇ **Langfuse 侧**：本次无 trace（`ratchet_source=local` 标在本地 metadata，服务端恢复后下次以服务端为准）。

> 任一阶段可 `SKILLPRISM_OBSERVABILITY=`（不设）回到纯本地，与最佳实践改造后完全一致。

---

## 14. 闭环图（含 Langfuse）

```
        自然语言意图
            │
            ▼
    ┌───────────────┐  审批检查点
    │  Agent(SKILL) │ ────────────► 用户确认
    └───────┬───────┘
            │ 引擎命令
            ▼
   ┌─────────────────────────────────────────────┐
   │ skillPrism 引擎（无 LLM，确定性）            │
   │  evaluate ─ benchmark ─ improve ─ ci         │
   └───────────────────┬─────────────────────────┘
                       │ trace/score/event/experiment（可选观测层）
                       ▼
              ┌─────────────────┐
              │ Langfuse（自建） │
              │  trace/score     │ ─► UI 可视化、Experiment 对比
              │  experiment      │ ─► 反馈：选最弱维度
              │  ratchet 真相源  │ ─► CI 门控（服务端历史最高分）
              └─────────────────┘
                       │
                       ▼
   scorecard / history.jsonl / git commits（本地不变）
```

---

## 15. 常见意图速查（Langfuse 集成版）

| 用户说 | Agent 跑 | Langfuse 产出 |
|---|---|---|
| "评估 X" | `evaluate-skill skills/X --detailed` | trace + 9 Dn score + rubric_total |
| "用 PBMC 跑 benchmark" | `test-skill --mode single --skill X --registry ... --code ...` | benchmark span + metric scores |
| "D5 让 LLM 也评" | `evaluate-skill ... --llm-judge` | llm_judge:Dn score + outlier event |
| "优化 X" | `improve-skill ... --record-baseline → --suggest → 编辑 → --judge [--apply]` | optimize trace + decision/delta score；R1 双写 rubric_total |
| "自动优化 3 轮" | `improve-skill ... --auto-edit --apply --max-rounds 3` | Experiment runs（各 round vs baseline） |
| "跑渐进测试" | `test-skill --mode gradual --skill X --registry ... --max-level 3` | gradual trace + level spans |
| "接 CI 别退化" | `skill-ci --skill X --registry ... --ratchet` | ci trace（fail 时完整）+ ratchet_source |
| "下一步攻哪个维度" | `skill-pipeline --intent "optimize skills" ...` | 查历史 Experiment 选维度 |

---

## 附录：Langfuse 相关环境变量

| 变量 | 作用 |
|---|---|
| `SKILLPRISM_OBSERVABILITY=langfuse` | 启用观测层（默认 noop） |
| `LANGFUSE_HOST/SECRET/PUBLICKEY` | 自建端点 + 鉴权 |
| `SKILLPRISM_TRACE_ON_FAIL=1` | CI 只在 fail 时建完整 trace |
| `SKILLPRISM_RATCHET_SOURCE=auto\|local` | ratchet 真相源（auto=服务端优先本地兜底） |
| `SKILLPRISM_NO_LOCAL_STATE=1` | R3 阶段：完全不写本地 baseline（仅服务端） |
| `SKILLPRISM_TRACE_EVIDENCE=1` | opt-in：上送维度 evidence（默认不上送，含文档片段） |

> 隐私：SKILL.md 正文、代码资产、绝对路径、`LANGFUSE_*` secret **从不上送**；
> evidence/reason/guard message 默认不上送，opt-in 时截断 + 正则脱敏（集成方案 §4.1）。
