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
| **D6 LLM 可调用性** | 0.10 | Agent 无法识别何时该用该 Skill | description 清晰，keyword 充分 | 提供「何时使用/何时不用」决策表；示例可直接被 Agent 复制执行 |
| **D7 性能与资源友好** | 0.08 | 默认参数内存/时间不可接受 | 中等数据集可在合理时间内跑完 | 提供性能提示；支持降采样；大内存步骤有警告 |
| **D8 可维护性** | 0.04 | 函数无注释；逻辑耦合严重 | 函数模块化，有基础注释 | 代码风格一致；docstring 完整；CHANGELOG/维护者信息清晰 |
| **D9 安全与可信** | 0.08 | 存在数据泄露、任意执行、硬编码密钥等高风险模式 | 无高风险模式；有基本数据隐私说明 | 通过外部安全扫描；明确声明数据隐私、随机种子、可复现性 |

> D5 的具体含义由 `skill_rubric_types.yaml` 中每个 `skill_type` 自行定义（如生信类型可命名为“生物信息学准确性”）。引擎检查通用要素（引用、参数、pitfalls），语义层面的准确性可由 Agent 或外部 judge 做第二意见（`--llm-judge`）。
>
> **评分实现说明**：D2、D5、D7 以及 D9 的部分检查当前基于**关键词、正则和简单结构启发式**。这些指标运行快速、无需 LLM，适合 CI 场景，但**不是完美的质量代理**——可能被关键词堆砌绕过，也可能对合法用法误报。建议将 Rubric 分数作为持续改进的指引，对关键技能结合 `--llm-judge`、benchmark 结果和人工复核综合判断。

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

对目标项目的 skills 目录批量运行（具体命令需根据项目实际工具链调整）：

```bash
# Rubric 9 维评分（含元数据、结构、文档检查）
evaluate-skill skills/<skill-name> --detailed
# 可选：冒烟测试与依赖可安装性检查
evaluate-skill skills/<skill-name> --run-smoke --run-deps
# 语言级静态检查与单元测试
ruff check skills/<skill-name>/scripts/python/
pytest tests/ -v -k <skill-name>
```

产出：每个 Skill 的 PASS/FAIL 列表与 9 维评分，以及关键错误汇总（frontmatter 非法、依赖冲突、语法错误等）。

### 3.2 人工领域评审

由具备领域背景的人员依据 Rubric 逐项打分（评分表见第 6 节），建议两人独立打分后取平均或讨论校准。

### 3.3 LLM 驱动的验证（由 Agent / Skill 完成）

引擎本身不调用 LLM。LLM 效果验证作为 Agent 工作流的一部分，由 `skills/skill-prism` 或类似的 Agent Skill 完成：Agent 读取 SKILL.md 后模拟三类真实调用场景——**直接任务**（「用 X 工具对 PBMC 数据做 Y 分析」）、**边界任务**（「数据没有 label，如何处理？」）、**错误恢复任务**（「运行时报 Z 错误，怎么解决？」）——检查生成的代码/命令是否合理可运行，并将问题反馈到优化循环。常用 prompt 模板可保存在 `skill_rubric_types.yaml` 的 `llm_tasks` 段。

---

## 四、Rubric 循环优化流程

### 4.1 周期建议

> 以下为**建议的治理流程**，供团队参考采用；引擎本身不强制任何评审周期。

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
4. **验证**：自动化检查通过、示例代码可运行、Rubric 复评得分提升、LLM 实测任务通过。
5. **归档**：更新 `SKILL_REVIEW_REPORT.md` 或创建版本化审计报告。

### 4.4 金标准 Benchmark 与 Rubric-PDCA 的融合

金标准 Benchmark 不是独立于 Rubric 的「另一套测试」，而是为 D3（可执行性/正确性）和 D5（领域准确性）提供**客观证据**的输入。对每次 Skill 修改，比较当前输出与金标准参考结果的一致性：

| 一致性层级 | 含义 | 判定方式 |
|---|---|---|
| **L1 结构一致** | 输出文件/格式与 expected 一致 | 文件存在、列名/obs 名匹配 |
| **L2 指标一致** | 关键量化指标在阈值范围内 | metric spec 全部通过 |
| **L3 分布一致** | 输出分布与参考分布无显著偏移 | tolerance / relative gate |
| **L4 LLM 可用** | LLM 能用当前输出完成下游任务 | LLM 实测下游任务通过 |

**操作要点**：

- Benchmark 回归测试必须在 PR 合并前通过（Hard Gate）。
- Rubric 复评在每次修改后执行，量化「改了多少分」；LLM 实测每季度/重大修改后执行，验证「Agent 还能不能用它干活」。
- 基线（baseline）只应在 Benchmark 全部通过且 Rubric 得分不下降时更新。

Benchmark 的工具化实现（registry 格式、metric 类型、baseline 机制）见 [体系概览](overview.md) 与 [Benchmark 指南](benchmark-guide.md)。

---

## 五、治理与基础设施

### 5.1 自动化工具与检查模块

**CLI 工具**（pip 安装 `skillprism` 后可用，共 7 个）：

| 命令 | 作用 | 建议集成 |
|---|---|---|
| `evaluate-skill` | Rubric 9 维评分、类型检测、生成 Scorecard | GitHub Actions / CI |
| `improve-skill` | 测量、识别短板、保留/回滚编辑（不调用 LLM） | Agent 驱动优化循环 |
| `test-skill` | 金标准 Benchmark 运行（`--mode single` / `--mode gradual`） | CI / 每次修改相关 Skill |
| `build-skill-test` | 构造 benchmark 定义 | 新增 benchmark 时 |
| `skill-pipeline` | Rubric + Benchmark + 识别最差 skill | 全量质量审计 |
| `skill-ci` | CI 模式 benchmark + 回归门控 | CI |
| `skill-gradual` | 失败优先的渐进式 benchmark 流水线 | 昂贵 Skill 的 CI |

**评估管线内的检查模块**（`skillprism` 包内模块，无独立 CLI，由 `evaluate-skill` 在评估过程中调用，结果出现在 `--detailed` 报告中）：

| 模块 | 作用 |
|---|---|
| `skillprism.security_evaluator` | D9 安全维度静态扫描 + SkillSpector 集成 |
| `skillprism.smoke_test_runner` | 按类型执行轻量级可执行性验证（`evaluate-skill --run-smoke`） |
| `skillprism.dependency_checker` | requirements/environment 可安装性检查（`evaluate-skill --run-deps`） |
| `skillprism.skill_lens_checks` | SkillLens 四维度检查（失败编码、具体性、风险黑名单、显性检查点） |
| `skillprism.test_prompts` | 管理 `test-prompts.json`，为 LLM 效果验证提供标准提示 |
| `skillprism.runtime_neutrality` | 检查 SKILL.md / README 是否绑定特定 Agent runtime |
| `skillprism.testing.boundary` | 边界/异常输入测试框架；level 0 benchmark 自动调用 |

**外部工具**：`pytest tests/`（分阶段功能测试）、`ruff` / `lintr`（代码风格与静态检查）、`pip --dry-run` / `renv::restore`（依赖可安装性）、`templates/regression_test.py`（Benchmark 结果与基线对比），建议接入 pre-commit / CI。

### 5.2 报告与看板

建议维护以下文档：

- `reports/SKILL_SCORECARD.md`：每个 Skill 的当前得分与历史趋势。
- `SKILL_OPTIMIZATION_BACKLOG.md`：待优化 Skill 与优先级。
- `SKILL_REVIEW_REPORT_YYYY-MM.md`：每次全量评审的详细报告。

### 5.3 准入与下线标准

> 以下为**建议的治理标准**，供团队参考采用；引擎不会自动阻止 Skill 上线或下线，需由团队在评审流程或 CI 配置中自行落实。

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
| D9 安全与可信 |  |  |  |

### 总分

- 加权总分：__ / 100
- 等级：A / B / C / D
- 优先优化维度：__
- 预计下次复评日期：YYYY-MM-DD
```

---

## 七、附录：快速启动命令

前置条件：`pip install -e ".[dev]"` 安装 `skillprism` 包（完整参数见 `evaluate-skill --help`）。

```bash
# 1. 对单个 Skill 做 Rubric 评估（自动检测类型）
evaluate-skill skills/bio-single-cell-clustering --detailed

# 2. 强制指定类型进行评估
evaluate-skill skills/bio-single-cell-fastq2mtx --type cmd --detailed

# 3. 批量生成全项目评分卡
evaluate-skill --all --skills-dir ./skills \
    --output reports/SKILL_SCORECARD.md --verbose

# 4. 跨项目复用：评估另一个项目的 skills
evaluate-skill --all \
    --skills-dir /path/to/Genomics-Skills/skills \
    --output /path/to/Genomics-Skills/reports/SKILL_SCORECARD.md

# 5. 使用自定义类型配置
evaluate-skill --config ./my_types.yaml --all --skills-dir ./skills

# 6. 运行项目测试套件
pytest tests/ -v
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
| **文档/编排型（Document/Orchestration）** | paperwriting-Skills | 写作模板、引用规范、报告结构 | 输出文本/文档，correctness 更难量化 |

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

| 类型 | 自动化检查 | 客观验证 | LLM / 专家验证 |
|---|---|---|---|
| **分析型** | 语法检查、静态分析、依赖安装、单元测试 | 已知标签数据集的金标准 Benchmark（聚类/注释/批次校正等，见 [Benchmark 指南](benchmark-guide.md)） | Agent 根据 SKILL.md 生成完整分析代码，检查方法选择与参数合理性 |
| **流程型（如 Genomics）** | shellcheck、命令参数模板校验、Docker/conda 环境可安装性 | 轻量冒烟测试（`samtools view -H`、`gatk --help` 等，不跑全量 WGS/WES）；输入文件、参考基因组版本、输出格式与 CPU/内存/GPU 资源声明检查 | 小规模端到端测试 |
| **数据库/API 型** | 查询语法检查（如 UniProt query syntax）、客户端语法检查 | `curl -I` 轻量探测 endpoint 可达性（注意频率控制）；示例响应在当前 API 版本下的合理性 | 认证方式、速率限制、超时处理的完整性审查 |
| **文档/编排型** | frontmatter、目录结构、模板文件存在性（自动化手段有限） | 模板渲染检查 | 专家评审写作流程/引用规范；同一提示多次调用的一致性测试；期刊格式、统计报告标准等事实抽样验证 |

### 8.4 跨领域 Rubric 模板

在实际评估时，建议保留 9 个维度（D1–D9）的外壳，但根据 Skill 类型调整每个维度内部的检查项：

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
| **D9 安全与可信** | 数据隐私、随机种子、危险操作扫描 | 凭据/密钥管理、危险命令黑名单 | API key 保护、速率限制遵守 | 敏感信息泄露、事实声明可溯源 |

### 8.5 金标准 vs LLM 实测的取舍矩阵

| Skill 类型 | 是否推荐金标准 | 推荐方式 | 主要验证手段 |
|---|---|---|---|
| 分析型-客观任务 | ✅ 强推荐 | 已知标签 benchmark 数据集 + 量化指标 | 自动化 benchmark + LLM 实测 |
| 分析型-探索性任务 | ⚠️ 有限推荐 | 专家共识集 + 稳定性指标 | LLM 实测 + 专家评审 |
| 命令型 | ⚠️ 有限推荐 | 轻量级 reference 数据冒烟测试 | 命令/工具可用性 + 小规模端到端测试 |
| 数据库/API 型 | ❌ 不适用 | 无 | API 探测 + 示例响应验证 + LLM 实测 |
| 文档/编排型 | ❌ 不适用 | 无 | LLM 一致性 + 专家评审 + 模板渲染检查 |

> 如何具体构建和维护金标准 Benchmark，详见 [Benchmark 指南](benchmark-guide.md)。

### 8.6 跨项目复用建议

如果要在多个项目（如 NanoResearch、Genomics、database、paperwriting 等）之间复用这套体系，建议：

1. **pip 安装 `skillprism` 作为独立引擎**，通过 `evaluate-skill` 的 `--skills-dir` 和 `--config` 参数指向不同项目。
2. **每个项目维护一个 `skill_rubric_types.yaml`**，定义该项目特有的 Skill 类型和检查规则；通用类型可直接继承默认配置。
3. **共享通用评分卡格式**，但允许每个项目补充类型特定字段（如 benchmark 指标、API endpoint 版本）。
4. **定期跨项目同步标杆 Skill**，把某个项目中评分 95+ 的 Skill 作为全组织的模板参考。
5. **在 CI 中统一调用**：`evaluate-skill --all --skills-dir ./skills --output reports/SKILL_SCORECARD.md`，不同项目只需修改 `--skills-dir` 和 `--config` 参数。

---

## 九、独立体系设计：配置驱动的评估引擎

> 本节说明如何把上述方法论从「具体项目专属」升级为「项目无关的独立评估体系」。

### 9.1 为什么要独立化？

早期的实现把检查规则硬编码在脚本里（例如：只有 `requirements.txt` 才算依赖文件，只有 Python/R 才算代码），导致**换项目就失效**、**新增类型要改代码**。独立化目标是把「规则」从「引擎」中分离：引擎只负责读取配置、执行检查、汇总分数；规则写在 YAML 配置里，可随项目扩展。

### 9.2 元模型（Meta-Model）

独立体系的核心是一个三层元模型：

| 层 | 组件 | 职责 |
|---|---|---|
| **Engine（评估引擎）** | `skillprism` 包 / `evaluate-skill` CLI | 读取配置、检测 Skill 类型、按维度执行检查、汇总评分生成报告 |
| **Type Registry（类型注册表）** | `skill_rubric_types.yaml` | 每个类型定义检测规则、frontmatter 要求、文件检查、关键词集合 |
| **Project Config（项目配置）** | CLI 参数 | skills 目录位置（`--skills-dir`）、自定义类型覆盖与权重调整（`--config`） |

### 9.3 当前实现

pip 包 `skillprism` 与配置文件 `skill_rubric_types.yaml` 已经按这个模型实现：引擎不硬编码任何项目特定的路径或文件；类型注册表内置 `analysis`、`cmd`、`api`、`document`、`generic` 五种类型。增加新类型只需修改 YAML 配置，无需改引擎代码；具体配置示例见 [体系概览](overview.md) 的「扩展点」一节。

### 9.4 内置类型是否足够泛化？

当前 4 个具体类型 + 1 个通用兜底：**对现有生信/科研场景基本够用，但还称不上终极完备**。边界上可能还需拆分或新增：

| 候选类型 | 适用场景 | 与现有类型的关系 |
|---|---|---|
| **workflow** | WDL/CWL/Nextflow/Snakemake 等声明式流程 | 可从 `cmd` 中拆分出来 |
| **agentic** | 多步推理、工具调用、agent 编排 | 新增类型 |
| **multimodal** | 图像/视频/音频生成与分析 | 新增类型 |
| **data-engineering** | ETL、数据清洗、数据库迁移 | 介于 `cmd` 与 `api` 之间 |
| **devops** | CI/CD、部署、监控 | 新增类型 |

**建议策略**：不要一次性定义太多类型；先用 `generic` 兜底收集 10-20 个无法归类的 Skill 再抽象新类型；每个新类型必须有明确的输入/输出形态、可执行性检查方式、领域准确性验证方式，否则应归入 `generic`。

### 9.5 类型不完善时的降级策略

如果自动类型检测不确定，引擎会返回 `generic` 类型，只执行最宽松的通用检查（基础 frontmatter、文档结构和示例、通用 pitfalls/参考文献提示、通用资源/稳健性关键词），**避免因为类型误判而给出不公正的分数**。

---

## 十、SkillLens 与 skill-prism 的融合

> 注：本体系受 Karpathy autoresearch 等工作启发，`skill-prism` 是**独立实现**。

### 10.1 SkillLens 四维度

Microsoft Research SkillLens（arXiv 2605.23899）通过实证发现以下维度对 Skill 实际效果影响最大。本体系已将它们融入现有 Rubric，并补充了显性检查点：

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
| **test-prompts.json** | 每个 skill 2-3 条代表性提示，用于效果验证；位于 `artifacts/<skill>/`，正式版由 Agent 撰写（引擎模板仅为兜底占位） | 文件存在且覆盖 trigger 与边界/歧义场景 |
| **Runtime neutrality** | 避免 skill 被绑定到 Claude Code、Cursor、Codex 等特定 runtime | SKILL.md / README.md 不出现 runtime-specific 措辞 |
| **Checkpoint markers** | 在删除、回滚、外部写操作等关键动作前强制停顿 | 出现 `🔴 STOP`、`CHECKPOINT`、`🛑` 等显性标记 |

这些检查不直接计入 Rubric 总分，但会出现在 `--detailed` 报告中，并为 `--auto-edit` 提供优化建议。

### 10.2 优化循环与实验历史（history.jsonl）

优化循环本身（`improve-skill --record-baseline/--suggest/--judge/--apply/--auto-edit` 的用法与两种优化模式）见 [体系概览](overview.md) 的「典型工作流」一节，本文不再重复。本节只记录方法论层面独有的两点：

1. **两层分离**：引擎层（`improve-skill`）只负责客观测量、识别最低分维度、判断保留/回滚，始终不调用 LLM；可选编辑层通过 `--auto-edit` 调用用户配置的 editor 命令改写 `SKILL.md`。
2. **棘轮机制**：Rubric 分或 benchmark 退步时自动回滚；`--ratchet` 保证不接受低于历史最高的分数。

每次 `evaluate-skill` / `improve-skill` 运行后，引擎向 `artifacts/<skill>/history.jsonl` 追加一条 JSONL 记录（skill 源树保持只读）：

```json
{
  "timestamp": "2026-06-22T12:00:00Z",
  "skill": "skills/my-skill",
  "commit_or_backup": "a1b2c3d",
  "old_score": 72.3,
  "new_score": 78.5,
  "status": "keep",
  "dimension": "D3",
  "note": "Added if-then fallback tables",
  "eval_mode": "static",
  "metadata": {}
}
```

**字段定义**：

| 字段 | 含义 |
|---|---|
| `timestamp` | ISO 8601 UTC 时间戳 |
| `skill` | skill 目录路径 |
| `commit_or_backup` | 当时的 git commit，或无 git 时的备份标识 |
| `old_score` / `new_score` | 本轮前后的 Rubric 总分 |
| `status` | `baseline` / `keep` / `revert` / `error` / `human-decide` |
| `dimension` | 本轮目标维度；baseline 记录为 `all` |
| `note` | 本轮改动的文字说明 |
| `eval_mode` | `full_test` / `dry_run` / `static` |
| `metadata` | 可选的附加信息（dict） |

查看历史：`improve-skill skills/<skill> --history`。历史数据用于追踪每轮优化的成败、识别触顶信号（连续低 Δ），并为探索性重写和策略调整提供依据。

### 10.3 棘轮模式（Ratchet）

`evaluate-skill --ratchet` 将当前 scorecard 与上一次 scorecard 对比，任一 Skill 融合总分下降即返回非零退出码。配合 CI 使用可防止退化。

---

## 十一、架构说明

三层架构（引擎层 / 可选能力层 / Skill 入口层）、baseline 目录布局（`artifacts/<skill>/baseline/`）、LLM 接入边界等架构事实，统一以 [体系概览](overview.md) 为准，本文不再复述。

---

## 十二、结语

这套框架的核心不是一次性把每个 Skill 打到满分，而是：

1. **让质量可见**：通过 Rubric 把「好/坏」变成数字。
2. **让改进有方向**：每次只攻最短的板。
3. **让效果可验证**：不仅看代码，更看 LLM Agent 能不能用它正确完成任务。

建议先在目标项目内选一个代表性 Skill 做完整 Rubric 评估与一次 PDCA 迭代，跑通后再批量推广到全部 Skill。
