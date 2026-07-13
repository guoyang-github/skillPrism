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
│  Layer 1: skillPrism 引擎（纯 Python 包 skillprism）          │
│  7 个 CLI：evaluate-skill / test-skill / build-skill-test /   │
│  improve-skill / skill-pipeline / skill-ci / skill-gradual    │
│  → 无 LLM 依赖、可复现、可测试、可 CI                        │
└─────────────────────────────────────────────────────────────┘
```

**关键原则**：

1. **引擎 LLM-free**：评分、benchmark、回滚全部确定性执行，不依赖任何 LLM provider。Agent 是执行者和 LLM 调用方，引擎只做测量。
2. **LLM 能力可插拔**：自动编辑和 LLM judge 通过外部命令接入，用户选 provider。
3. **结构化文件交换**：Agent 与引擎之间通过 `artifacts/<skill>/` 下的 JSON 文件传递验证结果（schema 见 §7），所有生成物都不写进 skill 树。
4. **人在回路**：默认 dry-run，必须 `--apply` 才真正修改文件。
5. **可扩展**：新 Skill 类型通过 YAML 配置注册，通常不需要改引擎代码。

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

一个 benchmark 目录的结构：

```text
benchmarks/<skill>/
├── registry.yaml        # benchmark 条目 + metrics（metrics 只写在这里）
├── tasks/<task>.yaml    # task spec：prompt 模板 + input/output 契约（无 metrics、无 type 字段）
├── data/                # 输入数据
├── expected/            # 期望输出
└── metrics.py           # 可选：用 @metric 装饰器注册自定义指标
```

**引擎没有内置 task 类型，也不加载任何 `runner.py`**。`task` 只是 registry 引用的 id，其输入/输出契约由 `tasks/<task>.yaml` 定义；指标函数通过 `skillprism.benchmark.metrics` 的 `@metric` 装饰器注册（内置一批通用指标，可用 per-registry `metrics.py` 扩展）。仓库 examples 中提供了 `clustering`、`table`、`document`、`deconvolution` 等任务示例。

Benchmark 框架还支持 `level`（0-3 难度分级）、`requires_gpu`、`real_data` 标记，以及 suite 分组。

### 2.3 Baseline & Judge（基线与回滚）

优化前必须 `--record-baseline`，把当前 Rubric 分数和 benchmark 结果存下来。之后每次编辑用 `--judge` 对比 baseline：

- 分数提升且 benchmark 不 regress → **KEEP**
- 分数没提升、benchmark 退化或触发 guard → **REVERT**

`--apply` 才真正执行 keep/revert。`--ratchet` 保证分数不会低于历史最高。这里的 baseline 指 `improve-skill` 的 scorecard baseline（`artifacts/<skill>/baseline/baseline.json`）——skillPrism 里共有三种 baseline，区别见 §6.3。

---

## 3. CLI 工具职责

skillPrism 共 7 个 CLI（`pip install -e ".[dev]"` 后可用）：

| 命令 | 职责 | 对应 Skill |
|---|---|---|
| `evaluate-skill` | 跑 Rubric，生成 scorecard | `skill-prism` |
| `test-skill --mode single` | 跑单个或某 level/suite 的 benchmark | `skill-prism` |
| `build-skill-test` | 构造 benchmark 定义 | `skill-prism` |
| `skill-ci` | CI 模式下运行 benchmark 并做回归门控 | `skill-prism` |
| `test-skill --mode gradual` | 失败优先的渐进式 benchmark 流水线 | `skill-prism` |
| `skill-gradual` | `test-skill --mode gradual` 的便捷封装（`skillprism.gradual:main`） | `skill-prism` |
| `improve-skill` | 测量、建议、judge、回滚 | `skill-prism` |
| `skill-pipeline` | 评估 + benchmark + 找出最差 + 准备优化 | `skill-prism` |

引擎本身**不调用 LLM**：Agent 是执行者和 LLM 调用方，引擎只做确定性测量，通过 CLI 参数和结构化交换文件（见 §7）消费 Agent 产出的结果。

### 3.1 意图 → 命令映射

`skills/skill-prism/SKILL.md` 是 Agent 的唯一入口，它把自然语言意图翻译成上述 CLI。高频映射：

| 自然语言意图 | Agent 执行动作 |
|---|---|
| "评估这个 skill" | `evaluate-skill skills/<skill>` |
| "跑 benchmark" | `test-skill --mode single --skill <skill> --registry benchmarks/<skill>/registry.yaml` |
| "用代码跑 benchmark" | `test-skill --skill <skill> --registry benchmarks/<skill>/registry.yaml --code <path>` |
| "渐进测试" | `test-skill --mode gradual --skill <skill> --registry benchmarks/<skill>/registry.yaml`（或 `skill-gradual`） |
| "CI 回归门控" | `skill-ci --skill <skill> --registry benchmarks/<skill>/registry.yaml` |
| "优化这个 skill" | `improve-skill skills/<skill> --record-baseline --suggest --judge` |
| "查看优化历史" | `improve-skill skills/<skill> --history` |
| "探索性重写" | `improve-skill skills/<skill> --explore-rewrite --apply` |
| "跑完整流水线" | `skill-pipeline --intent "run full quality pipeline"` |
| "再深入看看可读性和准确性" | `evaluate-skill skills/<skill> --llm-judge --llm-judge-count 3` |
| "验证 test-prompts" | `evaluate-skill skills/<skill> --prompts-verification artifacts/<skill>/prompts_verification.json` |

更多话术见 `skills/skill-prism/references/AGENT_GUIDE.md`。

### 3.2 test-skill 的三种执行模式

`test-skill` 的执行方式由 `--code`、`--results` 和环境变量 `SKILLPRISM_AGENT_COMMAND` 决定（优先级：`--code` > 显式 `--results` > `SKILLPRISM_AGENT_COMMAND` > 默认 results）：

1. **results 模式（默认）**：Agent 已经执行 prompt 并产出结果文件，引擎只验证已有输出，不触发任何执行。这是 Agent 驱动工作流的常态。
2. **external agent 模式**：配置了 `SKILLPRISM_AGENT_COMMAND` 时，引擎调用该外部命令执行任务。**这是引擎唯一会间接触发 LLM 的路径**，且完全由用户配置。
3. **code 模式**：`--code <path>` 时，引擎在沙箱中执行给定代码并评估产出。`--code` 与 `--results` 互斥。

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
3. **Task ↔ Metrics**：**强制相关**。metrics 不写在 task spec 里，而是写在 registry 的 benchmark 条目下（见 §2.2）；指标函数用 `@metric` 装饰器注册，例如 `table` 类任务常用 `row_count`/`col_count`，`clustering` 类任务常用 `n_clusters`/`silhouette_score`。

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
    --output reports/SKILL_SCORECARD.md
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
    --baseline benchmarks/bio-spatial-deconvolution-cell2location/baselines/initial.yaml \
    --suite gradual \
    --ratchet
```

`--baseline` 指向的是**用户自己管理的 benchmark 结果对比文件**（YAML，记录各 benchmark 的指标基线值，惯例放在 `benchmarks/<skill>/baselines/<name>.yaml`，可用 `skill-ci --ratchet` 在全部检查通过后刷新为当前结果），与 `improve-skill` 的 scorecard baseline 不是同一个东西——三种 baseline 的区别见 §6.3。

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
    --benchmark-registry benchmarks/my-skill/registry.yaml \
    --run-smoke
```

（`--benchmark-registry` 换成你自己 skill 的 registry 路径，格式为 `benchmarks/<skill>/registry.yaml`。）

---

## 6. 配置与生成物

### 6.1 `skill_rubric_types.yaml`

唯一的核心配置文件，实际顶层键：

- `scoring`：维度权重（`scoring.weights`）与等级阈值（`grade_thresholds`）。
- `skill_types`：Skill 类型、目录结构要求、每类维度检查规则。
- `llm_tasks`：任务 prompt 模板（供外部 LLM/Agent 使用，引擎不执行）。
- `security`：安全扫描规则。
- `llm_judge`：可选 LLM judge 配置。
- `editor`：可选自动 editor 配置。
- `optimization`：优化循环参数。

（文件中还含 `dimension_names`、`required_frontmatter_base` 等元数据键。）

注意：**这里没有 `benchmarks` 顶层键**。Benchmark 一律定义在 per-skill registry（`benchmarks/<skill>/registry.yaml`，见 §2.2），与本配置文件完全分离。

### 6.2 `artifacts/<skill>/`（生成物，skill 树外）

所有生成物写在项目根的 `artifacts/<skill>/` 下，**绝不写进 skill 树**：

- `baseline/`：`improve-skill` 的 scorecard baseline（见 §6.3 ①）；
- `test-prompts.json` / `llm_judgments.json` / `prompts_verification.json`：结构化交换文件（schema 见 §7）；
- `history.jsonl`：优化历史，每行一条 JSON；
- scorecard：评估结果；
- `ci/`：CI artifacts（`skill-ci` 报告、渐进测试产物，含每级 baseline，见 §6.3 ③）。

跨 skill 的汇总报告写在 `reports/`。

### 6.3 三种 baseline 对照表

"baseline" 在 skillPrism 里有三个互不相同的意思，不要混淆：

| # | 含义 | 位置 | 用途 | 写入命令 |
|---|---|---|---|---|
| ① | **scorecard baseline**（`improve-skill`） | `artifacts/<skill>/baseline/baseline.json`（+ `SKILL.md` 快照、`code_snapshot/`、滚动备份） | Rubric 分数与维度分的基线，judge keep/revert 与 `--ratchet` 的真相源；原子写 + flock 锁（`optimize.lock`） | `improve-skill <skill> --record-baseline` |
| ② | **benchmark 回归对比文件**（用户管理） | 用户指定路径，惯例 `benchmarks/<skill>/baselines/<name>.yaml` | 记录各 benchmark 指标基线值，供 `skill-ci --baseline <path>` 做回归对比 | `skill-ci --ratchet`（全部检查通过后刷新），或手工维护 |
| ③ | **gradual 每级 baseline** | `artifacts/<skill>/ci/gradual/.baselines/<skill>/gradual_baseline_level<N>.yaml` | 渐进测试每个 level 独立 ratchet，失败即停 | `test-skill --mode gradual` / `skill-gradual` 自动维护（`--no-ratchet` 可禁用） |

---

## 7. 结构化交换文件

Agent 与引擎之间通过 `artifacts/<skill>/` 下的结构化 JSON 文件交换结果：**Agent 产生，引擎消费**。引擎不执行 prompt、不调用 LLM。以下 schema 以 `skills/skill-prism/references/` 下的权威参考为准。

### 7.1 `test-prompts.json`

2–3 条代表性 prompt，Agent 撰写（引擎模板仅为兜底占位）。覆盖 happy path / ambiguous / boundary 三种场景：

```json
[
  {
    "id": 1,
    "scenario": "happy path",
    "prompt": "用 pbmc3k 数据做单细胞聚类，输出 h5ad。",
    "expected": "输出文件存在，obs 中含 leiden 列，cluster 数在 5–15 之间。"
  }
]
```

要求：具体输入 + 具体可验证的期望，禁止 "Use the X skill to ..." 这类元指令。详见 `skills/skill-prism/references/PROMPTS_VERIFICATION.md`。

### 7.2 `llm_judgments.json`

多评委 LLM judge 结果（Agent 生成，引擎自动发现；也可 `evaluate-skill --llm-judgments <path>` 显式传入）：

```json
{
  "judges": [
    {
      "dimension": "D2",
      "scores": [4, 5],
      "reasons": ["Clear examples.", "Well structured."],
      "aggregated_score": 4,
      "aggregate": "median",
      "model": "moonshot-v1-8k",
      "temperature": 0.2,
      "prompt_version": "1.0"
    }
  ]
}
```

- `dimension`：D2 / D5 / D6 / D8；
- `scores` / `reasons`：每个独立 judge 的结果，长度一致；
- `aggregated_score`：1–5 整数；`aggregate`：`median` / `mean` / `min` / `max`；
- `model` / `temperature` / `prompt_version`：可复现性元数据（Agent 生成时必须带上）。

详见 `skills/skill-prism/references/LLM_JUDGE.md`。

### 7.3 `prompts_verification.json`

test-prompts 的 with/without 对比验证结果（Agent 按验证协议生成，引擎自动发现；也可 `evaluate-skill --prompts-verification <path>` 显式传入）：

```json
{
  "skill": "<skill-name>",
  "results": [
    {
      "prompt_id": 1,
      "prompt": "...",
      "without_skill_output": "...",
      "with_skill_output": "...",
      "expected": "...",
      "improvement_score": 1.0,
      "passed": true,
      "eval_mode": "full_test"
    }
  ]
}
```

- `improvement_score`：0.0–1.0，由独立 judge 子 agent 给出；
- `passed`：with-skill 输出是否满足 expected；
- `eval_mode`：`full_test`（真实执行）/ `dry_run`（未执行、凭推测填写）。`dry_run` 占比 > 30% 时引擎告警，D8 分数不可信。

引擎行为：pass_rate < 50% → D6/D8 减 1 分；≥ 90% → 加 1 分。完整协议（三个独立子 agent、不得修改被测 skill）见 `skills/skill-prism/references/PROMPTS_VERIFICATION.md`。

---

## 8. LLM 在 skillPrism 中的边界

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

### 设计禁忌：不要给引擎加交互层包装

- **不要**围绕 skillPrism 构建 chatbot 包装或 REST API：引擎是确定性 Python 库 + CLI，交互层就是 Agent（`skills/skill-prism/SKILL.md`）。
- **不要**让引擎解析自然语言意图——意图翻译是 Agent 的职责。
- **不要**把 LLM judge 逻辑嵌入引擎——judge 通过外部命令或结构化文件接入。

---

## 9. 扩展点

### 9.1 加新 Skill 类型

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

### 9.2 加新 benchmark 任务

引擎没有内置 task 类型，也**不需要实现 `runner.py`**。加一个任务只需两步：

1. 写 task spec `benchmarks/my-skill/tasks/my-task.yaml`（prompt 模板 + input/output 契约，无 metrics、无 type 字段）；
2. 在 registry 里登记 benchmark 条目，metrics 直接写在条目下：

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

需要自定义指标时，在 registry 目录放 `metrics.py`，用 `@metric` 装饰器注册：

```python
from pathlib import Path
from typing import Any, Dict, Optional

from skillprism.benchmark.metrics import metric

@metric("exact_match")
def exact_match(actual_path: Path, expected_path: Optional[Path], task_spec: Dict[str, Any]) -> bool:
    ...
```

### 9.3 生成测试数据

`skillprism.testing.mock_data` 提供合成数据生成器，帮助 benchmark 不依赖真实大数据：

```python
from skillprism.testing.mock_data import generate_visium_data
adata_sp, adata_ref = generate_visium_data(n_spots=200, n_cells_ref=500)
```

### 9.4 CI 与渐进测试

- `skillprism.ci.pipeline` 可直接嵌入 CI workflow；
- `test-skill --mode gradual` 为昂贵 Skill 提供失败优先的 level 0→3 渐进式测试。

### 9.5 自定义 editor 或 judge

只要命令满足 stdin→stdout 约定即可：

- editor：读 prompt，输出完整 SKILL.md。
- judge：读 prompt，输出 `{"score": int, "reason": str}`。

---

## 10. 工程特性总览

skillPrism 内置以下经过实践验证的质量机制：9 维 rubric + 规则增强（模糊词、AI 腔废话、失败模式编码、检查点标记、体积控制）、多评委 LLM judge（默认 n=2）、test-prompts 自动生成与验证、P0-P3 优化策略库、维度相关簇分析、探索性重写、runtime neutrality 红灯扫描、实验历史 JSONL 跟踪、干跑比例告警（dry_run > 30%）、单轮单维度约束、反模式 guard、dry-run judge + `--apply` 人在回路、ratchet/回归门控，以及 `test-skill --mode gradual` 失败优先的 level 0→3 渐进测试（每级独立 baseline、真实数据 completion-only 验收、GPU-only benchmark 自动跳过）。逐项状态见 `docs/reference/roadmap.md`，机制细节见 `docs/reference/rubric-enhancements.md`、`docs/reference/optimization-strategy.md` 等专题文档。

工程独立性：

- 引擎无 LLM 依赖；
- 可安装为 Python 包；
- 支持任意 editor/judge 命令。

---

## 11. 文档地图

| 文档 | 阅读场景 |
|---|---|
| `README_CN.md` / `README.md`（英文） | 快速开始、安装、CLI 速查 |
| `docs/reference/overview.md`（本文） | 理解整体架构与设计 |
| `docs/reference/framework.md` | Rubric 细节、评分算法、扩展指南 |
| `docs/getting-started/cli-cheatsheet.md` | CLI 与自然语言速查表：想做什么、对 Agent 怎么说、对应 CLI 与关键参数 |
| `docs/reference/benchmark-guide.md` | 如何构造 benchmark |
| `docs/reference/cell2location.md` | cell2location 渐进四级示例完整指南 |
| `docs/tutorial/08-gradual-testing-and-real-data.md` | 教程第 8 章：渐进测试失败优先策略与真实数据验收 |
| `docs/reference/roadmap.md` | 已完成项与待办 |
| `skills/skill-prism/references/AGENT_GUIDE.md` | Agent 与 skillPrism 交互的标准话术 |
| `skills/skill-prism/references/LLM_JUDGE.md` | `llm_judgments.json` 权威 schema 与 judge 协议 |
| `skills/skill-prism/references/PROMPTS_VERIFICATION.md` | test-prompts 验证协议与 `prompts_verification.json` 权威 schema |
| `skills/skill-prism/SKILL.md` | 统一 Agent 入口：evaluate / test / improve / pipeline / ci |
| `examples/editor_wrappers/README.md` | 接入 OpenAI/Anthropic/Ollama/国产模型 |
| `examples/benchmark_cell2location/README.md` | 可一键运行的 渐进四级 benchmark 示例 |

---

## 12. 一句话总结

> **skillPrism = 无 LLM 依赖的 Skill 评估/验证引擎 + 可选的 LLM 自动编辑 + 可选的 LLM judge，通过 YAML 配置扩展，通过 `--apply` 和 guard 保证人在回路。**
