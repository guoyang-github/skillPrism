# skillPrism 体系概览

> 一份从 0 到 1 理解 skillPrism 的入口文档。

skillPrism 是一个**项目无关、可安装、可扩展的 AI Agent Skill 质量基础设施**。它把 Skill 的质量拆成三个可独立演进的部分：

- **评估（Rubric）**：静态检查 SKILL.md 和配套资产是否规范。
- **验证（Benchmark）**：用真实任务验证 Skill 是否正确、是否退化。
- **优化（Optimization）**：在测量门控下迭代改进 SKILL.md。

三者共享同一套配置（`skill_rubric_types.yaml`）和同一套 CLI，可以被 Agent、CI 或人工直接调用。

---

## 1. 核心设计：三层分离

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: Skill 入口（自然语言操作）                          │
│  skills/skill-prism/SKILL.md                                  │
│  → 统一 Agent 入口，告诉 Agent/用户怎么跑命令、什么时候该确认  │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  Layer 2: 可选能力（用户选择接入）                            │
│  - SKILL.md editor 命令（--auto-edit）                        │
│  - LLM-as-judge（--llm-judge）                                │
│  → 只通过 stdin/stdout 与环境变量接入，引擎不依赖具体 provider │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  Layer 1: skillPrism 引擎（纯 Python 包）                     │
│  evaluate_skill_rubric.py                                     │
│  optimize_skill.py                                            │
│  benchmark/runner.py                                          │
│  → 无 LLM 依赖、可复现、可测试、可 CI                        │
└─────────────────────────────────────────────────────────────┘
```

**关键原则**：

1. **引擎 LLM-free**：评分、benchmark、回滚全部确定性执行，不依赖任何 LLM provider。
2. **LLM 能力可插拔**：自动编辑和 LLM judge 通过外部命令接入，用户选 provider。
3. **人在回路**：默认 dry-run，必须 `--apply` 才真正修改文件。
4. **可扩展**：新 Skill 类型通过 YAML 配置注册，通常不需要改引擎代码。

---

## 2. 三个核心概念

### 2.1 Rubric（评分卡）

每个 Skill 从 9 个维度打分，每个维度 1-5 分，按权重融合为百分制：

| 维度 | 关注点 | 是否客观可自动检查 |
|---|---|---|
| D1 结构与元数据 | frontmatter、目录结构、命名 | ✅  mostly |
| D2 文档可理解性 | 输入输出、示例、pitfalls | ⚠️ 部分；可选 LLM judge |
| D3 可执行性/正确性 | 代码能否跑、语法、边界 | ✅  mostly |
| D4 环境/依赖可复现 | requirements、版本、安装说明 | ✅  mostly |
| D5 领域准确性 | 方法、参数、引用是否正确 | ⚠️ 部分；可选 LLM judge |
| D6 LLM 可调用性 | Agent 何时该用、输入输出明确 | ✅  mostly |
| D7 性能/鲁棒性 | 资源、时间、大输入处理 | ⚠️ 部分 |
| D8 可维护性 | 模块化、注释、CHANGELOG | ✅  mostly |
| D9 安全与可信 | 危险命令、隐私、扫描 | ✅  mostly |

权重和维度名称写在 `skill_rubric_types.yaml`，不同 Skill 类型可以有不同的 D5 定义。

### 2.2 Benchmark（任务级验证）

Rubric 是静态评分，Benchmark 是动态验证。Benchmark 定义在独立的 per-skill registry YAML 文件中（例如 `benchmarks/<skill>/registry.yaml`），通过 `test-skill --registry <path>` 加载，而不是写在 `skill_rubric_types.yaml` 里：

```yaml
benchmarks:
  document-generation:
    skill: document
    task: document
    input:
      path: "data/document_prompt.txt"
    expected:
      path: "expected/document_output.txt"
    metrics:
      - id: section_overlap
        type: min
        threshold: 0.6
      - id: token_jaccard
        type: min
        threshold: 0.3
      - id: length_ratio
        type: range
        min: 0.5
        max: 2.0
```

支持的任务类型：

- `clustering`：scRNA-seq 聚类（需 scanpy/sklearn）。
- `table`：CSV 表格任务。
- `document`：文本/文档生成，支持 ROUGE-L、BERTScore、语义相似度等可选指标。
- `deconvolution`：空间转录组去卷积，输出细胞类型比例矩阵。

Benchmark 框架还支持 `level`（0-3 难度分级）、`requires_gpu`、`real_data` 标记，以及 suite 分组。

### 2.3 Baseline & Judge（基线与回滚）

优化前必须 `--record-baseline`，把当前 Rubric 分数和 benchmark 结果存下来。之后每次编辑用 `--judge` 对比 baseline：

- 分数提升且 benchmark 不 regress → **KEEP**
- 分数没提升、benchmark 退化或触发 guard → **REVERT**

`--apply` 才真正执行 keep/revert。`--ratchet` 保证分数不会低于历史最高。

---

## 3. CLI 工具职责

| 命令 | 职责 | 对应 Skill |
|---|---|---|
| `evaluate-skill` | 跑 Rubric，生成 scorecard | `skill-prism` |
| `test-skill --mode single` | 跑单个或某 level/suite 的 benchmark | `skill-prism` |
| `build-skill-test` | 构造 benchmark 定义 | `skill-prism` |
| `skill-ci` | CI 模式下运行 benchmark 并做回归门控 | `skill-prism` |
| `test-skill --mode gradual` | 失败优先的渐进式 benchmark 流水线 | `skill-prism` |
| `improve-skill` | 测量、建议、judge、回滚 | `skill-prism` |
| `skill-pipeline` | 评估 + benchmark + 找出最差 + 准备优化 | `skill-prism` |

## 4. Skill 类型、Task、`--skill` 的关系

这是最容易混淆的三组概念：

| 概念 | 定义 | 出现在哪 | 示例 |
|---|---|---|---|
| **Skill 类型** | SKILL.md 的"分类标签"，决定 Rubric 怎么评判 | `skill_rubric_types.yaml` 的 `skill_types` | `analysis`、`cmd`、`api`、`document`、`generic` |
| **Task** | Benchmark 的输入/输出契约，决定数据怎么加载、注入哪些变量、用什么指标 | `benchmarks/<skill>/registry.yaml` 的 `task` 字段 | `table`、`clustering`、`document`、`deconvolution` |
| **`--skill`** | benchmark 的**关联标签**：告诉 `test-skill --skill` 这个 benchmark 属于谁 | `build-skill-test --skill` | `analysis`、`my-first-table` |

### `--skill` 到底填 skill 名称还是 skill 类型？

**都可以。** registry 里的 `skill` 字段是 benchmark 关联的 skill 名称，`test-skill` 用 `--skill <name>` 去做字符串匹配。

- 填 **skill 名称**（推荐）：`--skill my-first-table`。这个 benchmark 只给 `my-first-table` 用，最精确。
- 填 **skill 类型**：`--skill analysis`。如果某个 skill 的类型名恰好是 `analysis`，也能匹配到。

### 三者关系

1. **Skill 类型 ↔ `--skill`**：`--skill` 可以等于某个 Skill 类型（如 `analysis`），也可以等于具体 skill 名（如 `my-first-table`）。
2. **Skill 类型 ↔ Task**：**没有强制绑定**，只有常见对应。`analysis` 类型 skill 可以测 `table`、`clustering`、`deconvolution`；`document` 类型 skill 通常测 `document`。
3. **Task ↔ Metrics**：**强制相关**。每个 task 有默认 metrics 模板，例如 `table` 用 `row_count`/`col_count`，`clustering` 用 `n_clusters`/`silhouette_score`。

简记：

- **Skill 类型 = 怎么评文档**
- **Task = 怎么测代码**
- **`--skill` = 这个测试给谁用**

安装后即可使用：

```bash
pip install -e ".[dev]"
```

---

## 5. 典型工作流

### 5.1 一次性评估

```bash
evaluate-skill --all --skills-dir ./skills --run-smoke \
    --output docs/SKILL_SCORECARD.md
```

### 5.2 运行 benchmark

```bash
test-skill --mode single --skill document-demo \
    --code examples/benchmark_minimal/sample_skill_code.py \
    --registry examples/benchmark_minimal/benchmarks/document-demo/registry.yaml \
    --task document
```

### 5.3 手动优化 loop

```bash
improve-skill skills/foo --record-baseline
improve-skill skills/foo --suggest
# 手动编辑 skills/foo/SKILL.md
improve-skill skills/foo --judge
improve-skill skills/foo --judge --apply
```

### 5.4 自动优化 loop

配置 editor 命令（可用 OpenAI、Anthropic、Ollama 或国产 OpenAI 兼容模型）：

```bash
export SKILLPRISM_EDITOR_COMMAND="python examples/editor_wrappers/openai_editor.py"

improve-skill skills/foo \
  --record-baseline \
  --benchmark-registry examples/benchmark_minimal/benchmarks/document-demo/registry.yaml \
  --auto-edit \
  --apply \
  --max-rounds 3
```

### 5.5 CI 回归门控

```bash
skill-ci \
    --skill bio-spatial-deconvolution-cell2location \
    --registry examples/benchmark_cell2location/benchmarks/bio-spatial-deconvolution-cell2location/registry.yaml \
    --baseline examples/benchmark_cell2location/baselines/bio-spatial-deconvolution-cell2location.yaml \
    --suite darwin \
    --ratchet
```

### 5.6 渐进测试流水线

对计算昂贵的 Skill，从 level 0 单元测试逐级放行到真实数据：

```bash
test-skill --mode gradual \
    --skill bio-spatial-deconvolution-cell2location \
    --registry examples/benchmark_cell2location/benchmarks/bio-spatial-deconvolution-cell2location/registry.yaml \
    --max-level 2
```

### 5.7 完整质量流水线

```bash
skill-pipeline --intent "run full quality pipeline" \
    --skills-dir ./skills \
    --benchmark-registry ./benchmarks/skill-prism/registry.yaml \
    --run-smoke
```

---

## 6. 配置文件

### `skill_rubric_types.yaml`

唯一的核心配置文件，定义：

- `skill_types`：Skill 类型、目录结构要求、每类维度检查规则。
- `scoring.weights`：维度权重与等级阈值。
- `dimension_names`：D1–D9 的中文/英文名。
- `benchmarks`：任务、数据集、指标、通过阈值。
- `llm_judge`：可选 LLM judge 配置。
- `editor`：可选自动 editor 配置。

### `.skillprism_baseline.json` & `.skillprism_baseline/`

每个 Skill 目录下自动生成的 baseline 文件，记录：

- 当前 Rubric 分数和维度分；
- benchmark 结果；
- 历史最高分（用于 ratchet）；
- 渐进测试模式下每级独立的 baseline（`gradual_baseline_level<N>.yaml`）；
- SKILL.md 副本与代码资产快照（无 git 时用于回滚）。

---

## 7. LLM 在 skillPrism 中的边界

skillPrism **不内置 LLM**，但有三处可以接入 LLM：

| 位置 | 作用 | 是否必需 |
|---|---|---|
| `--auto-edit` editor 命令 | 自动改写 SKILL.md | 否 |
| `--llm-judge` judge 命令 | 给 D2/D5 提供第二意见 | 否 |
| Agent 自身（Skill 入口） | 解释结果、展示 diff、人工确认 | 是（Agent 天然有 LLM） |

这样设计的好处：

- CI 可以不配置 API key 就跑完整 Rubric 和 benchmark。
- 不会被某个 LLM provider 锁定。
- 测量结果可复现。

---

## 8. 扩展点

### 8.1 加新 Skill 类型

编辑 `skill_rubric_types.yaml`：

```yaml
skill_types:
  my-type:
    required_files: [SKILL.md]
    required_frontmatter: [name, description, keywords]
    dimension_checks:
      D4: {required_files: [requirements.txt]}
```

只要检查基于文件存在性和关键词匹配，就无需改引擎。

### 8.2 加新 benchmark 任务

实现 `<task>/runner.py` 并注册到 YAML：

```yaml
# benchmarks/my-skill/registry.yaml
benchmarks:
  my-task:
    skill: my-skill
    task: my-task
    level: 1
    input:
      path: data/input.txt
    expected:
      path: expected/output.txt
    metrics:
      - id: exact_match
        type: exact
        expected: true
```

### 8.3 生成测试数据

`skillprism.testing.mock_data` 提供合成数据生成器，帮助 benchmark 不依赖真实大数据：

```python
from skillprism.testing.mock_data import generate_visium_data
adata_sp, adata_ref = generate_visium_data(n_spots=200, n_cells_ref=500)
```

### 8.4 CI 与渐进测试

- `skillprism.ci.pipeline` 可直接嵌入 CI workflow；
- `test-skill --mode gradual` 为昂贵 Skill 提供失败优先的 level 0→3 渐进式测试。

### 8.5 自定义 editor 或 judge

只要命令满足 stdin→stdout 约定即可：

- editor：读 prompt，输出完整 SKILL.md。
- judge：读 prompt，输出 `{"score": int, "reason": str}`。

---

## 9. 与 darwin-skill 的关系

skillPrism 受 darwin-skill 启发，并已吸收其实证验证过的最佳实践：

- 9 维 rubric + 规则增强（模糊词、AI 腔废话、失败模式编码、检查点标记、体积控制）；
- 多评委 LLM judge（默认 n=2）；
- test-prompts 自动生成与验证；
- P0-P3 优化策略库；
- 维度相关簇分析；
- 探索性重写；
- runtime neutrality 红灯扫描；
- 实验历史 JSONL 跟踪；
- 干跑比例控制与警告（dry_run > 30% 告警）；
- 异常与边界处理（自动 git init、revert fallback、体积守卫）；
- 单轮单维度约束；
- 视觉成果卡片（可选 reporter）；
- dry-run judge + `--apply` 人在回路；
- 反模式 guard；
- ratchet/回归门控；
- benchmark 验证。

现在 skillPrism 还直接实现了 darwin-skill 的核心测试策略：

- `test-skill --mode gradual` CLI：level 0→3 失败优先的渐进式 benchmark；
- 每级独立 baseline 与 ratchet；
- 真实数据 benchmark 只做 completion-only 验收；
- GPU-only benchmark 在无 GPU 环境自动跳过。

但 skillPrism 仍保持**完全独立**：

- 不依赖 darwin-skill 代码；
- 引擎无 LLM；
- 可安装为 Python 包；
- 支持任意 editor/judge 命令。

---

## 10. 文档地图

| 文档 | 阅读场景 |
|---|---|
| `README.md` / `README_EN.md` | 快速开始、安装、CLI 速查 |
| `docs/reference/overview.md`（本文） | 理解整体架构与设计 |
| `docs/reference/framework.md` | Rubric 细节、评分算法、扩展指南 |
| `docs/reference/operational-playbook.md` | 自然语言交互操作手册：从安装、数据准备到评估/优化/流水线的 step-by-step 指南 |
| `docs/reference/benchmark-guide.md` | 如何构造 benchmark |
| `docs/reference/cell2location.md` | cell2location 渐进四级示例完整指南 |
| `docs/reference/gradual-testing.md` | 渐进测试失败优先测试策略 |
| `docs/tutorial/08-gradual-testing-and-real-data.md` | 教程第 8 章：渐进测试与真实数据验收 |
| `docs/reference/roadmap.md` | 已完成项与待办 |
| `skills/skill-prism/references/AGENT_GUIDE.md` | Agent 与 skillPrism 交互的标准话术 |
| `skills/skill-prism/SKILL.md` | 统一 Agent 入口：evaluate / test / improve / pipeline / ci |
| `examples/editor_wrappers/README.md` | 接入 OpenAI/Anthropic/Ollama/国产模型 |
| `examples/benchmark_cell2location/README.md` | 可一键运行的 渐进四级 benchmark 示例 |

---

## 11. 一句话总结

> **skillPrism = 无 LLM 依赖的 Skill 评估/验证引擎 + 可选的 LLM 自动编辑 + 可选的 LLM judge，通过 YAML 配置扩展，通过 `--apply` 和 guard 保证人在回路。**
