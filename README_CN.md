# Skills Validation 体系（skillPrism）

> 一套项目无关、配置驱动的 Skill 质量评估与持续优化体系。
> 核心设计：**可安装的 Python 包（skillprism）+ Skill 入口层**。引擎只做客观测量，所有 LLM 驱动的步骤通过可选 editor/judge 命令或 Agent 完成。
>
> English version: [README_EN.md](README_EN.md)
>
> 想先理解整体架构？阅读 [`docs/reference/overview.md`](docs/reference/overview.md)。

---

## 体系架构（三层分离）

```
Skill 入口层（自然语言）
  skills/skill-prism/SKILL.md    → "评估 / 测试 / 改进 / 流水线 / CI"
               │
               ▼
可选能力层（用户选择接入）
  - SKILL.md editor 命令（--auto-edit）
  - LLM-as-judge 命令（--llm-judge）
               │
               ▼
引擎层（skillprism Python 包，无 LLM 依赖）
  evaluate_skill_rubric.py     → 9 维度 Rubric 评分
  optimize_skill.py            → baseline / judge / 回滚
  benchmark/runner.py          → benchmark 注册表与执行
  orchestrator.py              → 质量流水线编排
  ci/                          → CI 门控
```

**核心原则**：引擎无 LLM 依赖、评分可复现、默认 dry-run、必须 `--apply` 才修改文件。

完整架构说明见 [`docs/reference/overview.md`](docs/reference/overview.md)。

---

## 目录结构

```
Skills_Validation/
├── README.md                                    # 本文件
├── docs/                                        # 文档中心（MkDocs 站点源）
│   ├── index.md                                 # 站点首页
│   ├── getting-started/                         # 快速入门
│   ├── tutorial/                                # 书式完全教程（8 章）
│   └── reference/                               # 深度参考
├── skillprism/                                  # pip 包：skillprism（引擎层）
│   ├── evaluate_skill_rubric.py                 # 评估引擎
│   ├── optimize_skill.py                        # 优化测量/回滚引擎
│   ├── gradual.py                               # 渐进失败优先测试模式
│   ├── rubric_enhancements.py                   # Rubric 规则增强
│   ├── experiment_history.py                    # 实验历史
│   ├── optimization_strategy.py                 # P0-P3 策略库
│   ├── dimension_clusters.py                    # 维度相关簇分析
│   ├── runtime_neutrality.py                    # Runtime 中立性检查
│   ├── security_evaluator.py                    # D9 安全维度评估器
│   ├── smoke_test_runner.py                     # 可执行性冒烟测试
│   ├── dependency_checker.py                    # 依赖可复现性检查
│   ├── skill_lens_checks.py                     # SkillLens 检查
│   ├── benchmark/                               # benchmark 框架
│   ├── ci/                                      # CI 流水线
│   ├── testing/                                 # 测试辅助模块
│   └── orchestrator.py                          # 质量流水线编排
├── pyproject.toml                               # pip 包配置
├── mkdocs.yml                                   # MkDocs 配置
├── evaluate_skill_rubric.py                     # 兼容入口
├── optimize_skill.py                            # 兼容入口
├── skill_rubric_types.yaml                      # Skill 类型注册表
├── .github/workflows/skill-rubric-ci.yaml       # CI 工作流模板
├── skills/                                      # Skill 入口层
│   └── skill-prism/                             # 统一 Agent 入口
│       ├── SKILL.md
│       └── references/AGENT_GUIDE.md            # Agent 交互行为规范
├── scripts/
├── benchmarks/                                  # per-skill benchmark registry
│   └── <skill>/
│       ├── registry.yaml
│       └── tasks/
│           └── <task>.yaml
├── examples/
│   ├── benchmark_minimal/                       # 最小可运行 Benchmark 示例
│   ├── benchmark_cell2location/                 # cell2location 渐进四级示例
│   └── editor_wrappers/                         # 编辑器封装示例
└── templates/
    ├── regression_test.py                       # 回归测试脚本
    ├── skill_standard/                          # 通用 Skill 模板
    ├── analysis/                                # 分析型模板
    ├── cmd/                                     # 命令型模板
    ├── api/                                     # API 型模板
    └── document/                                # 文档型模板
```

---

## 设计哲学

| 层 | 职责 | 是否调用 LLM |
|---|---|---|
| **skillprism（引擎）** | Rubric 评分、Benchmark 运行、回归对比、回滚 | ❌ 不调用 |
| **Skill 入口** | Agent 读取 SKILL.md，使用自身 LLM 编辑、决策、迭代 | ✅ 由 Agent 决定 |

这样引擎保持可测试、可复用、无 provider 依赖；Agent 通过 Skill 入口获得完整的工作流能力。

---

## 作为 Skill 使用：自然语言操作

把 `skills/skill-prism/` 复制到 Agent 的 skills 目录后，用户可以直接用自然语言驱动：

| 用户意图 | 核心命令（Agent 执行） | 是否需要人工确认 |
|---|---|---|
| "评估所有 skills" | `evaluate-skill --all --skills-dir ./skills` | 否 |
| "优化 bio-single-cell-clustering" | 见下方优化流程 | **是**（每轮编辑前/后） |
| "运行 skill 质量流水线" | `skill-pipeline --intent "..."` | 否 |
| "跑渐进测试" | `test-skill --mode gradual --skill <name> --registry ... --max-level 2` | 否（level 3 需确认） |

### 优化一个 Skill 的完整流程

```
用户：优化 bio-single-cell-clustering
   ↓
Agent：好的，我先记录 baseline，然后按 Rubric 短板逐轮改进 SKILL.md。
        每轮编辑前我会说明计划，编辑后我会展示 diff 和分数变化，等你确认。
   ↓
1. `improve-skill skills/bio-single-cell-clustering --record-baseline`
   → 引擎记录当前 SKILL.md 与 Rubric 分数作为 baseline（无 LLM 调用）
   ↓
2. `improve-skill skills/bio-single-cell-clustering --suggest`
   → 引擎指出最弱维度（如 D4 缺少 requirements.txt）
   ↓
3. Agent 规划修改并请求人工批准
   → 展示：最弱维度 + 建议 + 打算如何修改
   ↓
4. Agent 用自身 LLM 编辑 SKILL.md
   → 默认只改 SKILL.md，不改代码资产
   ↓
5. 展示 diff，请求人工确认
   → 用户：保留 / 回滚
   ↓
6. `improve-skill skills/bio-single-cell-clustering --judge [--benchmark-registry ...]`
   → 引擎复评：分数提升 / benchmark 不 regress → 保留；否则回滚
   ↓
7. Agent 展示分数变化与 diff，等待用户确认是否进入下一轮
   → 回到步骤 2，直到无提升或达到最大轮数
```

**必须人工参与的环节**：
- 授权 Agent 编辑目标 SKILL.md（尤其是代码资产）。
- 查看每轮 diff 与分数变化，决定保留/回滚/继续。
- 处理 D5（领域准确性）和 D9（安全扫描）的 critical/high 发现。
- 当涉及代码资产（`scripts/`、`examples/`、`requirements.txt`）修改时，默认需要人先确认，不能自动执行。

**引擎自动完成的环节**：
- Rubric 评分、短板识别、benchmark 运行、回归判断、git commit/revert。

---

## 快速开始

> 📖 完整书式教程见 `docs/tutorial/`；本地预览文档站点：
>
> ```bash
> make docs-serve
> # 访问 http://127.0.0.1:8000
> ```

### 1. 安装

```bash
pip install /path/to/Skills_Validation
```

### 2. 评估单个 Skill

```bash
# 安装 CLI 后从任意项目目录执行
evaluate-skill skills/bio-single-cell-clustering --detailed

# 未安装时从 repo 调用 wrapper
python /path/to/Skills_Validation/evaluate_skill_rubric.py \
    skills/bio-single-cell-clustering --detailed
```

> `evaluate-skill` 只跑 Rubric 静态评分（含 D9 安全扫描），不自动跑 benchmark。
> 完整评估需要再跑 `test-skill --mode single --code <path>` 或使用 `skill-pipeline`。

### 3. 批量评估整个项目的 skills

```bash
cd /path/to/Your-Project
evaluate-skill --all --skills-dir ./skills \
    --output docs/SKILL_SCORECARD.md --verbose
```

### 4. 跨项目复用

```bash
evaluate-skill --all \
    --skills-dir /path/to/Genomics-Skills/skills \
    --output /path/to/Genomics-Skills/SKILL_SCORECARD.md
```

### 5. 自定义类型配置

复制 `skill_rubric_types.yaml` 到目标项目，按需修改后：

```bash
evaluate-skill --config ./my_skill_rubric_types.yaml \
    --all --skills-dir ./skills
```

### 6. 启用冒烟测试与依赖检查

```bash
evaluate-skill --all --skills-dir ./skills \
    --run-smoke --run-deps --verbose
```

> `--run-smoke` 默认只做语法/边界检查；执行 skill 自带示例代码需额外加 `--allow-exec`。
> 示例执行在沙箱内（rlimits + 最小环境 + 超时），对**可信/内部** skill 可安全开启以获得真实 D3 可执行性信号；
> 对**不可信来源**的 skill 保持关闭。

### 7. 历史趋势追踪

```bash
evaluate-skill --all --skills-dir ./skills \
    --output docs/SKILL_SCORECARD.md --output-history docs/skill_history.jsonl
```

---

## 内置 Skill 类型

| 类型 | 适用场景 |
|---|---|
| `analysis` | Python/R 数据分析 Skill |
| `cmd` | Shell/CLI/命令型 Skill |
| `api` | 数据库/REST API Skill |
| `document` | 文档生成/科学写作/编排 Skill |
| `generic` | 无法归类时的通用兜底 |

---

## 评估维度

| 维度 | 权重 | 含义 |
|---|---|---|
| D1 | 0.10 | 目录与元数据规范 |
| D2 | 0.15 | 文档可理解性 |
| D3 | 0.18 | 可执行性/正确性 |
| D4 | 0.12 | 环境/依赖可复现 |
| D5 | 0.15 | 领域准确性 |
| D6 | 0.10 | LLM 可调用性 |
| D7 | 0.08 | 性能/资源/稳健性 |
| D8 | 0.04 | 可维护性 |
| **D9** | **0.08** | **安全与可信** |

权重、等级阈值均可在 `skill_rubric_types.yaml` 的 `scoring` 段配置。

> **关于静态启发式评分**：D2、D5、D7 等维度目前主要使用轻量关键词/结构启发式（如 Markdown 标题、表格、特定关键词出现次数）。这些指标便于快速、低成本地运行，但可能被关键词堆砌绕过，也可能对合法表达产生误报。建议将其作为质量信号而非绝对标准；对于关键技能，结合 `--llm-judge` 或人工复核以获得更准确的判断。

---

## 安装

```bash
pip install /path/to/Skills_Validation
# 或带安全扫描与开发依赖
pip install "/path/to/Skills_Validation[all]"
```

安装后获得 CLI 命令：

- `evaluate-skill` —— Rubric 静态评估
- `test-skill --mode single|gradual|quick` —— 单级 / 渐进 / 快速 benchmark 测试
- `build-skill-test` —— 生成 benchmark 任务
- `improve-skill` —— 优化 baseline / 测量 / 回滚（不自动调用 LLM）
- `skill-pipeline` —— 质量流水线编排
- `skill-ci` —— CI 门控

`improve-skill` 不自动调用 LLM；优化工作流由 `skills/skill-prism/SKILL.md` 驱动，Agent 使用自身 LLM 编辑 SKILL.md，引擎负责测量与回滚。

## Agent-Native Skill 入口

`skills/skill-prism/references/AGENT_GUIDE.md` 定义了 Agent 与 skillPrism 交互的标准话术、审批检查点、diff 展示、失败恢复和最终报告格式。`skills/skill-prism/SKILL.md` 是唯一 Agent 入口，覆盖以下意图：

| 用户意图 | 对应引擎命令 | 是否需要人工确认 |
|---|---|---|
| "评估所有 skills" | `evaluate-skill --all --skills-dir ./skills` | 否 |
| "测试 bio-single-cell-clustering" | `test-skill --skill ... --task ...` | 否（默认 verify-only，结果由 Agent/子 Agent 生成） |
| "用代码测试 bio-single-cell-clustering" | `test-skill --skill ... --task ... --code ...` | 否（代码由 Agent 提供） |
| "优化 bio-single-cell-clustering" | `improve-skill ... --record-baseline / --suggest / --judge` | **是**（每轮编辑） |
| "运行 skill 质量流水线" | `skill-pipeline --intent "..."` | 否 |
| "跑渐进测试" | `test-skill --mode gradual --skill ... --registry ...` | 否（level 3 需确认） |

## 工程工具与开发流程

```bash
# 开发安装
pip install -e ".[dev]"

# 运行测试
make test

# 测试覆盖率
make coverage

# 代码风格检查与格式化
make lint
make format

# CI 全量流程（Rubric + 文档 benchmark）
make docs-ci
```

仓库已配置：

- `pyproject.toml`：pytest、coverage、ruff 配置。
- `.pre-commit-config.yaml`：ruff + 基础 hooks + 本地 pytest。
- `.github/workflows/skill-rubric-ci.yaml`：多 Python 版本矩阵 + lint/test/rubric/benchmark/security。
- `CONTRIBUTING.md`：开发环境、PR checklist。

## 双层架构：引擎 + Skill 入口

```
Entry Layer: Skill (Agent-facing)
  - skills/skill-prism/SKILL.md       # 评估 / 测试 / 改进 / 流水线 / CI
  - skills/skill-prism/references/AGENT_GUIDE.md             # 标准话术与审批检查点

Engine Layer: pip package skillprism
  - evaluate-skill
  - test-skill --mode single|gradual|quick
  - build-skill-test
  - improve-skill
  - skill-pipeline
  - skill-ci
  - skillprism.evaluate_skill_rubric
  - skillprism.optimize_skill          # measurement / judge / rollback
  - skillprism.gradual                  # failure-mode-first staged pipeline
  - skillprism.rubric_enhancements      # Rubric 规则增强
  - skillprism.experiment_history       # 实验历史
  - skillprism.optimization_strategy    # P0-P3 策略库
  - skillprism.dimension_clusters       # 维度相关簇分析
  - skillprism.runtime_neutrality       # Runtime 中立性检查
  - skillprism.benchmark.runner
  - skillprism.benchmark.builder
  - skillprism.benchmark.regression
  - skillprism.ci.pipeline
  - skillprism.orchestrator
```

Agent 安装 `skills/skill-prism/` 后，用户可直接用自然语言驱动；引擎保持无 LLM 依赖。

详见 [`docs/reference/operational-playbook.md`](docs/reference/operational-playbook.md)。

---

## 棘轮模式（Ratchet）

防止 Skill 质量随修改退化：

```bash
evaluate-skill --all --skills-dir ./skills \
    --output docs/SKILL_SCORECARD.md --ratchet
```

如果任一 Skill 的总分低于上一次 scorecard，CLI 返回非零退出码。

---

## 自动优化（improve-skill）

skillprism 的优化受 Karpathy autoresearch / darwin-skill 等工作启发，但保持**完全独立**：

1. **引擎**：测量、识别最弱维度、判断保留/回滚。
2. **可选自动编辑**：通过配置外部 editor 命令，让 `improve-skill --auto-edit` 自动改写 `SKILL.md`。

**默认范围**：只编辑 `SKILL.md`（文档资产）。这样回滚简单、风险低、ROI 最高。
若需要编辑代码资产（`scripts/`、`examples/`、`requirements.txt`），必须**显式授权**，并附加 smoke test / benchmark gate。

### 两种优化模式

| 模式 | 使用方式 | 适用场景 |
|---|---|---|
| 手动/Agent 编辑（默认） | Agent / 用户手动编辑 `SKILL.md`，skillprism 负责测量与回滚 | 需要人工审阅每一轮 diff，或 Agent 已有自己的编辑策略 |
| 自动编辑 | `improve-skill ... --auto-edit --apply` | 想要一键自动分析 → 自动改 → 自动 judge → 保留/回滚的闭环 |

### Agent 工作流（手动编辑）

```bash
# 1. 记录 baseline
improve-skill skills/<skill> --record-baseline

# 2. 获取改进建议
improve-skill skills/<skill> --suggest

# 3. Agent / 用户手动编辑 skills/<skill>/SKILL.md
#    → 默认必须暂停并展示 diff，等人确认后再执行 judge

# 4. 判断编辑是否保留（默认 dry-run，只输出决策，不真正保留/回滚）
improve-skill skills/<skill> --judge

# 5. 用户确认后，真正应用决策
improve-skill skills/<skill> --judge --apply
```

### 一键自动优化（--auto-edit）

配置任意 editor 命令（例如调用 LLM 的脚本）：

```bash
export SKILLPRISM_EDITOR_COMMAND="python scripts/my_skill_editor.py"

improve-skill skills/<skill> \
  --record-baseline \
  --benchmark-registry benchmarks/<skill>/registry.yaml \
  --auto-edit \
  --apply \
  --max-rounds 3
```

- Editor 命令从 stdin 读取 prompt，把完整的 SKILL.md 内容输出到 stdout。
- skillprism 自动识别最弱维度、调用 editor、写入新 SKILL.md、再测量并决定保留/回滚。
- `--auto-edit` 会修改文件，因此必须搭配 `--apply` 才能执行。
- `--max-rounds N` 会自动迭代最多 N 轮，每轮把已保留的改进版作为新的 baseline 继续优化。
- 引擎本身仍然无 LLM 依赖；LLM 只在可选的 editor 命令里出现。

仓库已提供常用 LLM provider 的 editor wrapper 示例：

```bash
# OpenAI
export SKILLPRISM_EDITOR_COMMAND="python examples/editor_wrappers/openai_editor.py"

# Anthropic
export SKILLPRISM_EDITOR_COMMAND="python examples/editor_wrappers/anthropic_editor.py"

# 本地 Ollama
export SKILLPRISM_EDITOR_COMMAND="python examples/editor_wrappers/ollama_editor.py"
```

详见 `examples/editor_wrappers/README.md`。

**人在回路点**：
- 每轮编辑前：Agent 应说明打算改什么，等人批准。
- 每轮编辑后：展示 diff 与分数变化，等人确认保留/回滚。
- `--judge` 默认是 dry-run；只有用户明确授权时，才加 `--apply` 让引擎真正执行 keep/revert。
- 启用 `--ratchet` 后，分数不会低于历史最高分。

### 反模式黑名单（guard 自动检查）

`--judge` 时会自动运行以下 guard：

| 反模式 | 说明 |
|---|---|
| 一轮改多个维度 | 多维度同时显著提升时告警 |
| 干跑比例 >30% | 因环境缺失导致大量检查被跳过时告警 |
| `git reset --hard` | 发现即 block |
| 堆冗余凑分 | SKILL.md 行数暴增但分数提升 < 1 分时告警 |
| 同一个模型又改又评 | `--editor-model` 与 `--judge-model` 相同时告警 |
| 静默跳过异常 | 评估过程中出现 error 时告警 |

### Benchmark 驱动优化

提供 `--benchmark-registry` 后，判断编辑时会同时跑 benchmark：

```bash
improve-skill skills/bio-single-cell-clustering \
  --record-baseline \
  --benchmark-registry benchmarks/bio-single-cell-clustering/registry.yaml

# ... Agent 编辑 ...

improve-skill skills/bio-single-cell-clustering \
  --judge \
  --benchmark-registry benchmarks/bio-single-cell-clustering/registry.yaml \
  --apply
```

- Rubric 分数提升但 benchmark regress → 回滚
- benchmark 通过或严格改善，即使 Rubric 提升未达 `min_gain`，也可被接受
- 任一 guard block 触发 → 回滚

### 可选：LLM-as-judge

对于主观性较强的维度（D2 文档可理解性、D5 领域准确性），可以启用 LLM 作为第二评委：

```bash
export SKILLPRISM_LLM_JUDGE_COMMAND="python scripts/my_llm_judge.py"

evaluate-skill skills/<skill> --detailed --llm-judge
improve-skill skills/<skill> --judge --llm-judge
```

judge 命令从 stdin 读取 prompt，必须输出 JSON：

```json
{"score": 4, "reason": "示例清晰，领域指导准确。"}
```

- 引擎分数与 LLM 分数会按权重混合（默认 LLM 占 30%）。
- LLM judge 内置防御机制：JSON schema 校验、score 截断到 1–5、失败重试、以及与引擎分数偏差过大（默认 >2 分）的 outlier 自动丢弃。
- 引擎本身仍保持确定性和 provider 无关；LLM 只是可选插件。
- 可在 `skill_rubric_types.yaml` 的 `llm_judge` 段配置 `weight`、`max_retries`、`outlier_threshold`、`require_reason`。

---

## Benchmark 构建与运行

支持的任务类型：

- `clustering`：scRNA-seq 聚类（需 `scanpy`、`scikit-learn`）
- `table`：CSV 表格指标
- `document`：文本/文档生成质量（结构重叠、token Jaccard、长度比、可选 ROUGE-L / BERTScore / 语义相似度）

### 1. 运行已有 benchmark

```bash
test-skill --mode single --skill bio-single-cell-clustering \
    --registry examples/benchmark_minimal/benchmarks/bio-single-cell-clustering/registry.yaml \
    --code examples/benchmark_minimal/sample_skill_code.py

# 文档生成 benchmark（无需 LLM，使用确定性生成器）
test-skill --mode single --skill document-demo \
    --registry examples/benchmark_minimal/benchmarks/document-demo/registry.yaml \
    --code examples/benchmark_minimal/sample_document_skill_code.py
```

> `examples/benchmark_minimal/document_benchmark/` 包含一个**真实可运行**的文档生成任务：
> - `prompt.txt` 提供自然语言指令。
> - `generator.py` 根据关键词确定性生成 SKILL.md（不调用 LLM）。
> - 输出与 `expected/best_skill.md` 金标准对比，计算 section_overlap、token_jaccard、length_ratio 以及可选的语义/ROUGE-L/BERTScore 指标。

### 2. 创建新 benchmark（一次性准备）

#### 表格任务

```bash
build-skill-test \
  --id tiny_count \
  --name "Tiny Count" \
  --skill-type analysis \
  --task table \
  --dataset-source data/tiny_counts.csv \
  --expected-path expected/tiny_counts.csv \
  --metric row_count:min:2 \
  --generate-expected \
  --registry benchmarks/<skill>/registry.yaml
```

#### 文档生成任务

```bash
build-skill-test \
  --id skill_md_generation \
  --name "SKILL.md Generation" \
  --skill-type document \
  --task document \
  --dataset-source prompts/write_skill_md.txt \
  --expected-path expected/best_skill.md \
  --registry benchmarks/<skill>/registry.yaml
```

> 文档任务的 `expected_path` 通常是你手调的“金标准文档”。`build-skill-test` 会创建注册表条目；金标准文档需要人工准备好。

### 3. 与基线对比（优化/PR 环节）

```bash
python templates/regression_test.py \
    --results latest/bio-single-cell-clustering.yaml \
    --baseline baselines/bio-single-cell-clustering.yaml
```

---

## 质量流水线（skill-pipeline）

`skill-pipeline` 是把 Rubric 评估、Benchmark 运行、回归对比、识别最差 Skill、生成统一报告串在一起的一站式命令。

### 支持的意图

| 意图 | 行为 |
|---|---|
| `"evaluate all skills"` / `"score all skills"` | 只跑 Rubric 评估 |
| `"run benchmarks"` | 只跑 Benchmark 并对比基线 |
| `"run full quality pipeline"` | 跑 Rubric → Benchmark → 识别最差 Skill → 生成报告 |
| `"optimize skills"` / `"improve skills"` | 跑完整流水线 → 为最差 Skill 记录 baseline → 输出下一步 judge 命令 |

### 常用命令

```bash
# 完整流水线
skill-pipeline --intent "run full quality pipeline" \
    --skills-dir ./skills \
    --benchmark-registry ./benchmarks/<skill>/registry.yaml \
    --output docs/SKILL_QUALITY_REPORT.md \
    --run-smoke

# 只评估 Rubric
skill-pipeline --intent "evaluate all skills" \
    --skills-dir ./skills \
    --output docs/SKILL_QUALITY_REPORT.md \
    --run-smoke

# 只跑 benchmarks
skill-pipeline --intent "run benchmarks" \
    --skills-dir ./skills \
    --benchmark-registry ./benchmarks/<skill>/registry.yaml \
    --output docs/SKILL_QUALITY_REPORT.md

# 自动找出最差 Skill 并准备优化
skill-pipeline --intent "optimize skills" \
    --skills-dir ./skills \
    --benchmark-registry ./benchmarks/<skill>/registry.yaml

# 若已配置 SKILLPRISM_EDITOR_COMMAND，可直接对最差 Skill 自动编辑
# skill-pipeline 会在报告中输出对应命令
```

### 输出

- `docs/SKILL_QUALITY_REPORT.md`：合并报告，含 scorecard、benchmark 结果、最差 Skill 与下一步优化命令。
- `docs/_rubric_scorecard.md`：内部临时 scorecard（可忽略）。

### 与单独命令的区别

| 场景 | 推荐方式 |
|---|---|
| 只想看 Rubric 分数 | `evaluate-skill` |
| 只想验证某个 Skill 的 benchmark | `test-skill --mode single --skill ... --code <path>` |
| 想一次性得到完整质量报告 | `skill-pipeline --intent "run full quality pipeline"` |
| 想从最差 Skill 开始优化 | `skill-pipeline --intent "optimize skills"` |

> 实际编辑仍需 Agent 在人工确认下完成；`skill-pipeline` 负责定位目标并准备好测量门控。

---

## SkillLens 三维度

本体系吸收了 Microsoft Research SkillLens 实证有效的三个维度：

| 维度 | 落地位置 | 检查项 |
|---|---|---|
| 失败模式编码 | D2 | 是否显式列出 Pitfalls / Troubleshooting / 反模式 |
| 可执行具体性 | D2 + D6 | 是否避免「视情况而定/建议/可以考虑」等模糊措辞 |
| 高风险黑名单 | D9 | 是否明文禁止 `rm -rf /`、`git reset --hard` 等高危操作 |

---

## 扩展新类型

编辑 `skill_rubric_types.yaml`，在 `skill_types` 下新增条目即可。只要检查项基于「文件存在性」和「关键词匹配」，就无需修改 `evaluate_skill_rubric.py`。

详见 [`docs/reference/framework.md`](docs/reference/framework.md) 第 9 章。

## 路线图与待办

完整的已完成项、短期 backlog 和中长期路线图见 [`docs/reference/roadmap.md`](docs/reference/roadmap.md)。

---

## 依赖

- Python >= 3.9
- PyYAML
- 可选：`shellcheck`（用于流程型 Skill 的 shell 脚本检查）
- 可选：`skillspector`（NVIDIA Skill 安全扫描，用于 D9 深度检测）
- 可选：benchmark 任务所需依赖（如 `scanpy`、`scikit-learn` 等）

安装：

```bash
# 基础功能
pip install /path/to/Skills_Validation

# 含安全扫描 + 开发依赖
pip install "/path/to/Skills_Validation[all]"
```

---

## 许可证

本评估体系随原项目许可分发。
