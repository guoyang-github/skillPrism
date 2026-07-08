# Benchmark 最小可运行示例

本目录展示如何为 Skill 建立按 skill 拆分的 Benchmark registry，并一键运行金标准评估。

---

## 目录结构

```
benchmark_minimal/
├── benchmarks/
│   ├── bio-single-cell-clustering/
│   │   ├── registry.yaml          # 该 skill 的 benchmark 注册表
│   │   ├── tasks/
│   │   │   └── clustering.yaml    # Task spec（无 metrics/expected）
│   │   ├── data/                  # 输入数据（或生成/下载脚本）
│   │   └── expected/              # 期望输出（金标准）
│   └── document-demo/
│       ├── registry.yaml
│       ├── tasks/
│       │   └── document.yaml
│       ├── data/
│       └── expected/
├── baselines/
│   └── bio-single-cell-clustering.yaml   # 基线结果
├── generate_expected.py           # 生成期望输出（金标准）
├── sample_skill_code.py           # bio 示例 Skill 生成代码
└── sample_document_skill_code.py  # document 示例 Skill 生成代码
```

关键变化：

- `metrics` 和 `expected` 从 task spec 中移除，完全下沉到 `registry.yaml` 的 benchmark 条目里。
- 每个 skill 拥有独立的 `benchmarks/<skill>/registry.yaml`，避免一个全局注册表无限膨胀。
- 公共 metric 计算逻辑在 `skillprism/benchmark/metrics.py` 中通过 `@metric("id")` 注册；各 registry 目录下也可以放 `metrics.py` 注册私有 metric。

---

## 使用步骤

### 1. 运行文档生成 Benchmark

```bash
cd examples/benchmark_minimal
test-skill \
  --skill document-demo \
  --registry benchmarks/document-demo/registry.yaml \
  --code sample_document_skill_code.py \
  --task document
```

### 2. 运行单细胞聚类 Benchmark

```bash
cd examples/benchmark_minimal
test-skill \
  --skill bio-single-cell-clustering \
  --registry benchmarks/bio-single-cell-clustering/registry.yaml \
  --code sample_skill_code.py \
  --task clustering
```

第一次运行会从 scanpy 下载 `pbmc3k_processed` 数据集。

### 3. 保存基线

```bash
test-skill \
  --skill bio-single-cell-clustering \
  --registry benchmarks/bio-single-cell-clustering/registry.yaml \
  --code sample_skill_code.py \
  --task clustering \
  --output baselines/bio-single-cell-clustering.yaml
```

### 4. 修改 Skill 代码后重新运行

编辑 `sample_skill_code.py` 或 `sample_document_skill_code.py`，再次运行对应命令，观察指标变化。

### 5. 回归测试

```bash
python ../../templates/regression_test.py \
    --results baselines/bio-single-cell-clustering.yaml \
    --baseline baselines/bio-single-cell-clustering.yaml
```

---

## 扩展为真实项目

1. 将 `benchmark_minimal/benchmarks/` 复制到目标项目，按 skill 创建子目录。
2. 在每个 skill 目录下创建 `registry.yaml`、`tasks/<task>.yaml`、数据和 `expected/`。
3. 若需要自定义 metric，在对应 skill 目录下添加 `metrics.py`，用 `@metric("your_metric_id")` 注册。
4. 将各 skill 目录下的 `.benchmark_cache/` 加入 `.gitignore`。
