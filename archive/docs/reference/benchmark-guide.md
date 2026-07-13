# 金标准 Benchmark 构建与迭代优化指南（手把手版）

> 目标：从零开始，为一个 Skill 建立可重复、可自动化、可持续积累的金标准 Benchmark 集合，并把它接入回归测试与 CI。
>
> 读完本指南后，你应该能：
> 1. 跑通仓库自带的最小示例；
> 2. 为自己的 Skill 新增一个 Benchmark（注册表 + 任务契约 + 数据 + 金标准）；
> 3. 生成/维护 `expected` 金标准输出；
> 4. 保存基线、做回归测试；
> 5. 把 Benchmark 接入 GitHub Actions。

---

## 目录

1. [核心原则](#core-principles)
2. [快速体验：跑通最小示例](#quickstart)
3. [Benchmark 体系架构与执行模型](#architecture)
4. [从零创建一个 Table Benchmark](#table-benchmark)
5. [从零创建一个 Clustering Benchmark](#clustering-benchmark)
6. [从零创建一个 Document Benchmark](#document-benchmark)
7. [注册表字段完全参考](#registry-reference)
8. [执行方式与任务扩展](#execution-model)
9. [指标与阈值](#metrics)
10. [基线与回归测试](#baseline-regression)
11. [规模化与 CI/CD](#scale-ci)
12. [常见陷阱与排查](#troubleshooting)
13. [cell2location 空间解卷积实战（专题）](#cell2location)
14. [推荐实施路线图](#roadmap)
15. [延伸阅读](#further-reading)

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
│   │   ├── tasks/clustering.yaml    # Task spec（任务契约：prompt + 输入/输出占位符）
│   │   ├── data/                    # 输入数据
│   │   └── expected/adata.h5ad      # 金标准输出
│   └── document-demo/
│       ├── registry.yaml
│       ├── tasks/document.yaml
│       ├── data/                    # 输入 prompt 等
│       └── expected/best_skill.md
├── sample_skill_code.py             # 示例：Skill 生成的代码（聚类）
├── sample_document_skill_code.py    # 示例：文档 Skill 生成的代码
├── generate_expected.py             # 生成金标准输出
└── baselines/                       # 基线结果
    └── bio-single-cell-clustering.yaml
```

### 2.2 安装依赖

```bash
cd /path/to/Skills_Validation
pip install -e .
# 最小示例的聚类 benchmark 需要 scanpy
pip install scanpy
```

### 2.3 生成金标准输出

金标准（expected）是 Benchmark 的“正确答案”。对于聚类任务，它通常是一份跑过参考流程的 `adata.h5ad`。

```bash
cd examples/benchmark_minimal
python generate_expected.py
```

运行后金标准写入 `benchmarks/bio-single-cell-clustering/expected/adata.h5ad`。

> 如果 `expected/` 目录里已经有文件，说明仓库已提交一份预生成的金标准，你可以跳过这一步。

### 2.4 运行 Benchmark

```bash
test-skill \
    --skill bio-single-cell-clustering \
    --registry benchmarks/bio-single-cell-clustering/registry.yaml \
    --code sample_skill_code.py \
    --task clustering
```

典型输出（指标数值为示意，取决于数据与随机种子）：

```text
Running 1 benchmarks (skill: bio-single-cell-clustering)

[PASS] PBMC 3k Clustering: {'n_clusters': 8, 'silhouette_score': 0.12, 'largest_cluster_ratio': 0.28, '_metric_pass': {'n_clusters': True, 'silhouette_score': True, 'largest_cluster_ratio': True}, '_all_pass': True, '_actual_output': '...', '_expected_output': '...'}
```

解释：

- 引擎**只计算 registry `metrics` 里声明的指标**（本例为 `n_clusters`、`silhouette_score`、`largest_cluster_ratio`）；
- `ari`/`nmi` 等需要金标准对比的指标不会自动出现——把它们声明进 `metrics` 且 `expected` 存在时才会计算；
- `_metric_pass` 显示每个指标是否通过注册表里的阈值；
- `_all_pass: true` 表示本次 Benchmark 通过；
- 不传 `--code` 且未配置 `SKILLPRISM_AGENT_COMMAND` 时，`test-skill` 默认进入 results 模式：跳过执行，直接评估输出路径上已存在的结果文件（见 §8.1）。

### 2.5 文档 Benchmark 也跑一遍

```bash
test-skill \
    --skill document-demo \
    --registry benchmarks/document-demo/registry.yaml \
    --code sample_document_skill_code.py \
    --task document
```

基线保存与回归对比见 §10。

---

<a id="architecture"></a>

## 三、Benchmark 体系架构与执行模型
一个 Skill 的 Benchmark 目录由四部分组成（外加一个可选文件）：

1. **注册表（`benchmarks/<skill>/registry.yaml`）**：声明该 Skill 的 Benchmark 元数据、数据来源、指标阈值。
2. **任务契约（`benchmarks/<skill>/tasks/<task>.yaml`）**：定义 prompt、输入输出格式、`{placeholder}` 路径占位符。
3. **输入数据（`data/`）**：Skill 要处理的对象，可按 level 分子目录（如 `data/tiny/`、`data/small/`）。
4. **期望输出（`expected/`）**：金标准结果，可省略；但依赖 expected 的 metric 在没有 expected 时返回 `None` 并判 FAIL。
5. **私有 metric（`metrics.py`，可选）**：与注册表同级，用 `@metric("id")` 注册该 Skill 专属指标。

整体布局即 §2.1 所示的 `benchmarks/<skill>/` 目录（`registry.yaml` + `tasks/` + `data/` + `expected/` + 可选 `metrics.py`）。真实示例可对照 `examples/benchmark_cell2location/benchmarks/bio-spatial-deconvolution-cell2location/` 与 `examples/quickstart/benchmarks/csv-summary/`。

### 3.1 执行模型：没有内置任务类型，也没有 `runner.py`

引擎（`skillprism/benchmark/runner.py` 的 `run_single_benchmark`）对每个 benchmark 只有三条执行路径，按顺序判定：

1. **插件任务**：benchmark 的 `task` 字段命中已注册的插件（entry point 或 registry `plugins` 声明）时，整个 benchmark 交给插件函数处理，插件优先于一切内置路径。
2. **任务契约 + 执行器**：加载 `tasks/<task>.yaml`，解析 `{placeholder}` 占位符得到真实输入/输出路径，然后：
   - 传了 `--code` → `CodeExecutor` 在沙箱子进程中执行该代码，占位符以同名全局变量注入；
   - 配置了 `SKILLPRISM_AGENT_COMMAND` → `AgentExecutor` 把渲染后的 prompt 从 stdin 喂给外部 agent，路径通过环境变量传入；
   - 两者都没有 → results 模式，直接评估输出路径上已存在的文件。
3. 输出文件交给 `GenericEvaluator`，按 registry 声明的 `metrics` 逐条计算并判定阈值。

推论：

- 引擎**没有任何内置 task 类型**——`task` 只是一个用于查找 `tasks/<task>.yaml`（或插件）的标识符；`skillprism/benchmark/tasks/` 是空目录。
- 引擎**不会加载** `benchmarks/<skill>/runner.py`。旧文档里的 runner 机制已被「task spec 占位符注入 + `--code` 执行 + 插件」取代（详见 §8）。

---

<a id="table-benchmark"></a>

## 四、从零创建一个 Table Benchmark
Table 任务是最简单的 Benchmark：输入一个 CSV，输出一个 CSV，检查行数、列数等结构指标。假设你有一个 Skill `csv-summary-skill`，功能是把 CSV 加载进来并输出描述统计。

### 4.1 准备数据

```bash
mkdir -p benchmarks/csv-summary-skill/{data,tasks,expected}
cat > benchmarks/csv-summary-skill/data/sales.csv <<'EOF'
product,region,revenue
A,North,100
B,South,200
A,North,150
C,East,300
EOF
```

### 4.2 编写任务契约（Task spec）

`benchmarks/csv-summary-skill/tasks/csv_summary.yaml`：

```yaml
id: csv_summary
skill: csv-summary-skill
name: CSV Summary
description: Summarize a CSV file and write descriptive statistics.

prompt: |
  读取 {input_csv}，计算各数值列的描述统计，将结果写入 {output_csv}。

input:
  format: csv
  path: "{input_csv}"

output:
  format: csv
  path: "{output_csv}"
```

必填字段：`id`/`skill`/`name`/`description`/`prompt`/`input`/`output`；`input` 与 `output` 各需 `format` + `path`。`path` 里的 `{input_csv}`、`{output_csv}` 是占位符：运行时被替换为真实路径，并必须以同名占位符出现在 `prompt` 中（校验规则见 `skillprism/benchmark/task_spec.py`）。**Task spec 没有 `metrics` 字段，也没有 `type` 字段**——指标只写在注册表里。

### 4.3 方式 A：用 `build-skill-test` 注册

```bash
build-skill-test \
  --id csv_summary_sales \
  --name "CSV Summary: Sales" \
  --skill csv-summary-skill \
  --task csv_summary \
  --input data/sales.csv \
  --expected-path expected/sales_summary.csv \
  --metric row_count:min:3 \
  --metric col_count:min:2 \
  --suite smoke \
  --registry benchmarks/csv-summary-skill/registry.yaml
```

参数以 `skillprism/benchmark/builder.py` 的 argparse 为准：

| 参数 | 含义 |
|---|---|
| `--id` | Benchmark 唯一 ID（必填，registry 内不能重复）。 |
| `--name` | 人类可读名称（必填）。 |
| `--skill` | 所属 Skill 名（必填）。 |
| `--task` | 任务 id，对应 `tasks/<task>.yaml`（必填）。 |
| `--task-spec` | 显式指定 task spec 路径（默认 `tasks/<task>.yaml`，相对注册表目录）。 |
| `--input` | 输入数据路径，相对注册表目录（必填）。 |
| `--expected-path` | 金标准输出路径，相对注册表目录（可选）。 |
| `--metric` | `id:type:args`，可重复；如 `row_count:min:3`、`n_clusters:range:3:8`、`accuracy:exact:0.95`、`correlation:tolerance:0.05`。 |
| `--description` | 输入描述。 |
| `--suite` | 把该 benchmark 加入命名 suite（顶层 `suites`），可重复。 |
| `--level` | 难度等级 0–3，默认 1。 |
| `--gpu` / `--real-data` | 标记需要 GPU / 使用真实数据。 |
| `--generate-expected` | 仅支持 CSV：把 `--input` 复制到 `--expected-path`。 |
| `--registry` | 要写入的注册表文件，默认 `benchmark_registry.yaml`——**推荐显式传 `benchmarks/<skill>/registry.yaml`**。 |

注意 builder 的边界：

- 它**只写注册表条目**（以及可选的 `--generate-expected` 复制 CSV），不创建目录、不下载数据、不生成代码；
- 它要求 `tasks/<task>.yaml` **已存在**并通过校验，否则报错退出；
- 不存在 `--dataset-source` / `--dataset-type` / `--expected-format` 参数，`expected.format` 由文件后缀自动推断。

运行后 `benchmarks/csv-summary-skill/registry.yaml` 新增：

```yaml
  csv_summary_sales:
    name: CSV Summary: Sales
    skill: csv-summary-skill
    task: csv_summary
    level: 1
    input:
      path: data/sales.csv
    task_spec: tasks/csv_summary.yaml
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

### 4.4 方式 B：手动创建（理解原理）

手写同样的注册表条目即可（字段见 §7）。如需 expected，自行复制或计算，例如 `cp data/sales.csv expected/sales_summary.csv`。

### 4.5 编写 Skill 代码并运行

`--code` 指向的脚本在沙箱子进程中执行，task spec 的占位符以**同名全局变量**注入（另含 `output_dir`）。`sample_skill_code.py`：

```python
import pandas as pd

df = pd.read_csv(input_csv)      # input_csv：{input_csv} 解析后的绝对路径
summary = df.describe()
summary.to_csv(output_csv)       # output_csv：{output_csv} 解析后的绝对路径
```

运行：

```bash
test-skill \
    --skill csv-summary-skill \
    --registry benchmarks/csv-summary-skill/registry.yaml \
    --code sample_skill_code.py \
    --task csv_summary
```

如果输出 CSV 满足 `row_count >= 3` 且 `col_count >= 2`，就会 PASS。注意引擎不存在「内置 table 任务」：`input_csv`/`output_csv` 不是引擎魔法，而是你在 task spec 里自定义的占位符名——换成 `{input_path}`/`{output_path}` 同样可以，只要 prompt、input.path、output.path 三处一致。

---

<a id="clustering-benchmark"></a>

## 五、从零创建一个 Clustering Benchmark
Clustering Benchmark 需要三件事：数据、参考聚类结果（金标准）、一个任务契约。下面为 `bio-single-cell-clustering` 新增一个 `pbmc3k` Benchmark。

### 5.1 创建目录并生成金标准输出

```bash
mkdir -p benchmarks/bio-single-cell-clustering/{data,tasks,expected}
```

写一个 `generate_expected.py`（也可以临时写在 notebook 里），用固定参数的参考流程生成金标准后 `adata.write_h5ad("benchmarks/bio-single-cell-clustering/expected/adata.h5ad")`。完整脚本可直接参考 `examples/benchmark_minimal/generate_expected.py`。

### 5.2 编写任务契约

`benchmarks/bio-single-cell-clustering/tasks/clustering.yaml`（与 `examples/benchmark_minimal/` 一致）：

```yaml
id: clustering
skill: bio-single-cell-clustering
name: Single-cell clustering
description: Cluster a single-cell RNA-seq dataset and assign leiden cluster labels.

prompt: |
  对输入的 AnnData 单细胞数据进行聚类分析，使用 leiden 算法，并将结果保存为 H5AD。
  - 输入文件：{adata}
  - 输出文件：{output_h5ad}（obs 列必须包含 leiden）

input:
  format: h5ad
  path: "{adata}"

output:
  format: h5ad
  path: "{output_h5ad}"
```

### 5.3 注册 Benchmark

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

`dataset.type: builtin` 的数据由引擎在运行前加载并写入 `cache_dir`，再把真实路径注入 `{adata}` 占位符（见 §7.3）。`build-skill-test` 适合输入为本地文件的任务；builtin 数据集建议手写条目。

### 5.4 编写 Skill 代码

`sample_skill_code.py`（占位符同名全局变量由沙箱注入）：

```python
import scanpy as sc

adata = sc.read_h5ad(adata)
sc.pp.neighbors(adata, n_neighbors=15, n_pcs=30)
sc.tl.leiden(adata, resolution=0.5)
sc.tl.umap(adata)
adata.write_h5ad(output_h5ad)
```

### 5.5 运行

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
Document Benchmark 用来评估“生成文本型 Skill”的质量，例如让 Skill 根据 prompt 写一份 `SKILL.md`。假设要评估一个 `document-writer-skill`：输入 prompt，输出 Markdown 文档。

### 6.1 创建目录、prompt 与金标准

```bash
mkdir -p benchmarks/document-writer-skill/{data,tasks,expected}

cat > benchmarks/document-writer-skill/data/prompt.txt <<'EOF'
Write a concise SKILL.md for a Python data analysis skill that loads a CSV,
summarizes numeric columns, and outputs a report.
EOF
```

再手写一份你认为“最好”的 `expected/best_skill.md`（frontmatter + When to Use / Inputs / Outputs / Quick Start / Common Pitfalls 等章节）。`section_overlap` 等指标以它的标题集合为参照。

### 6.2 编写任务契约

`benchmarks/document-writer-skill/tasks/document.yaml`（与 `examples/benchmark_minimal/benchmarks/document-demo/` 一致）：

```yaml
id: document
skill: document-writer-skill
name: SKILL.md generation
description: Generate a SKILL.md document from a text prompt.

prompt: |
  根据输入的 prompt 生成一份 SKILL.md 文档。
  - 输入文件：{prompt_path}
  - 输出文件：{output_path}（Markdown，需包含角色、任务、使用示例等章节）

input:
  format: text
  path: "{prompt_path}"

output:
  format: markdown
  path: "{output_path}"
```

### 6.3 注册 Benchmark

```bash
build-skill-test \
  --id skill_md_writer \
  --name "SKILL.md Writer" \
  --skill document-writer-skill \
  --task document \
  --input data/prompt.txt \
  --expected-path expected/best_skill.md \
  --metric section_overlap:min:0.6 \
  --metric token_jaccard:min:0.3 \
  --metric length_ratio:range:0.5:2.0 \
  --registry benchmarks/document-writer-skill/registry.yaml
```

### 6.4 运行

```bash
test-skill \
    --skill document-writer-skill \
    --registry benchmarks/document-writer-skill/registry.yaml \
    --code sample_document_skill_code.py \
    --task document
```

引擎注册的文档指标只有三个（完整清单见 §9）：

- `section_overlap`：生成文档的标题覆盖金标准标题的比例；
- `token_jaccard`：词级 Jaccard 相似度；
- `length_ratio`：输出长度 / 金标准长度，防止过短/过长。

> `semantic_similarity`、`rouge_l`、`bert_score_f1` **不是注册 metric**。把它们写进 `metrics` 不会“因缺依赖而跳过”——未注册的 metric id 取值为 `None`，直接判 FAIL（见 §9.3）。需要这类指标时，在 registry 同级 `metrics.py` 里自行注册（见 §8.4）。

---

<a id="registry-reference"></a>

## 七、注册表字段完全参考
每个 Skill 拥有独立的注册表 `benchmarks/<skill>/registry.yaml`，声明该 Skill 的所有 Benchmark 元数据、金标准和指标阈值。

### 7.1 顶层字段

```yaml
schema_version: "2.0"         # 必填，当前固定 "2.0"
cache_dir: ".benchmark_cache" # 数据缓存目录，相对注册表目录；默认 .benchmark_cache
suites:                       # 可选，命名 suite（顶层，不属于单个 benchmark）
  smoke:
    benchmarks: [pbmc3k_clustering]
plugins: [my_plugin.run]      # 可选，自定义任务插件（见 §8.3）
benchmarks:                   # 必填，该 Skill 下所有 Benchmark 的集合
  ...
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `schema_version` | 是 | 当前固定 `"2.0"`。 |
| `cache_dir` | 否 | 数据缓存目录，默认 `.benchmark_cache`（相对注册表目录）。 |
| `suites` | 否 | 命名 suite → benchmark id 列表；`--suite` 只跑指定 suite。 |
| `plugins` | 否 | 自定义任务插件模块/可调用对象，运行前加载。 |
| `benchmarks` | 是 | benchmark id → 条目映射。 |

### 7.2 每个 Benchmark 的字段

```yaml
benchmark_id:
  name: "Human-readable name"
  skill: skill-name           # 所属 Skill
  task: clustering            # 任务 id → tasks/clustering.yaml（或同名插件）
  level: 1                    # 0=unit, 1=component, 2=integration, 3=release
  task_spec: tasks/clustering.yaml   # 可选，显式指定 task spec 路径
  input:
    path: data/pbmc3k.h5ad    # 相对注册表目录；覆盖 task spec 的输入模板
    description: "..."
  dataset:                    # 与 input.path 二选一：由引擎获取数据
    source: scanpy.datasets.pbmc3k_processed
    type: builtin             # builtin / local / url
    description: "..."
    checksum: sha256:abcd...  # url 类型建议加
  expected:                   # 可省略；依赖它的 metric 在缺失时返回 None → FAIL
    format: h5ad              # 描述性字段：h5ad / csv / markdown / json / yaml
    path: expected/adata.h5ad # 相对于注册表目录
    label_column: leiden      # 聚类标签列，默认 leiden
  expected_result: pass       # pass（默认）/ fail（负向测试）
  expected_error: "ValueError" # expected_result: fail 时错误需匹配的正则
  real_data: true             # 标记真实数据（结果里记 _real_data，供报告区分）
  requires_gpu: true          # 无 GPU 环境自动跳过
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
| `skill` | 是 | 该 Benchmark 所属的 Skill 名；`--skill` 按此匹配（旧字段 `skills` 列表仍兼容）。 |
| `task` | 是 | 任务 id：优先匹配同名插件，否则定位 `tasks/<task>.yaml`。 |
| `level` | 否 | 难度等级：`0` 单元、`1` 组件、`2` 集成、`3` 发布；`--level` 过滤用。 |
| `task_spec` | 否 | 显式 task spec 路径（相对注册表目录）；省略时默认 `tasks/<task>.yaml`。 |
| `input.path` | 否 | 本地输入路径（相对注册表目录），覆盖 task spec 的输入模板；与 `dataset` 二选一。 |
| `input.description` | 否 | 输入描述，只在报告里展示。 |
| `dataset.source` | 否 | 数据来源表达式/路径/URL（与 `input.path` 二选一）。 |
| `dataset.type` | 否 | `builtin` / `local` / `url`，见 §7.3。 |
| `dataset.description` | 否 | 描述，只在报告里展示。 |
| `dataset.checksum` | 否 | `url` 类型强烈建议加，用于校验下载完整性。 |
| `expected.format` | 否 | 输出格式，描述性字段（引擎不据此选择 evaluator）；示例统一用 `h5ad` / `csv` / `markdown`。 |
| `expected.path` | 否 | 金标准输出路径，相对注册表目录。**可省略；仅在 metric 需要与金标准对比时才需要。** |
| `expected.label_column` | 否 | 聚类等任务的标签列，默认 `leiden`。 |
| `expected_result` | 否 | `pass`（默认）或 `fail`；`fail` 表示该 benchmark 预期失败（负向测试）。 |
| `expected_error` | 否 | `expected_result: fail` 时，错误信息需匹配的正则（默认 `.+`，即任意非空错误）。 |
| `real_data` | 否 | 标记真实数据；结果中记录 `_real_data`，用于报告与基线策略区分。 |
| `requires_gpu` | 否 | 需要 GPU；无 GPU 环境自动 `[SKIP]`（可用 `--gpu/--no-gpu` 覆盖自动检测）。 |
| `metrics` | 否 | 指标及阈值列表；不填则无指标约束（`_all_pass` 恒为 true）。 |
| `metrics[].id` | 是 | 指标 ID，对应已注册的 metric 函数（§9）。 |
| `metrics[].type` | 是 | 阈值类型：`min` / `max` / `range` / `tolerance` / `exact`（§9.1）。 |
| `metrics[].threshold` 等 | 视类型 | `min`/`max`/`tolerance` 用 `threshold`；`range` 用 `min`+`max`；`exact` 用 `expected`；`tolerance` 可加 `reference`。 |

> **注意**：不要把 `expected` 当作指标值的容器。如果只是想检查 `n_spots == 1000`，应直接写成 metric（如 `n_spots: exact: 1000`），或写一个读取 actual output 的私有 metric。`expected` 留给真正的金标准输出文件（参考聚类标签、参考解卷积比例、参考文档）。详见 [`benchmark-metrics.md`](benchmark-metrics.md)。

### 7.3 `dataset.type` 详细说明

`dataset` 由引擎在运行前通过 `fetch_dataset` 获取，再把真实路径注入 task spec 的输入占位符。当 `input.path` 已给出具体路径时，`dataset` 不需要。三种类型：

- **`builtin`**：通过 Python 表达式直接加载（要求环境已装对应包），加载出的对象写入 `cache_dir`（AnnData 走 `write_h5ad`，DataFrame 走 `to_csv`）后再注入占位符。例：`source: scanpy.datasets.pbmc3k_processed`。
- **`local`**：数据已在本地，`source` 为相对注册表目录的路径，如 `source: data/pbmc3k_processed.h5ad`。
- **`url`**：从网络下载到 `cache_dir`；提供 `checksum: sha256:...` 时下载后校验，不匹配则报错。

### 7.4 负向测试（`expected_result: fail`）

有些 benchmark 用来验证 Skill 在错误输入下**应当失败**（例如输入文件损坏）。把 `expected_result` 设为 `fail` 后：执行产生非空错误且匹配 `expected_error` 正则 → 判 PASS；Skill 意外成功（无错误）→ 判 FAIL。

---

<a id="execution-model"></a>

## 八、执行方式与任务扩展

### 8.1 三种执行方式

| 方式 | 触发条件 | 行为 |
|---|---|---|
| `--code <path>` | 显式传代码文件 | `CodeExecutor` 在沙箱子进程执行：最小环境变量、cwd 限制在输出目录、内存/CPU/文件大小 rlimit 上限、超时保护；占位符以同名全局变量注入（另含 `output_dir`）。 |
| Agent 模式 | 设置 `SKILLPRISM_AGENT_COMMAND` 且未传 `--code` | `AgentExecutor` 调用外部命令：渲染后的 prompt 走 stdin，真实路径通过 `SKILLPRISM_INPUT_PATH` / `SKILLPRISM_OUTPUT_PATH` 环境变量传入；默认不透传其他环境变量（可用 `SKILLPRISM_AGENT_PASS_THROUGH_ENV` 逗号名单放行）。 |
| results 模式 | 两者都没有（`test-skill` 默认），或显式 `--results` | 跳过执行，直接评估输出路径上已存在的结果文件；文件不存在则报错。 |

输出路径的确定：`benchmark.output.path`（或 `expected_output.path`）→ 相对 `cache_dir`；否则默认 `<cache_dir>/output/<benchmark_id>/output.<ext>`。

### 8.2 占位符注入机制

Task spec 的 `input.path` / `output.path` 是形如 `{input_csv}` 的模板。运行时（`skillprism/benchmark/task_spec.py`）：

1. `benchmark.input.path` 给出具体路径时优先使用（相对注册表目录解析）；否则按 `dataset` 获取数据，再把缓存路径填入；
2. 两个占位符被解析为真实路径后：
   - 对 `prompt` 做 `str.format` 替换，生成喂给 agent 的最终 prompt；
   - 对 `--code` 执行，以**同名全局变量**注入沙箱（`input_csv`、`output_csv` 等，外加 `output_dir`）。

因此 Skill 代码与 prompt 看到的是同一组路径，task spec 是唯一的事实来源。

### 8.3 自定义任务类型：插件

当「task spec + 占位符 + `--code`」不能满足需求（例如多文件输出、特殊的执行编排），可以注册任务插件，而无需修改引擎源码：

- **Registry 插件**：在注册表顶层写 `plugins: [my_plugin.run]`，随 registry 加载；
- **Entry-point 插件**：pip 包声明 `skillprism.benchmark.task` 入口点，安装后全局可用。

插件函数签名 `my_task(benchmark, skill, code_path, registry, registry_dir) -> dict`，返回至少包含 `_all_pass` 的结果字典。插件按 `task` 名匹配，**优先于** task spec 路径。完整教程见 [`adding-a-benchmark-task-type.md`](adding-a-benchmark-task-type.md)。

### 8.4 私有 metric

公共 metric 注册在 `skillprism/benchmark/metrics.py`；Skill 专属 metric 写在 registry 同级的 `metrics.py` 里，随 registry 自动加载：

```python
# benchmarks/<skill>/metrics.py
from skillprism.benchmark.metrics import metric

@metric("my_metric")
def my_metric(actual_path, expected_path, task_spec):
    """返回单值；无法计算时返回 None（判 FAIL）。"""
    ...
```

签名固定为 `(actual_path, expected_path, task_spec)`：`actual_path` 是本次输出，`expected_path` 是金标准路径（可能为 `None`），`task_spec` 是任务契约字典。

---

<a id="metrics"></a>

## 九、指标与阈值
本节是速查；**选型和语义的唯一权威是 [`benchmark-metrics.md`](benchmark-metrics.md)**。

### 9.1 五种阈值类型

| 类型 | 判定（`metric_passes`） | YAML 字段 | 示例 |
|---|---|---|---|
| `min` | `value >= threshold` | `threshold` | `silhouette_score >= 0.25` |
| `max` | `value <= threshold` | `threshold` | `largest_cluster_ratio <= 0.60` |
| `range` | `min <= value <= max` | `min` + `max` | `n_clusters` 在 3–8 之间 |
| `tolerance` | `abs(value - reference) <= threshold` | `threshold`（+ 可选 `reference`，缺省取 value 自身） | 与参考值差距不超过 0.05 |
| `exact` | `value == expected` | `expected` | `n_spots == 10` |

### 9.2 已注册 metric 完整清单

公共 metric 全部通过 `@metric("id")` 注册在 `skillprism/benchmark/metrics.py`（标 ★ 的依赖 `expected`，无 expected 时返回 `None`）：

| 类别 | metric id |
|---|---|
| CSV / 表格 | `row_count`、`col_count`、`diff_row_count` ★、`expected_diff_rows` ★、`has_required_columns` |
| AnnData / 聚类 | `n_clusters`、`largest_cluster_ratio`、`silhouette_score`、`ari` ★、`nmi` ★ |
| 解卷积（比例矩阵 CSV） | `n_spots`、`n_cell_types`、`mean_rmse` ★、`max_rmse` ★、`mean_pearson` ★、`min_pearson` ★、`mean_jsd` ★ |
| 文档 / 文本 | `section_overlap`、`token_jaccard`、`length_ratio` |

补充：`silhouette_score` 需要 `adata.obsm['X_pca']`，缺失或簇数不合法时返回 `None`；`has_required_columns` 读取 task spec 的 `output.required_columns` 列表，未声明时恒为 true；`ari`/`nmi` 与解卷积类指标按 `expected.label_column`（默认 `leiden`）或行列交集对齐后计算。

### 9.3 判定规则（务必记住）

1. 只计算 registry `metrics` 里声明的指标；
2. metric 返回 `None`（缺 expected、缺 X_pca 等）→ 该指标 FAIL；
3. **metric id 未注册 → 值 `None` → FAIL**。不存在「缺依赖则跳过并提示」的机制；`semantic_similarity` / `rouge_l` / `bert_score_f1` / `_all_pass` 都不是注册 metric；
4. 全部指标通过 → `_all_pass: true`。

### 9.4 用 `build-skill-test` 写指标

```bash
--metric row_count:min:3
--metric n_clusters:range:3:8
--metric accuracy:exact:0.95
--metric correlation:tolerance:0.05
```

格式：`id:type:args`（`tolerance` 只接受一个 threshold 参数；需要 `reference` 时手改 YAML）。

---

<a id="baseline-regression"></a>

## 十、基线与回归测试

基线（baseline）记录“当前被接受版本”的指标快照。以后任何 Skill 改动，都要和基线做回归对比，得分不下降才允许合并。

### 10.1 保存基线

`test-skill --output`（或 `python -m skillprism.benchmark.runner --output`）把全量结果写成 YAML：

```bash
test-skill \
    --skill bio-single-cell-clustering \
    --registry ./benchmarks/bio-single-cell-clustering/registry.yaml \
    --code ./sample_skill_code.py \
    --output ./baselines/bio-single-cell-clustering.yaml
```

基线文件格式（节选）：

```yaml
skill: bio-single-cell-clustering
benchmarks:
  pbmc3k_clustering:
    n_clusters: 8
    silhouette_score: 0.12
    largest_cluster_ratio: 0.28
    _metric_pass: {n_clusters: true, silhouette_score: true, largest_cluster_ratio: true}
    _all_pass: true
    _actual_output: ...
    _expected_output: ...
_all_pass: true
_suite: null
_level: null
```

### 10.2 回归对比

修改 Skill 后再跑一次（`--output ./latest/<skill>.yaml`），然后用回归脚本对比：

```bash
python templates/regression_test.py \
    --results ./latest/bio-single-cell-clustering.yaml \
    --baseline ./baselines/bio-single-cell-clustering.yaml \
    --tolerance 0.03
```

判定规则：

- 对每个数值 metric 计算相对变化 `rel_diff = (current - baseline) / baseline`；
- 默认相对容差 `--tolerance 0.03`（±3%）；
- 单指标状态：`IMPROVED`（明显优于基线）/ `PASS`（容差内）/ `REGRESSION`（变差超容差）；
- 任一指标 `REGRESSION` → 整体输出 `RESULT: REJECT (regression detected)`，退出码 1；否则 `RESULT: ACCEPT (no regression detected)`，退出码 0。

> 随机性较强的任务（如聚类）建议用 3%–5%；确定性任务可用 0%。

### 10.3 更新基线

当改动确实提升了指标，并且已经通过代码审查后，更新基线并提交 Git：

```bash
cp latest/bio-single-cell-clustering.yaml \
   baselines/bio-single-cell-clustering.yaml
```

### 10.4 CI / 渐进测试中的基线

- `skill-ci --baseline <path>`：CI 门控中做回归对比，默认回归即失败（`--no-stop-on-regression` 可放宽）；`--ratchet` 在全部通过时把基线推进到当前结果。
- `test-skill --mode gradual`：逐级（level 0 → `--max-level`）放行，每级基线保存在 `artifacts/<skill>/ci/gradual/.baselines/<skill>/gradual_baseline_level<N>.yaml`，默认通过后自动 ratchet（`--no-ratchet` 关闭）。

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

### 11.2 数据来源

输入数据优先自动生成（合成、`builtin`、公开数据集脚本）；金标准 expected 通常需要参考流程或人工撰写；真实数据永远外部准备，用 `real_data: true` 标记、level 3 只做完成性验收。各类数据能否自动生成、如何融入流程的完整决策表见 [`data-building-decisions.md`](data-building-decisions.md)。

数据准备清单（接入前逐项检查）：

| 步骤 | 检查项 |
|---|---|
| 1 | Skill 目录包含 `SKILL.md` 且 frontmatter 完整 |
| 2 | 输入数据已放入 `benchmarks/<skill>/data/` 或提供下载脚本 / `dataset` 声明 |
| 3 | 期望输出已放入 `benchmarks/<skill>/expected/`（依赖金标准的 metric 需要） |
| 4 | 任务契约已写入 `benchmarks/<skill>/tasks/<task>.yaml` 并通过校验 |
| 5 | `benchmarks/<skill>/registry.yaml` 已注册该 benchmark |
| 6 | `test-skill --mode single` 验证通过 |
| 7 | 基线已保存（见 §10） |

### 11.3 合成数据

合成数据适合快速扩充聚类、解卷积等任务：用脚本（如 `scanpy.datasets.blobs`、`skillprism.testing.mock_data`）批量生成「输入 + 已知标签/比例」并写入 `data/` 与 `expected/`，再在注册表批量登记。具体生成方式与注意事项见 [`data-building-decisions.md`](data-building-decisions.md)；cell2location 的完整合成数据实例见 [`cell2location.md`](cell2location.md)。

### 11.4 GitHub Actions 示例

CI 中不要再手写 `python -m skillprism.benchmark.runner` 循环，直接用 `skill-ci` 做门控（静态检查 + 可选动态 benchmark + 基线回归 + ratchet）：

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
      - name: Run CI gate for changed skills
        run: |
          for skill in $(git diff --name-only origin/main | grep '^skills/' | cut -d'/' -f2 | sort -u); do
            echo "CI gate for $skill"
            skill-ci \
              --skill "$skill" \
              --registry "benchmarks/${skill}/registry.yaml" \
              --run-benchmark --code sample_skill_code.py \
              --baseline "baselines/${skill}.yaml" \
              --ratchet
          done
```

`skill-ci` 要点：

- `--run-benchmark` 才运行动态 benchmark（需 `--code`，CI 不调用 LLM 生成代码）；不加则只做静态检查 + results 模式评估；
- `--baseline` 开启回归门控，默认回归即失败（`--no-stop-on-regression` 放宽）；`--ratchet` 在全部通过时推进基线；
- `--suite` / `--level` 限定范围；`--no-smoke` / `--no-deps` 跳过冒烟与依赖检查；
- 产物默认写入 `artifacts/<skill>/ci/`（`--output-dir` 可改）。

### 11.5 数据缓存策略

- 使用 GitHub Actions Cache 或 DVC 缓存 Benchmark 数据；
- 在 PR 中只跑受影响的 Skill 的 Benchmark，避免全量运行耗时；
- 每周/每月跑一次全量 Benchmark，捕获依赖更新导致的回归。

---

<a id="troubleshooting"></a>

## 十二、常见陷阱与排查

### 12.1 金标准本身有噪声

公开数据的标签可能不完美：设置合理的容错阈值，对关键 Benchmark 做人工抽查，使用多个异构数据集避免单个噪声数据集主导结果。

### 12.2 过度拟合 Benchmark

Skill 只针对特定数据集优化、换数据就失效：每个 Skill 至少覆盖 2–3 个不同来源的数据集，定期加入新的公开数据集，不要为了提高分数牺牲通用性。

### 12.3 运行环境差异

CI 与本地环境可能不同：在 `pyproject.toml` 里固定依赖版本（或用 conda lock / Docker），对随机性强的任务设置随机种子。

### 12.4 数据泄露

训练集和测试集不能混用，Skill 不应在 Benchmark 数据上“调参”：Benchmark 数据只用于评估，示例代码不要硬编码 Benchmark 数据集，需要训练时训练数据必须与 Benchmark 数据隔离。

### 12.5 指标选择偏差

不要只选一个指标。建议：

- 聚类：同时看聚类数量、最大簇比例、Silhouette，以及（有金标准时）ARI、NMI；
- 解卷积：同时看 RMSE、Pearson、JSD，防止只拟合相关性忽略绝对比例；
- 文档：同时看结构（`section_overlap`）、词汇（`token_jaccard`）、长度（`length_ratio`）。

### 12.6 常见报错

| 报错 | 原因 | 解决 |
|---|---|---|
| `Error: benchmark id 'x' already exists` | ID 重复 | 换 ID 或先删除旧条目 |
| `Error: task spec not found: ...` | `tasks/<task>.yaml` 缺失（builder 或运行时） | 先写任务契约，或用 `task_spec` / `--task-spec` 显式指定 |
| `Task spec missing required fields` | 缺 `id/skill/name/description/prompt/input/output` | 按 §4.2 补齐必填字段 |
| `Prompt missing placeholders for input/output paths` | prompt 没包含 input/output 的占位符 | prompt 里加上 `{...}` 占位符 |
| `Benchmark missing 'input.path' and task spec path is templated` | 既无 `input.path` 又无 `dataset` | 补 `input.path` 或 `dataset` 声明 |
| `No executor available` | 未传 `--code`、未配 `SKILLPRISM_AGENT_COMMAND`、非 results 模式 | 加 `--code` 或 `--results`，或配置 agent 命令 |
| `results mode but output not found` | results 模式下输出文件不存在 | 先用 `--code` 执行生成输出 |
| `Checksum mismatch` | 下载数据损坏或被替换 | 检查 URL 和 checksum |
| `ModuleNotFoundError: No module named 'scanpy'` | 缺少任务依赖 | `pip install scanpy` |
| `_all_pass: false` | 某指标未通过；metric id 未注册或缺 expected 时值为 `None` 也判 FAIL | 看 `_metric_pass` 定位失败指标 |
| `[SKIP] ...: requires GPU` | `requires_gpu: true` 且无 GPU | 在 GPU 环境跑，或 `--gpu` 强制执行 |
| `RESULT: REJECT` | 相对基线退化 | 检查改动是否引入回归，必要时更新基线 |

---

<a id="cell2location"></a>

## 十三、cell2location 空间解卷积实战（专题）
cell2location（空间转录组细胞类型解卷积）的完整实战——合成数据生成、四级渐进 benchmark（level 0 烟雾测试 → level 3 真实 Visium 验收）、私有 metric、GPU/`real_data` 标记——已独立成篇：

- 教程：[`cell2location.md`](cell2location.md)
- 可运行示例：`examples/benchmark_cell2location/`（含 `benchmarks/bio-spatial-deconvolution-cell2location/` 的 registry、任务契约、分层数据与金标准）

本章的 §4–§6 是该实战所用机制的通用版，建议先读通再进入专题。

---

<a id="roadmap"></a>

## 十四、推荐实施路线图
| 阶段 | 时间 | 目标 |
|---|---|---|
| **Phase 1** | 1-2 周 | 为 3-5 个核心 Skill 各建 1-2 个 Benchmark，跑通本地和 CI |
| **Phase 2** | 1 个月 | 扩展到 10-15 个 Skill，建立 baseline 库 |
| **Phase 3** | 2-3 个月 | 覆盖全部客观任务 Skill，建立合成数据工厂 |
| **Phase 4** | 持续 | 每月新增公开数据集，每季度人工审核金标准质量 |

---

<a id="further-reading"></a>

## 十五、延伸阅读
- `examples/benchmark_minimal/`：仓库自带的最小可运行示例。
- `examples/quickstart/benchmarks/csv-summary/`：文档类 benchmark 的最小注册表示例。
- `examples/benchmark_cell2location/`：四级渐进 benchmark 完整实例。
- `templates/regression_test.py`：回归测试脚本。
- `skillprism/benchmark/runner.py` / `skillprism/benchmark/metrics.py` / `skillprism/benchmark/task_spec.py`：引擎运行器、指标实现、任务契约校验。
- [`benchmark-metrics.md`](benchmark-metrics.md)：metric 机制与选型的唯一权威。
- [`data-building-decisions.md`](data-building-decisions.md)：数据构建决策速查。
- [`adding-a-benchmark-task-type.md`](adding-a-benchmark-task-type.md)：自定义任务插件教程。
- [`cell2location.md`](cell2location.md)：空间解卷积 benchmark 实战专题。
- [`benchmark-bioinformatics.md`](benchmark-bioinformatics.md)：生物信息类 Skill 的 Benchmark 设计专项指南。
- [`../tutorial/full-cycle-demo.md`](../tutorial/full-cycle-demo.md)：评估 → benchmark → 优化全链路实操，衔接各环节。
