# Benchmark Metrics 参考与最佳实践

> 本文回答三个常见问题：
> 1. skillPrism 里的 benchmark metric 是怎么工作的？
> 2. `expected`（金标准）文件是否必须？
> 3. 生物信息、文本、表格等不同类型的 skill 该用什么指标？

---

## 1. Metric 的本质

skillPrism 的 benchmark 不会对「两个文件」直接做通用 diff，而是：

1. 把实际输出文件路径交给一个注册的 **metric 函数**；
2. metric 函数计算出一个**单值**（这个单值可以只来自 actual，也可以来自 actual 与 expected 的对比）；
3. 再用 `metric_passes(value, spec)` 判断该值是否满足阈值。

所以 metric 是**单值判断**，但这个单值可以来自 actual 与 expected 的对比。

### 1.1 metric 注册

内置 metric 函数通过 `@metric("id")` 装饰器注册在 `skillprism/benchmark/metrics.py` 中；私有 metric 可以写在某个 registry 同级目录的 `metrics.py` 中，随 registry 一起加载。注册后，在 `registry.yaml` 的 benchmark 条目里通过 `id` 引用：

```python
from skillprism.benchmark.metrics import metric

@metric("my_metric")
def my_metric(actual_path, expected_path, task_spec):
    ...
```

当前引擎使用 `GenericEvaluator`，所有 metric 都通过同一个 evaluator 按 `id` 查表调用，不再按输出格式选择不同的 evaluator。

### 1.2 metric 的五种比较方式

```yaml
metrics:
  - id: row_count
    type: min
    threshold: 1

  - id: mean_rmse
    type: max
    threshold: 0.45

  - id: n_clusters
    type: range
    min: 3
    max: 8

  - id: pearson
    type: tolerance
    reference: 0.8
    threshold: 0.05

  - id: _all_pass
    type: exact
    expected: true
```

| type | 含义 |
|---|---|
| `min` | `value >= threshold` |
| `max` | `value <= threshold` |
| `range` | `min <= value <= max` |
| `tolerance` | `abs(value - reference) <= threshold` |
| `exact` | `value == expected` |

---

## 2. `expected` 文件是否必须？

**不是必须的。**

`registry.yaml` 中的 `expected` 字段是可选的。是否需要它，取决于你想评估什么：

| 评估目标 | 是否需要 `expected` | 典型 metric |
|---|---|---|
| 输出本身是否有效 | 否 | `n_clusters`、`n_spots`、`row_count`、`silhouette_score`、`has_required_columns` |
| 输出与金标准是否一致 | 是 | `ari`、`nmi`、`mean_rmse`、`min_pearson`、`section_overlap`、`diff_row_count` |
| 负向测试（期望失败） | 否 | `expected_result: fail` + `expected_error` |

### 2.1 不需要 expected 的例子

如果你只关心“聚类结果是否合理”，可以直接对 actual output 做单值检查：

```yaml
benchmarks:
  pbmc3k_clustering:
    skill: bio-single-cell-clustering
    task: clustering
    level: 1
    dataset:
      source: scanpy.datasets.pbmc3k_processed
      type: builtin
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

这里不需要 `expected`，因为判断的是“输出自身是否在合理范围”。

### 2.2 需要 expected 的例子

如果你关心“输出与金标准有多像”，就需要 `expected`：

```yaml
benchmarks:
  c2l_level1_small:
    skill: bio-spatial-deconvolution-cell2location
    task: deconvolution
    level: 1
    input:
      path: data/small
    expected:
      path: expected/small_proportions.csv
      format: csv
    metrics:
      - id: mean_rmse
        type: max
        threshold: 0.45
      - id: min_pearson
        type: min
        threshold: 0.30
```

### 2.3 不要把 expected 里的指标值抄进 metric

如果你的 expected 文件本质上只是几个指标值（例如 `n_spots=1000, gene_num=10000`），**不要**先写进 expected 文件再让 metric 去读取。更好的做法是：

- 直接在 `metrics` 里用 `n_spots: exact: 1000` 和 `gene_num: exact: 10000`（如果已有对应 metric）；
- 或者写一个私有 metric（如 `@metric("gene_num")`），直接读取 actual output 计算。

`expected` 应该保留给**真正的金标准输出文件**（如参考聚类标签、参考反卷积比例、参考文档），而不是作为指标值的存储容器。

---

## 3. 内置 metric 分类

### 3.1 不依赖 expected 的 metric

这些 metric 只检查 actual output 自身：

| metric id | 计算方式 | 适用输出 |
|---|---|---|
| `row_count` | CSV 行数 | CSV |
| `col_count` | CSV 列数 | CSV |
| `has_required_columns` | 是否包含必要列 | CSV |
| `n_clusters` | 聚类数 | H5AD |
| `largest_cluster_ratio` | 最大簇占比 | H5AD |
| `silhouette_score` | 轮廓系数（需要 X_pca） | H5AD |
| `n_spots` | spot 数量 | CSV（反卷积） |
| `n_cell_types` | cell type 数量 | CSV（反卷积） |

### 3.2 依赖 expected 的 metric

这些 metric 需要 `expected` 文件存在，否则返回 `None` 并判定失败：

| metric id | 计算方式 | 适用输出 |
|---|---|---|
| `diff_row_count` | `abs(actual_rows - expected_rows)` | CSV |
| `expected_diff_rows` | 同上 | CSV |
| `ari` | Adjusted Rand Index vs expected labels | H5AD |
| `nmi` | Normalized Mutual Information vs expected labels | H5AD |
| `mean_rmse` | 每 cell type 与金标准的 RMSE 均值 | CSV（反卷积） |
| `max_rmse` | 最大 RMSE | CSV（反卷积） |
| `mean_pearson` | 每 cell type Pearson 均值 | CSV（反卷积） |
| `min_pearson` | 最小 Pearson | CSV（反卷积） |
| `mean_jsd` | 平均 Jensen-Shannon divergence | CSV（反卷积） |
| `section_overlap` | expected 中的 markdown 标题有多少出现在 output 中 | Markdown |
| `token_jaccard` | 词集合 Jaccard 相似度 | Markdown |
| `length_ratio` | `len(output) / len(expected)` | Markdown |

---

## 4. 最佳实践：不同 skill 类型该用什么？

### 4.1 生物信息类 skill（单细胞、空间转录组）

**你的需求通常有两层**：

1. **输出本身要有效**：
   - 文件能打开、shape 正确；
   - 关键指标在合理范围（如 n_clusters 3–20，silhouette > 0.1）。

2. **输出与金标准一致**（需要 expected）：
   - 聚类结果与 expected labels 的 ARI / NMI；
   - 反卷积比例与 expected 的 RMSE / Pearson。

**推荐配置模板**（聚类）：

```yaml
metrics:
  # 1. 自身有效性（无需 expected）
  - id: n_clusters
    type: range
    min: 3
    max: 20
  - id: silhouette_score
    type: min
    threshold: 0.1

  # 2. 与金标准一致（需要 expected）
  - id: ari
    type: min
    threshold: 0.8
  - id: nmi
    type: min
    threshold: 0.7
```

**推荐配置模板**（反卷积）：

```yaml
metrics:
  - id: n_spots
    type: min
    threshold: 100
  - id: n_cell_types
    type: min
    threshold: 2
  - id: mean_rmse
    type: max
    threshold: 0.40
  - id: min_pearson
    type: min
    threshold: 0.30
```

### 4.2 文本 / 文档类 skill

**需求**：结构相似、语义相似、长度合理。

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
```

如果 expected 文档较长，可以加 `semantic_similarity` 或 `bert_score_f1`（需安装额外依赖）；
如果 expected 是结构模板，优先 `section_overlap`。

### 4.3 表格 / 数据转换 skill

**需求**：行列数正确、必要列存在、数值列的统计量一致。

```yaml
metrics:
  - id: row_count
    type: min
    threshold: 1
  - id: col_count
    type: min
    threshold: 2
  - id: has_required_columns
    type: exact
    expected: 1
  - id: diff_row_count
    type: exact
    expected: 0
```

如果需要更细的数值对比（如某列的 sum、mean），可以写私有 metric：

```python
from skillprism.benchmark.metrics import metric
import pandas as pd

@metric("col_mean_age")
def col_mean_age(actual_path, expected_path, task_spec):
    df = pd.read_csv(actual_path)
    return float(df["age"].mean())
```

然后在 registry 中：

```yaml
metrics:
  - id: col_mean_age
    type: tolerance
    reference: 35.0
    threshold: 1.0
```

---

## 5. 什么时候需要 custom runner / plugin task？

如果满足以下条件，用内置 metric + `GenericEvaluator` 即可：

- 对比的是单一数值指标（行数、聚类数、RMSE、Pearson、标题重叠率等）；
- 输出格式是 CSV、H5AD、Markdown 之一。

如果出现以下情况，再写 custom runner / plugin：

- 需要比较两个文件内部的复杂结构（如 JSON 嵌套字段逐项对比）；
- 需要领域特定的可视化检查（如图表、UMAP 图像对比）；
- 需要调用外部 CLI 工具（如 R 脚本、专门的生物信息学验证工具）。

---

## 6. 小结

- skillPrism 的 benchmark metric 是**单值判断**，不是通用文件 diff；
- `expected` 文件**不是必须的**，只在需要对比 actual 与金标准时才需要；
- 如果 expected 只是几个指标值，应该直接写成 metric，不要先写进 expected 文件；
- 当前引擎使用 `GenericEvaluator`，所有 metric 按 `id` 查表调用；
- 生物信息类 skill 最佳实践：一层检查输出有效性（无需 expected），一层检查与金标准的一致性（需要 expected）；
- 文本类 skill 最佳实践：结构 + 词汇 + 语义 + 长度多维评估。
