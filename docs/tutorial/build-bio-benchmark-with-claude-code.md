> 学习目标：在全新工作目录里，从零为一个生信技能 `bio-single-cell-annotation-celltypist`（CellTypist 单细胞细胞类型注释）构建一套可运行的 benchmark。同一份产物用两种方式达成：**路径 A 命令行手动构建**、**路径 B 用 Claude Code 自然语言驱动构建**。两条路径互相印证。

# 手把手：用 Claude Code 为 CellTypist 注释技能构建 Benchmark

## 0. 这份文档要解决什么问题

很多人被 benchmark 的目录结构和概念绕晕：task、metric、evaluator、registry、expected 到底谁放哪？本文用**一个具体技能、一套具体数据、一组可直接复制运行的命令**，把构建流程走通。读完你应该能：

- 说清楚 `benchmarks/<skill>/` 下每个目录/文件是干什么的；
- 用命令行**手动**把一个 skill 的 level 0 / level 1 benchmark 跑通；
- 用 **Claude Code 自然语言**让 skill-prism skill 自动完成同样的事；
- 知道什么时候需要 `expected`、什么时候需要写私有 metric、真实接入 CellTypist 时该改哪一行。

!!! tip "两条路径，同一个产物"
    路径 A（命令行）让你看清每一步在干什么；路径 B（自然语言）是日常使用的高效方式。
    它们落到**同一份** `benchmarks/bio-single-cell-annotation-celltypist/` 目录上。建议先跟路径 A 走一遍，再用路径 B 复现，体会两者的对应关系。

---

## 1. 前置准备

### 1.1 安装 skillPrism（可编辑安装）

```bash
cd /mnt/c/Users/guoyang/Desktop/TEST/Skills_Validation
pip install -e .
```

安装后会得到五个命令：`evaluate-skill`、`test-skill`、`build-skill-test`、`improve-skill`、`skill-pipeline`。验证：

```bash
test-skill --help
build-skill-test --help
```

### 1.2 把 skill-prism 装进 Claude Code（用于路径 B）

skill-prism 本身是一个「会调用 skillPrism 命令」的 Agent skill。把它复制到 Claude Code 的 skill 目录，Claude 才能用自然语言驱动它：

```bash
mkdir -p ~/.claude/skills
cp -r /mnt/c/Users/guoyang/Desktop/TEST/Skills_Validation/skills/skill-prism ~/.claude/skills/skill-prism
```

复制后，`~/.claude/skills/skill-prism/SKILL.md` 就是 Claude 的「操作手册」。它在收到「构建 benchmark」「跑一下测试」这类自然语言时，会翻译成 `build-skill-test` / `test-skill` 等命令。

### 1.3 新建一个干净的工作目录

```bash
mkdir -p /mnt/c/Users/guoyang/Desktop/TEST/skillPrism_test
cd /mnt/c/Users/guoyang/Desktop/TEST/skillPrism_test
```

本文后续所有命令都默认在 `skillPrism_test/` 下执行。

### 1.4 关于「是不是真的装 CellTypist」

本文示例**不要求**安装 CellTypist、torch 或联网下载模型。我们用一段**确定性的 mock 注释逻辑**（按 Leiden 簇映射到细胞类型名）来演示完整闭环。

> 真实接入时，把第 4 步的 `sample_skill_code.py` 里「mock 注释」那几行换成真正的 CellTypist 调用即可，**task spec、registry、metric 完全不用改**。这正是 benchmark 的价值：被测对象可以换，标尺不变。

---

## 2. 目录蓝图（最终产物长什么样）

走完后，`skillPrism_test/` 会是这样：

```text
skillPrism_test/
├── skills/
│   └── bio-single-cell-annotation-celltypist/
│       └── SKILL.md                     # 被测技能的说明书（可以是占位）
├── benchmarks/
│   └── bio-single-cell-annotation-celltypist/   # ← 一个 skill 一个 benchmark 目录
│       ├── registry.yaml                # 注册表：benchmark 条目 + metric + suite
│       ├── metrics.py                   # 私有 metric（仅本 skill 用）
│       ├── tasks/
│       │   └── cell_type_annotation.yaml  # Task spec：prompt + 输入输出契约
│       ├── data/
│       │   ├── level0/input.h5ad        # 冒烟用极小数据
│       │   └── level1/input.h5ad        # 回归用小数据
│       └── expected/
│           └── level1.h5ad              # 金标准注释（level 1 才需要）
├── scripts/
│   └── generate_data.py                 # 生成上面的 data/ 和 expected/
└── sample_skill_code.py                 # 被测代码（mock 注释逻辑）
```

记住三句话：

1. **一个 skill = `benchmarks/<skill>/` 一个目录**，里面自带 `registry.yaml`、`tasks/`、`data/`、`expected/`，不再共用一个顶层 registry。
2. **task spec 只写契约**（prompt、输入输出格式），**不写 metric、不写 expected**——metric 和 expected 写在 `registry.yaml` 的 benchmark 条目里。
3. **`expected` 不是必须的**：只有 metric 需要和「金标准」对比时才要。Level 0 只检查输出结构，不需要 expected；Level 1 要和金标准比一致性，才需要 expected。

---

## 3. 路径 A：命令行手动构建

### 步骤 A1：建目录骨架

```bash
SKILL=bio-single-cell-annotation-celltypist
mkdir -p skills/$SKILL
mkdir -p benchmarks/$SKILL/tasks
mkdir -p benchmarks/$SKILL/data/level0
mkdir -p benchmarks/$SKILL/data/level1
mkdir -p benchmarks/$SKILL/expected
mkdir -p scripts
```

### 步骤 A2：写被测技能的 SKILL.md（占位即可）

`skills/bio-single-cell-annotation-celltypist/SKILL.md`：

```markdown
---
name: bio-single-cell-annotation-celltypist
description: 对单细胞 AnnData 做细胞类型注释，输出带 obs['cell_type'] 列的 h5ad。
---

# Cell Type Annotation (CellTypist)

## 任务
读取输入 h5ad，对每个细胞预测细胞类型，写入 `obs['cell_type']`，保存到输出 h5ad。

## 输入
- h5ad 文件，已含表达矩阵 `X`。

## 输出
- h5ad 文件，`obs` 中新增字符串列 `cell_type`，细胞顺序与输入一致。
```

> 真实场景这里会写完整的 CellTypist 使用说明。本文用占位 SKILL.md，因为 benchmark 的 task spec 才是真正驱动执行的 prompt。

### 步骤 A3：写数据生成脚本 `scripts/generate_data.py`

它负责产出 `data/level0/input.h5ad`、`data/level1/input.h5ad` 以及 level 1 的金标准 `expected/level1.h5ad`。**固定 `random_state` 保证可复现。**

```python
# scripts/generate_data.py
"""Generate synthetic AnnData + gold labels for the annotation benchmark.

Design choice (documented in docs/reference/data-building-decisions.md):
- We do NOT depend on CellTypist/torch/network. We synthesize clusters and a
  deterministic cluster->cell_type mapping as the gold standard.
- Input h5ad has NO cell_type column. Gold h5ad (level 1) carries obs['cell_type'].
- Cell order (obs_names) is identical between input and gold so positional
  metrics (ARI / accuracy) line up.
"""
from pathlib import Path

import numpy as np
import scanpy as sc

SKILL = "bio-single-cell-annotation-celltypist"
ROOT = Path("benchmarks") / SKILL

# Deterministic cluster -> cell type name mapping (the "ground truth").
CLUSTER_TO_TYPE = {
    "0": "CD4 T cell",
    "1": "CD8 T cell",
    "2": "B cell",
    "3": "NK cell",
    "4": "Monocyte",
    "5": "Dendritic cell",
}


def make_dataset(n_obs: int, n_vars: int, n_clusters: int, seed: int):
    rng = np.random.default_rng(seed)
    # Random counts; leiden clustering later gives the structural labels.
    X = rng.negative_binomial(5, 0.3, size=(n_obs, n_vars)).astype(float)
    adata = sc.AnnData(X)
    adata.var_names = [f"gene_{i}" for i in range(n_vars)]
    adata.obs_names = [f"cell_{i}" for i in range(n_obs)]

    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    sc.pp.pca(adata, n_comps=min(20, n_vars - 1), random_state=seed)
    sc.pp.neighbors(adata, random_state=seed)
    sc.tl.leiden(adata, resolution=0.5, random_state=seed, key_added="leiden")

    # Keep only clusters 0..n_clusters-1 that actually appear, map to types.
    present = sorted(set(adata.obs["leiden"].astype(str)), key=int)[:n_clusters]
    adata = adata[adata.obs["leiden"].astype(str).isin(present)].copy()
    adata.obs["cell_type"] = adata.obs["leiden"].astype(str).map(CLUSTER_TO_TYPE)
    return adata


def main() -> None:
    # Level 0: tiny smoke data (input only, no gold).
    ad0 = make_dataset(n_obs=60, n_vars=200, n_clusters=3, seed=0)
    ad0_input = ad0.copy()
    del ad0_input.obs["cell_type"]            # input must NOT carry the answer
    (ROOT / "data/level0").mkdir(parents=True, exist_ok=True)
    ad0_input.write(ROOT / "data/level0/input.h5ad")

    # Level 1: small regression data (input + gold labels).
    ad1 = make_dataset(n_obs=300, n_vars=800, n_clusters=6, seed=1)
    ad1_input = ad1.copy()
    del ad1_input.obs["cell_type"]
    (ROOT / "data/level1").mkdir(parents=True, exist_ok=True)
    (ROOT / "expected").mkdir(parents=True, exist_ok=True)
    ad1_input.write(ROOT / "data/level1/input.h5ad")
    ad1.write(ROOT / "expected/level1.h5ad")  # gold: carries obs['cell_type']

    print("wrote:", ROOT / "data/level0/input.h5ad")
    print("wrote:", ROOT / "data/level1/input.h5ad")
    print("wrote:", ROOT / "expected/level1.h5ad")


if __name__ == "__main__":
    main()
```

运行：

```bash
python scripts/generate_data.py
```

!!! warning "为什么输入 h5ad 要删掉 `cell_type`？"
    输入里如果带了答案，benchmark 就失去意义。金标准 `cell_type` 只放在 `expected/level1.h5ad`。
    输入与金标准的**细胞顺序必须一致**——ARI / 准确率这类 metric 是按位置对齐比较的。

### 步骤 A4：写 Task Spec

`benchmarks/bio-single-cell-annotation-celltypist/tasks/cell_type_annotation.yaml`：

```yaml
id: cell_type_annotation
skill: bio-single-cell-annotation-celltypist
name: Cell Type Annotation
description: 对输入 h5ad 做细胞类型注释，输出带 obs['cell_type'] 的 h5ad。

# 关键：告诉内置 metric（n_clusters / ari / nmi）去读 obs['cell_type'] 这一列，
# 而不是默认的 'leiden'。这样就能复用内置 metric，不必重写。
label_column: cell_type

prompt: |
  ## 角色
  单细胞细胞类型注释助手

  ## 任务
  读取输入 h5ad，对每个细胞预测细胞类型，写入 obs['cell_type']，保存到输出 h5ad。

  ## 输入
  - 文件路径：{input_h5ad}
  - 格式：h5ad（AnnData），含表达矩阵 X；obs 中不含 cell_type。

  ## 输出要求
  - 文件路径：{output_h5ad}
  - 格式：h5ad（AnnData）
  - obs 新增字符串列 cell_type
  - 细胞顺序与输入完全一致（obs_names 不变）

  ## 约束
  - 不要改变细胞顺序，不要删除细胞。
  - 只输出结果文件，不要额外说明文字。

input:
  format: h5ad
  path: "{input_h5ad}"

output:
  format: h5ad
  path: "{output_h5ad}"
```

> 占位符 `{input_h5ad}` / `{output_h5ad}` 的名字是**自由取的**，但要和 task spec 里 `input.path` / `output.path` 一致。skillPrism 会把它们解析成同名全局变量注入到 `--code` 脚本里（见步骤 A6）。

### 步骤 A5：写私有 metric（registry 同级 `metrics.py`）

`benchmarks/bio-single-cell-annotation-celltypist/metrics.py`：

```python
"""Private metrics for the cell-type-annotation benchmark.

These are auto-loaded by skillPrism because this file sits next to registry.yaml.
GenericEvaluator dispatches every metric by id, so private @metric functions and
built-in ones (n_clusters, ari, nmi, ...) are looked up in the same registry.
"""
from pathlib import Path
from typing import Any, Dict, Optional

from skillprism.benchmark.metrics import metric


@metric("cell_type_present")
def cell_type_present(
    actual_path: Path, expected_path: Optional[Path], task_spec: Dict[str, Any]
) -> int:
    """1 if obs['cell_type'] exists and has no empty/NA values, else 0."""
    import scanpy as sc

    adata = sc.read_h5ad(actual_path)
    if "cell_type" not in adata.obs.columns:
        return 0
    s = adata.obs["cell_type"].astype(str)
    if s.isna().any() or (s.str.len() == 0).any():
        return 0
    return 1


@metric("cell_type_accuracy")
def cell_type_accuracy(
    actual_path: Path, expected_path: Optional[Path], task_spec: Dict[str, Any]
) -> Optional[float]:
    """Fraction of cells whose predicted cell_type exactly matches the gold label.

    Requires an expected h5ad with obs['cell_type']; cells are aligned by position
    (generate_data.py guarantees identical obs_names order).
    """
    if expected_path is None or not expected_path.exists():
        return None
    import numpy as np
    import scanpy as sc

    actual = sc.read_h5ad(actual_path).obs["cell_type"].astype(str).to_numpy()
    gold = sc.read_h5ad(expected_path).obs["cell_type"].astype(str).to_numpy()
    if len(actual) != len(gold) or len(gold) == 0:
        return None
    return float(np.mean(actual == gold))
```

**关键点**：

- 文件名必须是 `metrics.py`，且放在 `registry.yaml` 同一目录；skillPrism 运行时会自动加载它。
- 用 `@metric("id")` 注册；函数签名固定为 `(actual_path, expected_path, task_spec)`。
- 这里同时示范两类私有 metric：`cell_type_present`（只看 actual，无需 expected）和 `cell_type_accuracy`（需要 expected 做对比）。
- 可复用的内置 metric（如 `ari`/`nmi`/`n_clusters`）直接在 registry 里引用即可，**不必**抄进 `metrics.py`。

### 步骤 A6：写被测代码 `sample_skill_code.py`

这是「学生答卷」——benchmark 要验证的注释能力。本文用确定性 mock：复刻 generate_data 的簇→类型映射。真实接入时把 mock 段换成 CellTypist 调用。

```python
# sample_skill_code.py
# Globals `input_h5ad` and `output_h5ad` are injected by skillPrism from the
# task spec placeholders {input_h5ad} / {output_h5ad}.
import scanpy as sc

CLUSTER_TO_TYPE = {
    "0": "CD4 T cell",
    "1": "CD8 T cell",
    "2": "B cell",
    "3": "NK cell",
    "4": "Monocyte",
    "5": "Dendritic cell",
}

adata = sc.read_h5ad(input_h5ad)

# --- mock annotation: deterministic cluster -> cell type ---------------------
# (Replace this block with real CellTypist when you go live.)
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
sc.pp.pca(adata, n_comps=min(20, adata.n_vars - 1))
sc.pp.neighbors(adata)
sc.tl.leiden(adata, resolution=0.5, key_added="leiden")
adata.obs["cell_type"] = adata.obs["leiden"].astype(str).map(CLUSTER_TO_TYPE)
adata.obs["cell_type"] = adata.obs["cell_type"].fillna("Unknown")
# ---------------------------------------------------------------------------

adata.write(output_h5ad)
```

> 注意：mock 用默认 `random_state`，和金标准（seed=1）的簇划分不会完全一致——这恰好让 level 1 的 ARI/准确率落在「合理但不满分」的区间，更接近真实场景，也便于演示阈值判定。

### 步骤 A7：用 `build-skill-test` 注册 benchmark

注册 **level 0**（无需 expected，只检查输出结构）：

```bash
SKILL=bio-single-cell-annotation-celltypist
build-skill-test \
  --id ann_level0_smoke \
  --name "Level 0: annotation smoke" \
  --skill $SKILL \
  --task cell_type_annotation \
  --task-spec tasks/cell_type_annotation.yaml \
  --level 0 \
  --input data/level0/input.h5ad \
  --metric cell_type_present:exact:1 \
  --metric n_clusters:range:3:12 \
  --metric largest_cluster_ratio:max:0.6 \
  --suite smoke \
  --suite gradual \
  --registry benchmarks/$SKILL/registry.yaml
```

注册 **level 1**（需要 expected，和金标准比一致性）：

```bash
SKILL=bio-single-cell-annotation-celltypist
build-skill-test \
  --id ann_level1_small \
  --name "Level 1: annotation vs gold" \
  --skill $SKILL \
  --task cell_type_annotation \
  --task-spec tasks/cell_type_annotation.yaml \
  --level 1 \
  --input data/level1/input.h5ad \
  --expected-path expected/level1.h5ad \
  --metric cell_type_present:exact:1 \
  --metric cell_type_accuracy:min:0.6 \
  --metric ari:min:0.4 \
  --metric nmi:min:0.5 \
  --suite gradual \
  --registry benchmarks/$SKILL/registry.yaml
```

参数速记：

| 参数 | 含义 |
|---|---|
| `--task-spec` | task spec 路径，相对 registry 目录；默认 `tasks/<task>.yaml` |
| `--input` | 输入数据路径，**相对 registry 目录** |
| `--expected-path` | 金标准路径，相对 registry 目录；不需要 expected 的 level 0 省略它 |
| `--metric id:type:args` | 指标阈值；可重复。`type` 为 `min/max/range/exact/tolerance` |
| `--suite` | 加入某个 suite（可重复），便于按场景挑选 |
| `--registry` | 注册表文件，**必填**，约定 `benchmarks/<skill>/registry.yaml` |

生成的 `benchmarks/bio-single-cell-annotation-celltypist/registry.yaml` 大致如下：

```yaml
schema_version: "2.0"
cache_dir: .benchmark_cache

suites:
  smoke:
    benchmarks: [ann_level0_smoke]
  gradual:
    benchmarks: [ann_level0_smoke, ann_level1_small]

benchmarks:
  ann_level0_smoke:
    name: "Level 0: annotation smoke"
    skill: bio-single-cell-annotation-celltypist
    task: cell_type_annotation
    level: 0
    task_spec: tasks/cell_type_annotation.yaml
    input:
      path: data/level0/input.h5ad
    metrics:
      - {id: cell_type_present, type: exact, expected: 1}
      - {id: n_clusters, type: range, min: 3, max: 12}
      - {id: largest_cluster_ratio, type: max, threshold: 0.6}

  ann_level1_small:
    name: "Level 1: annotation vs gold"
    skill: bio-single-cell-annotation-celltypist
    task: cell_type_annotation
    level: 1
    task_spec: tasks/cell_type_annotation.yaml
    input:
      path: data/level1/input.h5ad
    expected:
      path: expected/level1.h5ad
      format: h5ad
    metrics:
      - {id: cell_type_present, type: exact, expected: 1}
      - {id: cell_type_accuracy, type: min, threshold: 0.6}
      - {id: ari, type: min, threshold: 0.4}
      - {id: nmi, type: min, threshold: 0.5}
```

### 步骤 A8：跑通 benchmark

只跑冒烟 suite：

```bash
SKILL=bio-single-cell-annotation-celltypist
test-skill --skill $SKILL \
  --registry benchmarks/$SKILL/registry.yaml \
  --suite smoke \
  --code sample_skill_code.py
```

跑渐进（level 0 → level 1）：

```bash
test-skill --skill $SKILL \
  --registry benchmarks/$SKILL/registry.yaml \
  --suite gradual \
  --code sample_skill_code.py
```

逐条 benchmark 跑也可以：

```bash
test-skill --skill $SKILL \
  --registry benchmarks/$SKILL/registry.yaml \
  --task cell_type_annotation \
  --code sample_skill_code.py
```

`test-skill` 做了什么：

1. 读 `registry.yaml`，按 `--skill` 过滤条目；
2. 自动加载 registry 同级的 `metrics.py`（注册私有 metric）；
3. 对每个 benchmark：解析 task spec 占位符 → 在沙箱子进程里执行 `sample_skill_code.py`（注入 `input_h5ad`/`output_h5ad` 全局变量）→ 用 `GenericEvaluator` 按 metric `id` 查表计算 → 阈值判定 PASS/FAIL；
4. 输出汇总结果（`_all_pass`）。

!!! info "路径怎么解析？"
    `--skill` 只是过滤标签，**不推导路径**。`input`、`expected`、`task_spec` 这些相对路径都相对 **registry 文件所在目录** 解析。所以 `--registry benchmarks/$SKILL/registry.yaml` 一定要指对。

### 步骤 A9（可选）：保存基线

跑通后把当前结果存为基线，便于以后对比回归：

```bash
test-skill --skill $SKILL \
  --registry benchmarks/$SKILL/registry.yaml \
  --suite gradual \
  --code sample_skill_code.py \
  --output benchmarks/$SKILL/baselines/initial.yaml
```

> 基线也是按 skill 存放：`benchmarks/<skill>/baselines/<name>.yaml`。后续改动 skill 后再跑一次，diff 这份基线即可看出回归/改进。

---

## 4. 路径 B：用 Claude Code 自然语言驱动

前置已完成：§1.2 把 `skill-prism` 复制到 `~/.claude/skills/skill-prism`。现在 `cd skillPrism_test/` 启动 Claude Code，直接用自然语言让它完成路径 A 的全部工作。

### 4.1 可直接复制的 prompt（一次性构建）

```text
在当前目录 skillPrism_test 下，为生信技能 bio-single-cell-annotation-celltypist
（CellTypist 单细胞细胞类型注释）构建完整 benchmark。要求：

1. 一个 skill 一个 benchmark 目录：benchmarks/bio-single-cell-annotation-celltypist/，
   内含 registry.yaml、tasks/cell_type_annotation.yaml、metrics.py、data/、expected/。
2. 用合成 h5ad（不要装 CellTypist/torch、不要联网）。写一个 scripts/generate_data.py
   生成 data/level0/input.h5ad、data/level1/input.h5ad，以及 level 1 的金标准
   expected/level1.h5ad（obs['cell_type']）。固定 random_state 保证可复现。
   输入 h5ad 不能带 cell_type。
3. task spec 设置 label_column: cell_type，输出 obs['cell_type']，细胞顺序与输入一致。
4. 私有 metric 写在 benchmarks/.../metrics.py：cell_type_present（结构检查）、
   cell_type_accuracy（与金标准的逐细胞一致率）。ARI/NMI 复用内置 metric。
5. 用 build-skill-test 注册两个 benchmark：
   - ann_level0_smoke（level 0，无 expected）：cell_type_present:exact:1、
     n_clusters:range:3:12、largest_cluster_ratio:max:0.6，加入 smoke 与 gradual suite。
   - ann_level1_small（level 1，有 expected）：cell_type_present:exact:1、
     cell_type_accuracy:min:0.6、ari:min:0.4、nmi:min:0.5，加入 gradual suite。
6. 写 sample_skill_code.py（确定性的簇→细胞类型 mock 映射），并用
   test-skill --suite gradual --code sample_skill_code.py 跑通，给我 PASS/FAIL 结果。
```

### 4.2 Claude 内部会做什么

加载了 `skill-prism` skill 后，Claude 收到上面这段话，会按 `~/.claude/skills/skill-prism/SKILL.md` 的意图映射执行：

```text
用户："为这个 skill 构建 level 0/1 两个 benchmark"
Claude：
  1. 读 skills/bio-single-cell-annotation-celltypist/SKILL.md（若不存在则先建占位）
  2. 设计 task spec：benchmarks/.../tasks/cell_type_annotation.yaml
  3. 写 scripts/generate_data.py 并运行，产出 data/ 与 expected/
  4. 写 benchmarks/.../metrics.py（私有 metric）
  5. 写 sample_skill_code.py（mock 注释）
  6. 调用 build-skill-test 把两个 benchmark 写进 registry.yaml
  7. 调用 test-skill --suite gradual --code ... 验证，汇报结果
```

也就是说，路径 B 本质上是 Claude 替你执行了路径 A 的每一步，产物完全一致。

### 4.3 分轮对话更稳（推荐）

一次性 prompt 信息量大，分轮更容易纠偏：

```text
第 1 轮：先只生成 scripts/generate_data.py 并跑出 data/ 和 expected/，让我确认数据。
第 2 轮：写 task spec 和私有 metrics.py。
第 3 轮：用 build-skill-test 注册 ann_level0_smoke 和 ann_level1_small。
第 4 轮：写 sample_skill_code.py 并跑 test-skill --suite gradual，汇报结果。
```

每轮结束你都可以检查中间产物（数据 shape、registry 内容），再决定是否继续。

### 4.4 常用自然语言指令对照

| 你说 | Claude 会调用 |
|---|---|
| 「加一个 level 2 的 benchmark，数据更大、阈值更严」 | `build-skill-test --level 2 ...` |
| 「把 ann_level1_small 的 ari 阈值提高到 0.6」 | 直接改 `registry.yaml` 的 metric 阈值 |
| 「只跑冒烟测试」 | `test-skill --suite smoke --code ...` |
| 「真实数据验收，只检查完成不评分」 | `build-skill-test --real-data --gpu ...` |
| 「把当前结果存成基线」 | `test-skill ... --output benchmarks/<skill>/baselines/initial.yaml` |

---

## 5. 关键概念回扣（为什么这样设计）

### 5.1 metric 是「单值判断」，不是通用 diff

skillPrism 不会「比较两个文件」。它把 actual/expected 路径交给一个 metric 函数，函数返回**一个数**，再用 `type/threshold` 判定。这个数可以只来自 actual（如 `n_clusters`），也可以来自 actual↔expected 的对比（如 `ari`、`cell_type_accuracy`）。所以：

- 想验证「输出自身是否合理」→ 不用 expected，用 `cell_type_present`、`n_clusters`、`largest_cluster_ratio`。
- 想验证「输出和金标准多一致」→ 需要 expected，用 `ari`、`nmi`、`cell_type_accuracy`。

### 5.2 公共 metric 复用，私有 metric 隔离

- **内置/公共**：`skillprism/benchmark/metrics.py` 里的 `ari`、`nmi`、`n_clusters`、`largest_cluster_ratio` 等，所有 skill 直接在 registry 引用。
- **私有**：本 skill 特有的 `cell_type_present`、`cell_type_accuracy` 写在 `benchmarks/<skill>/metrics.py`，随 registry 自动加载，不污染全局。
- `GenericEvaluator` 按 `id` 统一查表，公共和私有地位相同。

### 5.3 expected 不要当「指标容器」

如果金标准本质上只是几个数（`n_spots=1000`），**不要**写成 expected 文件再让 metric 读——直接在 registry 里 `n_spots:exact:1000`，或写个私有 metric 读 actual。`expected` 只保留给**真正的金标准输出文件**（如本例的参考注释 `expected/level1.h5ad`）。

### 5.4 渐进测试 level 0–3

| Level | 数据 | 目的 | 本例 |
|---|---|---|---|
| 0 | 极小 | 冒烟：能跑、结构对 | 60 细胞，无 expected |
| 1 | 小 | 数值回归：逻辑对 | 300 细胞，对金标准 ARI/准确率 |
| 2 | 中 | 稳定性、更严阈值 | 可自行扩展 |
| 3 | 真实 | 验收 | `--real-data --gpu`，completion-only |

---

## 6. 真实接入 CellTypist 时改什么

只改 `sample_skill_code.py` 里的 mock 段，task spec / registry / metric 全部不变：

```python
# 真实接入（需要：pip install celltypist torch，且能联网下载模型）
import celltypist
from celltypist import models

adata = sc.read_h5ad(input_h5ad)
models.download_models(force_update=False)
pred = celltypist.annotate(adata, model="Immune_All_Low.pkl", majority_voting=True)
adata.obs["cell_type"] = pred.predicted_labels["majority_voting"].astype(str)
adata.write(output_h5ad)
```

真实数据验收再加一个 level 3：

```bash
build-skill-test \
  --id ann_level3_real \
  --name "Level 3: real PBMC acceptance" \
  --skill $SKILL --task cell_type_annotation \
  --level 3 --real-data --gpu \
  --input data/real_pbmc/input.h5ad \
  --metric cell_type_present:exact:1 \
  --metric n_clusters:range:5:30 \
  --suite release \
  --registry benchmarks/$SKILL/registry.yaml
```

---

## 7. 验证清单

跑完后逐项确认：

- [ ] `benchmarks/bio-single-cell-annotation-celltypist/registry.yaml` 存在，含 `ann_level0_smoke` 与 `ann_level1_small` 两个条目。
- [ ] `tasks/cell_type_annotation.yaml` 含 `label_column: cell_type`，占位符为 `{input_h5ad}`/`{output_h5ad}`。
- [ ] `metrics.py` 与 `registry.yaml` 同级，含 `cell_type_present`、`cell_type_accuracy` 两个 `@metric`。
- [ ] `data/level0/input.h5ad`、`data/level1/input.h5ad` 的 `obs` **不含** `cell_type`；`expected/level1.h5ad` 的 `obs` **含** `cell_type`。
- [ ] `test-skill --suite smoke --code sample_skill_code.py` 全部 PASS。
- [ ] `test-skill --suite gradual --code sample_skill_code.py` 全部 PASS（level 1 的 ari/accuracy 有数值）。
- [ ] （路径 B）用自然语言复现，得到的目录与命令行产物一致。

---

## 8. 常见问题

**Q1：`test-skill` 怎么找到 benchmark？**
完全靠 `--registry` 指向的 `registry.yaml`。`--skill` 只在 registry 内做条目过滤，不推导任何路径。所以每个 skill 的 benchmark 都收敛在 `benchmarks/<skill>/` 下。

**Q2：没有 `--code` 会怎样？**
进入 results 模式：要求输出文件已经存在，否则立即失败。用于「Agent 已经产出结果，只评估」的场景。

**Q3：`cell_type_accuracy` 和金标准对不齐怎么办？**
本例靠 `generate_data.py` 保证输入与金标准 `obs_names` 顺序一致，且 `sample_skill_code.py` 不删除/重排细胞。若你的流程会重排细胞，请在 metric 里改成按 `obs_names` 对齐再比较。

**Q4：能不能一个 metric 同时被多个 benchmark 复用？**
能。metric 函数只绑定 `id`（如 `ari`），不绑定 benchmark。任何 benchmark 条目都可用同一个 `ari`，只是各自的 `input`/`expected` 不同。公共 metric 放 `skillprism/benchmark/metrics.py`，私有放 registry 同级 `metrics.py`。

---

## 9. 下一步

- 把 mock 换成真实 CellTypist，加 level 3 真实数据验收（§6）。
- 接入 CI：把 `test-skill --suite release` 做成流水线门禁，配合基线 diff 看回归。
- 接入线上闭环：参考 `docs/tutorial/agent-langfuse-production-loop.md`，把线上 Agent（Langfuse trace）的产出回流到这套 benchmark，形成「线上采集 → 本地评估 → 优化 SKILL.md → 再上线」的闭环。
