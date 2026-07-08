# Benchmark 数据构建决策速查表

> 本文档回答三个问题：哪些 benchmark 数据可以自动生成？哪些必须手动准备？生成后的数据如何融入 skillPrism 流程？

## 核心原则

1. **输入数据尽量自动生成**（合成、builtin、公开数据集脚本）。
2. **金标准 expected 通常需要参考流程或人工判断**。
3. **真实数据永远需要外部准备**，skillPrism 只负责验收。
4. **所有数据最终都通过 `benchmarks/<skill>/registry.yaml` 注册**，由 runner 加载、由引擎评估。

## 决策总表

| 数据/资产 | 能否自动生成 | 生成方式 | 融入流程 |
|---|---|---|---|
| **Table 输入 CSV** | ✅ 可以 | 手写脚本、`build-skill-test` 直接使用本地文件 | `dataset.source` 指向 CSV 路径 |
| **Table expected** | ⚠️ 半自动 | `--generate-expected` 复制输入；真正统计量需脚本计算 | `expected_output.path` 指向 CSV |
| **Clustering 输入数据** | ✅ 可以 | `scanpy.datasets` builtin、合成脚本（`sc.datasets.blobs`） | `dataset.type: builtin` 或 `local` |
| **Clustering expected (adata.h5ad)** | ❌ 需参考流程 | 用固定参数跑 scanpy 聚类流程生成金标准 | `expected_output.path` 指向 h5ad |
| **Document prompt** | ❌ 手动 | 人工设计评估 prompt | `dataset.source` 指向 txt |
| **Document expected (best_skill.md)** | ❌ 手动 | 人工撰写或精选的“最佳答案” | `expected_output.path` 指向 md |
| **Deconvolution 合成数据** | ✅ 可以 | `skillprism.testing.mock_data.generate_visium_data()` 或自定义脚本 | 脚本生成 `input/` + `expected/` |
| **Deconvolution 真实数据** | ❌ 外部准备 | 从公开数据库或实验获取 | 标记 `real_data: true`，level 3 completion-only |
| **Level 0 边界测试输入** | ✅ 自动 | 引擎根据 task 类型自动生成空文件、单列、0 cell 等 | 输出到 `_boundary_report` |
| **Baseline 快照** | ✅ 自动 | 跑通后用 `--output baselines/<skill>.yaml` 保存 | 与后续结果做 `regression_test.py` |

## 按任务类型详细说明

### Table 任务

```yaml
benchmarks:
  csv_summary_sales:
    task: table
    dataset:
      source: data/sales/input/sales.csv
      type: local
    expected:
      format: csv
      path: expected/sales/sales_summary.csv
```

- **输入**：可以是一个小 CSV，手写即可。
- **expected**：
  - 如果只是想检查输出结构和行数，可以用 `--generate-expected` 把输入复制一份到 expected。
  - 如果要检查统计量（如 `revenue_sum >= 500`），需要写一个脚本计算正确结果作为 expected。

### Clustering 任务

```yaml
benchmarks:
  pbmc3k_clustering:
    task: clustering
    dataset:
      source: scanpy.datasets.pbmc3k_processed
      type: builtin
    expected:
      format: anndata
      path: expected/pbmc3k/adata.h5ad
```

- **输入**：优先用 `scanpy.datasets` 的 builtin 数据，零下载、零维护。
- **expected**：必须用固定参数跑一遍参考流程（neighbors → leiden → umap），把结果存为 `adata.h5ad`。
- **合成数据扩展**：用 `sc.datasets.blobs()` 批量生成不同 seed 的数据，适合 level 0/1。

### Document 任务

```yaml
benchmarks:
  skill_md_writer:
    task: document
    dataset:
      source: data/skill_md/prompt.txt
      type: local
    expected:
      format: markdown
      path: expected/skill_md/best_skill.md
```

- **输入 prompt**：人工设计，要覆盖 Skill 的核心能力。
- **expected**：人工写一份“理想答案”。这是 document benchmark 最大的手动成本。
- 技巧：可以先让多个模型/版本生成答案，人工挑选或融合出 best_skill.md。

### Deconvolution / 复杂生物信息任务

```yaml
benchmarks:
  synthetic_lymph_node_deconv:
    task: deconvolution
    dataset:
      source: data/synthetic_lymph_node/input
      type: local
    expected:
      format: csv
      path: expected/synthetic_lymph_node/proportions.csv
```

- **合成数据**：用 `skillprism.testing.mock_data.generate_visium_data()` 或自定义脚本生成 reference + spatial + 真实比例。
- **真实数据**：
  - 参考 scRNA-seq：cellxgene Census、已发表数据。
  - 空间数据：10x Genomics Visium 公开数据。
  - 金标准：如果有 matched 数据直接用；否则用固定参考实现跑一次作为 expected/基线。

## 数据融入流程的步骤

无论数据是自动生成还是手动准备，都要走以下四步：

```
1. 准备数据
   ├── input/        ← Skill 要处理的数据
   └── expected/     ← 金标准（用于对比）

2. 编写 runner.py（可选）
   └── 把 input 传给 Skill 代码，保存 output

3. 注册到 benchmarks/<skill>/registry.yaml
   ├── task                              # 对应 benchmarks/<skill>/tasks/<task>.yaml
   ├── dataset.source / type
   ├── expected.path
   └── metrics

4. 运行并保存基线
   └── test-skill --mode single → baselines/<skill>.yaml
```

## 推荐的数据来源优先级

| 优先级 | 来源 | 适用场景 |
|---|---|---|
| 1 | **builtin 数据集**（`scanpy.datasets` 等） | 快速原型、level 0/1、CI |
| 2 | **合成数据脚本** | 需要完美标签、大批量、边界 case |
| 3 | **公开数据库** | 需要真实分布、可引用 |
| 4 | **已发表论文数据** | 有金标准标签 |
| 5 | **用户/实验真实数据** | level 3 release 验收 |

## 自动化脚本模板

### 批量生成 clustering 合成数据

```python
import scanpy as sc
from pathlib import Path

out_dir = Path("benchmarks/synthetic/clustering")
out_dir.mkdir(parents=True, exist_ok=True)

for seed in range(10):
    adata = sc.datasets.blobs(n_variables=500, n_observations=1000, n_clusters=5)
    adata.obs["true_label"] = adata.obs["blobs"]
    adata.write_h5ad(out_dir / f"seed_{seed}.h5ad")
```

然后在注册表里批量注册，或用 `benchmark_factory.py` 动态生成。

### 用 build-skill-test 快速创建 table benchmark

```bash
build-skill-test \
  --id csv_summary_sales \
  --name "CSV Summary: Sales" \
  --skill csv-summary-skill \
  --task table \
  --dataset-source data/sales/input/sales.csv \
  --expected-path expected/sales/sales_summary.csv \
  --metric row_count:min:3 \
  --metric revenue_sum:min:500 \
  --generate-expected \
  --registry benchmarks/csv-summary-skill/registry.yaml
```

### 生成 clustering 金标准

```python
import scanpy as sc
from pathlib import Path

out_dir = Path("benchmarks/bio-single-cell-clustering/expected/pbmc3k")
out_dir.mkdir(parents=True, exist_ok=True)

adata = sc.datasets.pbmc3k_processed()
sc.pp.neighbors(adata, n_neighbors=15, n_pcs=30)
sc.tl.leiden(adata, resolution=0.5)
sc.tl.umap(adata)
adata.write_h5ad(out_dir / "adata.h5ad")
```

## 常见陷阱

1. **把输入直接当 expected**：`--generate-expected` 对 table 只是复制输入，不等于正确答案。
2. **金标准随环境漂移**：聚类流程的默认参数、随机种子、依赖版本都可能改变 expected，要固定。
3. **真实数据进 Git**：大文件不要提交，用 `.benchmark_cache/` 或 DVC。
4. **边界测试依赖 skill 代码**：level 0 的边界输入是自动生成的，但边界测试能不能通过取决于 Skill 代码的健壮性。

## 延伸阅读

- [Benchmark 构造指南](./benchmark-guide.md)：从零创建 table/clustering/document/deconvolution benchmark 的完整步骤。
- [cell2location 完整示例](./cell2location.md)：四级 gradual benchmark 的数据构建实战。
- [新增 Benchmark 任务类型](./adding-a-benchmark-task-type.md)：如果现有 task 类型不满足需求，如何扩展。
