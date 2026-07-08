# 金标准 Benchmark 构建与迭代优化指南（手把手版）

> 目标：从零开始，为一个 Skill 建立可重复、可自动化、可持续积累的金标准 Benchmark 集合，并把它接入回归测试与 CI。
>
> 读完本指南后，你应该能：
> 1. 跑通仓库自带的最小示例；
> 2. 为自己的 Skill 新增一个 Benchmark；
> 3. 生成/维护 `expected` 金标准输出；
> 4. 保存基线、做回归测试；
> 5. 把 Benchmark 接入 GitHub Actions。

---

## 目录

1. [核心原则](#core-principles)
2. [快速体验：跑通最小示例](#quickstart)
3. [Benchmark 体系架构](#architecture)
4. [从零创建一个 Table Benchmark](#table-benchmark)
5. [从零创建一个 Clustering Benchmark](#clustering-benchmark)
6. [从零创建一个 Document Benchmark](#document-benchmark)
7. [注册表字段完全参考](#registry-reference)
8. [Runner 编写指南](#runner-guide)
9. [指标与阈值](#metrics)
10. [基线与回归测试](#baseline-regression)
11. [规模化与 CI/CD](#scale-ci)
12. [常见陷阱与排查](#troubleshooting)
13. [cell2location 空间解卷积 Benchmark 实战](#cell2location)
14. [附录：完整文件示例](#appendix-examples)
15. [推荐实施路线图](#roadmap)
16. [延伸阅读](#further-reading)

---

<a id="core-principles"></a>

## 一、核心原则
1. **从少量开始，逐步扩展**：每个 Skill 先建 1–3 个核心 Benchmark，跑通流程后再批量增加。
2. **公开数据优先**：优先使用已发表、有参考标签的数据集，降低构建成本。
3. **不将大数据存入 Git**：用缓存目录 + 元数据清单管理数据，仓库只保留规范、脚本和小样例。
4. **客观任务才用金标准**：聚类、注释、批次校正、差异表达、双细胞检测、去卷积、表格处理等适合；纯可视化、轨迹推断等慎用。
5. **Metric 驱动决策**：每次 Skill 修改必须通过 Benchmark 回归测试，得分不下降才允许合并。
6. **确定性优先**：一个 Benchmark 应该能在干净环境里重复跑，并得到相同结果。

---

<a id="quickstart"></a>

## 二、快速体验：跑通最小示例
仓库已经提供了一个完整可运行的最小示例：`examples/benchmark_minimal/`。建议先跑一遍，建立直觉。

### 2.1 目录结构

```text
examples/benchmark_minimal/
├── benchmarks/                      # 按 skill 拆分的 benchmark 注册表与数据
│   ├── bio-single-cell-clustering/
│   │   ├── registry.yaml            # 该 skill 的 benchmark 注册表
│   │   ├── tasks/
│   │   │   └── clustering.yaml      # Task spec（无 metrics/expected）
│   │   └── data/                    # 输入数据（或下载脚本）
│   └── document-demo/
│       ├── registry.yaml
│       ├── tasks/
│       │   └── document.yaml
│       ├── data/                    # 输入 prompt 等
│       └── expected/                # 金标准输出
│           └── best_skill.md
├── sample_skill_code.py             # 示例：Skill 生成的代码
├── sample_document_skill_code.py    # 示例：文档 Skill 生成的代码
├── generate_expected.py             # 生成金标准输出
└── baselines/                       # 基线结果
    └── bio-single-cell-clustering.yaml
```

### 2.2 安装依赖

```bash
cd /path/to/Skills_Validation
pip install -e .
# 最小示例需要 scanpy
pip install scanpy
```

### 2.3 生成金标准输出

金标准（expected）是 Benchmark 的“正确答案”。对于聚类任务，它通常是一份跑过参考流程的 `adata.h5ad`。

```bash
cd examples/benchmark_minimal
python generate_expected.py
```

运行后你会看到：

```text
generating expected output for bio-single-cell-clustering ...
expected output written to benchmarks/bio-single-cell-clustering/expected/adata.h5ad
```

此时目录变成：

```text
benchmarks/bio-single-cell-clustering/
├── registry.yaml
├── tasks/
│   └── clustering.yaml
├── data/
└── expected/
    └── adata.h5ad          # 刚生成的金标准
```

> 如果 `expected/` 目录里已经有文件，说明仓库已提交一份预生成的金标准，你可以跳过这一步。

### 2.4 运行 Benchmark

```bash
test-skill \
    --skill bio-single-cell-clustering \
    --registry benchmarks/bio-single-cell-clustering/registry.yaml \
    --code sample_skill_code.py \
    --task clustering
```

典型输出：

```text
Running 1 benchmarks for bio-single-cell-clustering

[PASS] PBMC 3k Clustering: {'n_clusters': 7, 'largest_cluster_ratio': 0.35, 'silhouette_score': 0.45, 'ari': 1.0, 'nmi': 1.0, '_metric_pass': {'n_clusters': True, 'silhouette_score': True, 'largest_cluster_ratio': True}, '_all_pass': True}
```

解释：

- `n_clusters`、`largest_cluster_ratio`、`silhouette_score` 是引擎计算的指标；
- `ari`、`nmi` 是因为 `expected/` 里有一份 `adata.h5ad`，引擎自动与金标准对比；
- `_metric_pass` 显示每个指标是否通过注册表里的阈值；
- `_all_pass: true` 表示本次 Benchmark 通过。

### 2.5 保存基线

基线（baseline）是“当前被认可的版本”的指标快照。以后任何改动都要和基线对比。

```bash
python -m skillprism.benchmark.runner \
    --skill bio-single-cell-clustering \
    --registry benchmarks/bio-single-cell-clustering/registry.yaml \
    --code sample_skill_code.py \
    --output baselines/bio-single-cell-clustering.yaml
```

生成的 `baselines/bio-single-cell-clustering.yaml` 内容类似：

```yaml
skill: bio-single-cell-clustering
benchmarks:
  pbmc3k_clustering:
    n_clusters: 7
    largest_cluster_ratio: 0.35
    silhouette_score: 0.45
    ari: 1.0
    nmi: 1.0
    _all_pass: true
```

### 2.6 做回归测试

修改 `sample_skill_code.py` 后再跑一次，并把结果保存下来：

```bash
python -m skillprism.benchmark.runner \
    --skill bio-single-cell-clustering \
    --registry benchmarks/bio-single-cell-clustering/registry.yaml \
    --code sample_skill_code.py \
    --output latest/bio-single-cell-clustering.yaml
```

然后和基线对比：

```bash
python ../../templates/regression_test.py \
    --results latest/bio-single-cell-clustering.yaml \
    --baseline baselines/bio-single-cell-clustering.yaml \
    --tolerance 0.03
```

如果指标变化在 ±3% 以内，输出：

```text
RESULT: ACCEPT (no regression detected)
```

如果有指标变差超过 3%，输出：

```text
RESULT: REJECT (regression detected)
```

### 2.7 文档 Benchmark 也跑一遍

```bash
test-skill \
    --skill document-demo \
    --registry benchmarks/document-demo/registry.yaml \
    --code sample_document_skill_code.py \
    --task document
```

---

<a id="architecture"></a>

## 三、Benchmark 体系架构
一个 Benchmark 由四部分组成：

1. **注册表（`benchmarks/<skill>/registry.yaml`）**：声明该 Skill 的 Benchmark 元数据、数据来源、指标阈值。
2. **任务契约（`benchmarks/<skill>/tasks/<task>.yaml`）**：定义 prompt、输入输出格式、变量占位符。
3. **输入数据（`data/`）**：Skill 要处理的对象。
4. **期望输出（`expected/`）**：金标准结果，用于计算误差或结构相似度。

```text
project-root/
├── skills/
│   └── bio-single-cell-clustering/
│       ├── SKILL.md
│       └── ...
├── benchmarks/                       # 入 Git
│   └── bio-single-cell-clustering/
│       ├── registry.yaml             # 该 skill 的 benchmark 注册表
│       ├── tasks/
│       │   └── clustering.yaml       # Task spec（无 metrics/expected）
│       ├── data/                     # 输入数据
│       │   └── pbmc3k_processed.h5ad
│       ├── expected/                 # 金标准输出
│       │   └── adata.h5ad
│       └── metrics.py                # 可选：私有 metric 注册
└── .benchmark_cache/                 # 不入 Git
```

> 注：真正干活的是 `skillprism.benchmark.runner` 和 `skillprism.benchmark.metrics`，安装 `pip install -e .` 后即可调用。

---

<a id="table-benchmark"></a>

## 四、从零创建一个 Table Benchmark
Table 任务是最简单的 Benchmark 类型：输入一个 CSV，输出一个 CSV，检查行数、列数、数值统计等。

### 4.1 场景

假设你有一个 Skill `csv-summary-skill`，功能是把 CSV 加载进来并输出描述统计。

### 4.2 准备数据

```bash
mkdir -p benchmarks/csv-summary-skill/data
cat > benchmarks/csv-summary-skill/data/sales.csv <<'EOF'
product,region,revenue
A,North,100
B,South,200
A,North,150
C,East,300
EOF
```

### 4.3 方式 A：用 `build-skill-test` 快速创建注册表

```bash
build-skill-test \
  --id csv_summary_sales \
  --name "CSV Summary: Sales" \
  --skill csv-summary-skill \
  --task table \
  --input data/sales.csv \
  --expected-path expected/sales_summary.csv \
  --metric row_count:min:3 \
  --metric col_count:min:2 \
  --metric revenue_sum:min:500 \
  --generate-expected \
  --registry benchmarks/csv-summary-skill/registry.yaml
```

参数解释：

| 参数 | 含义 |
|---|---|
| `--id` | Benchmark 唯一 ID，全局不能重复。 |
| `--skill` | 关联标签：具体 skill 名或 skill 类型，可多次出现。推荐用具体 skill 名。 |
| `--task` | 任务类型：`table`、`clustering`、`document` 等。 |
| `--dataset-source` | 数据来源路径、URL 或 builtin 表达式。 |
| `--dataset-type` | `local`、`url`、`builtin`，省略则自动推断。 |
| `--expected-path` | 金标准输出相对于注册表的路径。 |
| `--expected-format` | 输出格式，省略则根据后缀推断。 |
| `--metric` | `name:type:args`，可多次出现。 |
| `--generate-expected` | 对 `table` 任务，自动把输入复制到 `--expected-path`。 |
| `--registry` | 要写入的注册表文件。 |

运行后，`benchmarks/csv-summary-skill/registry.yaml` 会新增：

```yaml
  csv_summary_sales:
    name: CSV Summary: Sales
    skill: csv-summary-skill
    task: table
    level: 1
    input:
      path: data/sales.csv
    expected:
      format: csv
      path: expected/sales_summary.csv
    metrics:
      - id: row_count
        type: min
        threshold: 3
      - id: col_count
        type: min
        threshold: 2
      - id: revenue_sum
        type: min
        threshold: 500
```

同时 `expected/sales_summary.csv` 被自动创建（当前是输入的副本）。

### 4.4 方式 B：手动创建（理解原理）

如果你不想用 builder，也可以手写注册表：

```yaml
benchmarks:
  csv_summary_sales:
    name: CSV Summary: Sales
    skill: csv-summary-skill
    task: table
    level: 1
    input:
      path: data/sales.csv
    expected:
      format: csv
      path: expected/sales_summary.csv
    metrics:
      - id: row_count
        type: min
        threshold: 3
      - id: col_count
        type: min
        threshold: 2
      - id: revenue_sum
        type: min
        threshold: 500
```

然后自己复制输入到 expected：

```bash
cp benchmarks/csv-summary-skill/data/sales.csv \
   benchmarks/csv-summary-skill/expected/sales_summary.csv
```

### 4.5 编写 Skill 代码

`sample_skill_code.py` 里写：

```python
import pandas as pd

df = pd.read_csv(input_csv)
summary = df.describe()
summary.to_csv(output_csv)
```

> 引擎在执行 `table` 任务时，会把 `input_csv`、`output_csv`、`output_dir` 注入到这段代码的命名空间。

### 4.6 运行

```bash
test-skill \
    --skill csv-summary-skill \
    --registry benchmarks/csv-summary-skill/registry.yaml \
    --code sample_skill_code.py \
    --task table
```

如果输出 CSV 有至少 3 行、2 列、`revenue` 列求和 ≥ 500，就会 PASS。

---

<a id="clustering-benchmark"></a>

## 五、从零创建一个 Clustering Benchmark
Clustering Benchmark 需要三件事：数据、参考聚类结果、一个能把 Skill 代码跑起来的 runner。

### 5.1 场景

为 `bio-single-cell-clustering` 新增一个 `pbmc3k` Benchmark。

### 5.2 创建目录

```bash
mkdir -p benchmarks/bio-single-cell-clustering/{data,expected}
```

### 5.3 生成金标准输出

写 `generate_expected.py`（也可以临时写在 notebook 里）：

```python
import scanpy as sc
from pathlib import Path

out_dir = Path("benchmarks/bio-single-cell-clustering/expected")
out_dir.mkdir(parents=True, exist_ok=True)

adata = sc.datasets.pbmc3k_processed()
sc.pp.neighbors(adata, n_neighbors=15, n_pcs=30)
sc.tl.leiden(adata, resolution=0.5)
sc.tl.umap(adata)

adata.write_h5ad(out_dir / "adata.h5ad")
print("expected output written to", out_dir / "adata.h5ad")
```

运行：

```bash
python generate_expected.py
```

### 5.4 编写 `runner.py`

`benchmarks/bio-single-cell-clustering/runner.py`：

```python
#!/usr/bin/env python3
"""Runner for PBMC 3k clustering benchmark."""

from pathlib import Path
from typing import Any

import scanpy as sc


def run(skill_code: str, input_data: Any, output_dir: Path) -> Path:
    """Execute skill-generated code on input data and return output path."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if isinstance(input_data, Path):
        adata = sc.read_h5ad(input_data)
    else:
        adata = input_data

    # 在受控命名空间里执行 Skill 生成的代码
    exec(skill_code, {"adata": adata, "sc": sc})

    output_path = output_dir / "output.h5ad"
    adata.write_h5ad(output_path)
    return output_path
```

`run` 函数约定：

- 参数 `skill_code`：Skill 生成的 Python 代码字符串；
- 参数 `input_data`：数据集，可能是 `Path` 或已经加载的对象；
- 参数 `output_dir`：要求你写入输出的目录；
- 返回值：输出文件的 `Path`。

### 5.5 注册 Benchmark

在 `benchmarks/bio-single-cell-clustering/registry.yaml` 中添加：

```yaml
schema_version: "2.0"
cache_dir: ".benchmark_cache"

benchmarks:
  pbmc3k_clustering:
    name: PBMC 3k Clustering
    skill: bio-single-cell-clustering
    task: clustering
    level: 1
    dataset:
      source: scanpy.datasets.pbmc3k_processed
      type: builtin
      description: 10x Genomics PBMC 3k processed dataset
    expected:
      format: h5ad
      path: expected/adata.h5ad
      label_column: leiden
    metrics:
      - id: n_clusters
        type: range
        min: 3
        max: 8
      - id: silhouette_score
        type: min
        threshold: 0.10
      - id: largest_cluster_ratio
        type: max
        threshold: 0.60
```

> 对 `clustering` 任务，通常手写注册表条目；`build-skill-test` 适合输入为本地文件或 URL 的任务。上一步生成的 `adata.h5ad` 就是 expected。

### 5.6 编写 Skill 代码

`sample_skill_code.py`：

```python
sc.pp.neighbors(adata, n_neighbors=15, n_pcs=30)
sc.tl.leiden(adata, resolution=0.5)
sc.tl.umap(adata)
```

### 5.7 运行

```bash
test-skill \
    --skill bio-single-cell-clustering \
    --registry benchmarks/bio-single-cell-clustering/registry.yaml \
    --code sample_skill_code.py \
    --task clustering
```

---

<a id="document-benchmark"></a>

## 六、从零创建一个 Document Benchmark
Document Benchmark 用来评估“生成文本型 Skill”的质量，例如让 Skill 根据 prompt 写一份 `SKILL.md`。

### 6.1 场景

评估一个 `document-writer-skill`，输入 prompt，输出 Markdown 文档。

### 6.2 创建目录和文件

```bash
mkdir -p benchmarks/document-writer-skill/{data,expected}

cat > benchmarks/document-writer-skill/data/prompt.txt <<'EOF'
Write a concise SKILL.md for a Python data analysis skill that loads a CSV,
summarizes numeric columns, and outputs a report.
EOF
```

### 6.3 准备金标准文档

手写一份你认为“最好”的 `expected/best_skill.md`：

```markdown
---
name: csv-summary-skill
description: Load a CSV file, summarize numeric columns, and produce a report.
tool_type: python
keywords:
  - csv
  - summary
  - pandas
---

# CSV Summary Skill

## When to Use

Use this skill when you need a quick statistical summary of a CSV file.

## Inputs

| Name | Type | Description |
|---|---|---|
| `input_csv` | file path | Path to the input CSV file |

## Outputs

A Markdown report containing:

- Row and column counts
- Mean / min / max for each numeric column

## Quick Start

```python
import pandas as pd

df = pd.read_csv(input_csv)
report = df.describe()
print(report.to_markdown())
```

## Common Pitfalls

- Non-numeric columns are ignored by `describe()`.
- Large files may require memory consideration.
```

### 6.4 编写 `runner.py`

`runner.py` 负责把 prompt 喂给 Skill，拿到 `output.md`。

```python
#!/usr/bin/env python3
"""Runner for document generation benchmark."""

from pathlib import Path


def run(skill_code: str, prompt_path: Path, output_dir: Path) -> Path:
    """Generate output.md from the prompt and return its path."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt_text = Path(prompt_path).read_text(encoding="utf-8")

    # 这里调用你的 Skill/LLM 生成文档
    # 示例：假设 skill_code 是一个函数定义，最后一行返回生成的 markdown
    namespace = {"prompt": prompt_text}
    exec(skill_code, namespace)
    generated = namespace.get("generated_markdown", prompt_text)

    output_path = output_dir / "output.md"
    output_path.write_text(generated, encoding="utf-8")
    return output_path
```

### 6.5 注册 Benchmark

```bash
build-skill-test \
  --id skill_md_writer \
  --name "SKILL.md Writer" \
  --skill document-writer-skill \
  --task document \
  --input data/prompt.txt \
  --expected-path expected/best_skill.md \
  --registry benchmarks/document-writer-skill/registry.yaml
```

### 6.6 运行

```bash
test-skill \
    --skill document-writer-skill \
    --registry benchmarks/document-writer-skill/registry.yaml \
    --code sample_skill_code.py \
    --task document
```

默认会计算：

- `section_overlap`：生成文档的标题有多少覆盖了金标准标题；
- `token_jaccard`：词级 Jaccard 相似度；
- `length_ratio`：长度比，防止过短/过长。

可选启用更重度的指标：

```yaml
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
  - id: rouge_l
    type: min
    threshold: 0.5
  - id: bert_score_f1
    type: min
    threshold: 0.85
```

> 需要安装 `rouge-score` 和 `bert-score`，否则这些指标会被跳过并给出提示。

---

<a id="registry-reference"></a>

## 七、注册表字段完全参考
每个 Skill 拥有独立的注册表 `benchmarks/<skill>/registry.yaml`，声明该 Skill 的所有 Benchmark 元数据、金标准和指标阈值。下面给出完整字段说明。

### 7.1 顶层字段

```yaml
schema_version: "2.0"        # 必填，当前固定 2.0
cache_dir: ".benchmark_cache" # 数据缓存目录，默认 .benchmark_cache
benchmarks:                   # 必填，该 Skill 下所有 Benchmark 的集合
  ...
```

### 7.2 每个 Benchmark 的字段

```yaml
benchmark_id:
  name: "Human-readable name"
  skill: skill-name           # 所属 Skill
  task: clustering            # clustering / table / document / annotation / ...
  level: 1                    # 0=unit, 1=component, 2=integration, 3=release
  dataset:
    source: scanpy.datasets.pbmc3k_processed
    type: builtin             # builtin / local / url
    description: "..."
    checksum: sha256:abcd...  # url 类型建议加
  expected:
    format: anndata           # anndata / csv / markdown / json / yaml / h5ad
    path: expected/adata.h5ad # 相对于注册表目录
    label_column: leiden      # 部分任务需要
  metrics:
    - id: n_clusters
      type: range
      min: 3
      max: 8
```

字段说明：

| 字段 | 必填 | 说明 |
|---|---|---|
| `benchmark_id`（YAML key） | 是 | 全局唯一标识，只能包含字母、数字、下划线、连字符。 |
| `name` | 是 | 人类可读名称。 |
| `skill` | 是 | 该 Benchmark 所属的 Skill 名。 |
| `task` | 是 | 任务类型，决定引擎调用哪个 task spec。 |
| `level` | 否 | 难度等级：`0` 单元、`1` 组件、`2` 集成、`3` 发布。 |
| `dataset.source` | 否 | 数据来源（与 `input.path` 二选一）。 |
| `dataset.type` | 否 | `builtin` / `local` / `url`。 |
| `dataset.description` | 否 | 描述，只在报告里展示。 |
| `dataset.checksum` | 否 | `url` 类型强烈建议加，用于校验下载完整性。 |
| `input.path` | 否 | 本地输入路径（相对于注册表目录），可替代 `dataset`。 |
| `input.description` | 否 | 输入描述。 |
| `expected.format` | 否 | 输出格式，自动推断。 |
| `expected.path` | 否 | 金标准输出路径，相对于注册表目录。**仅在 metric 需要与金标准对比时才需要。** |
| `expected.label_column` | 否 | 聚类等任务需要，默认 `leiden`。 |
| `metrics` | 否 | 指标及阈值；不填则无指标约束。 |

> **注意**：不要把 `expected` 当作指标值的容器。如果只是想检查 `n_spots == 1000` 或 `gene_num == 10000`，应直接写成 metric（如 `n_spots: exact: 1000`），或写一个读取 actual output 的私有 metric。`expected` 应该留给真正的金标准输出文件（如参考聚类标签、参考反卷积比例、参考文档）。
>
> 详见 [`benchmark-metrics.md`](benchmark-metrics.md)。
| `metrics[].id` | 是 | 指标 ID，对应 `skillprism.benchmark.metrics` 中注册的函数。 |

### 7.3 `dataset.type` 详细说明

#### `builtin`

数据集通过 Python 表达式直接加载。例如：

```yaml
dataset:
  source: scanpy.datasets.pbmc3k_processed
  type: builtin
```

引擎会执行 `eval(source)` 拿到数据对象。要求运行环境已安装对应包。

#### `local`

数据已经存在本地，路径相对于注册表目录。

```yaml
dataset:
  source: data/pbmc3k_processed.h5ad
  type: local
```

对于简单的本地文件，也可以直接用 `input`：

```yaml
input:
  path: data/prompt.txt
```

#### `url`

从网络下载，下载后存放到 `cache_dir`。

```yaml
dataset:
  source: https://example.com/data.h5ad
  type: url
  checksum: sha256:abcd1234...
```

如果提供了 `checksum`，下载后会校验；不匹配则报错。

---

<a id="runner-guide"></a>

## 八、Runner 编写指南
### 8.1 什么时候需要 Runner

- **简单 table**：通常不需要 runner，引擎会自动把 `input_csv`、`output_csv` 注入到 Skill 代码里。
- **clustering / annotation**：通常需要 runner，因为需要把 `adata` 对象传给 Skill 代码并保存输出。
- **document**：通常需要 runner，因为需要把 prompt 文本传给 Skill 并生成 Markdown。
- **自定义流程**：任何引擎默认不支持的数据加载/保存逻辑，都需要 runner。

### 8.2 Runner 接口

必须提供一个函数：

```python
def run(skill_code: str, input_data: Any, output_dir: Path) -> Path:
    ...
```

- `skill_code`：Skill 生成的 Python 代码字符串。
- `input_data`：数据集。`builtin` 类型是对象；`local`/`url` 类型是 `Path`。
- `output_dir`：要求写入输出的目录（已存在）。
- 返回值：生成的输出文件路径。

### 8.3 Clustering Runner 模板

```python
#!/usr/bin/env python3
from pathlib import Path
from typing import Any
import scanpy as sc


def run(skill_code: str, input_data: Any, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if isinstance(input_data, Path):
        adata = sc.read_h5ad(input_data)
    else:
        adata = input_data

    exec(skill_code, {"adata": adata, "sc": sc})

    output_path = output_dir / "output.h5ad"
    adata.write_h5ad(output_path)
    return output_path
```

### 8.4 Document Runner 模板

```python
#!/usr/bin/env python3
from pathlib import Path


def run(skill_code: str, prompt_path: Path, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt_text = Path(prompt_path).read_text(encoding="utf-8")

    namespace = {"prompt": prompt_text}
    exec(skill_code, namespace)
    generated = namespace.get("generated_markdown", "")

    output_path = output_dir / "output.md"
    output_path.write_text(generated, encoding="utf-8")
    return output_path
```

### 8.5 Table Runner 模板

如果你需要自定义 CSV 处理流程：

```python
#!/usr/bin/env python3
from pathlib import Path
from typing import Any


def run(skill_code: str, input_path: Any, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "output.csv"
    exec(
        skill_code,
        {
            "input_csv": str(input_path),
            "output_csv": str(output_path),
            "output_dir": str(output_dir),
        },
    )
    return output_path
```

---

<a id="metrics"></a>

## 九、指标与阈值
### 9.1 阈值类型

| 类型 | 含义 | 示例 |
|---|---|---|
| `min` | `value >= threshold` | `silhouette_score >= 0.25` |
| `max` | `value <= threshold` | `largest_cluster_ratio <= 0.60` |
| `range` | `min <= value <= max` | `n_clusters` 在 3–8 之间 |
| `tolerance` | `|value - reference| <= threshold` | 与参考值差距不超过 0.05 |
| `exact` | `value == expected` | 严格相等 |

YAML 示例：

```yaml
metrics:
  - id: n_clusters
    type: range
    min: 3
    max: 8
  - id: silhouette_score
    type: min
    threshold: 0.25
  - id: largest_cluster_ratio
    type: max
    threshold: 0.60
  - id: ari
    type: min
    threshold: 0.70
```

### 9.2 Clustering 指标

引擎自动计算：

- `n_clusters`：聚类数目；
- `largest_cluster_ratio`：最大簇占比；
- `silhouette_score`：轮廓系数（需要 `adata.obsm['X_pca']`）；
- `ari`：Adjusted Rand Index（需要 expected 输出）；
- `nmi`：Normalized Mutual Information（需要 expected 输出）。

### 9.3 Table 指标

引擎自动计算：

- `row_count` / `col_count` / `cell_count`；
- `sum_<col>` / `mean_<col>` / `min_<col>` / `max_<col>`（数值列）；
- `expected_diff_rows`：与 expected 行数差（如果 expected 存在）。

### 9.4 Document 指标

引擎自动计算：

- `section_overlap`：标题重叠率；
- `token_jaccard`：词级 Jaccard；
- `length_ratio`：长度比；
- `semantic_similarity`：句子嵌入余弦相似度（需 `sentence-transformers`）；
- `rouge_l`：ROUGE-L F1（需 `rouge-score`）；
- `bert_score_f1`：BERTScore F1（需 `bert-score`）。

### 9.5 用 `build-skill-test` 写指标

```bash
--metric row_count:min:3
--metric n_clusters:range:3:8
--metric accuracy:exact:0.95
--metric correlation:tolerance:0.85:0.05
```

格式：`name:type:args`。

---

<a id="baseline-regression"></a>

## 十、基线与回归测试
### 10.1 为什么需要基线

基线记录“当前被接受版本”的指标。以后任何 Skill 改动，都要和基线做回归对比。

### 10.2 保存基线

```bash
python -m skillprism.benchmark.runner \
    --skill bio-single-cell-clustering \
    --registry ./benchmarks/bio-single-cell-clustering/registry.yaml \
    --code ./sample_skill_code.py \
    --output ./baselines/bio-single-cell-clustering.yaml
```

> 也可以直接调用 `skillprism.benchmark.runner` 的 `run_benchmarks` API。

基线文件格式：

```yaml
skill: bio-single-cell-clustering
benchmarks:
  pbmc3k_clustering:
    n_clusters: 7
    largest_cluster_ratio: 0.35
    silhouette_score: 0.45
    ari: 1.0
    nmi: 1.0
    _all_pass: true
```

### 10.3 运行新版本并保存结果

```bash
python -m skillprism.benchmark.runner \
    --skill bio-single-cell-clustering \
    --registry ./benchmarks/bio-single-cell-clustering/registry.yaml \
    --code ./sample_skill_code.py \
    --output ./latest/bio-single-cell-clustering.yaml
```

### 10.4 回归测试

```bash
python templates/regression_test.py \
    --results ./latest/bio-single-cell-clustering.yaml \
    --baseline ./baselines/bio-single-cell-clustering.yaml \
    --tolerance 0.03
```

判定规则：

- 对每个 metric 计算相对变化 `rel_diff = (current - baseline) / baseline`；
- 默认相对容差 `--tolerance 0.03`（±3%）；
- 分类：
  - `IMPROVED`：current 明显优于 baseline；
  - `PASS`：变化在容差内；
  - `REGRESSION`：current 比 baseline 差超过容差 → **整体 REJECT**。

> 随机性较强的任务（如聚类）建议用 3%–5%；确定性任务可用 0%。

### 10.5 更新基线

当改动确实提升了指标，并且已经通过代码审查后，更新基线：

```bash
cp latest/bio-single-cell-clustering.yaml \
   baselines/bio-single-cell-clustering.yaml
```

然后把这次更新提交到 Git。

---

<a id="scale-ci"></a>

## 十一、规模化与 CI/CD
### 11.1 优先级矩阵

| Skill 影响度 | 构建 Benchmark 成本 | 策略 |
|---|---|---|
| 高 | 低 | **优先建**，立即覆盖 |
| 高 | 高 | 分阶段建，先用公开数据，再补专属数据 |
| 低 | 低 | 批量建，利用合成数据 |
| 低 | 高 | 暂缓，用 generic 检查兜底 |

### 11.2 数据来源规模化

| 来源 | 优势 | 劣势 |
|---|---|---|
| **公共数据库** | 真实、可引用 | 需清洗、标签可能不一致 |
| **内置示例数据** | 快速、零下载 | 规模小、场景有限 |
| **合成数据** | 标签完美、可批量生成 | 可能不反映真实分布 |
| **已发表论文数据** | 有金标准标签 | 下载/授权复杂 |
| **用户贡献** | 覆盖真实使用场景 | 质量参差不齐 |

### 11.3 合成数据生成

对于聚类、注释等任务，可用合成数据快速扩充：

```python
import scanpy as sc
import numpy as np
from pathlib import Path

out_dir = Path("benchmarks/synthetic/clustering")
out_dir.mkdir(parents=True, exist_ok=True)

for seed in range(10):
    adata = sc.datasets.blobs(n_variables=500, n_observations=1000, n_clusters=5)
    adata.obs["true_label"] = adata.obs["blobs"]
    adata.write_h5ad(out_dir / f"seed_{seed}.h5ad")
```

然后在注册表里注册 10 个 Benchmark，或写一个 `benchmark_factory.py` 批量生成。

### 11.4 GitHub Actions 示例

```yaml
# .github/workflows/skill-benchmarks.yaml
name: Skill Benchmarks

on:
  pull_request:
    paths:
      - 'skills/**'
      - 'benchmarks/**'

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Cache benchmark data
        uses: actions/cache@v4
        with:
          path: .benchmark_cache
          key: benchmarks-${{ hashFiles('benchmarks/*/registry.yaml') }}
      - name: Install package
        run: pip install -e .
      - name: Install benchmark deps
        run: pip install scanpy pandas
      - name: Run changed skill benchmarks
        run: |
          for skill in $(git diff --name-only origin/main | grep '^skills/' | cut -d'/' -f2 | sort -u); do
            echo "Running benchmarks for $skill"
            python -m skillprism.benchmark.runner \
                --skill "$skill" \
                --registry "benchmarks/${skill}/registry.yaml" \
                --code sample_skill_code.py \
                --output "latest/${skill}.yaml" || true
          done
      - name: Regression test
        run: |
          for f in latest/*.yaml; do
            skill=$(basename "$f" .yaml)
            if [ -f "baselines/${skill}.yaml" ]; then
              python templates/regression_test.py \
                  --results "$f" \
                  --baseline "baselines/${skill}.yaml" \
                  --tolerance 0.03
            fi
          done
```

### 11.5 数据缓存策略

- 使用 GitHub Actions Cache 或 DVC 缓存 Benchmark 数据；
- 在 PR 中只跑受影响的 Skill 的 Benchmark，避免全量运行耗时；
- 每周/每月跑一次全量 Benchmark，捕获依赖更新导致的回归。

---

<a id="troubleshooting"></a>

## 十二、常见陷阱与排查
### 12.1 金标准本身有噪声

公开数据的标签可能不完美。建议：

- 设置合理的容错阈值；
- 对关键 Benchmark 做人工抽查；
- 使用多个异构数据集，避免单个噪声数据集主导结果。

### 12.2 过度拟合 Benchmark

Skill 只针对特定数据集优化，换数据就失效。建议：

- 每个 Skill 至少覆盖 2–3 个不同来源的数据集；
- 定期加入新的公开数据集；
- 不要为了提高 benchmark 分数而牺牲通用性。

### 12.3 运行环境差异

CI 与本地环境可能不同。建议：

- 在 `pyproject.toml` 里固定依赖版本；
- 使用 conda lock 或 Docker；
- 对随机性强的任务设置随机种子。

### 12.4 数据泄露

训练集和测试集不能混用；Skill 不应在 Benchmark 数据上“调参”。建议：

- Benchmark 数据只用于评估；
- Skill 的示例代码里不要硬编码 Benchmark 数据集；
- 如果 Skill 需要训练，训练数据必须与 Benchmark 数据隔离。

### 12.5 指标选择偏差

不要只选一个指标。建议：

- 聚类：同时看 ARI、NMI、Silhouette、聚类数量、最大簇比例；
- 注释：同时看 Accuracy、Macro F1、Micro F1；
- 文档：同时看结构、词汇、长度、语义相似度。

### 12.6 常见报错

| 报错 | 原因 | 解决 |
|---|---|---|
| `Error: benchmark id 'x' already exists` | ID 重复 | 换 ID 或先删除旧条目 |
| `Checksum mismatch` | 下载数据损坏或被替换 | 检查 URL 和 checksum |
| `ModuleNotFoundError: No module named 'scanpy'` | 缺少任务依赖 | `pip install scanpy` |
| `_all_pass: false` | 某个指标未通过 | 查看 `_metric_pass` 看哪个指标失败 |
| `RESULT: REJECT` | 相对基线退化 | 检查改动是否引入回归，必要时更新基线 |
| `runner.py not found` | 引擎没找到 runner | 确认 `runner.py` 在 `benchmarks/<skill>/` 目录下（registry 同级）|

---

<a id="cell2location"></a>

## 十三、cell2location 空间解卷积 Benchmark 实战
> cell2location 是空间转录组（Spatial Transcriptomics）领域常用的细胞类型解卷积工具。本节展示如何从零开始，为它建立一个端到端、可复现的金标准 Benchmark。

---

### 13.1 任务特点

| 项目 | 说明 |
|---|---|
| 输入 | 单细胞参考数据（带 `cell_type` 标签）+ 空间转录组数据 |
| 输出 | 每个 spatial spot 上各 cell type 的比例/丰度矩阵 |
| 评价方式 | 与 ground truth 比例比较 RMSE、Pearson 相关、Jensen-Shannon divergence |
| 难点 | 训练慢、依赖 PyTorch/scvi-tools、API 版本变化快 |

---

### 13.2 目录结构

```text
benchmarks/
└── bio-spatial-deconvolution-cell2location/
    ├── registry.yaml             # 该 skill 的 benchmark 注册表
    ├── tasks/
    │   └── deconvolution.yaml    # Task spec（无 metrics/expected）
    ├── data/                     # 输入数据
    │   ├── ref.h5ad              # 单细胞参考
    │   └── spatial.h5ad          # 空间数据
    ├── expected/                 # 金标准输出
    │   └── proportions.csv       # 真实比例
    └── metrics.py                # 可选：私有 metric 注册
```

---

### 13.3 生成合成数据与金标准

真实 cell2location 训练较慢，且需要 GPU 才能达到较好效果。为了把 Benchmark 做得**轻量、可复现、CI 友好**，我们先使用合成数据：

1. 生成 3 种 cell type 的单细胞参考；
2. 用已知比例混合这些 cell type，生成 50 个 spatial spot；
3. 把真实比例保存为 `expected/proportions.csv`。

创建 `generate_expected.py`：

```python
#!/usr/bin/env python3
"""Generate synthetic reference + spatial data for cell2location benchmark."""

import numpy as np
import pandas as pd
import anndata as ad
from pathlib import Path

np.random.seed(42)

out_dir = Path("benchmarks/bio-spatial-deconvolution-cell2location")
input_dir = out_dir / "data"
expected_dir = out_dir / "expected"
input_dir.mkdir(parents=True, exist_ok=True)
expected_dir.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------- #
# 1. 单细胞参考数据：3 种 cell type，200 个基因，每种 100 个细胞
# --------------------------------------------------------------------------- #
n_genes = 200
cell_types = ["T_cell", "B_cell", "Myeloid"]
n_cells_per_type = 100
markers_per_type = 20

base_expr = np.random.poisson(0.5, size=n_genes)
ref_list = []
labels = []

for i, ct in enumerate(cell_types):
    expr = np.tile(base_expr, (n_cells_per_type, 1)).astype(float)
    marker_idx = np.arange(i * markers_per_type, (i + 1) * markers_per_type)
    # marker 基因高表达
    expr[:, marker_idx] += np.random.poisson(10, size=(n_cells_per_type, markers_per_type))
    ref_list.append(expr)
    labels.extend([ct] * n_cells_per_type)

ref_expr = np.vstack(ref_list)
ref = ad.AnnData(X=ref_expr)
ref.obs["cell_type"] = labels
ref.var_names = [f"gene_{j}" for j in range(n_genes)]
ref.obs_names = [f"cell_{k}" for k in range(ref.n_obs)]
ref.layers["counts"] = ref.X.copy()
ref.write_h5ad(input_dir / "ref.h5ad")

# --------------------------------------------------------------------------- #
# 2. 空间数据：50 个 spot，每个 spot 由已知比例混合而成
# --------------------------------------------------------------------------- #
n_spots = 50
proportions = np.random.dirichlet(alpha=[2, 2, 2], size=n_spots)

# 每种 cell type 的平均表达谱
type_profiles = np.array([
    ref_expr[np.array(labels) == ct].mean(axis=0)
    for ct in cell_types
])

spot_expr = proportions @ type_profiles
spatial_counts = np.random.poisson(spot_expr * 1000)

spatial = ad.AnnData(X=spatial_counts)
spatial.obs_names = [f"spot_{s}" for s in range(n_spots)]
spatial.var_names = ref.var_names
spatial.layers["counts"] = spatial.X.copy()
spatial.write_h5ad(input_dir / "spatial.h5ad")

# --------------------------------------------------------------------------- #
# 3. 保存真实比例作为金标准
# --------------------------------------------------------------------------- #
prop_df = pd.DataFrame(proportions, columns=cell_types, index=spatial.obs_names)
prop_df.index.name = "spot_id"
prop_df.to_csv(expected_dir / "proportions.csv")

print("Generated:")
print("  -", input_dir / "ref.h5ad")
print("  -", input_dir / "spatial.h5ad")
print("  -", expected_dir / "proportions.csv")
```

运行：

```bash
cd examples/benchmark_minimal  # 或你的 benchmarks 目录
python generate_expected.py
```

---

### 13.4 编写 `runner.py`

`runner.py` 负责加载参考和空间数据，把 Skill 代码跑起来，生成 `proportions.csv`。

如果默认 task spec 不满足需求，可在 registry 同级目录放可选的自定义 `runner.py`。创建 `benchmarks/bio-spatial-deconvolution-cell2location/runner.py`：

```python
#!/usr/bin/env python3
"""Runner for the synthetic lymph node deconvolution benchmark."""

from pathlib import Path
from typing import Any
import anndata as ad


def run(skill_code: str, input_dir: Path, output_dir: Path) -> Path:
    """Load reference/spatial data, execute skill code, return proportions CSV."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    input_dir = Path(input_dir)
    ref_adata = ad.read_h5ad(input_dir / "ref.h5ad")
    st_adata = ad.read_h5ad(input_dir / "spatial.h5ad")

    output_csv = output_dir / "proportions.csv"

    exec(
        skill_code,
        {
            "ref_adata": ref_adata,
            "st_adata": st_adata,
            "output_csv": str(output_csv),
        },
    )
    return output_csv
```

> `run` 函数约定：`skill_code` 是 Skill 生成的代码字符串；`input_dir` 是数据集目录；返回值是输出文件路径。

---

### 13.5 示例 Skill 代码（cell2location）

把下面内容保存为 `sample_skill_code.py`。这是 LLM 根据 cell2location Skill 的 `SKILL.md` 可能生成的代码。

```python
# 注意：实际运行需要安装 cell2location 及其依赖
#   pip install cell2location scanpy anndata
# 以下 API 以 cell2location 0.1.x 为例，请按你的版本调整。

import scanpy as sc
from cell2location.models import RegressionModel, Cell2location

# 确保使用原始 counts
ref_adata.X = ref_adata.layers["counts"]
st_adata.X = st_adata.layers["counts"]

# --------------------------------------------------------------------------- #
# 1. 用单细胞参考估计 cell type 表达特征（签名）
# --------------------------------------------------------------------------- #
RegressionModel.setup_anndata(adata=ref_adata, labels_key="cell_type")
mod = RegressionModel(ref_adata)
mod.train(max_epochs=100)
ref_adata = mod.export_posterior(
    adata=ref_adata,
    use_quantiles=True,
    qargs={"sig": 0.999, "mu": 1},
)

# 签名矩阵
inf_aver = ref_adata.varm["mean_per_cluster_mu_fg"]

# --------------------------------------------------------------------------- #
# 2. 在空间数据上解卷积
# --------------------------------------------------------------------------- #
Cell2location.setup_anndata(adata=st_adata)
mod = Cell2location(
    st_adata,
    cell_state_df=inf_aver,
    N_cells_per_location=10,
)
mod.train(max_epochs=500)
st_adata = mod.export_posterior(st_adata, sample_name="means")

# --------------------------------------------------------------------------- #
# 3. 保存估计比例
# --------------------------------------------------------------------------- #
proportions = st_adata.obsm["q05_cell_abundance_w_sf"]
# 为了和 ground truth 公平比较，按行归一化为比例
proportions = proportions.div(proportions.sum(axis=1), axis=0)
proportions.to_csv(output_csv)
```

> 如果 cell2location 训练太慢或环境不满足，可先用一个轻量替代实现（如 NNLS / 线性回归）作为 Skill 代码，Benchmark 的目录结构、runner 和评价指标完全不变。

---

### 13.6 注册 Benchmark

在 `benchmarks/bio-spatial-deconvolution-cell2location/registry.yaml` 里添加：

```yaml
  synthetic_lymph_node_deconv:
    name: Synthetic Lymph Node Deconvolution
    skill: bio-spatial-deconvolution-cell2location
    task: deconvolution
    level: 1
    input:
      path: data
      description: Synthetic Visium-like spots with known cell type proportions
    expected:
      format: csv
      path: expected/proportions.csv
    metrics:
      - id: mean_rmse
        type: max
        threshold: 0.15
      - id: mean_pearson
        type: min
        threshold: 0.70
      - id: mean_jsd
        type: max
        threshold: 0.10
```

指标说明：

| 指标 | 含义 | 阈值方向 |
|---|---|---|
| `mean_rmse` | 每个 cell type RMSE 的平均 | 越小越好，用 `max` 限制上限 |
| `mean_pearson` | 每个 cell type Pearson 相关的平均 | 越大越好，用 `min` 限制下限 |
| `mean_jsd` | 每个 spot 的 Jensen-Shannon divergence 平均 | 越小越好，用 `max` 限制上限 |

---

### 13.7 运行 Benchmark

```bash
test-skill \
    --skill bio-spatial-deconvolution-cell2location \
    --registry benchmarks/bio-spatial-deconvolution-cell2location/registry.yaml \
    --code sample_skill_code.py \
    --task deconvolution
```

如果通过，你会看到类似输出：

```text
Running 1 benchmarks for bio-spatial-deconvolution-cell2location

[PASS] Synthetic Lymph Node Deconvolution: {'n_spots': 50, 'n_cell_types': 3, 'mean_rmse': 0.08, 'mean_pearson': 0.85, 'mean_jsd': 0.04, ..., '_all_pass': True}
```

---

### 13.8 保存基线与回归测试

保存基线：

```bash
python -m skillprism.benchmark.runner \
    --skill bio-spatial-deconvolution-cell2location \
    --registry benchmarks/bio-spatial-deconvolution-cell2location/registry.yaml \
    --code sample_skill_code.py \
    --output baselines/bio-spatial-deconvolution-cell2location.yaml
```

修改 Skill 后再跑：

```bash
python -m skillprism.benchmark.runner \
    --skill bio-spatial-deconvolution-cell2location \
    --registry benchmarks/bio-spatial-deconvolution-cell2location/registry.yaml \
    --code sample_skill_code_v2.py \
    --output latest/bio-spatial-deconvolution-cell2location.yaml
```

回归测试：

```bash
python templates/regression_test.py \
    --results latest/bio-spatial-deconvolution-cell2location.yaml \
    --baseline baselines/bio-spatial-deconvolution-cell2location.yaml \
    --tolerance 0.03
```

---

### 13.9 扩展到真实数据

合成数据跑通后，可以替换为真实数据集：

1. **参考数据**：从 cellxgene Census、已发表 scRNA-seq 或你自己的单细胞实验获取。
2. **空间数据**：10x Genomics Visium 公开数据（如 human lymph node）。
3. **金标准**：
   - 如果有 matched 单细胞空间数据，直接用真实比例；
   - 否则，先用一个稳定的参考实现（如固定参数的 cell2location）跑一次，把结果作为基线/expected。

示例真实数据注册表条目：

```yaml
  human_lymph_node_deconv:
    name: Human Lymph Node Deconvolution
    skill: bio-spatial-deconvolution-cell2location
    task: deconvolution
    level: 3
    real_data: true
    requires_gpu: true
    input:
      path: data/real_visium
      description: 10x Visium human lymph node with matched scRNA-seq reference
    expected:
      format: csv
      path: expected/real_proportions.csv
    metrics:
      - id: mean_rmse
        type: max
        threshold: 0.20
      - id: mean_pearson
        type: min
        threshold: 0.60
```

---

### 13.10 关键注意事项

| 注意点 | 建议 |
|---|---|
| 输入格式 | cell2location 需要原始 counts，确保 `.X` 或 `layers["counts"]` 是整数计数矩阵 |
| 比例归一化 | Skill 输出保存前最好按行归一化为比例，方便与 ground truth 公平比较 |
| 随机性 | 在 Skill 代码里设置 `scvi.settings.seed` 和 PyTorch seed，提高可复现性 |
| 运行资源 | 真实数据建议 GPU；CI 中可只跑合成数据，或减小 `max_epochs` |
| 版本锁定 | cell2location / scvi-tools API 变化快，CI 中固定版本，避免训练结果漂移 |
| 评价指标 | 不要只看 Pearson，建议同时看 RMSE 和 JSD，防止只拟合相关性忽略绝对比例 |

---

<a id="appendix-examples"></a>

## 十四、附录：完整文件示例
### A. 按 Skill 拆分的 `registry.yaml` 示例

`benchmarks/bio-single-cell-clustering/registry.yaml`：

```yaml
schema_version: "2.0"
cache_dir: ".benchmark_cache"

benchmarks:
  pbmc3k_clustering:
    name: PBMC 3k Clustering
    skill: bio-single-cell-clustering
    task: clustering
    level: 1
    dataset:
      source: scanpy.datasets.pbmc3k_processed
      type: builtin
      description: 10x Genomics PBMC 3k processed dataset
    expected:
      format: h5ad
      path: expected/adata.h5ad
      label_column: leiden
    metrics:
      - id: n_clusters
        type: range
        min: 3
        max: 8
      - id: silhouette_score
        type: min
        threshold: 0.10
      - id: largest_cluster_ratio
        type: max
        threshold: 0.60
```

`benchmarks/csv-summary-skill/registry.yaml`：

```yaml
schema_version: "2.0"
cache_dir: ".benchmark_cache"

benchmarks:
  csv_summary_sales:
    name: CSV Summary: Sales
    skill: csv-summary-skill
    task: table
    level: 1
    input:
      path: data/sales.csv
    expected:
      format: csv
      path: expected/sales_summary.csv
    metrics:
      - id: row_count
        type: min
        threshold: 3
      - id: col_count
        type: min
        threshold: 2
```

`benchmarks/document-writer-skill/registry.yaml`：

```yaml
schema_version: "2.0"
cache_dir: ".benchmark_cache"

benchmarks:
  skill_md_writer:
    name: SKILL.md Writer
    skill: document-writer-skill
    task: document
    level: 1
    input:
      path: data/prompt.txt
    expected:
      format: markdown
      path: expected/best_skill.md
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

### B. 完整 Clustering Runner

```python
#!/usr/bin/env python3
"""Default runner for the PBMC 3k clustering benchmark."""

from pathlib import Path
from typing import Any

import scanpy as sc


def run(skill_code: str, input_data: Any, output_dir: Path) -> Path:
    """Execute skill-generated code on input data and return output path."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if isinstance(input_data, Path):
        adata = sc.read_h5ad(input_data)
    else:
        adata = input_data

    exec(skill_code, {"adata": adata, "sc": sc})

    output_path = output_dir / "output.h5ad"
    adata.write_h5ad(output_path)
    return output_path
```

### C. 完整 Document Runner

```python
#!/usr/bin/env python3
"""Runner for document generation benchmark."""

from pathlib import Path


def run(skill_code: str, prompt_path: Path, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt_text = Path(prompt_path).read_text(encoding="utf-8")

    namespace = {"prompt": prompt_text}
    exec(skill_code, namespace)
    generated = namespace.get("generated_markdown", "")

    output_path = output_dir / "output.md"
    output_path.write_text(generated, encoding="utf-8")
    return output_path
```

### D. 基线文件示例

```yaml
skill: bio-single-cell-clustering
version: "2026-06-16"
benchmarks:
  pbmc3k_clustering:
    n_clusters: 7
    largest_cluster_ratio: 0.35
    silhouette_score: 0.45
    ari: 1.0
    nmi: 1.0
    _all_pass: true
```

---

<a id="roadmap"></a>

## 十五、推荐实施路线图
| 阶段 | 时间 | 目标 |
|---|---|---|
| **Phase 1** | 1-2 周 | 为 3-5 个核心 Skill 各建 1-2 个 Benchmark，跑通本地和 CI |
| **Phase 2** | 1 个月 | 扩展到 10-15 个 Skill，建立 baseline 库 |
| **Phase 3** | 2-3 个月 | 覆盖全部客观任务 Skill，建立合成数据工厂 |
| **Phase 4** | 持续 | 每月新增公开数据集，每季度人工审核金标准质量 |

---

<a id="further-reading"></a>

## 十六、延伸阅读
- `examples/benchmark_minimal/`：仓库自带的最小可运行示例。
- `templates/regression_test.py`：回归测试脚本。
- `skillprism/benchmark/runner.py`：引擎 benchmark 运行器。
- `skillprism/benchmark/metrics.py`：引擎指标实现。
- `docs/OPERATIONAL_PLAYBOOK.md`：如何把 Benchmark 接入 Skill 评估与优化流程。
- [`benchmark-bioinformatics.md`](benchmark-bioinformatics.md)：生物信息类 Skill 的 Benchmark 设计专项指南。
