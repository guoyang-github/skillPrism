# skillPrism（Skills Validation 体系）

> 一套项目无关、配置驱动的 Skill 质量评估与持续优化体系。
> 核心设计：**可安装的 Python 包（skillprism）+ Skill 入口层**。引擎只做客观测量，所有 LLM 驱动的步骤通过可选 editor/judge 命令或 Agent 完成。
>
> English version: [README.md](README.md)
>
> 想先理解整体架构？阅读 [`docs/reference/overview.md`](docs/reference/overview.md)。

---

## 核心能力

- **9 维 Rubric 静态评估**：结构、文档、可执行性、可复现性、领域准确性、可调用性、性能、可维护性、安全，权重与检查项全部配置化。
- **Benchmark 注册表**：按 skill 拆分的任务级正确性测试（聚类、表格、文档生成等），支持金标准对比与自定义 metric。
- **人在回路优化闭环**：baseline → 短板建议 → 编辑 → judge → 保留/回滚，默认 dry-run，`--apply` 才动文件。
- **CI 质量门控**：ratchet 防退化、回归对比、多 Python 版本矩阵工作流模板。
- **Agent 原生入口**：复制 `skills/skill-prism/` 到 Agent 的 skills 目录，即可用自然语言驱动全流程。

---

## 三层架构

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

| 层 | 职责 | 是否调用 LLM |
|---|---|---|
| **skillprism（引擎）** | Rubric 评分、Benchmark 运行、回归对比、回滚 | ❌ 不调用 |
| **Skill 入口** | Agent 读取 SKILL.md，使用自身 LLM 编辑、决策、迭代 | ✅ 由 Agent 决定 |

**核心原则**：引擎无 LLM 依赖、评分可复现、默认 dry-run、必须 `--apply` 才修改文件。

完整架构说明见 [`docs/reference/overview.md`](docs/reference/overview.md)。

---

## 快速开始

> 📖 完整书式教程见 `docs/tutorial/`；本地预览文档站点：`make docs-serve`（访问 http://127.0.0.1:8000）。

### 1. 安装

```bash
pip install -e .
pip install -e ".[all]"          # 可选：安全扫描 + 开发依赖
pip install -e ".[benchmark]"    # 可选：benchmark 依赖（scanpy、scikit-learn 等）
```

### 2. 评估一个 Skill

```bash
evaluate-skill skills/bio-single-cell-clustering --detailed
```

> `evaluate-skill` 只跑 Rubric 静态评分（含 D9 安全扫描），不自动跑 benchmark。

### 3. 批量评估并生成报告

```bash
evaluate-skill --all --skills-dir ./skills \
    --output reports/SKILL_SCORECARD.md --run-smoke --verbose
```

> `--run-smoke` 默认只做语法/边界检查；执行 skill 自带示例代码需额外加 `--allow-exec`（沙箱内运行，仅对可信 skill 开启）。

### 4. 运行 Benchmark

```bash
# 聚类 benchmark（scanpy）
test-skill --mode single --skill bio-single-cell-clustering \
    --registry examples/benchmark_minimal/benchmarks/bio-single-cell-clustering/registry.yaml \
    --code examples/benchmark_minimal/sample_skill_code.py

# 文档生成 benchmark（确定性生成器，无需 LLM）
test-skill --mode single --skill document-demo \
    --registry examples/benchmark_minimal/benchmarks/document-demo/registry.yaml \
    --code examples/benchmark_minimal/sample_document_skill_code.py
```

> `examples/benchmark_minimal/` 是最小可运行示例：每个 skill 一个 `benchmarks/<skill>/` 目录，内含 `registry.yaml`、`tasks/`、`data/`、`expected/`；`sample_*_skill_code.py` 是预生成的被测代码。结构说明见该目录的 `README.md`。

### 5. 构建新 Benchmark

```bash
build-skill-test \
    --id skill_md_generation \
    --name "SKILL.md Generation" \
    --skill my-skill \
    --task document \
    --input prompts/write_skill_md.txt \
    --expected-path expected/best_skill.md \
    --registry benchmarks/my-skill/registry.yaml
```

完整构建流程（含数据准备、metric 选择）见 [`docs/reference/benchmark-guide.md`](docs/reference/benchmark-guide.md)。

---

## CLI 命令

安装后获得以下命令：

| 命令 | 用途 |
|---|---|
| `evaluate-skill` | Rubric 静态评估（单个或 `--all` 批量） |
| `test-skill --mode single\|gradual\|quick` | 运行 benchmark：单级 / 失败优先渐进 / 快速 |
| `build-skill-test` | 生成 benchmark 注册表条目 |
| `improve-skill` | 优化闭环：baseline / 建议 / judge / 回滚（不自动调用 LLM） |
| `skill-pipeline` | 质量流水线编排（评估 → benchmark → 最差 skill 报告） |
| `skill-ci` | CI 质量门控 |
| `skill-gradual` | `test-skill --mode gradual` 的便捷封装 |

---

## 作为 Agent Skill 使用

把 `skills/skill-prism/` 复制到 Agent 的 skills 目录后，用户可以直接用自然语言驱动，Agent 将其翻译为引擎命令：

| 用户意图 | 核心命令（Agent 执行） | 是否需要人工确认 |
|---|---|---|
| "评估所有 skills" | `evaluate-skill --all --skills-dir ./skills` | 否 |
| "测试 bio-single-cell-clustering" | `test-skill --skill ... --task ...` | 否（默认验证 Agent 已生成的结果） |
| "用代码测试 bio-single-cell-clustering" | `test-skill --skill ... --task ... --code ...` | 否 |
| "跑渐进测试" | `test-skill --mode gradual --skill ... --registry ...` | 否（level 3 需确认） |
| "优化 bio-single-cell-clustering" | `improve-skill ... --record-baseline / --suggest / --judge` | **是**（每轮编辑） |
| "运行 skill 质量流水线" | `skill-pipeline --intent "..."` | 否 |

`skills/skill-prism/references/AGENT_GUIDE.md` 定义了 Agent 与 skillPrism 交互的标准话术、审批检查点、diff 展示、失败恢复和最终报告格式。完整的「自然语言 → CLI」映射见 [`docs/getting-started/cli-cheatsheet.md`](docs/getting-started/cli-cheatsheet.md)。

### 优化一个 Skill 的典型交互

```
用户：优化 bio-single-cell-clustering
   ↓
1. improve-skill <skill> --record-baseline   → 记录当前分数为 baseline（无 LLM）
2. improve-skill <skill> --suggest           → 指出最弱维度
3. Agent 规划修改并请求人工批准               → 展示最弱维度 + 建议 + 修改计划
4. Agent 用自身 LLM 编辑 SKILL.md            → 默认只改 SKILL.md
5. 展示 diff，请求人工确认                    → 用户：保留 / 回滚
6. improve-skill <skill> --judge [--apply]   → 复评：分数提升且不 regress → 保留
7. 回到步骤 2，直到无提升或达到最大轮数
```

**必须人工参与**：授权编辑（尤其是 `scripts/`、`examples/`、`requirements.txt` 等代码资产）、审阅每轮 diff 与分数变化、处理 D5/D9 的 critical/high 发现。

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

维度中融入了 SkillLens 实证有效的三类信号：失败模式编码（D2，是否显式列出 Pitfalls/Troubleshooting）、可执行具体性（D2+D6，是否避免「视情况而定/建议」等模糊措辞）、高风险黑名单（D9，是否明文禁止 `rm -rf /` 等高危操作）。

> **关于静态启发式评分**：D2、D5、D7 等维度目前主要使用轻量关键词/结构启发式（如 Markdown 标题、表格、特定关键词出现次数），便于快速低成本运行，但可能被关键词堆砌绕过，也可能对合法表达产生误报。建议将其作为质量信号而非绝对标准；对关键 skill，结合 `--llm-judge` 或人工复核。

---

## Skill 类型

`skill_rubric_types.yaml` 内置五种类型，各自可覆盖维度名、权重与检查项：

| 类型 | 适用场景 |
|---|---|
| `analysis` | Python/R 数据分析 Skill |
| `cmd` | Shell/CLI/命令型 Skill |
| `api` | 数据库/REST API Skill |
| `document` | 文档生成/科学写作/编排 Skill |
| `generic` | 无法归类时的通用兜底 |

**扩展新类型**：在 `skill_rubric_types.yaml` 的 `skill_types` 下新增条目即可；只要检查项基于「文件存在性」和「关键词匹配」，就无需修改引擎代码。详见 [`docs/reference/framework.md`](docs/reference/framework.md)。

---

## 优化工作流（improve-skill）

引擎负责测量、识别最弱维度、判断保留/回滚；编辑有两种模式：

| 模式 | 使用方式 | 适用场景 |
|---|---|---|
| 手动/Agent 编辑（默认） | Agent / 用户手动编辑 `SKILL.md`，引擎测量与回滚 | 需要人工审阅每一轮 diff |
| 自动编辑 | `improve-skill ... --auto-edit --apply` | 一键自动 分析 → 改 → judge → 保留/回滚 |

**默认编辑范围**：只改 `SKILL.md`（文档资产），回滚简单、风险低。修改代码资产必须显式授权，并附加 smoke test / benchmark gate。

### 手动/Agent 模式

```bash
improve-skill skills/<skill> --record-baseline   # 1. 记录 baseline
improve-skill skills/<skill> --suggest           # 2. 获取改进建议
# 3. Agent / 用户编辑 SKILL.md（默认必须暂停展示 diff，等人确认）
improve-skill skills/<skill> --judge             # 4. dry-run：只输出决策
improve-skill skills/<skill> --judge --apply     # 5. 用户确认后真正应用
```

### 自动编辑模式（--auto-edit）

配置任意 editor 命令（从 stdin 读 prompt，把完整 SKILL.md 输出到 stdout）：

```bash
export SKILLPRISM_EDITOR_COMMAND="python examples/editor_wrappers/openai_editor.py"

improve-skill skills/<skill> \
  --record-baseline \
  --benchmark-registry benchmarks/<skill>/registry.yaml \
  --auto-edit --apply --max-rounds 3
```

`--max-rounds N` 自动迭代最多 N 轮，每轮把已保留的改进版作为新 baseline。常用 provider 的 wrapper 见 `examples/editor_wrappers/`（OpenAI / Anthropic / Ollama）。

### Benchmark 驱动优化

提供 `--benchmark-registry` 后，judge 时会同时跑 benchmark：Rubric 提升但 benchmark regress → 回滚；benchmark 通过或严格改善，即使 Rubric 提升未达 `min_gain` 也可被接受。

### 安全机制

- `--judge` 默认 **dry-run**，必须 `--apply` 才真正保留/回滚。
- `--ratchet`：分数不低于历史最高，防止质量随修改退化（也可用于 `evaluate-skill --ratchet`）。
- 反模式 guard 自动检查：一轮改多个维度、干跑比例 >30%、`git reset --hard`（发现即 block）、堆冗余凑分、同一模型又改又评、静默跳过异常。

### 可选：LLM-as-judge

对主观维度（D2 文档可理解性、D5 领域准确性）可启用 LLM 第二评委：

```bash
export SKILLPRISM_LLM_JUDGE_COMMAND="python scripts/my_llm_judge.py"

evaluate-skill skills/<skill> --detailed --llm-judge
improve-skill skills/<skill> --judge --llm-judge
```

judge 命令从 stdin 读 prompt，输出 `{"score": 4, "reason": "..."}` JSON。引擎分数与 LLM 分数按权重混合（默认 LLM 占 30%），内置 JSON schema 校验、分数截断、失败重试与 outlier 丢弃。`weight`、`max_retries`、`outlier_threshold`、`require_reason` 均可在 `skill_rubric_types.yaml` 的 `llm_judge` 段配置。

---

## Benchmark 构建与运行

支持的任务类型：

- `clustering`：scRNA-seq 聚类（需 `scanpy`、`scikit-learn`）
- `table`：CSV 表格指标
- `document`：文本/文档生成质量（结构重叠、token Jaccard、长度比，可选 ROUGE-L / BERTScore / 语义相似度）

设计要点：`metrics` 和 `expected` 定义在 `registry.yaml` 的 benchmark 条目里（不放在 task spec）；公共 metric 计算逻辑在 `skillprism/benchmark/metrics.py` 用 `@metric("id")` 注册，各 registry 目录可放私有 `metrics.py`。

### 构建示例

```bash
# 表格任务（--generate-expected 自动生成金标准）
build-skill-test \
  --id tiny_count --name "Tiny Count" \
  --skill my-skill --task table \
  --input data/tiny_counts.csv \
  --expected-path expected/tiny_counts.csv \
  --metric row_count:min:2 --generate-expected \
  --registry benchmarks/my-skill/registry.yaml
```

### 与基线对比（优化/PR 环节）

```bash
python templates/regression_test.py \
    --results latest/<skill>.yaml \
    --baseline baselines/<skill>.yaml
```

---

## 质量流水线（skill-pipeline）

`skill-pipeline` 把 Rubric 评估、Benchmark 运行、回归对比、识别最差 Skill、生成统一报告串成一条命令：

| 意图 | 行为 |
|---|---|
| `"evaluate all skills"` | 只跑 Rubric 评估 |
| `"run benchmarks"` | 只跑 Benchmark 并对比基线 |
| `"run full quality pipeline"` | Rubric → Benchmark → 识别最差 Skill → 生成报告 |
| `"optimize skills"` | 完整流水线 → 为最差 Skill 记录 baseline → 输出下一步 judge 命令 |

```bash
skill-pipeline --intent "run full quality pipeline" \
    --skills-dir ./skills \
    --benchmark-registry ./benchmarks/<skill>/registry.yaml \
    --output reports/SKILL_QUALITY_REPORT.md \
    --run-smoke
```

输出：`reports/SKILL_QUALITY_REPORT.md`（合并报告，含 scorecard、benchmark 结果、最差 Skill 与下一步优化命令）及同目录的内部临时 scorecard（可忽略）。

| 场景 | 推荐方式 |
|---|---|
| 只想看 Rubric 分数 | `evaluate-skill` |
| 只想验证某个 Skill 的 benchmark | `test-skill --mode single --skill ... --code <path>` |
| 想一次性得到完整质量报告 | `skill-pipeline --intent "run full quality pipeline"` |
| 想从最差 Skill 开始优化 | `skill-pipeline --intent "optimize skills"` |

> 实际编辑仍需 Agent 在人工确认下完成；`skill-pipeline` 负责定位目标并准备好测量门控。

---

## 工程工具

```bash
pip install -e ".[dev]"   # 开发安装
make test                 # 运行测试
make coverage             # 测试覆盖率
make lint && make format  # 代码风格
make docs-ci              # CI 全量流程（Rubric + 文档 benchmark）
```

仓库已配置：`pyproject.toml`（pytest、coverage、ruff、mypy）、`.pre-commit-config.yaml`、`.github/workflows/skill-rubric-ci.yaml`（多 Python 版本矩阵 + lint/test/rubric/benchmark/security）、`CONTRIBUTING.md`（开发环境与 PR checklist）。

---

## 项目结构

```
Skills_Validation/
├── skillprism/                    # pip 包：引擎层
│   ├── evaluate_skill_rubric.py   # 评估引擎
│   ├── optimize_skill.py          # 优化测量/回滚引擎
│   ├── gradual.py                 # 渐进失败优先测试模式
│   ├── rubric_enhancements.py     # Rubric 规则增强
│   ├── optimization_strategy.py   # P0-P3 策略库
│   ├── security_evaluator.py      # D9 安全维度评估器
│   ├── benchmark/                 # benchmark 框架（runner/builder/metrics/plugins）
│   ├── ci/                        # CI 流水线
│   └── orchestrator.py            # 质量流水线编排
├── skills/skill-prism/            # Skill 入口层（统一 Agent 入口）
│   ├── SKILL.md
│   └── references/                # AGENT_GUIDE / LLM_JUDGE 等协议文档
├── benchmarks/<skill>/            # per-skill benchmark registry
├── examples/                      # 最小 benchmark、cell2location 四级示例、editor wrappers
├── templates/                     # Skill 模板（analysis/cmd/api/document/skill_standard）+ 回归脚本
├── docs/                          # 文档中心（getting-started / tutorial / reference）
├── tests/                         # pytest 单元测试
├── skill_rubric_types.yaml        # Skill 类型注册表
├── evaluate_skill_rubric.py       # 兼容入口
├── optimize_skill.py              # 兼容入口
└── pyproject.toml                 # pip 包配置
```

---

## 依赖

- Python >= 3.9、PyYAML
- 可选：`shellcheck`（流程型 Skill 的 shell 脚本检查）、`skillspector`（D9 深度安全扫描）、benchmark 任务依赖（`scanpy`、`scikit-learn` 等）

---

## 更多阅读

- [`docs/reference/overview.md`](docs/reference/overview.md)：系统总览（架构、模块边界、数据流）
- [`docs/getting-started/cli-cheatsheet.md`](docs/getting-started/cli-cheatsheet.md)：CLI 与自然语言速查表
- [`docs/reference/framework.md`](docs/reference/framework.md)：Rubric 细节、评分算法、扩展指南
- [`docs/reference/benchmark-guide.md`](docs/reference/benchmark-guide.md)：Benchmark 构建指南
- [`docs/reference/roadmap.md`](docs/reference/roadmap.md)：已完成项与路线图
- [`docs/tutorial/`](docs/tutorial/)：书式教程

---

## 许可证

[MIT](LICENSE)
