# skillPrism 自然语言交互操作手册

> 目标：让 Agent 用户和 CLI 用户都能按步骤完成 Skill 评估、Benchmark 构建与优化。
> 本手册聚焦「怎么操作」，架构设计见 [体系概览](overview.md)，评分算法见 [Rubric 与优化框架](framework.md)，Benchmark 构建细节见 [Benchmark 构造指南](benchmark-guide.md)。

---

## 目录

1. [前置准备](#prerequisites)
2. [Step 1：安装 skillPrism 引擎](#install)
3. [Step 2：准备一个 Skill 与数据](#prepare-skill)
4. [Step 3：评估 Skill（自然语言 + CLI）](#evaluate)
5. [Step 4：构建并运行 Benchmark](#benchmark)
6. [Step 5：优化 Skill（人在回路）](#optimize)
7. [Step 6：运行完整质量流水线](#pipeline)
8. [Step 7：接入 CI / 定期审计](#ci)
9. [附录 A：数据准备清单](#appendix-a)
10. [附录 B：自然语言话术速查](#appendix-b)
11. [附录 C：CLI 速查表](#appendix-c)
12. [附录 D：常见问题](#appendix-d)
13. [附录 E：按类型使用 Skill 模板](#appendix-e)
14. [附录 F：自定义 Benchmark 任务插件](#appendix-f)

---

<a id="prerequisites"></a>

## 一、前置准备
### 1.1 你需要什么

| 角色 | 需要准备 |
|---|---|
| **Agent 用户** | 把 `skills/skill-prism` 复制到 Agent 的 skills 目录 |
| **CLI 用户** | 安装 `skillprism` pip 包 |
| **数据** | 一个能代表该 Skill 真实能力的输入 + 期望输出 |
| **环境** | Python >= 3.9；可选 `shellcheck`、`skillspector`、benchmark 专用依赖 |

### 1.2 核心原则

- **引擎不做 LLM 调用**：评分、benchmark、回滚都是确定性的。
- **默认 dry-run**：`--judge` 只报告决策，必须加 `--apply` 才修改文件。
- **人在回路**：编辑 `SKILL.md` 前/后都要确认。
- **Benchmark 是硬门槛**：Rubric 分数提升但 benchmark 退化 → 回滚。

---

<a id="install"></a>

## Step 1：安装 skillPrism 引擎
### Agent 用户

把仓库中的统一 Agent 入口复制到 Agent 的 skills 目录（以 Claude Code 为例）：

```bash
mkdir -p ~/.claude/skills/skill-prism

cp -r /path/to/Skills_Validation/skills/skill-prism/* ~/.claude/skills/skill-prism/
```

同时安装引擎：

```bash
pip install /path/to/Skills_Validation
```

### CLI 用户

```bash
cd /path/to/Skills_Validation
pip install -e ".[dev]"
```

安装后获得命令：

- `evaluate-skill`：评估 SKILL.md 质量
- `test-skill`：测试生成的代码
- `build-skill-test`：构造 benchmark 注册表
- `improve-skill`：优化 SKILL.md
- `skill-pipeline`：运行完整质量流水线
- `skill-ci`：CI 门控

验证安装：

```bash
evaluate-skill --help
improve-skill --help
test-skill --mode single --help
```

---

<a id="prepare-skill"></a>

## Step 2：确认目标 Skill 与准备数据

> 本节适用于**评估和优化已有 Skill**的场景。如果你要创建新 Skill，只需确保目标目录符合下方结构即可。

### 2.1 目标 Skill 目录结构

skillPrism 评估/优化的最小单元是一个 Skill 目录，通常长这样：

```text
skills/<skill-name>/
├── SKILL.md              # 唯一必需文件
├── scripts/              # 代码资产（可选）
├── examples/             # 示例（可选，强烈建议）
├── requirements.txt      # 依赖（可选，强烈建议）
└── tests/                # 测试（可选）
```

`SKILL.md` 必须包含 frontmatter：

```yaml
---
name: <skill-name>
description: <一句话说明用途>
keywords:
  - <keyword1>
  - <keyword2>
tool_type: python   # python / r / cli / api / document / ...
---
```

### 2.2 数据准备原则

评估只是静态打分；如果要**完整验证** Skill 的能力，就需要为它准备 Benchmark 数据。

| 任务类型 | 需要准备的数据 | 存储位置建议 |
|---|---|---|
| **分析型（analysis）** | 输入数据文件或 builtin 数据集引用；期望输出 | `benchmarks/<skill>/data/<dataset-or-task>/`、`benchmarks/<skill>/expected/<expected-file>` |
| **命令型（cmd）** | 参考基因组/索引声明；工具 `--help` 输出；轻量 smoke 数据 | `benchmarks/<skill>/data/<dataset-or-task>/` |
| **API 型（api）** | endpoint 可达性探测；示例响应 | `benchmarks/<skill>/expected/` |
| **文档型（document）** | prompt 文本；金标准 Markdown | `benchmarks/<skill>/data/prompt.txt`、`benchmarks/<skill>/expected/best_skill.md` |

任务契约（prompt、输入输出格式）统一写在 `benchmarks/<skill>/tasks/<task>.yaml`；`metrics` 与 `expected` 字段在 `benchmarks/<skill>/registry.yaml` 的对应 benchmark 条目中声明。

**数据管理原则**：

1. **大文件不要入 Git**：用 `.gitignore` 忽略 `.benchmark_cache/`、`data/`。
2. **公开数据优先**：使用已发表、有参考标签的数据集。
3. **提供下载脚本**：如果数据不能入 Git，提供 `download.py` 或 `Makefile` 目标。
4. **小样本可入 Git**：< 1 MB 的 CSV、prompt 文本可以提交。

### 2.3 已有 Skill 的评估前检查清单

```bash
# 1. 确认 SKILL.md 存在
ls skills/<skill-name>/SKILL.md

# 2. 确认 frontmatter 完整
head -20 skills/<skill-name>/SKILL.md

# 3. 确认依赖文件（可选但建议）
ls skills/<skill-name>/requirements.txt

# 4. 确认示例可运行（可选但建议）
ls skills/<skill-name>/examples/minimal_example.py
```

如果只想先做**静态 Rubric 评估**，以上检查已足够；如果要跑**完整质量流水线**，继续 Step 4 准备 Benchmark。

---

<a id="evaluate"></a>

## Step 3：评估 Skill（自然语言 + CLI）
### 3.1 自然语言交互

**用户**："评估所有 skills，生成评分卡。"

**Agent 回应**：

> 好的，我将对 `./skills` 下的所有 Skill 运行 Rubric 评估，生成 `docs/SKILL_SCORECARD.md`。默认包含规则增强检查（模糊词、失败模式编码、检查点标记、runtime 红灯扫描）和 test-prompts 自动生成。这是一次纯测量，不会修改任何文件。

**Agent 后台执行**：

```bash
evaluate-skill --all --skills-dir ./skills \
    --output docs/SKILL_SCORECARD.md --run-smoke
```

**Agent 汇报模板**：

```markdown
- 评估了 N 个 Skill
- 最高：<skill>（<score> / 100，Grade <A/B/C/D>）
- 最低：<skill>（<score> / 100，Grade <A/B/C/D>）
- 最常见短板：D<dim>（<dim_name>）
- 需要人工复核的 D5/D9 发现：<count> 个
- 自动生成的 test-prompts：<count> 个
- Runtime 红灯警告：<count> 个
```

### 3.2 CLI 视角

```bash
# 单个 Skill 详细评估（默认启用规则增强、runtime 红灯扫描、test-prompts 自动生成）
evaluate-skill skills/my-skill --detailed

# 批量评估
evaluate-skill --all --skills-dir ./skills \
    --output docs/SKILL_SCORECARD.md \
    --run-smoke --run-deps

# 棘轮模式：分数下降即报错
evaluate-skill --all --skills-dir ./skills \
    --output docs/SKILL_SCORECARD.md --ratchet

# 主观维度第二意见（默认 2 个评委）
evaluate-skill skills/my-skill --llm-judge --llm-judge-count 3

# 不自动生成 test-prompts
evaluate-skill skills/my-skill --no-generate-prompts
```

!!! note "实验历史"
    每次 `evaluate-skill` 都会自动写入 `artifacts/<skill>/history.jsonl`，不需要手动指定路径。`--output-history` 是另一个用于趋势跟踪的全局 JSONL 文件。

### 3.3 结果解读

| 分数 | 等级 | 行动 |
|---|---|---|
| ≥ 90 | A | 标杆候选 |
| 75–89 | B | 可用，按短板修复 |
| 60–74 | C | 必须修复明显缺陷 |
| < 60 | D | 不建议上线 |
| D9 < 3 | — | 阻塞：存在高危安全模式 |

---

<a id="benchmark"></a>

## Step 4：构建并运行 Benchmark
### 4.1 数据准备

假设你要为已有的 `my-skill` 新增一个 table benchmark，数据准备如下：

```bash
mkdir -p benchmarks/my-skill/data/sales/input
mkdir -p benchmarks/my-skill/expected/sales

cat > benchmarks/my-skill/data/sales/input/sales.csv <<'EOF'
product,region,revenue
A,North,100
B,South,200
A,North,150
C,East,300
EOF

# 金标准输出（手动或脚本生成）
# 这里使用 pandas.DataFrame.describe() 的真实输出
cat > benchmarks/my-skill/expected/sales/sales_summary.csv <<'EOF'
,revenue
count,4.0
mean,187.5
std,85.39125638299666
min,100.0
25%,137.5
50%,175.0
75%,225.0
max,300.0
EOF
```

### 4.2 注册 Benchmark

```bash
build-skill-test \
  --id csv_summary_sales \
  --name "CSV Summary: Sales" \
  --skill my-skill \
  --task table \
  --dataset-source data/sales/input/sales.csv \
  --dataset-type local \
  --expected-path expected/sales/sales_summary.csv \
  --expected-format csv \
  --metric row_count:min:8 \
  --metric col_count:min:2 \
  --metric max_revenue:min:300 \
  --registry benchmarks/my-skill/registry.yaml
```

### 4.3 编写 Skill 代码

`sample_skill_code.py`：

```python
import pandas as pd

df = pd.read_csv(input_csv)
summary = df.describe()
summary.to_csv(output_csv)
```

### 4.4 运行 Benchmark

```bash
test-skill --mode single --skill my-skill \
    --registry benchmarks/my-skill/registry.yaml \
    --code sample_skill_code.py
```

### 4.5 渐进测试与基线

对于计算昂贵的 skill，使用渐进测试：

```bash
# 从 level 0 跑到 level 2，逐级放行
test-skill --mode gradual --skill my-skill \
    --registry benchmarks/my-skill/registry.yaml \
    --code sample_skill_code.py \
    --max-level 2
```

每级通过后会自动把 baseline 保存到 `artifacts/<skill>/ci/gradual/.baselines/<skill>/gradual_baseline_level<N>.yaml`。

```bash
# 只跑 smoke suite
test-skill --mode single --skill my-skill \
    --registry benchmarks/my-skill/registry.yaml \
    --code sample_skill_code.py \
    --suite smoke

# 快速 gate：level 0 + level 1
test-skill --mode quick --skill my-skill \
    --registry benchmarks/my-skill/registry.yaml \
    --code sample_skill_code.py
```

### 4.6 对比基线

```bash
# 运行并输出到指定目录
test-skill --mode single --skill my-skill \
    --registry benchmarks/my-skill/registry.yaml \
    --code sample_skill_code_v2.py \
    --output-dir latest

# 对比基线
python templates/regression_test.py \
    --results latest/my-skill.yaml \
    --baseline baselines/my-skill.yaml \
    --tolerance 0.03
```

### 4.7 使用 Suite 组织 Benchmark

在 `benchmarks/<skill>/registry.yaml` 中可以把多个 benchmark 分组：

```yaml
suites:
  smoke:
    description: 轻量快速验证
    benchmarks:
      - csv_summary_sales
      - csv_summary_inventory
  regression:
    description: 全量回归
    benchmarks:
      - csv_summary_sales
      - single_cell_clustering
```

运行：

```bash
test-skill --mode single --skill my-skill --registry benchmarks/my-skill/registry.yaml --suite smoke
```

### 4.8 预期失败的用例

某些 benchmark 用来验证 Skill 在错误输入下是否能优雅失败。注册时加 `expected_result: fail`：

```yaml
benchmarks:
  corrupted_csv_should_fail:
    name: "Corrupted CSV should fail gracefully"
    task: table
    expected_result: fail
    expected_error: ".*ParserError.*"
```

只要返回的错误信息匹配 `expected_error` 正则，该 benchmark 即算通过。

---

<a id="optimize"></a>

## Step 5：优化 Skill（人在回路）
### 5.1 自然语言交互流程

**用户**："优化 my-skill。"

**Agent 回应**：

> 我会按以下步骤优化，每轮都会先征求你的意见：
> 1. 记录当前 SKILL.md 的 baseline。
> 2. 找出 Rubric 最弱维度。
> 3. 告诉你我的修改计划，等你批准。
> 4. 我修改 SKILL.md，展示 diff。
> 5. 引擎 judge 决定保留或回滚。
> 6. 询问你是否继续下一轮。
>
> 默认只改 `SKILL.md`，不会动代码资产。

#### 第 1 步：记录 baseline

```bash
improve-skill skills/my-skill --record-baseline \
    --benchmark-registry benchmarks/my-skill/registry.yaml
```

#### 第 2 步：识别短板

```bash
improve-skill skills/my-skill --suggest
```

**Agent 汇报示例**：

> 最弱维度是 **D4（环境/依赖可复现性）**：缺少 requirements.txt 和安装说明。
>
> 所属簇：**结构簇**（D1-D4），建议同时检查 D2、D3 是否也能一起提升。
>
> P0-P3 策略：**P1 · structure**——重组 workflow、补充 frontmatter、添加检查点。

#### 第 3 步：提出修改计划并请求批准

**Agent 对用户说**：

> 我计划对 `skills/my-skill/SKILL.md` 做如下修改：
> - 增加 `requirements.txt` 示例；
> - 在 SKILL.md 中补充依赖安装命令；
> - 添加 Python 版本说明。
>
> 这次只改 **D4** 一个维度，保持变量单一。
>
> 是否继续？（继续 / 跳过 / 停止）

#### 第 4 步：Agent 编辑 SKILL.md

Agent 用自身 LLM 编辑 `SKILL.md`。**默认只改 SKILL.md，且只改一个维度**；改代码资产需额外授权。

#### 第 5 步：展示 diff 并运行 judge（dry-run）

```bash
git diff -- skills/my-skill/SKILL.md
improve-skill skills/my-skill --judge \
    --benchmark-registry benchmarks/my-skill/registry.yaml
```

#### 第 6 步：用户确认后 apply

```bash
improve-skill skills/my-skill --apply \
    --benchmark-registry benchmarks/my-skill/registry.yaml
```

#### 第 7 步：询问是否继续

> 编辑已保留，baseline 已更新。是否继续下一轮优化？（继续 / 停止）

#### 第 8 步：触顶时探索性重写

如果连续多轮分数提升很小（hill-climbing 触顶），Agent 可以建议：

> 当前优化似乎进入局部最优，是否尝试从头重写 SKILL.md？

```bash
improve-skill skills/my-skill --explore-rewrite --apply
```

#### 第 9 步：查看优化历史

```bash
improve-skill skills/my-skill --history
```

会输出 `artifacts/<skill>/history.jsonl` 中的尝试记录。

### 5.2 一键自动优化（需配置 editor）

```bash
export SKILLPRISM_EDITOR_COMMAND="python examples/editor_wrappers/openai_editor.py"

improve-skill skills/my-skill \
    --record-baseline \
    --benchmark-registry benchmarks/my-skill/registry.yaml \
    --auto-edit --apply --max-rounds 3
```

> `--auto-edit` 会实际改写 `SKILL.md`，必须搭配 `--apply`。

#### 自动优化高级参数

```bash
# 遇到回滚立即停止（保守模式）
improve-skill skills/my-skill --auto-edit --apply --max-rounds 5 --stop-on-regression

# 允许一定分数下降，只要 benchmark 有改善（探索模式）
improve-skill skills/my-skill --auto-edit --apply --max-rounds 5 --allow-regression 1.0

# 输出 judge 结果为 JSON，方便接入流水线
improve-skill skills/my-skill --judge --apply --output-json results/judge.json
```

### 5.3 主观维度第二意见（LLM-as-judge）

如果你希望 D2 可读性、D5 领域准确性等主观维度有 LLM 第二意见，可配置外部 judge 命令：

```bash
export SKILLPRISM_LLM_JUDGE_COMMAND="python scripts/my_llm_judge.py"

# 评估时启用（默认 2 个独立评委）
evaluate-skill skills/my-skill --detailed --llm-judge

# 优化时启用
improve-skill skills/my-skill --judge --llm-judge --apply
```

judge 命令从 stdin 读 prompt，输出 JSON：`{"score": 4, "reason": "..."}`。

默认 `n_judges=2`，聚合方法为 `median`。可通过 `--llm-judge-count` 调整。

> 对 Agent 用户来说，直接说"再帮我看看可读性和领域准确性"即可，Agent 会自己决定是否启用。

---

<a id="pipeline"></a>

## Step 6：运行完整质量流水线
### 6.1 自然语言交互

**用户**："运行 skill 质量流水线。"

**Agent 回应**：

> 我将依次执行：Rubric 评估 → Benchmark 运行与基线对比 → 识别最差 Skill → 生成合并报告。不修改任何文件。

**Agent 后台执行**：

```bash
skill-pipeline --intent "run full quality pipeline" \
    --skills-dir ./skills \
    --benchmark-registry benchmarks/<skill>/registry.yaml \
    --output docs/SKILL_QUALITY_REPORT.md \
    --run-smoke
```

**Agent 汇报模板**：

```markdown
## Skill Quality Report Summary
- Skills evaluated: N
- Benchmarks run: M
- Overall rubric pass rate: X%
- Worst skill: <name> (<score> / 100, Grade <grade>)
- Weakest dimension: D<dim>
- Recommended next command: `improve-skill skills/<worst> --record-baseline`
```

### 6.2 支持的意图

| 意图 | 行为 |
|---|---|
| `"evaluate all skills"` / `"score all skills"` | 只跑 Rubric |
| `"run benchmarks"` | 只跑 Benchmark 并对比基线 |
| `"run full quality pipeline"` | Rubric → Benchmark → 识别最差 Skill → 报告 |
| `"optimize skills"` / `"improve skills"` | 跑完整流水线 → 为最差 Skill 记录 baseline |
| `"run gradual pipeline"` / `"run darwin pipeline"` | 跑 level 0→3 渐进测试 |

---

<a id="ci"></a>

## Step 7：接入 CI / 定期审计
### 7.1 GitHub Actions

复制 `.github/workflows/skill-rubric-ci.yaml` 到目标项目，默认在 PR 修改 `skills/**`、`skillprism/**`、`tests/**` 时触发。

### 7.2 本地 pre-commit

```bash
pre-commit install
make lint
make test
make docs-ci
```

### 7.3 季度评审

```bash
# 生成全量评分卡 + 历史
evaluate-skill --all --skills-dir ./skills \
    --output docs/SKILL_SCORECARD.md \
    --output-history docs/skill_history.jsonl \
    --run-smoke --run-deps

# 运行完整流水线
skill-pipeline --intent "run full quality pipeline" \
    --skills-dir ./skills \
    --benchmark-registry benchmarks/<skill>/registry.yaml \
    --output docs/SKILL_QUALITY_REPORT.md
```

产出：

- `docs/SKILL_SCORECARD.md`
- `docs/SKILL_QUALITY_REPORT.md`
- `docs/skill_history.jsonl`

---

<a id="appendix-a"></a>

## 附录 A：数据准备清单
| 步骤 | 检查项 |
|---|---|
| 1 | Skill 目录包含 `SKILL.md` 且 frontmatter 完整 |
| 2 | 输入数据已放入 `benchmarks/<skill>/data/<dataset-or-task>/` 或提供下载脚本 |
| 3 | 期望输出已放入 `benchmarks/<skill>/expected/` |
| 4 | 任务契约已写入 `benchmarks/<skill>/tasks/<task>.yaml` |
| 5 | `benchmarks/<skill>/registry.yaml` 已注册该 benchmark |
| 6 | 运行 `test-skill --mode single` 验证通过 |
| 7 | 基线已保存到 `baselines/` |

---

<a id="appendix-b"></a>

## 附录 B：自然语言话术速查
| 你想说 | 实际调用的命令 |
|---|---|
| "评估所有 skills" | `evaluate-skill --all --skills-dir ./skills --output docs/SKILL_SCORECARD.md` |
| "完整评估 X" | `evaluate-skill skills/X --detailed` + `test-skill --mode single --skill X --code ... --registry benchmarks/X/registry.yaml` |
| "优化 X" | `improve-skill skills/X --record-baseline --benchmark-registry benchmarks/X/registry.yaml` → `--suggest` → 编辑 → `--judge --benchmark-registry benchmarks/X/registry.yaml` → `--apply --benchmark-registry benchmarks/X/registry.yaml` |
| "自动优化 X" | `improve-skill skills/X --record-baseline --benchmark-registry benchmarks/X/registry.yaml --auto-edit --apply --max-rounds 3` |
| "探索性重写 X" | `improve-skill skills/X --explore-rewrite --apply` |
| "查看 X 的优化历史" | `improve-skill skills/X --history` |
| "运行质量流水线" | `skill-pipeline --intent "run full quality pipeline" --skills-dir ./skills --benchmark-registry benchmarks/<skill>/registry.yaml` |
| "渐进测试 X" | `test-skill --mode gradual --skill X --code ... --registry benchmarks/X/registry.yaml --max-level 2` |
| "扫描安全问题" | `evaluate-skill --all --skills-dir ./skills --output docs/SECURITY_SCORECARD.md` |

---

<a id="appendix-c"></a>

## 附录 C：CLI 与自然语言对照速查表

### 自然语言 → CLI 命令

| 你想做什么 | 对 Agent 这样说 | 对应 CLI |
|---|---|---|
| 评估一个 skill | "帮我看看这个 skill 写得怎么样" | `evaluate-skill skills/<skill>` |
| 评估所有 skills | "评估所有 skills" | `evaluate-skill --all --skills-dir ./skills` |
| 深入检查可读性/领域准确性 | "再帮我看看可读性和领域准确性" | `evaluate-skill skills/<skill> --llm-judge` |
| 跑单个 benchmark | "跑一下这个 skill 的 benchmark" | `test-skill --mode single --skill <skill> --registry benchmarks/<skill>/registry.yaml --code ...` |
| 渐进测试 | "帮我做渐进测试" | `test-skill --mode gradual --skill <skill> --registry benchmarks/<skill>/registry.yaml --code ...` |
| 快速 gate | "快速验证一下" | `test-skill --mode quick --skill <skill> --registry benchmarks/<skill>/registry.yaml --code ...` |
| 优化 skill | "帮我优化这个 skill" | `improve-skill skills/<skill> --record-baseline --benchmark-registry benchmarks/<skill>/registry.yaml --suggest --judge --apply` |
| 自动优化 | "自动帮我改到不能改为止" | `improve-skill skills/<skill> --record-baseline --benchmark-registry benchmarks/<skill>/registry.yaml --auto-edit --apply --max-rounds 5` |
| 查看优化历史 | "看看这个 skill 的优化记录" | `improve-skill skills/<skill> --history` |
| 运行完整流水线 | "跑一下完整质量流水线" | `skill-pipeline --intent "run full quality pipeline" --skills-dir ./skills --benchmark-registry benchmarks/<skill>/registry.yaml` |
| CI 检查 | "接入 CI" / "跑 CI 门控" | `skill-ci --skill <skill> --registry benchmarks/<skill>/registry.yaml` |

### 全局常用参数

| 参数 | 作用 | 适用命令 |
|---|---|---|
| `--skills-dir` | 指定 skills 根目录 | `evaluate-skill`, `skill-pipeline` |
| `--config` | 指定 `skill_rubric_types.yaml` | `evaluate-skill`, `improve-skill` |
| `--output` | 输出报告路径 | `evaluate-skill`, `skill-pipeline` |
| `--verbose` / `-v` | 打印详细评分过程 | 所有 |
| `--apply` | 真正执行 keep/revert，否则 dry-run | `improve-skill` |
| `--ratchet` | 分数不 regress | `evaluate-skill`, `improve-skill` |

### `evaluate-skill` 参数

| 参数 | 作用 | 常用场景 |
|---|---|---|
| `--detailed` | 输出每维度证据与建议 | 日常评估 |
| `--all` | 批量评估 `--skills-dir` 下所有 skill | 生成 scorecard |
| `--run-smoke` | 运行示例/代码冒烟测试 | 验证可执行性 |
| `--run-deps` | 检查依赖是否可安装 | CI / 可复现性 |
| `--llm-judge` | 主观维度第二意见 | D2/D5 需要更细判断 |
| `--llm-judge-count N` | 评委数量（默认 2） | 提高主观评分稳定性 |
| `--output-history <path>` | 写入全局趋势 JSONL | 追踪历史变化 |

### `test-skill` 参数

| 参数 | 作用 | 常用场景 |
|---|---|---|
| `--mode single` | 跑单个或某 level/suite 的 benchmark | 日常验证 |
| `--mode gradual` | level 0 → max-level 逐级放行 | 发布前完整验证 |
| `--mode quick` | level 0 + level 1 快速 gate | PR / 快速检查 |
| `--skill <skill>` | skill 名或路径 | 所有 mode |
| `--code <path>` | 要执行的生成代码文件 | 所有 mode |
| `--registry <path>` | benchmark 注册表 YAML | 所有 mode |
| `--level N` | single 模式下只跑某一级 | 单独调试 |
| `--max-level N` | gradual 模式下最高级 | 控制成本 |
| `--suite <name>` | 只跑某 suite | 跑 smoke / regression |
| `--output <path>` | 保存结果 YAML | 基线对比 |

### `build-skill-test` 参数

| 参数 | 作用 | 常用场景 |
|---|---|---|
| `--id <id>` | benchmark 唯一标识 | 必填 |
| `--name <name>` | 人类可读名称 | 必填 |
| `--skill <skill>` | 关联标签：具体 skill 名或 skill 类型（可重复） | 必填。推荐用具体 skill 名 |
| `--task <task>` | task 契约 | 必填 |
| `--level {0,1,2,3}` | benchmark 难度等级 | 默认 1 |
| `--dataset-source <path>` | 输入数据路径/表达式 | 必填 |
| `--dataset-type {local,url,builtin}` | 数据类型 | 自动推断 |
| `--expected-path <path>` | 金标准输出路径 | 推荐 |
| `--expected-format <format>` | 输出格式 | 自动推断 |
| `--metric <spec>` | 指标定义，可重复 | 默认用 task 模板 |
| `--suite <name>` | 加入指定 suite，可重复 | 组织 suite |
| `--registry <path>` | 注册表文件 | 默认 `benchmarks/<skill>/registry.yaml` |
| `--generate-expected` | 自动生成 expected（仅部分 task 支持） | table 简单复制 |
| `--gpu` | 标记需要 GPU | GPU 任务 |
| `--real-data` | 标记真实数据（只检查完成，不评分） | level 3 |

### `improve-skill` 参数

| 参数 | 作用 | 常用场景 |
|---|---|---|
| `--record-baseline` | 记录当前 Rubric/benchmark 作为基线 | 优化第一步 |
| `--suggest` | 打印最弱维度与策略建议 | 决定改哪里 |
| `--judge` | 对比 baseline，决定 keep/revert | 编辑后评估 |
| `--apply` | 真正执行 keep/revert | 确认决策后 |
| `--auto-edit` | 调用外部 editor 自动改 SKILL.md | 自动优化 |
| `--max-rounds N` | 自动优化最大轮数 | 控制成本 |
| `--min-gain <float>` | 最低分数提升才保留（默认 1.0） | 过滤微提升 |
| `--stop-on-regression` | 遇到回滚立即停止 | 保守自动优化 |
| `--explore-rewrite` | 探索性重写 SKILL.md | 跳出局部最优 |
| `--history` | 查看优化历史 | 复盘 |
| `--benchmark-registry <path>` | 启用 benchmark gate | 需要验证代码时 |
| `--edit-code` | 允许 editor 修改代码资产 | 默认只改 SKILL.md |

### `skill-pipeline` 参数

| 参数 | 作用 | 常用场景 |
|---|---|---|
| `--intent <text>` | 自然语言意图 | 必填 |
| `--skills-dir` | skills 根目录 | 批量 |
| `--benchmark-registry <path>` | benchmark 注册表 | 含 benchmark 的意图 |
| `--output <path>` | 统一质量报告 | 生成报告 |
| `--run-smoke` | 同时跑 smoke test | 完整检查 |

### `skill-ci` 参数

| 参数 | 作用 | 常用场景 |
|---|---|---|
| `--skill <skill>` | 目标 skill | CI |
| `--registry <path>` | benchmark 注册表 | CI |
| `--output-dir <path>` | CI 产物目录 | CI |
| `--run-benchmark` | 同时运行动态 benchmark（需 `--code`） | 完整 CI |
| `--code <path>` | 预生成的 skill 代码 | `--run-benchmark` 时必需 |
| `--baseline <path>` | 基线结果 YAML | 回归门控 |
| `--stop-on-regression` | benchmark 退化即失败 | 严格 CI |
| `--ratchet` | 通过时更新基线 | 自动 ratchet |
| `--no-smoke` | 跳过 smoke test | 快速 CI |
| `--no-deps` | 跳过依赖检查 | 快速 CI |

### 常用组合示例

```bash
# 生成完整 scorecard
evaluate-skill --all --skills-dir ./skills \
    --output docs/SKILL_SCORECARD.md --run-smoke --run-deps

# 跑单个 benchmark
test-skill --mode single --skill <skill> \
    --registry benchmarks/<skill>/registry.yaml \
    --code sample_skill_code.py

# 渐进测试到 level 2
test-skill --mode gradual --skill <skill> \
    --registry benchmarks/<skill>/registry.yaml \
    --code sample_skill_code.py --max-level 2

# 手动优化循环
improve-skill skills/<skill> --record-baseline \
    --benchmark-registry benchmarks/<skill>/registry.yaml
improve-skill skills/<skill> --suggest
# 编辑 SKILL.md
improve-skill skills/<skill> --judge --apply \
    --benchmark-registry benchmarks/<skill>/registry.yaml

# 自动优化 3 轮
improve-skill skills/<skill> --auto-edit --apply --max-rounds 3 \
    --benchmark-registry benchmarks/<skill>/registry.yaml

# 构造 benchmark
build-skill-test \
    --id csv_summary_sales \
    --name "CSV Summary: Sales" \
    --skill my-first-table \
    --task table \
    --dataset-source data/sales/input/sales.csv \
    --expected-path expected/sales/sales_summary.csv \
    --metric row_count:min:8 \
    --registry benchmarks/my-first-table/registry.yaml

# 完整质量流水线
skill-pipeline --intent "run full quality pipeline" \
    --skills-dir ./skills \
    --benchmark-registry benchmarks/<skill>/registry.yaml \
    --output docs/SKILL_QUALITY_REPORT.md --run-smoke
```

---

<a id="appendix-d"></a>

## 附录 D：常见问题
### Q1：安装后 `skillprism` 无法 import

确认包已正确安装：

```bash
pip install -e ".[dev]"
python -c "import skillprism; print(skillprism.__file__)"
```

### Q2：`--auto-edit` 报错 "no skill editor configured"

需要配置 editor 命令：

```bash
export SKILLPRISM_EDITOR_COMMAND="python examples/editor_wrappers/openai_editor.py"
```

### Q3：Benchmark 因数据文件损坏失败

删除缓存/下载的损坏文件，重新运行。例如：

```bash
rm -f examples/benchmark_minimal/data/pbmc3k_processed.h5ad
```

### Q4：judge 退出码为 1

表示编辑被回滚。检查：

- Rubric 分数是否没有提升（delta < `--min-gain`）
- benchmark 是否 regress
- 是否触发 guard block

### Q5：`--run-deps` 很慢

`pip install --dry-run` 需要解析依赖图。首次慢，后续可缓存；或在 CI 中单独跑。

### Q6：smoke test 运行示例失败

检查示例是否自包含。推荐在示例中使用内置数据集或提供下载脚本。

---

<a id="appendix-e"></a>

## 附录 E：按类型使用 Skill 模板
skillPrism 为常见 Skill 类型提供模板，复制后按需修改：

```bash
# 分析型（Python/R 数据分析）
cp -r templates/analysis skills/my-analysis-skill

# 命令型（shell/cli 工具）
cp -r templates/cmd skills/my-cmd-skill

# API 型（REST/HTTP 调用）
cp -r templates/api skills/my-api-skill

# 文档型（报告/文档生成）
cp -r templates/document skills/my-document-skill
```

每个模板包含 `SKILL.md`、示例代码和 `requirements.txt`。

---

<a id="appendix-f"></a>

## 附录 F：自定义 Benchmark 任务插件
如果内置任务（`table`、`clustering`、`document`、`deconvolution`）不满足需求，可以注册自定义任务。

**Python 入口点方式**（适合发布为 pip 包）：

```python
# setup.py / pyproject.toml
[project.entry-points."skillprism.benchmark.task"]
my_task = "my_package.benchmarks:my_task"
```

**Registry 内联方式**（适合单仓库脚本）：

```yaml
plugins:
  - my_plugin.run

benchmarks:
  my_custom_bench:
    name: "Custom benchmark"
    task: run
    skills: [analysis]
```

插件函数签名：

```python
def my_task(benchmark, skill, code_path, registry, registry_dir):
    return {"_all_pass": True, "custom_metric": 0.95}
```

自定义任务优先于内置任务，失败时会回退到内置任务的错误信息。
