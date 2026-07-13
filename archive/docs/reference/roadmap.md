# TODO 与路线图

本文档记录 skillPrism 已完成的里程碑和已知的改进方向。

---

## ✅ 已完成（截至当前版本）

- [x] 确定性 rubric 引擎，9 个维度（D1–D9）。
- [x] 通过 `skill_rubric_types.yaml` 实现项目无关的类型注册。
- [x] 可安装的 Python 包（`skillprism`），提供 7 个 CLI 入口：
  `evaluate-skill`、`test-skill`、`build-skill-test`、`improve-skill`、
  `skill-pipeline`、`skill-ci`、`skill-gradual`。
- [x] 可选的 LLM-as-judge，用于主观维度（D2/D5），具备：
  - provider 无关的子进程/调用方接口，
  - JSON schema 校验，
  - 重试逻辑，
  - 分数截断（clamping），
  - 针对引擎分数的 outlier 保护。
- [x] Benchmark 框架：task 由 task spec（`benchmarks/<skill>/tasks/<task>.yaml`）声明，
  引擎不内置 task 类型实现；`clustering`、`table`、`document`、`deconvolution`
  为约定类型并配有对应 metric，可通过 entry points / registry 插件扩展新 task。
- [x] 真实可运行的 `document` benchmark 示例（`examples/benchmark_minimal/`，
  使用确定性的 SKILL.md 生成器）。
- [x] 人在回路优化循环（`improve-skill`）：dry-run judge、`--apply` 闸门、
  反模式 guard、`--ratchet` 模式。
- [x] 质量流水线编排器（`skill-pipeline` CLI），支持多种意图。
- [x] Agent 原生的 SKILL.md 入口与 Agent 交互指南。
- [x] `pytest` 测试套件（58 个测试文件，367 个用例）。
- [x] 中英文 README、操作手册与 scorecard 示例。
- [x] Benchmark `suite` 分组与 `expected_result: fail` 负向测试。
- [x] 结构化 JSON/YAML/Markdown benchmark 输出。
- [x] 智能优化循环：维度优先级、维度簇、`--no-stop-on-regression`。
- [x] 端到端 optimize 测试，覆盖 baseline → edit → judge → keep。
- [x] 自定义 benchmark task 插件 API（entry points 与 registry 插件）。
- [x] 按类型的 `SKILL.md` 模板：`analysis`、`cmd`、`api`、`document`。
- [x] Judge 报告渲染 SKILL.md diff 并导出 JSON。
- [x] `--edit-code` 标志允许自动编辑修改代码资产，带快照/回滚。
- [x] MkDocs 静态文档站点（Material 主题）。
- [x] `docs/tutorial/` 下的 8 章书式教程。
- [x] `skillprism.testing` 模块，提供 mock 数据与边界用例辅助。
- [x] Benchmark 框架增强：`level`（0-3）、`requires_gpu`、`real_data`、suite 回归。
- [x] `skillprism.ci` 模块与 `skill-ci` CLI（run、compare、ratchet、stop-on-regression）。
- [x] 失败模式优先的渐进流水线：`test-skill --mode gradual` 与 `skill-gradual` CLI，
  已集成到 `skills/skill-prism/SKILL.md`。
- [x] 端到端 cell2location 示例，含 level 0-3 benchmark。
- [x] 编排器 `--intent "run gradual pipeline"` 集成。
- [x] MIT 许可证。
- [x] 工程化工具链：
  - `ruff` lint/format 配置，
  - `pytest-cov` 覆盖率配置，
  - `pre-commit` hooks，
  - `Makefile`，
  - `CONTRIBUTING.md`，
  - GitHub Actions CI 工作流（多 Python 版本矩阵）。
- [x] `mypy --strict` 类型检查覆盖整个 `skillprism/`（`pyproject.toml` 中
  `strict = true`，`make type-check` 通过）。
- [x] 按 skill 类型的 `enabled_dimensions`，以及用于框架级 skill 的专用 `meta` 类型。
- [x] LLM judge 可复现性元数据（`model`、`temperature`、`prompt_version`）
  与可配置的按维度 prompt 模板。
- [x] `scripts/langfuse_to_benchmark.py`：从 Langfuse trace 生成 benchmark 条目。

---

## 📋 短期待办

### Benchmark 与真实场景验证

- [x] 添加真实的 `deconvolution` benchmark 示例，含合成与真实数据级别
  （`examples/benchmark_cell2location/`）。
- [ ] 添加真实的 `clustering` benchmark，使用可下载的 scRNA-seq 数据与金标准标签
  （当前示例使用 `scanpy.datasets.pbmc3k_processed`）。
- [ ] 添加真实的 `table` benchmark，使用 CSV 输入与期望输出。
- [ ] 添加至少一个基因组学以外领域的 benchmark（如 SQL 查询生成、API 编排）。
- [x] 在 `docs/tutorial/` 中提供 `build-skill-test` 分步示例。

### LLM-as-Judge 加固

- [x] 单个可选 LLM judge，带 schema 校验、重试与 outlier 保护。
- [x] 多评委共识，可配置 `n_judges` 与聚合方式（`median`、`mean`、`min`、`max`）。
- [ ] 用小型人工标注集校准 LLM judge。
- [ ] 增加 prompt 注入 / 对抗性输出检测。
- [ ] 支持按维度覆盖权重。
- [ ] 采集并暴露 LLM judge 的延迟/成本指标。

### 优化循环

- [x] 提供 `--auto-edit` 作为可选的一站式自主优化器（已完成）。引擎保持无 LLM；
  editor 是外部的、provider 无关的命令。
- [x] 为 `--auto-edit` 增加 `--max-rounds` 自动迭代。
- [x] 增加按维度的编辑策略模板（D1–D9）。
- [x] 提供 OpenAI、Anthropic、Ollama 的 editor wrapper 示例。
- [x] 增加端到端测试，覆盖 `--record-baseline`、编辑、`--judge`、
  `--apply` 的 keep/revert。
- [x] 在 judge 报告中自动渲染 diff。
- [x] 增加 `--max-rounds` 保护与 `--no-stop-on-regression` 选项。
- [x] 支持在显式 `--edit-code` 标志下编辑代码资产，并附加 smoke/benchmark 闸门。

### Skill 入口层

- [ ] 为 Agent 使用增加交互式确认包装（如 `ask_user` 辅助函数）。
- [x] 为每种内置类型（`analysis`、`cmd`、`api`、`document`）提供
  按 skill 的 `SKILL.md` 模板。
- [ ] 增加 judge 结果解析辅助，便于 Agent 以编程方式消费引擎输出。
- [ ] 为常见 LLM provider（OpenAI、Anthropic、本地 vLLM/ollama）提供
  `scripts/my_skill_editor.py` wrapper 示例。

---

## 🚀 中期路线图

- [ ] **CI/CD 自举（dogfooding）**：在每次 CI 构建中对本仓库自身运行 skillPrism，
  任何 skill 回归即构建失败。
- [x] **文档网站**：从 Markdown 文件迁移到带搜索的静态站点（MkDocs）。
- [x] **可搜索的 API 参考**：从 docstring 自动生成 API 文档。
- [ ] **Registry 版本化**：对 `skill_rubric_types.yaml` 做版本管理，
  并提供 schema 版本间的迁移说明。
- [x] **插件 API**：允许第三方包通过 entry points 注册新的 benchmark task
  与 rubric 检查。
- [ ] **更多插件钩子**：允许插件注册新的 rubric 维度与 skill 类型检测器。
- [ ] **Web 仪表盘**：可视化 scorecard 历史与 benchmark 趋势。

---

## 🔬 研究 / 验证

- [ ] 在代表性 skill 语料上关联 rubric 分数与人工评判（Spearman / Kendall）。
- [ ] 研究 `--llm-judge` 对 D2/D5 与人工分数相关性的影响。
- [ ] 在同一组 skill 上对比 `--auto-edit`（用户提供的 LLM editor）与手动
  Agent 编辑的效果。

---

## 如何认领一个条目

1. 开一个 issue，描述该条目与你的方案。
2. 先简要讨论设计，避免返工。
3. 实现时附带测试与文档更新。
4. 确保 `make test` 与 `make lint` 通过。
5. 提交引用本路线图的 pull request。
