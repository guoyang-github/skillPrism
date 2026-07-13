# skillPrism × Langfuse 集成方案

> 将 skillPrism 的「Skill 评估 + 优化」能力嫁接到 Langfuse 的可观测/实验体系上，
> 形成团队级、跨机器、可追溯的工程化评估优化闭环。
>
> 状态：设计稿。实施前需确认部署形态（自建 / Cloud）与数据合规边界。

---

## 1. 背景与目标

### 1.1 现状

skillPrism 已是一个成熟的本地评估优化引擎（经最佳实践改造后）：

- **引擎层**（`skillprism/`，无 LLM 依赖）：9 维 Rubric 评分（`evaluate_skill_rubric.py`）、
  benchmark 执行（`benchmark/runner.py`）、去卷积/聚类/表格/文档评分器、
  优化 keep/revert 循环（`optimize_skill.py`，原子状态 + flock）、
  回归对比（`benchmark/regression.py`，方向感知）、CI 门控（`ci/pipeline.py`）。
- **可选能力层**：外部 editor 命令（`--auto-edit`）、LLM-as-judge 命令（`--llm-judge`），
  均为 stdin/stdout 契约，provider 无关。
- **状态**：`artifacts/<skill>/baseline/baseline.json` / `artifacts/<skill>/history.jsonl` 本地文件，
  已原子写 + flock，但仍是**单机本地**。

### 1.2 痛点

| 维度 | 本地现状 | 问题 |
|---|---|---|
| 优化历史 | `history.jsonl` 单机 | 团队不可共享、不可查询、不可跨 skill 对比 |
| Ratchet 真相源 | 本地 JSON | 跨机器不一致；CI 与本地可能用不同 baseline |
| LLM-judge 治理 | outlier 静默丢弃、wrapper 静默兜底 | 已改为日志，但无集中分析；人类评分无法注入 |
| 回归诊断 | 本地 YAML diff | 无可视化、无跨时间趋势 |
| 最弱维度选择 | 3 套本地启发式（已统一） | 无基于历史实验的统计依据 |
| 评估可观测性 | stdout + scorecard 文件 | 无 trace、无 span、无维度级下钻 |

### 1.3 目标

1. **可观测**：每次 `evaluate` / `test` / `improve` / `ci` 运行成为一条 Langfuse Trace，
   维度/benchmark/guard/judge 各为 span，分数为 score。
2. **可对比**：优化各轮 candidate 作为 Experiment run，与 baseline 逐维度/逐指标对比，
   替代手写 history + 本地回归 YAML。
3. **可治理**：LLM-judge 评分全部落库，支持离线分析与人类评分注入；outlier 不再静默。
4. **可门控**：CI ratchet 真相源迁到服务端，跨机器一致；回归默认 fail（已默认开）。
5. **不破原则**：引擎层保持「无 LLM 依赖、确定性、可复现」；Langfuse 是**可选观测层**，
   默认关闭，环境变量开启，引擎代码不 import langfuse。

---

## 2. 设计原则

| 原则 | 含义 |
|---|---|
| **观测层外挂** | 引擎 `dependencies` 仍只有 `pyyaml`；Langfuse 走 optional-dependency + 延迟 import |
| **只读不写引擎结果** | Langfuse 只采集引擎已产出的分数/决策，不改变引擎确定性结果 |
| **隐私优先** | SKILL.md 正文/代码/绝对路径从不上送；字段级清单见 §4.1，默认最小化、敏感字段 opt-in |
| **离线可用** | 未启用 / 无网络 / 未安装 langfuse 时，引擎行为与本轮改造后完全一致 |
| **契约复用** | 沿用现有 `SKILLPRISM_EDITOR_COMMAND` / `SKILLPRISM_LLM_JUDGE_COMMAND` 外挂契约 |
| **服务端为真相源** | ratchet / 历史最佳分以 Langfuse score 为准，本地状态降级为缓存 |

---

## 3. 体系架构

```
┌──────────────────────────────────────────────────────────────────────┐
│  Langfuse（自建或 Cloud）                                             │
│  ├─ Dataset   : skill test-prompts + benchmark task specs            │
│  ├─ Trace     : 每次 evaluate/test/improve/ci run                    │
│  ├─ Score     : 9 维 Rubric + benchmark 指标 + LLM-judge + 决策       │
│  ├─ Experiment: 优化各轮 candidate vs baseline                       │
│  └─ Evaluator : LLM-judge 迁为 Langfuse evaluation（+ 人类评分）      │
└──────────────▲───────────────────────────────────────────────────────┘
               │ OpenTelemetry / langfuse SDK（可选层，延迟 import）
┌──────────────┴───────────────────────────────────────────────────────┐
│  skillprism/observability/   ← 新模块，零 LLM 依赖                    │
│  ├─ tracer.py        Backend 协议 + 工厂                              │
│  ├─ noop_tracer.py   默认 NoopBackend（零开销）                       │
│  ├─ langfuse_tracer  LangfuseBackend（延迟 import langfuse）          │
│  └─ sink.py          SkillReport/BenchmarkResult/ExperimentRecord     │
│                       → trace + span + score 映射                     │
└──────────────▲────────────────────────────────────────────────────────┘
               │ 注入点（见 §5）
   evaluate_skill_rubric / benchmark.runner / optimize_skill /
   orchestrator / ci.pipeline 的关键步骤
```

三层不变：Skill 入口层（SKILL.md）/ 引擎层（skillprism）/ 可选能力层（editor/judge）。
Langfuse 对接落在**可选观测层**，与 editor/judge 同层并列。

---

## 4. 数据模型映射

| skillPrism 概念 | Langfuse 概念 | 映射说明 |
|---|---|---|
| 一次 `evaluate_skill` 调用 | `Trace` | name=`evaluate:<skill>`，metadata 含 skill_type/config 版本 |
| 单维度评估（D1..D9） | `Span` + `Score` | span name=Dn，score name=Dn，value=1-5，comment=summary |
| `SkillReport.total_weighted` | `Score` | name=`rubric_total`，value=0-100 |
| `run_single_benchmark` | `Span` | name=`benchmark:<id>`，metadata 含 task/level/suite |
| 单个 metric（row_count/mean_rmse…） | `Score` | name=metric id，value=数值，data_type=NUMERIC |
| `_all_pass`（benchmark/ci） | `Score` | name=`benchmark_pass`/`ci_pass`，data_type=CATEGORICAL |
| `judge_candidate` 决策 | `Score` | name=`decision`，value=keep/revert/human-decide（CATEGORICAL） |
| `score_delta` | `Score` | name=`score_delta`，value=浮点 |
| guard violation | `Event` | name=guard rule，level=warning/error，payload=violation |
| 优化一轮（auto-edit round） | `Trace`（子）或 `Span` | name=`optimize:<skill>:round-N` |
| `experiment_history` 一条 record | `Experiment` item | 迁移：本地 jsonl → 服务端 experiment run |
| `artifacts/<skill>/baseline/baseline.json` | Langfuse score 历史 | ratchet 真相源改为查服务端上次 `rubric_total` |
| test-prompts.json | `Dataset` items | 每个 prompt → dataset item（input=prompt, expected=行为描述） |
| per-skill task spec (`benchmarks/<skill>/tasks/<task>.yaml`) | `Dataset` items | 每个 task → dataset item（input=task spec, expected=金标准） |
| editor/judge prompt 模板 | `Prompt` 版本 | 版本化、A/B 测试 |

**方向约定**：lower-better metric（rmse/jsd/…）在 score name 上加后缀 `:lower_better`，
便于离线分析按方向解读（regression.py 已有 `_is_lower_better`，复用）。

### 4.1 隐私边界：字段级上送清单

自建下数据不出本地，但仍需明确「什么上送、什么不上送」，避免元数据过度暴露
内部 skill 结构，也便于合规审计。**默认最小化**，敏感字段需显式 opt-in。

| 字段 | 上送？ | 落点 | 说明 |
|---|---|---|---|
| skill 名 / 路径 | ✅ | trace name + metadata | `skills/foo` 级，**不上送绝对路径**（仅相对 skill 名） |
| skill_type | ✅ | trace metadata | analysis/cmd/api/... |
| 维度分数 D1..D9 | ✅ | score | 1-5 整数 |
| `rubric_total` | ✅ | score | 0-100 |
| 维度 evidence/suggestions 文本 | ⚠️ opt-in | score comment | 默认**不上送**（可能含 skill 文档片段）；`SKILLPRISM_TRACE_EVIDENCE=1` 开启 |
| benchmark metric 值 | ✅ | score | row_count/rmse/... |
| `_all_pass` / decision | ✅ | score | categorical |
| guard violation 消息 | ⚠️ opt-in | event payload | 默认只上送 `rule` + `severity`，**不上送 message 正文**（可能含命令片段）；opt-in 开启 message |
| `score_delta` | ✅ | score | 浮点 |
| commit sha / branch / ci_run_id | ✅ | trace metadata | 用于 ratchet 与归因 |
| LLM-judge reason 文本 | ⚠️ opt-in | score comment | 默认不上送（可能含 SKILL.md 摘要）；opt-in 开启 |
| **SKILL.md 正文 / 代码资产内容** | ❌ 从不 | — | 引擎层不上送；editor/judge 的 LLM 调用单独 `@observe`（那条链路本就是外挂，由 wrapper 自行决定） |
| 绝对文件系统路径 | ❌ 从不 | — | 仅 skill 名 |
| 环境变量 / secret | ❌ 从不 | — | `AgentExecutor` 最小 env 不透传 `LANGFUSE_*` |

**脱敏规则**（`sink.py` 实现）：
- 路径脱敏：`Path` 值统一取 `.name`，剥离父目录。
- 文本字段（evidence/reason/guard message）：默认 `None`，opt-in 时截断 200 字符 + 正则脱敏
  （`sk-...`/`http(s)://...`/email 打码）。
- 配置项 `observability.redact_patterns`（复用 `security_evaluator` 的正则思路）可扩展。

---

## 5. 模块设计与集成点

### 5.1 新模块 `skillprism/observability/`

```python
# skillprism/observability/tracer.py
from typing import Optional, Protocol

class ObservabilityBackend(Protocol):
    def start_run(self, name: str, metadata: dict) -> "Run": ...
    def span(self, run: "Run", name: str, metadata: Optional[dict] = None): ...
    def score(self, run: "Run", name: str, value,
              comment: Optional[str] = None, data_type: str = "NUMERIC"): ...
    def event(self, run: "Run", name: str, payload: Optional[dict] = None): ...

def get_backend() -> ObservabilityBackend:
    import os
    if os.environ.get("SKILLPRISM_OBSERVABILITY") == "langfuse":
        try:
            from .langfuse_tracer import LangfuseBackend
            return LangfuseBackend()
        except ImportError:
            print("Warning: langfuse 未安装，回退 noop。pip install 'skillprism[observability]'")
    return NoopBackend()
```

```python
# skillprism/observability/langfuse_tracer.py（延迟 import）
class LangfuseBackend:
    def __init__(self):
        from langfuse import Langfuse          # 仅在此处 import
        self.client = Langfuse()              # 读 LANGFUSE_HOST/SECRET/PUBLICKEY
    def start_run(self, name, metadata):
        return Run(trace=self.client.trace(name=name, metadata=metadata), client=self.client)
    def span(self, run, name, metadata=None):
        return run.trace.span(name=name, metadata=metadata or {})
    def score(self, run, name, value, comment=None, data_type="NUMERIC"):
        run.trace.score(name=name, value=value, comment=comment, data_type=data_type)
    def event(self, run, name, payload=None):
        run.trace.event(name=name, payload=payload or {})
```

### 5.2 注入点（最小侵入，复用已验证的函数）

| 引擎函数 | 文件 | 注入 | 产出 |
|---|---|---|---|
| `evaluate_skill` | `evaluate_skill_rubric.py` | `start_run("evaluate:<skill>")`；维度循环内 `span(Dn)` + `score(Dn)`；末尾 `score(rubric_total)` | 9 span + 9 score + total |
| `run_single_benchmark` | `benchmark/runner.py` | `span("benchmark:<id>")`；每个 metric `score(metric_id)`；`score(benchmark_pass)` | metric scores + pass |
| `_judge_candidate_unlocked` | `optimize_skill.py` | `start_run("optimize:<skill>:round-N")`；span: eval/benchmark/guards/decision；`score(decision)`/`score(score_delta)`；guard `event` | 决策 + delta + guard events |
| `run_gradual_pipeline` | `gradual.py` | `start_run("gradual:<skill>")`；每 level `span(levelN)` + `score(levelN_pass)` | level pass/fail |
| `CIPipeline.run` | `ci/pipeline.py` | `start_run("ci:<skill>")`；`score(ci_pass)`、`score(rubric_total)`、`score(benchmark_pass)` | ci 门控结果 |

注入采用「`get_backend()` 默认 noop」方式，引擎函数只多 1-2 行 wrapper 调用，
不破坏现有 207 测试（noop 路径零行为变化）。

### 5.3 sink 映射器

`skillprism/observability/sink.py` 负责把引擎数据结构映射为 trace/score：

- `emit_skill_report(backend, run, report, config)`：遍历 `report.dimensions` 发 score，发 `rubric_total`。
- `emit_benchmark_result(backend, run, result)`：遍历 metric 发 score（按 `_is_lower_better` 标注方向）。
- `emit_guard_violations(backend, run, violations)`：每个 violation 发 event（block=error，warn=warning）。

复用 `regression._is_lower_better`、`evaluate_skill_rubric.get_weights`，避免新逻辑。

---

## 6. 数据流

### 6.1 评估流

```
用户/Agent: evaluate-skill skills/foo --llm-judge
  → evaluate_skill(foo) ──trace──→ Langfuse
      ├─ span D1..D9（score=Dn）
      ├─ span llm-judge（score=D2/D5/D6/D8 blended）   ← 见 §7
      └─ score rubric_total
  → 本地 scorecard.md（不变）
  → Langfuse UI 可见该 trace 的 9 维分数 + 总分
```

### 6.2 优化流（闭环核心）

```
improve-skill skills/foo --auto-edit --apply --max-rounds N
  → _run_auto_edit_rounds ──trace──→ Langfuse
      for round in 1..N:
        ├─ span evaluate_candidate（score=rubric_total）
        ├─ span benchmark_gate（score=metrics + benchmark_pass）
        ├─ span guards（event=violations）
        ├─ score decision（keep/revert）
        ├─ score score_delta
        └─ 若 keep：baseline 更新 → 下轮；若 revert：见 §5 回滚
  → Langfuse Experiment：各 round 作为 run，与 baseline 对比
  → 本地 artifacts/<skill>/baseline/baseline.json（缓存，真相源在服务端）
```

### 6.3 CI 流

```
skill-ci --skill foo --run-benchmark --code <path>
  → CIPipeline.run ──trace──→ Langfuse
      ├─ score ci_pass / rubric_total / benchmark_pass
      └─ 回归对比：查 Langfuse 上次 main 分支的 rubric_total
          （服务端 ratchet，替代本地 artifacts/<skill>/baseline/baseline.json）
  → exit code 0/1（回归默认 fail，已开）
```

---

## 7. LLM-judge 迁移到 Langfuse Eval

现状：`SKILLPRISM_LLM_JUDGE_COMMAND` 外挂脚本吐 `{score, reason}` JSON，
`llm_judge.py` 做 schema 校验 + outlier 丢弃 + 重试 + 混合（已硬化）。

迁移路径（两步，可渐进）：

**Step A（桥接，不破坏现有契约）**：保留 `LLMJudge` 本地逻辑，
在 `judge_dimension` / `judge_dimension_multi` 末尾把每次 judge 结果作为 score 发到 Langfuse
（`score(llm_judge:Dn, value, comment=reason)`）。outlier 丢弃时也发 event（已加 WARN 日志）。
→ 零行为变化，只是多了服务端可观测。

**Step B（迁移到 Langfuse Evaluator）**：在 Langfuse 定义自定义 Evaluator
（Python SDK 的 `evaluator` 或 LLM-as-judge eval），D2/D5/D6/D8 的 judge 改为调
`langfuse.evaluate()`。评分自动落为 trace score，支持人类评分（`langfuse.score(user_id=...)`）注入。
本地 `LLMJudge` 降级为离线兜底。`skill_rubric_types.yaml` 的 `llm_judge` 段增加
`backend: local | langfuse` 配置项。

**收益**：outlier 不再本地丢弃——所有 judge 分数落库，离线可统计 LLM 与引擎的分歧分布；
人类评分注入后可作为金标准校准 LLM-judge 权重。

---

## 8. Dataset + Experiment 闭环

这是把 skillPrism 从「单机评估」升级为「工程化评估优化体系」的关键。

### 8.1 Dataset 同步

- `build-skill-test`（`benchmark/builder.py`）写 `benchmarks/<skill>/registry.yaml` 时，
  同时 `langfuse.create_dataset_item(dataset_name=f"skill:{skill}:tasks", input=task_spec, expected=金标准)`。
- `ensure_test_prompts`（`test_prompts.py`）生成 `test-prompts.json` 时，
  同步到 `dataset_name=f"skill:{skill}:prompts"`。
- 现有 `test-prompts.json` 仍是本地真相（离线可用），Langfuse Dataset 是镜像 + 团队共享。

### 8.2 Experiment 对比

- `improve-skill --auto-edit --max-rounds N` 每轮 candidate 作为一个 Experiment run
  （`langfuse.experiment(name=f"optimize:{skill}", run_name=f"round-{N}")`）。
- baseline 作为对照 run。Langfuse Experiment 视图直接给「第 K 轮 vs baseline」的
  逐维度/逐指标 diff —— **替代当前 `history.jsonl` + 回归 YAML 比对**。
- `format_history_table`（`experiment_history.py`）增加一个 Langfuse 后端读取分支，
  从服务端拉历史 run 渲染表格。

### 8.3 反馈闭环

- `run_optimize_setup`（`orchestrator.py`）不再只输出「下一步命令」，
  而是查 Langfuse 找「最近 N 轮无提升的维度」→ 选最弱维度 → 生成下一轮 editor prompt。
- `optimization_strategy.py` 的 P0-P3 策略选择从「本地启发式」升级为「基于历史实验的统计选择」
  （某维度连续 K 轮尝试无收益 → 切换策略或建议人工介入）。

---

## 9. Ratchet 迁移策略（本地状态 → 服务端真相源）

现状（已改造）：`evaluate_skill_rubric.py` ratchet 路径用 `get_weights(config)` 正确计算，
对比本地上次 scorecard；`stop_on_regression` 默认 True；`artifacts/<skill>/baseline/baseline.json` 原子写 + flock；
`historical_best_score` read-modify-write 已用 flock 串行化。

目标：ratchet 真相源迁到 Langfuse 服务端，本地状态降级为**离线缓存**。
迁移必须**可回退、不丢历史、不阻塞 CI**。

### 9.1 三阶段迁移

**阶段 R1 — 双写（只增量，不读）**
- `save_baseline` / `record_baseline` 写本地 JSON 的同时，发一条 `rubric_total` score 到 Langfuse
  （metadata 标 `source=local-mirror`、`commit=<git sha>`、`branch`、`ci_run_id`）。
- ratchet 判定**仍读本地** scorecard（现状不变）。
- 风险：零。仅多一次服务端写入，失败降级为 warning（不阻塞）。
- 验收：服务端出现与本地一致的 `rubric_total` 序列；抽样比对一致率 100%。

**阶段 R2 — 读服务端，本地兜底**
- ratchet 判定改为：先查 Langfuse 该 skill 在 `branch=main` 的最近 `rubric_total`，
  有则用服务端值；**无网络 / 查询失败 / 无记录**则回退读本地 scorecard（与 R1 一致）。
- 本地 JSON 仍写（缓存角色）。
- 引入 `ratchet_source` 字段记录本次用的是 `langfuse | local`，写入 trace metadata 便于审计。
- 风险：中。需保证服务端查询超时短（≤2s）+ 失败必降级，不阻塞 CI。
- 验收：断网时 CI 仍以本地兜底通过；服务端可用时 ratchet 跨机器一致。

**阶段 R3 — 服务端为真相源，本地可选**
- ratchet 只读服务端 `historical_best`（按 score name 聚合 max）。
- 本地 `artifacts/<skill>/baseline/baseline.json` 降级为**纯离线缓存**：仅在无服务端时用，
  且写入时标 `stale=true`；下次服务端可用时以服务端为准覆盖本地。
- `historical_best_score` 的 read-modify-write 竞争**彻底消除**（服务端原子聚合）。
- 可选：`SKILLPRISM_NO_LOCAL_STATE=1` 完全不写本地 JSON（仅服务端）。
- 风险：中。需服务端 SLA 保障；保留本地缓存作为兜底。
- 验收：两台机器并行 CI，ratchet 基线一致；服务端短时宕机，CI 降级本地不 fail。

### 9.2 历史数据导入

- 阶段 R1 上线时，跑一次性 **backfill 脚本**：遍历各 skill 的 `artifacts/<skill>/history.jsonl`
  与 `artifacts/<skill>/baseline/SKILL.md.bak.*`，把历史 `rubric_total` 与 `historical_best_score`
  作为 score 批量导入 Langfuse（metadata 标 `source=backfill`、`backfilled_at`）。
- 导入幂等：以 `(skill, commit, timestamp)` 去重，重复导入不产生重复 score
  （Langfuse score 支持 `id` 字段，用确定性 id `<skill>:<commit>`）。
- 导入后，R2 的服务端查询即有历史可比。

### 9.3 `historical_best_score` 迁移

- 现状：本地 JSON 字段，flock 保护下的 read-modify-write。
- 迁移：R3 后由 Langfuse score 聚合（`max(rubric_total) where skill=... and branch=main`）替代。
- 过渡期（R2）：本地仍维护 `historical_best_score`，但 R2 判定优先用服务端 max；
  若服务端无记录（新 skill），回退本地字段。
- **不再需要**本地 `historical_best_score` 的手动重置（此前需手改 JSON 才能降 ratchet 目标）——
  服务端聚合可按时间窗口重算。

### 9.4 回退策略

- 任一阶段若出问题：`SKILLPRISM_OBSERVABILITY=` （不设）即回到纯本地 ratchet，
  与本轮最佳实践改造后完全一致。
- R2/R3 的服务端调用全部包在 `try/except + 超时`，失败降级本地，不抛到引擎、不 fail CI。
- 服务端数据不可信时（例如导入错误），可按 `source=backfill` 标签批量删除后重导。

---

## 10. 自建部署与运维

**部署形态已定：自建**（含敏感 skill 元数据，不出本地）。

### 10.1 组件栈（Langfuse v3 自建标准栈）

| 组件 | 作用 | 版本/选型建议 |
|---|---|---|
| `langfuse-web` | API + 前端 | Langfuse v3 官方镜像 |
| `langfuse-worker` | 异步入库（ClickHouse 写入） | 与 web 同版 |
| Postgres | 元数据（project/api key/dataset/prompt/score 索引） | ≥14，托管或自管 |
| ClickHouse | trace/score/event 原始数据（高写入量） | ≥23.3，**必须自管或托管** |
| Redis | 队列/缓存 | ≥7 |
| 对象存储 | 大 payload（如 scorecard 文件、prompt 版本附件） | MinIO（自建）或 S3 |

### 10.2 部署形态选型

| 形态 | 适用 | 取舍 |
|---|---|---|
| **docker-compose**（单机） | 单团队 / PoC / P1-P3 阶段 | 简单；单点；ClickHouse 单副本；不可扩 |
| **k8s（Helm chart）** | 多团队 / 生产 / P4+ | 可扩、滚动升级；运维成本高；需 PV/Ingress/证书 |

**建议**：P1-P3 用 docker-compose 单机起步（够用、低运维），P4（团队级闭环）前评估迁 k8s。
ClickHouse 与 Postgres 无论哪种形态都建议**独立持久化卷 + 定期备份**。

### 10.3 最小 docker-compose 拓扑（PoC）

```yaml
# 简化示意，生产需补资源限制/健康检查/备份
services:
  postgres:    # 元数据
  clickhouse:  # trace/score（卷持久化）
  redis:       # 队列
  minio:       # 对象存储
  langfuse-web:
  langfuse-worker:
```

- 网络：仅 `langfuse-web` 对内暴露（Ingress/TLS）；其余组件仅集群内可达。
- 启动顺序：`postgres/clickhouse/redis/minio` → `langfuse-web/worker`（depends_on + healthcheck）。

### 10.4 存储与容量

- ClickHouse 是**高写入量**组件：trace + score + event 全部进 CH。
  按 §10.6 采样后，估算：单 skill CI 每次 run ~10 span + ~15 score ≈ 25 行；
  10 个 skill × 每日 20 次 CI = 5000 行/日 ≈ 180 万行/年，CH 轻松承受。
- **保留策略**：trace TTL 90 天（热查询），score 聚合长期保留（ratchet 真相源）。
  ClickHouse `TTL ... TO DISK 'cold'` 分层，或定期归档。
- Postgres 小（元数据），常规备份即可。

### 10.5 高可用与备份

- PoC：单副本，接受短时宕机（观测层宕机**不阻塞 CI**，见 §12）。
- 生产：`langfuse-web` 多副本 + LB；ClickHouse 建议双副本或托管；
  Postgres 定期 `pg_dump`；MinIO 跨节点 erasure coding。
- **关键约束**：观测层 SLA 不等于引擎 SLA。引擎确定性结果不依赖 Langfuse 可用性。

### 10.6 网络与 CI 连通

- CI runner 需能访问 `langfuse-web` 的 API（443/内部端口）。
- 自建在内网：CI runner 经内网直连；跨网络经 mTLS/VPN。
- **超时**：CI 内 Langfuse 调用统一 `connect=2s, read=5s`，超时即降级 noop，不阻塞 CI。
- 出站：自建无出站需求（数据全在内网）；仅 Langfuse 镜像拉取需出站（或内网镜像仓库）。

### 10.7 鉴权与多租户

- **Langfuse project ↔ skill 集合**：一个 repo / 一个 skill 集合 = 一个 project。
  project 间数据隔离。
- **API key 两种**：
  - CI：service account（`LANGFUSE_SECRET`），project 级，CI 注入。
  - 个人开发：个人 key（`LANGFUSE_PUBLICKEY` 标注 user），便于追责与 UI 归属。
- **secret 管理**：通过 CI secret / 环境变量注入，不落 skill 仓库；
  `AgentExecutor` 的最小 env（已改造）不会把 `LANGFUSE_*` 泄露进 agent 子进程（需把
  `LANGFUSE_*` 加入 `SKILLPRISM_AGENT_PASS_THROUGH_ENV` 才透传，默认不透）。

### 10.8 配置（自建）

```bash
# 启用观测层
export SKILLPRISM_OBSERVABILITY=langfuse
export LANGFUSE_HOST=https://langfuse.internal   # 自建内网地址
export LANGFUSE_SECRET=sk-...                     # CI service account
export LANGFUSE_PUBLICKEY=pk-...                  # 个人/CI 标注

# CI 采样：高频场景只上送 fail + ci_pass
export SKILLPRISM_TRACE_ON_FAIL=1

# ratchet 迁移阶段控制（见 §9）
export SKILLPRISM_RATCHET_SOURCE=auto            # auto=服务端优先本地兜底；local=纯本地
```

```toml
# pyproject.toml
[project.optional-dependencies]
observability = ["langfuse>=2.0"]
all = [..., "langfuse>=2.0"]
```

引擎 `dependencies` 仍只 `pyyaml>=6.0` —— 零 LLM 依赖原则不破。

### 10.9 配额与采样

- `evaluate-skill`（手动/低频）：全量 trace。
- `skill-ci`（高频）：默认 `SKILLPRISM_TRACE_ON_FAIL=1` —— 只在 `_all_pass=False` 时建完整 trace；
  通过时只发 `ci_pass` + `rubric_total` 两个 score（不建 span），压住 CH 写入量。
- `--auto-edit` 多轮：全量 trace（低频、高价值）。

---

## 11. 分阶段实施路线

部署：自建 docker-compose 起步（P0-P3），P4 前评估迁 k8s。Ratchet 按 §9 的 R1→R2→R3 独立推进。

| 阶段 | 范围 | 交付物 | 风险 |
|---|---|---|---|
| **P0 自建部署** | docker-compose 起 Langfuse v3 栈（§10.3）；建 project + CI service key；连通性验证 | 可用的内网 Langfuse + 一条手发 score | 低 |
| **P1 可观测（只读 trace）** | `observability/` 模块 + 5 注入点（noop 默认）+ LangfuseBackend + `emit_*` sink + 隐私脱敏（§4.1）；`evaluate-skill` 能在 Langfuse 看到 9 维 trace | 新模块 + 注入 + stub e2e 测试 | 低，引擎行为不变 |
| **P2 LLM-judge 桥接** | Step A：judge 结果发 score；outlier 发 event | `llm_judge.py` 末尾 hook + 测试 | 低 |
| **P3 Dataset 同步** | `build-skill-test` / `ensure_test_prompts` 同步 dataset item（幂等） | 两个写入点 + 幂等测试 | 低 |
| **P3.5 Ratchet R1 双写** | `save_baseline` 同步发 `rubric_total` score；ratchet 仍读本地；跑历史 backfill（§9.2） | 双写 + backfill 脚本 + 抽样比对 | 低 |
| **P4 Experiment 闭环** | auto-edit 各轮作 experiment run；`format_history_table` 增服务端分支 | optimize 注入 + 历史读取分支 | 中，需离线回退 |
| **P4.5 Ratchet R2 读服务端** | ratchet 判定服务端优先、本地兜底；`ratchet_source` 审计字段 | ratchet 逻辑分支 + 降级测试 | 中，超时/降级 |
| **P5 LLM-judge 迁移 Eval** | Step B：`backend: langfuse` + 人类评分注入 | `llm_judge.py` backend 分支 + 配置 | 中，双轨期 |
| **P5.5 Ratchet R3 服务端真相源** | ratchet 只读服务端 max；本地降级纯缓存；可选 `SKILLPRISM_NO_LOCAL_STATE=1` | ratchet 收尾 + 跨机一致性测试 | 中，需 SLA |
| **P6 反馈闭环** | `run_optimize_setup` 基于历史实验选最弱维度 | orchestrator 增强 | 中，策略统计需调参 |

P0-P2 即带来「自建可观测 + LLM-judge 可治理」核心价值；P3.5-P4.5 解决团队级 ratchet 一致性；
P5-P6 是高阶闭环。建议 P0-P2 先落地验证，再按价值推进。Ratchet 的 R1 可与 P2 并行（低风险）。

---

## 12. 风险与边界

| 风险 | 缓解 |
|---|---|
| 引擎确定性被观测层污染 | Backend 只读采集，不回写引擎结果；noop 默认；全套 207 测试在 noop 路径不变 |
| SKILL.md 正文 / 代码内容外泄 | §4.1 字段级清单：正文与绝对路径**从不**上送；evidence/reason/guard message 默认不上送，opt-in 且脱敏 |
| 元数据暴露内部 skill 结构 | 仅上送 skill 名（非绝对路径）+ 分数 + 决策；自建内网不出网；project 隔离 |
| 离线/无网络不可用 | `NoopBackend` 默认；网络异常时 LangfuseBackend try/except + 超时降级 noop，不抛引擎 |
| 自建 ClickHouse 写爆 | §10.4/§10.9 采样：CI `TRACE_ON_FAIL=1` 只上 fail trace + score；trace TTL 90 天 |
| 自建组件宕机阻塞 CI | 观测层调用全非阻塞 + 超时 + 降级；CI 门控以本地引擎结果为准，观测层不可用**不 fail CI** |
| Ratchet 双写不一致 | §9 R1 只增量不读 → R2 服务端优先本地兜底 → R3 服务端真相源；任一阶段可 `SKILLPRISM_RATCHET_SOURCE=local` 回退 |
| 服务端 ratchet 数据不可信 | backfill 用确定性 `id=<skill>:<commit>` 幂等；可按 `source=backfill` 批量删重导 |
| `LANGFUSE_*` secret 泄进 agent 子进程 | `AgentExecutor` 最小 env 默认不透传（已改造）；需透传才显式加入 `SKILLPRISM_AGENT_PASS_THROUGH_ENV` |
| Langfuse SDK 版本漂移 | 延迟 import + `langfuse>=2.0` 下限；NoopBackend 保证无 SDK 也能跑 |

**明确不做**：
- 不把 SKILL.md 全文 / 代码资产内容作为 trace metadata 上送。
- 不用 Langfuse 替代引擎的确定性评分（rubric 分仍由引擎算，Langfuse 只记录）。
- 不让观测层可用性影响 CI 门控（观测层宕，CI 仍以本地引擎结果判定）。
- 不引入 Langfuse SDK 之外的额外运行时依赖。

---

## 13. 验收标准

**P0 自建部署**：
- 内网可访问 Langfuse UI；CI runner 能用 service key 发一条 score 并在 UI 可见。

**P1 可观测**：
1. `SKILLPRISM_OBSERVABILITY=langfuse` 时，`evaluate-skill skills/foo` 在 Langfuse 出现一条 trace，
   含 9 span + 9 Dn score + 1 `rubric_total` score。
2. 未设该环境变量时，引擎输出与本轮改造后完全一致（207 测试全绿）。
3. LangfuseBackend 在网络异常/SDK 缺失时降级 noop，不抛引擎。
4. §4.1 隐私字段：SKILL.md 正文、绝对路径、evidence 默认**不在** trace 出现（断言测试）。

**P3.5 R1 双写**：
5. `save_baseline` 后服务端出现 `rubric_total` score，与本地一致；backfill 幂等不重复。

**P4.5 R2 读服务端**：
6. 断网时 ratchet 回退本地不 fail CI；服务端可用时两台机器 ratchet 基线一致；`ratchet_source` 字段记录来源。

**P4 Experiment**：
7. `improve-skill --auto-edit --apply` 各轮在 Langfuse 形成可对比 experiment runs。

---

## 14. 与现有最佳实践改造的关系

本轮最佳实践改造已为 Langfuse 对接铺好基础：

- **原子状态 + flock**（P1-1）→ Langfuse 成为真相源后，本地状态降级为缓存仍保持完整。
- **`_run_auto_edit_rounds` locked wrapper**（P1-1）→ trace 注入点清晰（一个外层函数）。
- **`_judge_candidate_unlocked` / `_run_bloat_gate`**（P0-4/P2-1）→ 决策点已结构化，
  `score(decision)` 注入位置明确。
- **regression 方向感知**（P0-6）→ metric score 的 `:lower_better` 后缀有现成依据。
- **outlier 日志**（P2-8）→ 桥接 Langfuse event 的现成 hook。
- **config schema**（P2-4）→ 新增 `llm_judge.backend` 配置项自动被校验。
- **静默 except 改日志**（P2-9）→ 观测层降级路径的失败可见。

即：最佳实践改造让 Langfuse 注入点从「散落在 280 行 god-function 里」变成「结构化、已测试、
单一职责的函数边界」，对接成本与回归风险都显著降低。

---

## 附录 A：最小 PoC 清单（P0 + P1）

**P0 自建部署**：
0. docker-compose 起 Langfuse v3 栈（§10.3）：postgres / clickhouse / redis / minio / langfuse-web / langfuse-worker。
1. 建一个 project（对应一个 skill 仓库），生成 CI service key，验证内网可达 + UI 可见。

**P1 可观测**：
2. 新建 `skillprism/observability/{__init__,tracer,noop_tracer,langfuse_tracer,sink}.py`；
   `sink.py` 内置 §4.1 脱敏（路径取 `.name`、文本字段默认 None + opt-in 截断 + 正则脱敏）。
3. `evaluate_skill_rubric.py:evaluate_skill` 头尾各加 `get_backend().start_run(...)` 与 `emit_skill_report(...)`。
4. `pyproject.toml` 加 `[observability]` optional-dependency。
5. 新增 `tests/test_observability.py`：stub backend 断言 evaluate_skill 产出 9 span + total score；
   **隐私断言**：SKILL.md 正文 / 绝对路径 / evidence 默认不在 trace 出现。
6. 文档：本文件 + README 增「可观测性」章节。
