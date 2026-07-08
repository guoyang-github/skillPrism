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

### `sample_skill_code.py` 与 `runner.py` 的区别

| 对比项 | `--code sample_skill_code.py` | `runner.py` |
|---|---|---|
| **角色** | 被测对象：Agent/用户按 SKILL.md 生成的可执行代码 | 测试 harness：benchmark 框架加载并调用的脚本 |
| **谁写** | Agent 或 Skill 作者 | Benchmark 作者（你或 Agent） |
| **注入变量** | task spec 规定的变量，如 `input_csv`、`output_csv` | `skill_code`（字符串）、`input_path`、`output_dir` |
| **适用场景** | 简单、单文件、直接处理输入 | 复杂、多步、需要预处理、需要控制执行环境 |
| **文件位置** | 任意路径，通过 `--code` 传入 | 约定放在 expected 同级目录的 `runner.py`，由 runner 自动发现 |
| **是否被评估** | **是**，它的输出会被拿来与 expected 对比 | **否**，它只是组织测试过程的胶水代码 |

简单记忆：

- **`sample_skill_code.py` = 学生答卷**：它就是你想要验证的 Skill 执行能力。
- **`runner.py` = 监考老师**：它负责把卷子发下去、收上来、交给阅卷系统。

多数场景用 `--code` 就够了。只有当 benchmark 需要复杂预处理、多文件协作、或者你想显式控制 Skill 代码如何被调用时，才需要写 `runner.py`。

## 4.3 理解 Level 0-3 的数据策略与区别

渐进测试（`--mode gradual`）把 benchmark 分成 4 个 level，难度递增：

| Level | 数据规模 | 核心目标 | 与上一级的区别 | 数据从哪来 |
|---|---|---|---|---|
| **0** | 最小（如 10 行、10 个 spot） | 快速冒烟：不崩溃、输出形状正确、基本语法没问题 | 只验证"能跑"，不关心数值精度 | 用户准备或 `skillprism.testing.mock_data` 生成 |
| **1** | 小（如 50-100 样本） | 数值回归：基本逻辑正确 | 开始验证输出数值/结构是否满足预期 | 用户准备或 mock_data 生成 |
| **2** | 中（如 200-500 样本） | 稳定性、相关性、更严格的指标 | 数据变大后，验证算法依然稳定、指标不异常 | 用户准备或 mock_data 生成 |
| **3** | 真实数据 | 真实世界验收 | 用真实分布的数据做最终验收 | 真实数据集（builtin、url 或用户本地数据） |

**Level 1 和 Level 2 的本质区别**：不是"代码不同"，而是**数据规模和验收严格度不同**。

- 同一个 `sample_skill_code.py` 会分别跑在 level 1 和 level 2 的数据上。
- Level 1 的阈值可以宽松（如 `row_count:min:8`），Level 2 的阈值可以更严格（如 `row_count:min:45`）。
- Level 2 更容易暴露大数据下的性能问题、数值稳定性问题或边界 case。

!!! warning "Level 0-2 的数据不会自动 magically 出现"
    skillPrism 引擎不会自动为每个 skill 生成 level 0-2 的合成数据。你需要：
    1. 自己准备数据；或
    2. 用 `skillprism.testing.mock_data` 生成后保存到本地目录；或
    3. 使用库内置数据集（如 `scanpy.datasets.pbmc3k_processed`）。

    然后为每个 level 单独注册一个 benchmark 条目。

### 用 mock_data 生成合成数据

skillPrism 提供了一组辅助函数，用于生成轻量合成数据：

```python
from skillprism.testing.mock_data import (
    generate_table_csv,      # 生成 CSV 表格
    generate_anndata,        # 生成单细胞 AnnData
    generate_visium_data,    # 生成空间 Visium 数据
    generate_document_prompt, # 生成文档任务 prompt
)
```

示例：为 table task 生成 level 0 数据：

```python
from pathlib import Path
from skillprism.testing.mock_data import generate_table_csv

Path("benchmarks/my-first-table/data/level0/input").mkdir(parents=True, exist_ok=True)
generate_table_csv(
    rows=10, cols=3,
    output_path=Path("benchmarks/my-first-table/data/level0/input/sales.csv"),
)
```

示例：为 clustering task 生成 level 1 数据：

```python
from pathlib import Path
from skillprism.testing.mock_data import generate_anndata

adata = generate_anndata(n_obs=100, n_vars=500, n_cell_types=3)
adata.write(Path("benchmarks/my-first-clustering/data/level1/input/adata.h5ad"))
```

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

### `runner.py` 示例

```python
# benchmarks/my-first-table/runner.py
import pandas as pd
from pathlib import Path

def run(skill_code, input_path, output_dir):
    df = pd.read_csv(input_path)
    summary = df.describe()
    output_path = Path(output_dir) / "output.csv"
    summary.to_csv(output_path)
    return output_path
```

!!! tip "简单用 --code，复杂用 runner.py"
    对大多数 skill 来说，`--code` 足够。只有当你的 benchmark 需要"先预处理数据，再调用 skill 代码，再后处理结果"时，才需要 `runner.py`。

## 4.7 自然语言交互（Agent 场景）

如果你已经加载了 `skills/skill-prism/SKILL.md`，可以直接对 Agent 说：

- "帮我为 my-first-table 建一个 csv_summary benchmark"
- "给这个 table skill 准备一套 level 0 到 level 2 的测试数据"
- "跑一下这个 skill 的 csv_summary benchmark"

Agent 的内部流程：

```text
用户：帮我为 my-first-table 建一个 benchmark
Agent：
  1. 读取 skills/my-first-table/SKILL.md
  2. 设计 task spec：benchmarks/my-first-table/tasks/csv_summary.yaml
  3. 用 skillprism.testing.mock_data 生成 level 0-2 输入数据
  4. 用参考实现（如 pandas）生成 level 0-2 金标准输出
  5. 写 sample_skill_code.py（被测代码）或 runner.py（复杂 harness）
  6. 调用 build-skill-test 把 benchmark 注册进 benchmarks/<skill>/registry.yaml
  7. 调用 test-skill --mode gradual 验证
```

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
| `--registry` | 注册表文件路径（必填） | `benchmarks/my-first-table/registry.yaml` |
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

Suite 是一组预定义的 benchmark 列表，方便不同场景快速选择。

```yaml
suites:
  smoke:
    description: 轻量快速验证
    benchmarks:
      - csv_summary_sales

  gradual:
    description: 失败优先的渐进验证（level 0 → 2）
    benchmarks:
      - csv_summary_sales
      - csv_summary_medium
```

运行指定 suite：

```bash
test-skill --skill my-first-table \
    --registry benchmarks/my-first-table/registry.yaml \
    --suite smoke \
    --code sample_skill_code.py
```

## 4.10 运行 Benchmark

### Verify-only 模式（默认）

```bash
test-skill --skill my-first-table --registry benchmarks/my-first-table/registry.yaml --task csv_summary
```

skillPrism 会读取 task spec，生成 prompt，然后只评估已存在的输出。默认适用于 Agent 已经生成结果的场景。

### Code/Execute 模式

```bash
test-skill --skill my-first-table --registry benchmarks/my-first-table/registry.yaml --task csv_summary --code sample_skill_code.py
```

skillPrism 会执行代码并评估输出。

### Registry 模式

```bash
test-skill --skill my-first-table --registry benchmarks/my-first-table/registry.yaml --code sample_skill_code.py
```

## 4.11 本章小结

- Benchmark 验证 Skill 在真实数据上的能力，需要：**Task Spec + 输入数据 + 执行代码/Agent + 金标准 + 注册表**。
- **Task Spec** 是 Skill 特异性的规范文件，定义任务 prompt、输入输出格式。
- **执行代码有两种形式**：
  - `--code sample_skill_code.py`：被测代码，Agent/Skill 作者写，简单场景直接用。
  - `runner.py`：测试 harness，benchmark 作者写，复杂场景用。
- **金标准**用参考实现或人工标注生成；`build-skill-test --generate-expected` 只对部分 task 做简单复制。
- **Level 0-2** 数据需要用户/Agent 自己准备，或用 `skillprism.testing.mock_data` 生成后保存为本地文件。
- `--skill` 是关联标签，推荐填具体 skill 名；`--task` 引用 task spec；`--level` 是难度/数据规模等级。
- `build-skill-test` 只生成注册表；`test-skill` 才真正执行。
- Suite 是预定义的 benchmark 分组，常见约定：`smoke`、`gradual`、`release`。
- 自然语言模式下，Agent 读取 `SKILL.md` 后设计 task spec、生成数据/金标准/代码、注册 benchmark、再调用 runner。

## 4.12 练习

1. 用 `generate_table_csv` 生成 level 0 和 level 1 数据，各保存一份。
2. 用参考实现生成 level 0 和 level 1 的金标准输出。
3. 为 `my-first-table` 写一个 task spec `csv_summary`。
4. 用 `build-skill-test` 把 level 0 和 level 1 两个 benchmark 注册到 `benchmarks/my-first-table/registry.yaml`。
5. 写一个简单的 `sample_skill_code.py` 并跑通 benchmark。
6. 把 `--code` 方式改写成 `runner.py` 方式，重新运行。
7. 在注册表中添加 `smoke` 和 `gradual` 两个 suite。
