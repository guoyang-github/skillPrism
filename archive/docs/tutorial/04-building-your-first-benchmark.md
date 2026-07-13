> 学习目标：理解新架构下 benchmark 的完整流程，为一个 table skill 准备 task spec、数据、注册表，并跑通验证。

# 第 4 章：构建你的第一个 Benchmark

## 4.1 为什么需要 Benchmark

Rubric 评分是静态的；Benchmark 是动态的。它验证 Skill 在真实输入上能否产生正确的输出。

一句话概括 benchmark 的流程：

```text
Task Spec（任务契约）+ 输入数据 + Agent/代码 → 产生输出 → 与金标准对比 → 计算指标 → PASS/FAIL
```

## 4.2 Benchmark 的五个组成部分

| 组成部分 | 作用 | 谁来写 | 存放位置示例 |
|---|---|---|---|
| **Task Spec** | 描述任务：输入输出格式、给 Agent 的 prompt | Skill / Benchmark 作者 | `benchmarks/<skill>/tasks/<task>.yaml` |
| **输入数据** | 给 Skill 执行的原材料 | 用户 / Agent / 参考脚本 | `benchmarks/<skill>/data/<dataset-or-task>/` |
| **执行代码（可选）** | 把输入转换成输出的可执行脚本 | 用户 / Agent / Skill 作者 | `sample_skill_code.py` |
| **金标准输出（expected）** | 人工或脚本生成的正确结果 | 用户 / Agent / 参考实现 | `benchmarks/<skill>/expected/<expected-file>` |
| **注册表（registry）** | 告诉 skillPrism 这个 benchmark 的元数据、金标准和指标 | `build-skill-test` 生成 | `benchmarks/<skill>/registry.yaml` |

!!! tip "关键概念"
    - `build-skill-test` 只负责**生成注册表**，它不跑代码、不写执行代码、也不生成金标准（`--generate-expected` 只对部分 task 做简单复制）。
    - `test-skill` 负责**加载 task spec、生成 prompt、调用 Agent/执行代码、计算指标**。
    - Task spec 是 Skill 特异性的：每个 Skill 描述自己要测什么任务，而不是使用通用 task 类型。

### `--code` 与插件：两种执行深度

| 对比项 | `--code sample_skill_code.py` | 自定义插件 |
|---|---|---|
| **角色** | 被测对象：Agent/用户按 SKILL.md 生成的可执行代码 | 任务 harness：完全自定义 benchmark 的执行逻辑 |
| **谁写** | Agent 或 Skill 作者 | Benchmark 作者（你或 Agent） |
| **注入变量** | task spec 规定的占位符变量，如 `input_csv`、`output_csv` | 插件函数签名 `run(benchmark, skill, code_path, registry, registry_dir)` |
| **适用场景** | 简单、单文件、直接处理输入 | 复杂、多步、需要预处理或完全控制执行过程 |
| **文件位置** | 任意路径，通过 `--code` 传入 | registry 内联 `plugins:` 或 entry point 注册 |
| **是否被评估** | **是**，它的输出会被拿来与 expected 对比 | 由插件自行组织执行并产出输出文件 |

简单记忆：**`--code` 是学生答卷**——验证 Skill 的执行能力；**插件是自带考场的考试**——当 task spec + `--code` 表达不了你的任务时才需要。

多数场景用 `--code` 就够了。插件机制详见 [扩展 benchmark 任务类型](../reference/adding-a-benchmark-task-type.md)。

## 4.3 理解 Level 0-3 的数据策略

渐进测试把 benchmark 分成 4 个 level，难度与数据规模递增：

| Level | 典型数据 | 核心目标 | 数据从哪来 |
|---|---|---|---|
| **0** | 最小（如 10 行、10 个 spot） | 冒烟：不崩溃、输出形状正确 | 用户准备或 `skillprism.testing.mock_data` 生成 |
| **1** | 小（如 50-100 样本） | 数值回归：基本逻辑正确 | 用户准备或 mock_data 生成 |
| **2** | 中（如 200-500 样本） | 稳定性、更严格的阈值 | 用户准备或 mock_data 生成 |
| **3** | 真实数据 | 真实世界验收（只做完成性检查） | 真实数据集 |

**Level 1 和 Level 2 的本质区别**不是代码不同，而是**数据规模和验收严格度不同**：
同一份 `sample_skill_code.py` 分别跑在不同规模的数据上，level 越高阈值可以越严。

!!! warning "Level 0-2 的数据不会自动出现"
    skillPrism 引擎不会自动生成合成数据。你需要自己准备，或用
    `skillprism.testing.mock_data`（`generate_table_csv` / `generate_anndata` /
    `generate_visium_data`）生成后保存到 `benchmarks/<skill>/data/<level>/`，
    再为每个 level 单独注册 benchmark 条目。具体写法见下文 §4.5。

四级 level 的完整定义、渐进运行方式与真实数据验收，见
[第 8 章：渐进测试模式与真实数据验收](08-gradual-testing-and-real-data.md)。

## 4.4 Task Spec 是什么？

在新架构下，**Task 不再是通用类型（如 table/clustering），而是每个 Skill 特异性的规范文件**。它定义：

1. 任务描述（给 Agent 的 prompt 模板）
2. 输入数据格式与路径占位符
3. 输出内容格式与路径占位符

存放位置：`benchmarks/<skill>/tasks/<task>.yaml`

示例 `benchmarks/my-first-table/tasks/csv_summary.yaml`：

```yaml
id: csv_summary
skill: my-first-table
name: CSV Summary
description: 验证 my-first-table 能否对 CSV 做描述性统计

prompt: |
  ## 角色
  数据分析助手

  ## 任务
  对输入 CSV 进行统计摘要分析，并将结果保存到输出路径。

  ## 输入
  - 文件路径：{input_csv}
  - 格式：CSV

  ## 输出要求
  - 文件路径：{output_csv}
  - 格式：CSV

input:
  format: csv
  path: "{input_csv}"

output:
  format: csv
  path: "{output_csv}"
```

### Task Spec 与 Registry 的关系

- **Task Spec**：定义任务的通用契约（prompt、输入输出格式）。
- **Registry**：引用一个 task spec，并提供**具体数据**、**金标准输出**和**评估指标**。

```yaml
benchmarks:
  csv_summary_sales:
    name: "CSV Summary: Sales"
    skill: my-first-table
    task: csv_summary
    level: 1
    task_spec: tasks/csv_summary.yaml
    input:
      path: data/level1/input/sales.csv
    expected:
      format: csv
      path: expected/level1/sales_summary.csv
    metrics:
      - id: row_count
        name: 输出行数
        type: min
        threshold: 8
        description: 输出至少包含 8 行数据
```

## 4.5 准备数据

下面以 `my-first-table` skill 为例，展示如何从零准备 level 0 数据。

### 生成 level 0 输入数据

```bash
mkdir -p benchmarks/my-first-table/data/level0/input
```

```python
from pathlib import Path
from skillprism.testing.mock_data import generate_table_csv

Path("benchmarks/my-first-table/data/level0/input").mkdir(parents=True, exist_ok=True)
generate_table_csv(
    rows=10,
    cols=3,
    output_path=Path("benchmarks/my-first-table/data/level0/input/sales.csv"),
    seed=42,
)
```

### 生成金标准输出

金标准（expected output）是 benchmark 的"正确答案"。对于 table task，可以用参考实现生成：

```python
import pandas as pd
from pathlib import Path

input_path = Path("benchmarks/my-first-table/data/level0/input/sales.csv")
expected_path = Path("benchmarks/my-first-table/expected/level0/sales_summary.csv")
expected_path.parent.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(input_path)
df.describe().to_csv(expected_path)
```

!!! tip "金标准怎么来？"
    - 简单任务：用你信任的实现生成（如 `pandas.describe()`）。
    - 复杂任务：由领域专家确认第一批 expected output，或用稳定的参考实现生成。
    - 可以用同一个参考实现先生成 level 0-2 的金标准，再让 Skill 去逼近它。
    - `build-skill-test --generate-expected` 目前只对 `csv` task 做简单复制；复杂任务需要自己写生成脚本。

## 4.6 准备 Skill 执行代码

`SKILL.md` 是说明书，benchmark 需要一段**可执行代码**来验证 Skill 的能力（如果使用 `--code` 模式）。

### `--code sample_skill_code.py` 示例

```python
# sample_skill_code.py
import pandas as pd

df = pd.read_csv(input_csv)
summary = df.describe()
summary.to_csv(output_csv)
```

!!! tip "复杂场景用插件"
    对大多数 skill 来说，`--code` 足够。如果 benchmark 需要"先预处理数据，再调用 skill 代码，再后处理结果"等多步编排，用[自定义插件](../reference/adding-a-benchmark-task-type.md)而不是往 `--code` 里塞测试逻辑——`--code` 应该保持是被测代码本身。

## 4.7 自然语言交互（Agent 场景）

如果你已经加载了 `skills/skill-prism/SKILL.md`，可以直接对 Agent 说：

- "帮我为 my-first-table 建一个 csv_summary benchmark"
- "给这个 table skill 准备一套 level 0 到 level 2 的测试数据"
- "跑一下这个 skill 的 csv_summary benchmark"

Agent 会替你执行本章 §4.4–§4.10 的每一步（读 SKILL.md → 设计 task spec → 生成数据/金标准
→ 注册 benchmark → 运行验证），产物与手动构建完全一致。完整的自然语言构建示范见
[手把手：用 Claude Code 为 CellTypist 注释技能构建 Benchmark](build-bio-benchmark-with-claude-code.md)。

## 4.8 注册 Benchmark

用 `build-skill-test` 把 benchmark 写进注册表：

```bash
build-skill-test \
  --id csv_summary_sales \
  --name "CSV Summary: Sales" \
  --skill my-first-table \
  --task csv_summary \
  --task-spec tasks/csv_summary.yaml \
  --level 0 \
  --input data/level0/input/sales.csv \
  --expected-path expected/level0/sales_summary.csv \
  --metric row_count:min:8 \
  --metric col_count:min:2 \
  --registry benchmarks/my-first-table/registry.yaml
```

### 参数说明

| 参数 | 含义 | 示例 |
|---|---|---|
| `--id` | benchmark 唯一标识 | `csv_summary_sales_l1` |
| `--name` | 人类可读名称 | `"CSV Summary: Sales Level 1"` |
| `--skill` | 关联的 skill 名 | `my-first-table` |
| `--task` | task spec id | `csv_summary` |
| `--task-spec` | task spec 文件路径（相对注册表目录，默认 `tasks/<task>.yaml`） | `tasks/csv_summary.yaml` |
| `--level` | benchmark 难度等级（0-3，默认 1） | `--level 1` |
| `--input` | 输入数据路径（相对注册表目录） | `data/level1/input/sales.csv` |
| `--expected-path` | 金标准输出路径（相对注册表目录） | `expected/level1/sales_summary.csv` |
| `--metric` | 指标，格式 `id:type:args` | `row_count:min:8` |
| `--registry` | 注册表文件路径（有默认值 `benchmark_registry.yaml`，但推荐**显式**传 `benchmarks/<skill>/registry.yaml`） | `benchmarks/my-first-table/registry.yaml` |
| `--suite` | 加入指定 suite（可多次指定） | `--suite smoke --suite gradual` |
| `--generate-expected` | 对支持的 task 自动生成 expected | 目前仅 `csv` 简单复制 |
| `--gpu` | 标记需要 GPU | `--gpu` |
| `--real-data` | 标记使用真实数据（不评分，只检查完成） | `--real-data` |

### 生成的 YAML 结构

```yaml
benchmarks:
  csv_summary_sales:
    name: "CSV Summary: Sales"
    skill: my-first-table
    task: csv_summary
    level: 0
    task_spec: tasks/csv_summary.yaml
    input:
      path: data/level0/input/sales.csv
    expected:
      format: csv
      path: expected/level0/sales_summary.csv
    metrics:
      - id: row_count
        name: 输出行数
        type: min
        threshold: 8
        description: 输出至少包含 8 行数据
      - id: col_count
        name: 输出列数
        type: min
        threshold: 2
        description: 输出至少包含 2 列
```

### Metric 类型

| 类型 | 自然语言含义 | 示例 |
|---|---|---|
| `min` | "实际值至少要达到多少" | `row_count:min:8` 表示输出至少要有 8 行 |
| `max` | "实际值不能超过多少" | `largest_cluster_ratio:max:0.6` 表示最大簇占比不超过 60% |
| `range` | "实际值要在某个区间内" | `n_clusters:range:3:8` 表示聚类数在 3 到 8 之间 |
| `exact` | "实际值必须完全等于预期值" | `pass_count:exact:10` |

## 4.9 使用 Suite

Suite 是 registry 中预定义的一组 benchmark 列表，用 `--suite <name>` 只跑该组，
`build-skill-test --suite <name>`（可重复）在注册时把 benchmark 加入 suite：

```yaml
suites:
  smoke:
    description: 轻量快速验证
    benchmarks: [csv_summary_sales]
  gradual:
    description: 失败优先的渐进验证（level 0 → 2）
    benchmarks: [csv_summary_sales, csv_summary_medium]
```

```bash
test-skill --skill my-first-table \
    --registry benchmarks/my-first-table/registry.yaml \
    --suite smoke \
    --code sample_skill_code.py
```

Suite 的完整定义与常见约定（`smoke` / `gradual` / `release`）见
[测试一个 Skill](../getting-started/test.md)。

## 4.10 运行 Benchmark

`test-skill` 按执行来源分三种用法，更完整的模式说明见
[测试一个 Skill](../getting-started/test.md)：

```bash
# Results 模式（默认）：Agent 已产出结果，只评估已存在的输出
test-skill --skill my-first-table --registry benchmarks/my-first-table/registry.yaml --task csv_summary

# Code 模式：执行代码再评估输出
test-skill --skill my-first-table --registry benchmarks/my-first-table/registry.yaml --task csv_summary --code sample_skill_code.py

# 整份 registry：不带 --task，跑该 skill 的全部 benchmark
test-skill --skill my-first-table --registry benchmarks/my-first-table/registry.yaml --code sample_skill_code.py
```

逐级放行用渐进模式（失败即停、自动 ratchet 基线，详见第 8 章）：

```bash
test-skill --skill my-first-table --registry benchmarks/my-first-table/registry.yaml --mode gradual --max-level 2
```

## 4.11 本章小结

- Benchmark 验证 Skill 在真实数据上的能力，需要：**Task Spec + 输入数据 + 执行代码/Agent + 金标准 + 注册表**。
- **Task Spec** 是 Skill 特异性的规范文件，定义任务 prompt、输入输出格式。
- **执行方式**：
  - `--code sample_skill_code.py`：被测代码，Agent/Skill 作者写，简单场景直接用。
  - 自定义插件：复杂多步编排场景用，见 [扩展 benchmark 任务类型](../reference/adding-a-benchmark-task-type.md)。
- **金标准**用参考实现或人工标注生成；`build-skill-test --generate-expected` 只对部分 task 做简单复制。
- **Level 0-2** 数据需要用户/Agent 自己准备，或用 `skillprism.testing.mock_data` 生成后保存为本地文件。
- `--skill` 是关联标签，推荐填具体 skill 名；`--task` 引用 task spec；`--level` 是难度/数据规模等级。
- `build-skill-test` 只生成注册表；`test-skill` 才真正执行。
- Suite 是预定义的 benchmark 分组，常见约定：`smoke`、`gradual`、`release`。
- 自然语言模式下，Agent 读取 `SKILL.md` 后设计 task spec、生成数据/金标准/代码、注册 benchmark、再调用 `test-skill` 执行。

## 4.12 练习

1. 用 `generate_table_csv` 生成 level 0 和 level 1 数据，各保存一份。
2. 用参考实现生成 level 0 和 level 1 的金标准输出。
3. 为 `my-first-table` 写一个 task spec `csv_summary`。
4. 用 `build-skill-test` 把 level 0 和 level 1 两个 benchmark 注册到 `benchmarks/my-first-table/registry.yaml`。
5. 写一个简单的 `sample_skill_code.py` 并跑通 benchmark。
6. 阅读 [扩展 benchmark 任务类型](../reference/adding-a-benchmark-task-type.md)，了解什么场景需要写插件。
7. 在注册表中添加 `smoke` 和 `gradual` 两个 suite。
