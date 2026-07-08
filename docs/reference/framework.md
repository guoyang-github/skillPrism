# Skill 评估与持续优化框架

> 适用于各类 AI Agent Skill（如生信分析、基因组学流程、数据库 API、科学写作等）的系统性评估、打分、迭代与维护。
> 
> 目标：建立一套可复现、可量化、可持续的 Skill Quality Assurance（SQA）体系。
>
> 如果你是第一次接触 skillPrism，建议先阅读 [体系概览](overview.md) 以理解整体架构，本文是深度参考手册。

---

## 一、总体方法论：Rubric-PDCA 闭环

将每个 Skill 视为一个交付单元，采用 **Rubric 多维评分 + PDCA 循环优化** 的组合方法：

```
        ┌─────────────────────────────────────────┐
        │  Plan：制定/更新 Rubric 与优化目标        │
        │  （定义「好技能」的标准与优先级）          │
        └─────────────────┬───────────────────────┘
                          ▼
        ┌─────────────────────────────────────────┐
        │  Do：执行多维度评估（自动+人工）          │
        │  （结构、代码、文档、可运行性、LLM 效果）   │
        └─────────────────┬───────────────────────┘
                          ▼
        ┌─────────────────────────────────────────┐
        │  Check：汇总评分、定位短板、产出报告       │
        │  （量化得分、识别关键缺陷、排序优化项）      │
        └─────────────────┬───────────────────────┘
                          ▼
        ┌─────────────────────────────────────────┐
        │  Act：修复、验证、归档并更新基线           │
        │  （改什么、怎么改、改完如何验证）           │
        └─────────────────────────────────────────┘
                          │
                          └──────▶ 回到 Plan
```

**核心原则**：

1. **量化优先**：每个维度必须给出 1-5 分的可解释分数，避免「感觉还行」。
2. **自动为先**：能用脚本/CI 检查的项，不要依赖人工；人工只做语义与领域判断。
3. **以 LLM 最终效果为北极星**：Skill 的好坏最终体现为 LLM Agent 调用该技能时能否一次正确完成用户任务。
4. **小步快跑**：每次优化聚焦 1-2 个最高收益维度，避免一次性重写。

---

## 二、评估维度 Rubric（1-5 分制）

每个 Skill 从以下 **9 个维度**评估，每个维度 1-5 分。权重通过 `skill_rubric_types.yaml` 的 `scoring.weights` 配置，可直接修改而无需改引擎。

### 2.1 维度定义与评分标准

| 维度 | 权重建议 | 1 分（差） | 3 分（及格） | 5 分（优秀） |
|---|---|---|---|---|
| **D1 目录与元数据规范** | 0.10 | 缺少 SKILL.md 或 frontmatter 错误；命名不规范 | 基本文件齐全，frontmatter 完整，命名合规 | 目录结构完全符合模板；元数据精准；依赖锁定完整 |
| **D2 文档可理解性** | 0.15 | 文档混乱，缺少输入输出说明，示例无法运行 | 章节完整，示例可运行，参数表清晰 | 文档自解释；决策树/选择表丰富；示例覆盖常见场景 |
| **D3 代码正确性** | 0.18 | 存在明显 Bug 或语法错误；运行即报错 | 主要流程可运行，偶发边界问题 | 代码健壮；边界处理完善；异常信息明确；有单元测试 |
| **D4 工具依赖可复现** | 0.12 | requirements 缺失或版本冲突严重 | requirements/renv 存在且基本可安装 | 提供 conda/renv/docker 锁定；CI 安装通过；版本兼容说明清晰 |
| **D5 领域准确性** | 0.15 | 算法或参数使用明显错误；误导用户 | 方法选择基本合理，参数范围合理 | 方法经过文献/基准验证；参数建议有依据；pitfalls 完整 |

> D5 的具体含义由 `skill_rubric_types.yaml` 中每个 `skill_type` 自行定义。例如生信类型可命名为“生物信息学准确性”，API 类型可命名为“API 准确性”，文档类型可命名为“文档准确性”。引擎检查通用要素（引用、参数、pitfalls），语义层面的准确性可由 Agent 或外部 judge 做第二意见（`--llm-judge`）。
| **D6 LLM 可调用性** | 0.10 | Agent 无法识别何时该用该 Skill | description 清晰，keyword 充分 | 提供「何时使用/何时不用」决策表；示例可直接被 Agent 复制执行 |
| **D7 性能与资源友好** | 0.08 | 默认参数内存/时间不可接受 | 中等数据集可在合理时间内跑完 | 提供性能提示；支持降采样；大内存步骤有警告 |
| **D8 可维护性** | 0.04 | 函数无注释；逻辑耦合严重 | 函数模块化，有基础注释 | 代码风格一致；docstring 完整；CHANGELOG/维护者信息清晰 |
| **D9 安全与可信** | 0.08 | 存在数据泄露、任意执行、硬编码密钥等高风险模式 | 无高风险模式；有基本数据隐私说明 | 通过外部安全扫描；明确声明数据隐私、随机种子、可复现性 |

> **评分实现说明**：D2、D5、D7 以及 D9 的部分检查当前基于**关键词、正则和简单结构启发式**（如是否出现 `#`、`|`、`version`、`reference`、`memory`、特定风险模式等）。这些指标运行快速、无需 LLM，适合 CI 场景，但**不是完美的质量代理**——它们可能被关键词堆砌绕过，也可能对合法用法误报。建议将 Rubric 分数作为持续改进的指引，对关键技能结合 `--llm-judge`、benchmark 结果和人工复核进行综合判断。

**总分计算**：

```
Score = Σ (维度得分 × 权重) / 5 × 100   # 转换为百分制
```

**等级划分**（供参考）：

- **A（90-100）**：标杆 Skill，可作为模板。
- **B（75-89）**：良好，有少量优化空间。
- **C（60-74）**：可用，但必须修复明显缺陷。
- **D（<60）**：不建议上线，需重写或下线。

### 2.2 评分配置化

所有权重、等级阈值均写入 `skill_rubric_types.yaml`。引擎只做客观评分，不涉及 LLM 实测融合：

```yaml
scoring:
  weights:
    D1: 0.10
    D2: 0.15
    D3: 0.18
    D4: 0.12
    D5: 0.15
    D6: 0.10
    D7: 0.08
    D8: 0.04
    D9: 0.08
  grade_thresholds:
    A: 90
    B: 75
    C: 60
```

最终显示分 = 静态 Rubric 分。LLM 驱动的验证/优化由 Agent 通过 Skill 入口完成，不混入引擎评分。

### 2.3 安全维度 D9 与 NVIDIA SkillSpector

D9 的设计参考了 NVIDIA SkillSpector（2026）的两阶段安全扫描思想：

1. **静态模式扫描**：检测环境变量收集、外部网络传输、任意代码执行（eval/exec/subprocess/os.system）、硬编码密钥、路径遍历、提示注入标记、过度代理声明等。
2. **外部扫描器集成**（可选）：如果安装了 `skillspector`，评估引擎可调用其 CLI 并将结果合并到 D9。

D9 不是替代安全审计，而是把安全作为 Skill 质量的一个可量化维度纳入 Rubric。

---

## 三、评估执行流程（Checklist）

### 3.1 自动化初筛（脚本/CI）

对目标项目的 skills 目录批量运行以下检查（具体命令需根据项目实际工具链调整）：

```bash
# 1. 元数据与结构检查（示例）
python validate_skill.py skills/<skill-name>

# 2. 代码静态检查
ruff check skills/<skill-name>/scripts/python/      # Python
lintr skills/<skill-name>/scripts/r/                # R

# 3. 依赖可安装性检查
pip install -r skills/<skill-name>/requirements.txt --dry-run
Rscript -e "renv::restore(lockfile='skills/<skill-name>/renv/renv.lock')"

# 4. 示例可运行性（冒烟测试）
pytest tests/ -v -k <skill-name>
```

**自动化产出**：

- 每个 Skill 的 PASS/FAIL 列表
- 关键错误汇总（frontmatter 非法、依赖冲突、代码语法错误等）

### 3.2 人工领域评审

由具备生物信息学背景的人员，依据 Rubric 逐项打分。建议两人独立打分后取平均或讨论校准。

**评审工具**：使用本框架附带的评分表（见第 6 节）。

### 3.3 LLM 驱动的验证（由 Agent / Skill 完成）

引擎本身不调用 LLM。LLM 效果验证应作为 Agent 工作流的一部分，由 `skills/skill-prism` 或类似的 Agent Skill 完成：

1. Agent 读取 SKILL.md。
2. Agent 使用自身 LLM 模拟真实调用场景：
   - **直接任务**：「用 X 工具对 PBMC 数据做 Y 分析」
   - **边界任务**：「数据没有 label，如何处理？」
   - **错误恢复任务**：「运行时报 Z 错误，怎么解决？」
3. Agent 检查生成的代码/命令是否合理、可运行。
4. 将发现的问题反馈到 SKILL.md 优化循环。

**任务模板参考**：可在 `skill_rubric_types.yaml` 的 `llm_tasks` 段保存常用 prompt 模板，供 Agent Skill 引用。

---

## 四、Rubric 循环优化流程

### 4.1 周期建议

| 活动 | 频率 | 责任人 |
|---|---|---|
| 自动化初筛 | 每次 PR / 每周一次 | CI / 维护脚本 |
| 全量 Rubric 评分 | 每季度一次 | 领域专家 + QA |
| LLM 驱动验证 | 每季度一次 + 新 Skill 上线前 | Agent / LLM 评测小组 |
| 标杆 Skill 评选 | 每半年一次 | 项目委员会 |

### 4.2 优化优先级矩阵

根据评分结果，将 Skill 落入以下矩阵：

```
            高影响（常用/核心）
                   ▲
                   │  重点优化区      标杆候选区
                   │  (Fix First)     (Promote)
                   │
    低使用率 ◄─────┼────────────────────────►  高使用率
                   │
                   │  观察/下线区     快速修补区
                   │  (Deprecate)     (Quick Patch)
                   ▼
            低影响（边缘/少用）
```

**处理策略**：

- **标杆候选区**：整理为模板，推广最佳实践。
- **重点优化区**：投入主要资源，按 Rubric 短板逐项修复。
- **快速修补区**：修复关键缺陷即可，不必追求完美。
- **观察/下线区**：评估是否保留；若无维护价值，移入 `skills_bak/` 或归档。

### 4.3 单次优化迭代步骤

1. **定位短板**：从评分表中找出得分最低的 1-2 个维度。
2. **制定修复计划**：明确改动点、预期得分提升、验证方式。
3. **执行修复**：优先修改 SKILL.md、示例代码、依赖配置。
4. **验证**：
   - 自动化检查通过
   - 示例代码可运行
   - Rubric 复评得分提升
   - LLM 实测任务通过
5. **归档**：更新 `SKILL_REVIEW_REPORT.md` 或创建版本化审计报告。

### 4.4 金标准 Benchmark 与 Rubric-PDCA 的融合

金标准 Benchmark 不是独立于 Rubric 的「另一套测试」，而是为 D3（可执行性/正确性）和 D5（领域准确性）提供**客观证据**的输入。

#### 一致性评价方法

对每次 Skill 修改，比较当前输出与金标准参考结果的一致性：

| 一致性层级 | 含义 | 判定方式 |
|---|---|---|
| **L1 结构一致** | 输出文件/格式与 expected 一致 | 文件存在、列名/obs 名匹配 |
| **L2 指标一致** | 关键量化指标在阈值范围内 | metric spec 全部通过 |
| **L3 分布一致** | 输出分布与参考分布无显著偏移 | tolerance / relative gate |
| **L4 LLM 可用** | LLM 能用当前输出完成下游任务 | LLM 实测下游任务通过 |

#### 与 Rubric-PDCA 闭环的配合

```
Plan: 设定 Benchmark 通过标准（metric thresholds）和 Rubric 目标分
   │
   ▼
Do:  修改 Skill + 跑自动化 Rubric + 跑 Benchmark 回归
   │
   ▼
Check: 比较当前指标 vs 基线；Rubric 短板是否改善；LLM 实测是否通过
   │
   ▼
Act:   通过则更新 baseline；失败则回滚或继续优化
   │
   └────▶ 回到 Plan
```

**操作要点**：

- Benchmark 回归测试必须在 PR 合并前通过（Hard Gate）。
- Rubric 复评在每次修改后执行，量化「改了多少分」。
- LLM 实测每季度/重大修改后执行，验证「Agent 还能不能用它干活」。
- 基线（baseline）只应在 Benchmark 全部通过且 Rubric 得分不下降时更新。

#### Benchmark 工具化

本体系将 Benchmark 基础设施打包为可复用模块：

- `skillprism.benchmark.runner`：读取 `benchmarks/<skill>/registry.yaml` 并运行测试
- `skillprism.benchmark.metrics`：计算任务指标（clustering、table 等）
- `skillprism.benchmark.regression`：与 baseline 对比
- CLI：`test-skill --mode single`

Benchmark 注册表采用与 Skill 类型解耦的设计：每个 skill 拥有独立的注册表 `benchmarks/<skill>/registry.yaml`，其中每个 benchmark 条目声明 `task`、`dataset`/`input`、`expected`、`metrics` 和可选的 `metrics.py`（私有 metric 注册）；任务契约（prompt、输入输出格式等）定义在 `benchmarks/<skill>/tasks/<task>.yaml` 中。

---

## 五、治理与基础设施

### 5.1 必须落地的自动化工具

| 工具 | 作用 | 建议集成 |
|---|---|---|
| `evaluate-skill` / `evaluate_skill_rubric.py` | Rubric 多维评分、类型检测、生成 Scorecard | GitHub Actions / CI |
| `skillprism.optimize_skill` | 测量、识别短板、保留/回滚编辑（不调用 LLM） | Agent 驱动优化循环 |
| `test-skill --mode single` | 金标准 Benchmark 运行 | CI / 每次修改相关 Skill |
| `skill-pipeline` | Rubric + Benchmark + 识别最差 skill | 全量质量审计 |
| `security_evaluator.py` | D9 安全维度静态扫描 + SkillSpector 集成 | CI / 安全审计 |
| `smoke_test_runner.py` | 按类型执行轻量级可执行性验证（含边界/异常处理检查） | CI / 本地开发 |
| `dependency_checker.py` | requirements/environment 可安装性检查 | CI |
| `skill_lens_checks.py` | SkillLens 四维度检查（失败编码、具体性、风险黑名单、显性检查点） | CI / 优化前 |
| `skillprism.testing.boundary` | 边界/异常输入测试框架；level 0 benchmark 自动调用 | CI / level 0 benchmark |
| `test_prompts.py` | 管理 `test-prompts.json`，为 LLM 效果验证提供标准提示 | CI / 优化前 |
| `runtime_neutrality.py` | 检查 SKILL.md / README 是否绑定特定 Agent runtime | CI / 优化前 |
| `pytest tests/` | 分阶段功能测试 | CI / 本地开发 |
| `ruff` / `lintr` | 代码风格与静态检查 | pre-commit / CI |
| `pip --dry-run` / `renv::restore` | 依赖可安装性验证 | CI |
| `templates/regression_test.py` | Benchmark 结果与基线对比 | CI / 优化验证 |

### 5.2 报告与看板

建议维护以下文档：

- `docs/SKILL_SCORECARD.md`：每个 Skill 的当前得分与历史趋势。
- `SKILL_OPTIMIZATION_BACKLOG.md`：待优化 Skill 与优先级。
- `SKILL_REVIEW_REPORT_YYYY-MM.md`：每次全量评审的详细报告。

### 5.3 准入与下线标准

**新 Skill 上线标准**：

- Rubric 显示总分 ≥ 75
- D1、D2、D3、D9 单项 ≥ 4
- LLM 实测 3 个用例全部通过，且 LLM 实测分 ≥ 60
- CI 自动化检查通过
- 若该 Skill 有 Benchmark，所有指标通过且不下降

**Skill 下线触发条件**：

- 连续两个季度评分 < 60
- 依赖工具已停止维护且无法替代
- 与另一个 Skill 高度重复且质量更差

---

## 六、附录：Skill 评分表模板

```markdown
## Skill 评分表

| Skill 名称 | 评估日期 | 评估人 | 版本 |
|---|---|---|---|
| `bio-xxx-xxx` | YYYY-MM-DD | Name | v1.0 |

### 维度得分

| 维度 | 得分 (1-5) | 证据/问题 | 优化建议 |
|---|---|---|---|
| D1 目录与元数据规范 |  |  |  |
| D2 文档可理解性 |  |  |  |
| D3 代码正确性 |  |  |  |
| D4 工具依赖可复现 |  |  |  |
| D5 生物信息学准确性 |  |  |  |
| D6 LLM 可调用性 |  |  |  |
| D7 性能与资源友好 |  |  |  |
| D8 可维护性 |  |  |  |

### 总分

- 加权总分：__ / 100
- 等级：A / B / C / D
- 优先优化维度：__
- 预计下次复评日期：YYYY-MM-DD
```

---

## 七、附录：快速启动命令

假设 `evaluate_skill_rubric.py` 与 `skill_rubric_types.yaml` 位于 `/path/to/Skills_Validation/`。

```bash
# 1. 对单个 Skill 做 Rubric 评估（自动检测类型）
python /path/to/Skills_Validation/evaluate_skill_rubric.py \
    skills/bio-single-cell-clustering --detailed

# 2. 强制指定类型进行评估
python /path/to/Skills_Validation/evaluate_skill_rubric.py \
    skills/bio-single-cell-fastq2mtx --type cmd --detailed

# 3. 批量生成全项目评分卡
python /path/to/Skills_Validation/evaluate_skill_rubric.py \
    --all --skills-dir ./skills --output docs/SKILL_SCORECARD.md --verbose

# 4. 跨项目复用：评估另一个项目的 skills
python /path/to/Skills_Validation/evaluate_skill_rubric.py \
    --all \
    --skills-dir /path/to/Genomics-Skills/skills \
    --output /path/to/Genomics-Skills/docs/SKILL_SCORECARD.md

# 5. 使用自定义类型配置
python /path/to/Skills_Validation/evaluate_skill_rubric.py \
    --config ./my_types.yaml \
    --all --skills-dir ./skills

# 6. 运行项目已有分阶段功能测试（示例）
python tests/run_tests.py all
```

---

## 八、跨领域 Skill 泛化评估方法论

> 本节把上述 Rubric-PDCA 体系从生信分析 Skill 扩展到其他类型的 Skill，如论文写作、基因组学流程、数据库 API 等。核心思想是：**通用维度保持不变，执行层检查根据 Skill 类型做适配**。

### 8.1 Skill 类型学（Taxonomy）

根据已考察的多个 `./skills` 目录，可将 Skill 归为四大类：

| 类型 | 代表项目 | 核心交付物 | 可执行性特征 |
|---|---|---|---|
| **分析型（Analysis）** | NanoResearch-Skills | Python/R 分析代码、notebook | 在数据上运行，产生统计/可视化结果 |
| **命令型（cmd/CLI）** | Genomics-Skills | shell 脚本、命令行调用、WDL/CWL | 依赖参考基因组、BAM/VCF 等中间文件 |
| **数据库/API 型** | database-Skills | REST API 调用、查询语法、客户端 | 依赖外部服务可用性、网络、认证 |
| **文档/编排型（Document/Orchestration）** | paperwriting-Skills | 写作模板、引用规范、报告结构 | 输出文本/文档， correctness 更难量化 |

### 8.2 通用维度 vs 类型适配维度

**对所有类型都适用的通用维度（Universal Dimensions）**：

| 维度 | 通用含义 |
|---|---|
| **UD1 元数据规范** | SKILL.md frontmatter 完整、命名规范、目录结构清晰 |
| **UD2 文档可理解性** | 输入/输出/用途明确，示例充足，章节组织合理 |
| **UD3 LLM 可调用性** | description 精准，keywords 充分，何时使用/不使用的决策指引清晰 |
| **UD4 可维护性** | 代码/模板模块化，有注释/说明，版本兼容信息清晰 |
| **UD5 安全与稳健性** | 有错误处理、边界提示、数据备份/不破坏输入等意识 |

**需要按类型适配的维度（Adaptive Dimensions）**：

| 类型 | 适配后的核心检查项 |
|---|---|
| **分析型** | 代码语法、单元测试、benchmark 数据集、结果指标（ARI、准确率等） |
| **流程型** | 命令语法、参数完整性、参考数据/索引要求、资源（CPU/GPU/内存）声明 |
| **数据库/API 型** | API endpoint 可用性、查询语法正确性、认证方式、速率限制与错误码处理 |
| **写作/编排型** | 模板完整性、引用格式正确性、输出风格一致性、事实可验证性 |

### 8.3 各类型 Skill 的验证策略

#### 分析型 Skill

- **自动化**：语法检查、静态分析、依赖安装、单元测试。
- **金标准 Benchmark**：对聚类、注释、批次校正等客观任务，用已知标签数据集做回归测试。详见 [Benchmark 指南](benchmark-guide.md)。
- **LLM 实测**：让 Agent 根据 SKILL.md 生成完整分析代码并执行，检查是否选对方法、参数是否合理。

#### 流程型 Skill（如 Genomics）

- **自动化**：shellcheck/bash 语法检查、命令参数模板校验、Docker/conda 环境可安装性。
- **轻量级冒烟测试**：不跑全量 WGS/WES（太耗时/耗资源），而是用 `samtools view -H`、`gatk --help`、`bcftools --version` 等验证工具可调用。
- **输入/输出规范检查**：每个步骤是否声明了必需的输入文件、参考基因组版本、输出格式。
- **资源声明检查**：是否声明 CPU、内存、GPU、运行时间预估。

#### 数据库/API 型 Skill

- **自动化**：查询语法检查（如 UniProt query syntax）、Python 客户端语法检查。
- **API 可用性探测**：用 `curl -I` 或轻量请求验证 endpoint 可达（注意频率控制，避免滥用）。
- **示例响应检查**：示例中的 URL/参数是否能在当前 API 版本下返回合理结果。
- **认证与限制**：是否说明 API key、速率限制、超时处理。

#### 文档/编排型 Skill

- **自动化有限**：主要检查 frontmatter、目录结构、模板文件存在性。
- **专家评审为主**：由领域专家检查写作流程、引用规范、期刊格式要求是否完整。
- **LLM 一致性测试**：同一提示多次调用，检查输出风格/格式是否稳定、是否符合模板。
- **事实可验证性**：对涉及具体期刊格式、统计报告标准的内容，抽样验证是否正确。

### 8.4 跨领域 Rubric 模板

在实际评估时，建议保留 8 个维度的外壳，但根据 Skill 类型调整每个维度内部的检查项：

| 维度 | 分析型 | 命令型 | 数据库/API 型 | 文档/编排型 |
|---|---|---|---|---|
| **D1 结构与元数据** | SKILL.md、examples、requirements | SKILL.md、examples、reference data 声明 | SKILL.md、API docs、client scripts | SKILL.md、templates、style guides |
| **D2 文档可理解性** | 输入数据状态、参数表、pipelines | 输入文件、参考基因组、参数表 | Query syntax、返回格式、认证 | 写作流程、格式要求、检查清单 |
| **D3 可执行性/正确性** | 代码语法、单元测试、benchmark | 命令语法、工具 `--help` 通过 | API endpoint 可达、查询可执行 | 模板可渲染、格式符合规范 |
| **D4 环境/依赖可复现** | conda/pip/renv/Docker | conda/Docker、参考数据下载 | API key、SDK 版本 | 模板依赖、字体/引用样式 |
| **D5 领域准确性** | 算法/参数正确性 | 流程顺序、参数符合 GATK/bwa 等规范 | 查询字段、ID 映射规则正确 | 期刊格式、统计报告标准正确 |
| **D6 LLM 可调用性** | description、keywords、决策表 | description、keywords、WDL/CWL 选择 | description、keywords、何时用 REST | description、keywords、写作阶段匹配 |
| **D7 性能/资源** | 内存、时间、降采样提示 | CPU/GPU/内存/磁盘、运行时间 | 批处理大小、分页、缓存策略 | 输出长度控制、迭代次数 |
| **D8 可维护性** | 函数模块化、docstring | 脚本模块化、日志/错误处理 | 客户端封装、错误码处理 | 模板模块化、版本更新机制 |

### 8.5 金标准 vs LLM 实测的取舍矩阵

| Skill 类型 | 是否推荐金标准 | 推荐方式 | 主要验证手段 |
|---|---|---|---|
| 分析型-客观任务 | ✅ 强推荐 | 已知标签 benchmark 数据集 + 量化指标 | 自动化 benchmark + LLM 实测 |
| 分析型-探索性任务 | ⚠️ 有限推荐 | 专家共识集 + 稳定性指标 | LLM 实测 + 专家评审 |
| 命令型 | ⚠️ 有限推荐 | 轻量级 reference 数据冒烟测试 | 命令/工具可用性 + 小规模端到端测试 |
| 数据库/API 型 | ❌ 不适用 | 无 | API 探测 + 示例响应验证 + LLM 实测 |
| 文档/编排型 | ❌ 不适用 | 无 | LLM 一致性 + 专家评审 + 模板渲染检查 |

> 如何具体构建和维护金标准 Benchmark，详见 [Benchmark 指南](benchmark-guide.md)。

### 8.6 通用评估执行流程

无论哪种类型，单次完整评估都遵循以下步骤：

```
1. 类型识别
   └── 判断 Skill 属于分析型/命令型/数据库型/文档型

2. 结构检查（自动化）
   └── SKILL.md、frontmatter、目录结构、必需文件

3. 可执行性检查（按类型适配）
   └── 分析型：py_compile / R CMD check
   └── 命令型：shellcheck / command --help
   └── API 型：语法检查 + 轻量 endpoint 探测
   └── 文档型：模板存在性 + 格式样例检查

4. 领域准确性检查（人工 + 工具辅助）
   └── 分析型：benchmark 指标
   └── 命令型：参数与 best practice 对照
   └── API 型：查询结果与官方文档对照
   └── 文档型：专家抽样评审

5. LLM 驱动验证（由 Agent / Skill 完成，引擎不直接调用 LLM）
   └── 让 Agent 用该 Skill 完成 3 个典型任务
   └── 记录：是否选对、是否执行、输出是否可用
   └── 将问题反馈给 skill-prism 循环

6. 汇总评分、定位短板、制定 PDCA 优化计划
```

### 8.7 跨项目复用建议

如果要在多个项目（如 NanoResearch、Genomics、database、paperwriting 等）之间复用这套体系，建议：

1. **把 `evaluate_skill_rubric.py` 作为独立引擎**，通过 `--skills-dir` 和 `--config` 参数指向不同项目。
2. **每个项目维护一个 `skill_rubric_types.yaml` 或 `skill_types.yaml`**，定义该项目特有的 Skill 类型和检查规则；通用类型可直接继承默认配置。
3. **共享通用评分卡格式**，但允许每个项目补充类型特定字段（如 benchmark 指标、API endpoint 版本）。
4. **定期跨项目同步标杆 Skill**，把某个项目中评分 95+ 的 Skill 作为全组织的模板参考。
5. **在 CI 中统一调用**（假设引擎已复制到项目 `scripts/` 目录）：
   ```bash
   python scripts/evaluate_skill_rubric.py --all --skills-dir ./skills --output docs/SKILL_SCORECARD.md
   ```
   不同项目只需修改 `--skills-dir` 和 `--config` 参数。

---

## 九、独立体系设计：配置驱动的评估引擎

> 本节说明如何把上述方法论从「具体项目专属」升级为「项目无关的独立评估体系」。

### 9.1 为什么要独立化？

之前的实现把检查规则硬编码在脚本里（例如：只有 `requirements.txt` 才算依赖文件，只有 Python/R 才算代码）。这带来两个问题：

1. **换项目就失效**：一个论文写作 Skill 没有 `requirements.txt` 不代表它差；一个 API Skill 没有 `scripts/python/` 也不代表结构错误。
2. **新增类型要改代码**：每出现一种新的 Skill 形态，都要修改评估脚本。

**独立化目标**：把「规则」从「引擎」中分离出来。引擎只负责读取配置、执行检查、汇总分数；规则写在 YAML 配置里，可随项目扩展。

### 9.2 元模型（Meta-Model）

独立体系的核心是一个三层元模型：

```
┌─────────────────────────────────────┐
│  Engine（评估引擎）                  │
│  - 读取配置                          │
│  - 检测 Skill 类型                   │
│  - 按维度执行检查                    │
│  - 汇总评分、生成报告                 │
└─────────────────────────────────────┘
            ↑ 读取
┌─────────────────────────────────────┐
│  Type Registry（类型注册表）          │
│  - skill_types.yaml                  │
│  - 每个类型定义检测规则、frontmatter   │
│    要求、文件检查、关键词集合          │
└─────────────────────────────────────┘
            ↑ 适配
┌─────────────────────────────────────┐
│  Project Config（项目配置）           │
│  - skills 目录位置                    │
│  - 自定义类型覆盖                     │
│  - 权重调整（可选）                   │
└─────────────────────────────────────┘
```

### 9.3 当前实现

当前脚本 `evaluate_skill_rubric.py` 与配置文件 `skill_rubric_types.yaml` 已经按这个模型实现：

- **引擎**：`evaluate_skill_rubric.py` 不再硬编码任何项目特定的路径或文件。
- **类型注册表**：`skill_rubric_types.yaml` 定义了 `analysis`、`cmd`、`api`、`document`、`generic` 五种类型。
- **项目配置**：通过 CLI 参数 `--skills-dir` 和 `--config` 指定。

### 9.4 配置示例：增加一个新类型

假设未来出现一类「Agentic Reasoning Skill」，只需修改 `skill_rubric_types.yaml`：

```yaml
skill_types:
  reasoning:
    label: 推理/编排型
    description: Skills that orchestrate multi-step reasoning or agent workflows
    detection:
      tool_type: [reasoning, agent, orchestrator]
      keywords:
        - reasoning
        - agent
        - multi-step
        - chain-of-thought
      file_patterns:
        - "prompts/*.md"
    frontmatter_recommended: [tool_type, allowed-tools]
    dimension_names_override:
      D3: 推理流程可用性
      D4: 提示/工具依赖说明
      D5: 推理准确性
      D7: 输出稳定性
    dimension_checks:
      D1:
        dependency_file_candidates:
          - prompts
          - tools.yaml
      D2:
        io_keywords:
          - input
          - output
          - reasoning
          - workflow
        code_example_markers:
          - "```"
          - "Step 1"
      D5:
        accuracy_keywords:
          - validation
          - verification
          - fact-check
        pitfall_keywords:
          - hallucination
          - ambiguity
          - fallback
      D7:
        resource_keywords:
          - tokens
          - iterations
          - steps
        robustness_keywords:
          - fallback
          - retry
          - error
```

**无需修改 `evaluate_skill_rubric.py`**，新类型即可被自动识别和评估（如果只需要基于文件存在性和关键词的检查）。

### 9.5 跨项目使用方式

```bash
# 1. 在目标项目内使用默认配置
python /path/to/Skills_Validation/evaluate_skill_rubric.py \
    --all --skills-dir ./skills --output docs/SKILL_SCORECARD.md

# 2. 在 Genomics 项目内复用同一引擎
python /path/to/Skills_Validation/evaluate_skill_rubric.py \
    --all \
    --skills-dir /path/to/Genomics-Skills/skills \
    --output /path/to/Genomics-Skills/docs/SKILL_SCORECARD.md

# 3. 使用自定义类型配置
python /path/to/Skills_Validation/evaluate_skill_rubric.py \
    --config /path/to/my_types.yaml \
    --all --skills-dir ./skills
```

### 9.6 内置类型是否足够泛化？

当前 4 个具体类型 + 1 个通用兜底：**对现有生信/科研场景基本够用，但还称不上终极完备**。

边界上可能还需拆分或新增：

| 候选类型 | 适用场景 | 与现有类型的关系 |
|---|---|---|
| **workflow** | WDL/CWL/Nextflow/Snakemake 等声明式流程 | 可从 `cmd` 中拆分出来 |
| **agentic** | 多步推理、工具调用、agent 编排 | 新增类型 |
| **multimodal** | 图像/视频/音频生成与分析 | 新增类型 |
| **data-engineering** | ETL、数据清洗、数据库迁移 | 介于 `cmd` 与 `api` 之间 |
| **devops** | CI/CD、部署、监控 | 新增类型 |

**建议策略**：
- 不要一次性定义太多类型。
- 先用 `generic` 兜底收集 10-20 个无法归类的 Skill，再抽象出新的类型。
- 每个新类型必须有明确的 **输入/输出形态**、**可执行性检查方式**、**领域准确性验证方式**，否则应归入 `generic`。

### 9.7 类型不完善时的降级策略

如果自动类型检测不确定，脚本会返回 `generic` 类型。`generic` 只执行最宽松的通用检查：

- 基础 frontmatter
- 文档结构和示例
- 通用 pitfalls/参考文献提示
- 通用资源/稳健性关键词

这样可以**避免因为类型误判而给出不公正的分数**。

---

## 十、SkillLens 与 skill-prism 的融合

> 注：本体系受 `alchaincyf/darwin-skill` 与 Karpathy autoresearch 启发，
> 但 `skill-prism` 是本体系的**独立实现**，并非原样复制 darwin-skill。

### 10.1 SkillLens 四维度

Microsoft Research SkillLens（arXiv 2605.23899）通过实证发现以下维度对 Skill 实际效果影响最大。本体系已将它们融入现有 Rubric，并补充了 darwin-skill 强调的显性检查点：

| SkillLens 维度 | 含义 | 落地位置 |
|---|---|---|
| **失败模式编码** | 显式列出已知失败路径，而非泛泛提醒 | D2 文档可理解性 |
| **可执行具体性** | 禁用「视情况而定/建议/可以考虑」等模糊措辞 | D2 + D6 LLM 可调用性 |
| **高风险黑名单** | 明文禁止 `rm -rf /`、`git reset --hard` 等高危操作 | D9 安全与可信 |
| **显性检查点** | 在关键决策前加入 `🔴 STOP` / `CHECKPOINT` 等标记，强制 Agent 停顿确认 | D2 + D7 + D9 |

### 10.1.1 补充检查：test-prompts、runtime neutrality 与 checkpoint markers

除 SkillLens 四维度外，引擎还会自动执行以下轻量检查：

| 检查项 | 作用 | 期望 |
|---|---|---|
| **test-prompts.json** | 为每个 skill 保存 2-3 条代表性提示，用于 LLM 效果验证 | 文件存在且覆盖 happy path 与边界/歧义场景 |
| **Runtime neutrality** | 避免 skill 被绑定到 Claude Code、Cursor、Codex 等特定 runtime | SKILL.md / README.md 不出现 runtime-specific 措辞 |
| **Checkpoint markers** | 在删除、回滚、外部写操作等关键动作前强制停顿 | 出现 `🔴 STOP`、`CHECKPOINT`、`🛑` 等显性标记 |

这些检查不直接计入 Rubric 总分，但会出现在 `--detailed` 报告中，并为 `--auto-edit` 提供优化建议。

### 10.2 skill-prism 优化循环

受 Karpathy autoresearch 和 `alchaincyf/darwin-skill` 启发，本体系将优化拆分为两层，但保持**完全独立**：

- **引擎层**：`skillprism.optimize_skill` 负责客观测量、识别最低分维度、判断保留/回滚。
- **可选编辑层**：通过 `--auto-edit` 调用用户配置的 editor 命令自动改写 `SKILL.md`；默认则由 Agent/用户手动编辑。

```
Agent / 用户 / 外部 editor 编辑 SKILL.md
        ↓
引擎 --record-baseline 记录当前 Rubric 分与 benchmark 状态
        ↓
引擎 --suggest 输出最低分维度与改进建议
        ↓
生成候选 SKILL.md
        ↓
引擎 --judge 复评：
    新分 ≥ 旧分 + min_gain 且 benchmark 不 regress → git commit 保留
    否则                                          → git revert 回滚
        ↓
人在回路确认（或 --auto-edit 自动迭代）→ 下一轮
```

**两种优化模式**：

| 模式 | 编辑方式 | 适用场景 |
|---|---|---|
| 手动 / Agent（默认） | Agent / 用户手动编辑，引擎负责测量与回滚 | 需要人工审阅每轮 diff |
| `--auto-edit` | `improve-skill ... --auto-edit --apply` | 一键自动分析 → 自动改 → 自动 judge → 保留/回滚 |

**配置 editor 命令**：

```bash
export SKILLPRISM_EDITOR_COMMAND="python scripts/my_skill_editor.py"
```

或配置 `skill_rubric_types.yaml`：

```yaml
editor:
  enabled: true
  command: python scripts/my_skill_editor.py
  max_retries: 2
```

**推荐做法**：
- 若需要人工确认每轮编辑，使用默认手动模式。
- 若需要 turnkey 自动闭环，配置 editor 命令后使用 `--auto-edit --apply --max-rounds N`。
- 使用仓库提供的 `examples/editor_wrappers/` 快速接入 OpenAI、Anthropic 或 Ollama。
- 引擎始终不直接调用 LLM；editor 命令由用户选择并提供。

**关键原则**：

1. **单一可编辑资产**：每次只改一个 `SKILL.md`。
2. **引擎不调用 LLM**：避免引擎依赖 provider，评分客观可复现。
3. **编辑能力可插拔**：通过外部 editor 命令接入，不进入引擎。
4. **按维度编辑策略**：`--auto-edit` 会根据最弱维度（D1–D9）向 editor 发送具体的编辑策略提示。
5. **棘轮机制**：Rubric 分或 benchmark 退步时自动回滚。
6. **人在回路**：默认每轮暂停，展示 diff 和分数变化，等用户确认；`--auto-edit` 仍需 `--apply` 才能执行。

### 10.3 棘轮模式（Ratchet）

`evaluate-skill --ratchet` 将当前 scorecard 与上一次 scorecard 对比，任一 Skill 融合总分下降即返回非零退出码。配合 CI 使用可防止退化。

---

## 十一、三层架构：引擎、可选能力与 Skill 入口

完整的架构说明见 [体系概览](overview.md)。本文只给出与实现相关的要点。

```
Layer 3 (Skill 入口): 自然语言操作
  - skills/skill-prism/SKILL.md → "评估 / 测试 / 改进 / 流水线 / CI"

Layer 2 (可选能力): 用户选择接入
  - SKILL.md editor 命令（--auto-edit）
  - LLM-as-judge 命令（--llm-judge，默认 2 个独立评委）
  - Prompts 验证（--prompts-verification）

Layer 1 (Engine):  pip 包 skillprism
  - CLI: evaluate-skill / improve-skill / test-skill / skill-pipeline / skill-ci
  - Python API: skillprism.evaluate_skill_rubric / skillprism.optimize_skill / skillprism.benchmark / skillprism.orchestrator
```

**价值**：
- 引擎层保证可复现、可集成 CI，且无 LLM provider 依赖。
- 可选能力层通过 stdin/stdout 命令接入，不锁定 provider。
- Skill 入口层让最终用户用自然语言驱动（"评估所有 skills" / "优化 X" / "运行流水线"）。
- 每个 meta-Skill 自带 `scripts/` 封装脚本，优先调用已安装的包，降级时通过相对路径定位 repo 入口。

---

## 十二、结语

这套框架的核心不是一次性把每个 Skill 打到满分，而是：

1. **让质量可见**：通过 Rubric 把「好/坏」变成数字。
2. **让改进有方向**：每次只攻最短的板。
3. **让效果可验证**：不仅看代码，更看 LLM Agent 能不能用它正确完成任务。

建议先在目标项目内选一个代表性 Skill 做完整 Rubric 评估与一次 PDCA 迭代，跑通后再批量推广到全部 Skill。
