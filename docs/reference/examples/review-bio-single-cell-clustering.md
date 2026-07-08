# Skill 评估报告：bio-single-cell-clustering

> 评估日期：2026-06-15  
> 评估人：Kimi Code CLI（自动评估 + 人工复核）  
> 评估依据：`SKILL_EVALUATION_AND_OPTIMIZATION_FRAMEWORK.md` 中的 Rubric 体系  
> 工具：`evaluate_skill_rubric.py` + 人工领域评审 + 合成数据冒烟测试

---

## 一、总体结论

| 项目 | 结果 |
|---|---|
| **Skill 名称** | `bio-single-cell-clustering` |
| **路径** | `skills/bio-single-cell-clustering` |
| **自动化 Rubric 得分** | **88.0 / 100** |
| **人工复核后建议得分** | **87.0 / 100** |
| **等级** | **B（良好，有少量优化空间）** |
| **优先级** | 快速修补区（Quick Patch）：修复 2-3 个结构性短板即可达到 A 级 |

**一句话评价**：该 Skill 文档质量高、方法选择准确、核心代码可运行，但存在元数据字段缺失、示例不自包含、代码目录不规范等可快速修复的问题。

---

## 二、各维度详细评分

### D1 目录与元数据规范（自动 4/5 → 人工 4/5）

| 检查项 | 结果 |
|---|---|
| SKILL.md 存在 | ✅ |
| frontmatter 可解析 | ✅ |
| name 符合 kebab-case | ✅ |
| examples/ 目录存在且非空 | ✅ |
| requirements.txt 存在 | ✅ |
| usage-guide.md 存在 | ✅ |
| **frontmatter 包含 `languages` 字段** | ❌ |

**问题**：`SKILL.md` frontmatter 缺少 `languages` 字段（当前为 `name, description, tool_type, primary_tool, supported_tools, keywords`）。根据项目模板 `docs/SKILL_BUILD_GUIDE.md`，`languages` 为必需字段。

**优化建议**：
```yaml
languages: [python, r]
```

---

### D2 文档可理解性（自动 5/5 → 人工 5/5）

**优点**：
- 文档结构清晰，按 Scanpy / Seurat 分两大节。
- 每个小节包含 Goal、Approach、代码块，符合 LLM Agent 学习模式。
- 提供 Parameter Reference 表格、Method Comparison 表格、Related Skills。
- 明确标注 Louvain deprecated，推荐 Leiden，体现方法选择意识。

**可改进点**：
- 缺少独立的 "Common Pitfalls" 或 "Troubleshooting" 小节（虽然有 `deprecated` 提示，但不够系统）。
- 输入数据状态可更明确：应强调 "input must be normalized/integrated"，避免用户直接对原始 counts 跑 PCA。

---

### D3 代码正确性（自动 3/5 → 人工 3/5）

**检查项**：
- Python 示例 `examples/cluster_scanpy.py` 语法正确 ✅
- R 示例 `examples/cluster_seurat.R` 语法未检查（依赖 R 环境），但肉眼无语法错误 ✅
- Python 函数 docstring 覆盖率：示例脚本无函数封装，不适用 ⚠️

**关键问题**：
- 示例脚本依赖外部文件 `preprocessed.h5ad` / `preprocessed.rds`，不是自包含的。Agent 复制代码后无法直接运行，会报 `FileNotFoundError`。

**冒烟测试验证**：

使用 200 细胞 × 500 基因合成数据验证核心 API 调用顺序：

```python
sc.pp.scale(adata)
sc.tl.pca(adata, n_comps=20)
sc.pp.neighbors(adata, n_neighbors=10, n_pcs=10)
sc.tl.leiden(adata, resolution=0.5)
sc.tl.umap(adata)
```

**结果**：`SYNTHETIC SMOKE TEST PASSED`，聚出 2 个 clusters。

**优化建议**：
1. 在示例中改用 `sc.datasets.pbmc3k_processed()` 或提供可下载测试数据链接。
2. 或者增加一个 `minimal_self_contained_example.py`，让 Agent 能直接复制运行。

---

### D4 工具依赖可复现（自动 5/5 → 人工 5/5）

- `requirements.txt` 存在且包含版本约束。
- `SKILL.md` 中有 Version Compatibility 表格。
- 项目级 Docker 环境可用（`docker/Dockerfile-ray*`）。

**无重大问题**。

---

### D5 生物信息学准确性（自动 5/5 → 人工 4/5）

**优点**：
- 方法选择正确：PCA → neighbors → Leiden → UMAP/tSNE 是标准流程。
- 推荐 Leiden 优于 Louvain，符合当前单细胞分析最佳实践。
- 提供 resolution 范围（0.2-2.0）、n_pcs 范围（10-50）、n_neighbors 范围（10-30）。

**可改进点**：
- 缺少对输入数据状态的明确说明：应说明必须在**归一化/高变基因选择之后**运行。
- 没有讨论不同分辨率选择的生物学意义（如 0.5 vs 1.0 在真实数据中的差异）。
- References 小节存在但较简略，可补充 1-2 篇关键文献（Leiden 论文、UMAP 论文）。

**人工评分**：从 5 分调整为 4 分，留有余地。

---

### D6 LLM 可调用性（自动 5/5 → 人工 5/5）

**优点**：
- `description` 字段详细，明确说明何时使用。
- `keywords` 包含 8 个关键词，覆盖 clustering、PCA、UMAP、Leiden 等核心概念。
- 文档中有 "Complete Clustering Pipeline" 小节，便于 Agent 直接复制完整流程。

**无重大问题**。

---

### D7 性能与资源友好（自动 5/5 → 人工 4/5）

**优点**：
- 文档提到 "tSNE (slower than UMAP)"、"JackStraw (more rigorous but slow)"，有速度意识。

**可改进点**：
- 缺少针对大数据集的明确提示（如 >100k 细胞时建议降采样、使用 `sc.pp.neighbors` 的 `method='umap'` 等）。
- 没有内存警告：UMAP 在大规模数据上可能占用大量内存。
- 没有提供性能优化参数（如 `sc.tl.umap(adata, min_dist=...)` 对速度的影响）。

**人工评分**：从 5 分调整为 4 分。

---

### D8 可维护性（自动 3/5 → 人工 3/5）

**问题**：
- 代码直接放在 `examples/` 目录下，没有按规范组织到 `scripts/python/` 和 `scripts/r/`。
- 示例脚本没有函数封装，缺少 docstring。
- 没有 `CHANGELOG` 或维护者信息。

**优化建议**：
1. 创建 `scripts/python/core_analysis.py` 和 `scripts/r/core_analysis.R`，将核心逻辑封装为函数。
2. 示例脚本改为调用封装函数。
3. 添加函数 docstring。

---

## 三、优化建议汇总（按优先级排序）

| 优先级 | 维度 | 优化项 | 预计收益 |
|---|---|---|---|
| **P0** | D1 | 在 `SKILL.md` frontmatter 中补 `languages: [python, r]` | 自动化检查从 4→5，避免合规问题 |
| **P0** | D3 | 示例改为自包含（使用内置数据集或提供测试数据） | 大幅提升 Agent 一次性成功率 |
| **P1** | D8 | 按规范建立 `scripts/python/` 和 `scripts/r/`，封装核心函数 | 可维护性从 3→4/5 |
| **P1** | D5 | 明确输入数据状态要求，补充关键文献 | 提升生信准确性与可信度 |
| **P2** | D7 | 增加大数据集性能提示（降采样、内存警告） | 提升健壮性 |
| **P2** | D2 | 增加独立 "Common Pitfalls" 小节 | 提升 LLM 错误恢复能力 |

**预计修复后总分**：91-94 分，可从 B 晋升到 **A** 级。

---

## 四、修复示例

### 修复 1：补全 frontmatter

```yaml
---
name: bio-single-cell-clustering
description: ...
tool_type: mixed
primary_tool: Seurat
supported_tools: [scanpy, matplotlib, leidenalg, scikit-learn]
languages: [python, r]
keywords: ["single-cell", "clustering", "PCA", "UMAP", "tSNE", "Leiden", "Louvain", "dimensionality-reduction"]
---
```

### 修复 2：自包含最小示例

在 `examples/minimal_example.py` 中：

```python
import scanpy as sc

# Self-contained smoke test using built-in data
adata = sc.datasets.pbmc3k_processed()

sc.pp.neighbors(adata, n_neighbors=15, n_pcs=30)
sc.tl.leiden(adata, resolution=0.5)
sc.tl.umap(adata)

sc.pl.umap(adata, color='leiden')
```

### 修复 3：规范代码目录

```
bio-single-cell-clustering/
├── SKILL.md
├── usage-guide.md
├── requirements.txt
├── scripts/
│   ├── python/
│   │   └── core_analysis.py
│   └── r/
│       └── core_analysis.R
└── examples/
    ├── minimal_example.py
    ├── cluster_scanpy.py
    └── cluster_seurat.R
```

---

## 五、附录：自动化评分原始输出

```text
D1 目录与元数据规范: 4/5
D2 文档可理解性: 5/5
D3 代码正确性: 3/5
D4 工具依赖可复现: 5/5
D5 生物信息学准确性: 5/5 (自动) / 4/5 (人工复核)
D6 LLM 可调用性: 5/5
D7 性能与资源友好: 5/5 (自动) / 4/5 (人工复核)
D8 可维护性: 3/5

自动加权总分: 88.0 / 100
人工复核后建议总分: 87.0 / 100
```

---

## 六、后续行动建议

1. **立即执行 P0 修复**（frontmatter + 自包含示例），预计 10 分钟即可完成。
2. **本周内完成 P1 修复**（scripts 目录规范化）。
3. **下次 Rubric 复评时**验证修复效果，目标冲击 A 级（90+）。
