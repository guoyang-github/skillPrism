# 建考题：构建 Benchmark

Benchmark 是 skill 的「考题」：给一份输入，跑一遍 skill，用金标准（expected output）和指标（metric）判分。本文讲怎么把一套考题建出来——你要做什么、对 Agent 怎么说、得到什么、注意什么。

建出来的考题怎么跑，见 [运行考试](./05-run-benchmark.md)；只想先快速抽查看 skill 行不行，见 [快速抽查](./03-quick-verify.md)。

## 1. 为什么先有题，才有考试

考试需要标准答案，而标准答案只有懂业务的人能给——Agent 可以代写代码、造数据、算指标，但「这个结果到底对不对」只有你能拍板。反过来，打分这件事任何人（或 CI）都能立刻做：题一旦建好，之后每次改 skill、换模型、升依赖，都是一键重考。

所以建考题是全流程中**最需要你参与的一步**。前面的 [安装与配置](./01-install-and-setup.md)、静态检查（rubric，见 [rubric 参考](../reference/rubric.md)）大多是 Agent 代劳；这一步你必须亲自回答几个关键问题。好消息是，你只需回答四个问题，剩下的目录、文件、代码全由 Agent 补齐。

## 2. 四问：你回答，Agent 代劳

加载 `skills/skill-prism/SKILL.md` 后，对 Agent 说「帮我给 `<skill名>` 建一套 benchmark」，Agent 会依次问你四个问题：

| 问题 | 你要给的答案 | Agent 据此做什么 |
|---|---|---|
| ① 考什么任务 | 一句话说清核心能力，如「对 CSV 做统计摘要」 | 写 task spec：prompt 模板 + 输入输出格式 |
| ② 用什么数据 | 你给真实/已有数据，或让 Agent 造模拟数据 | 生成/整理 `data/` 下的输入文件 |
| ③ 标准答案是什么 | 你给金标准，或让 Agent 用参考实现算出来**你审核** | 生成 `expected/` 下的金标准文件 |
| ④ 怎么判分 | 选 metric 和阈值（见 §5 速查表） | 调用 `build-skill-test` 写进 registry |

四个问题可以一次性答完，例如：

```text
[user] 帮我给 csv-summary-skill 建一套 benchmark：
① 考它对 CSV 做统计摘要的能力；
② 数据你造一份 10 行 3 列的小样；
③ 金标准用 pandas.describe 算出来，生成后我先过目；
④ 判分用 row_count 至少 8 行、col_count 至少 2 列。
```

如果你只有模糊想法，只答①也可以——让 Agent 把②③④各提一个方案，你逐项确认。回答完，Agent 会建好完整目录、注册 benchmark、并跑一遍验证，然后向你报告产物清单：

```text
[agent] 已注册 benchmark `csv_summary_sales`（level 1，已加入 smoke / gradual suite）：
- task spec：benchmarks/csv-summary-skill/tasks/csv_summary.yaml
- 输入数据：data/level1/input/sales.csv（10 行 3 列，seed=42）
- 金标准：expected/level1/sales_summary.csv ← 请过目确认
- 注册表：benchmarks/csv-summary-skill/registry.yaml
下一步可以说「测一下 csv-summary-skill」。
```

产物与你手动构建完全一致。四问之外不需要你操心的：目录结构、task spec 的 YAML 字段、占位符命名、CLI 参数拼写——这些 Agent 都会按本文 §3 的约定处理。

!!! warning "标准答案的质量决定考试的意义"
    四个问题里，③最值得花时间。金标准错了，考试就在奖励错误答案。两种稳妥做法：
    - **简单任务**：用你信任的参考实现生成（如对 CSV 用 `pandas.describe()`），然后人工核对一遍输出。
    - **复杂任务**：第一批 expected 由领域专家确认；也可以先让多个模型各生成一份，人工挑选或融合出「最佳答案」。

    Agent 用参考实现算出来的金标准，**一定要你过目确认后再注册**。

## 3. 目录与文件

建好后每个 skill 一个目录，结构固定：

```text
benchmarks/<skill>/
├── registry.yaml          # 该 skill 的所有 benchmark 条目 + suites
├── tasks/
│   └── <task>.yaml        # task spec：prompt 模板 + 输入输出格式
├── data/                  # 输入数据（可按 level 分子目录）
├── expected/              # 金标准输出
└── metrics.py             # 可选：该 skill 的私有 metric
```

真实示例可对照 `examples/benchmark_minimal/benchmarks/`（`bio-single-cell-clustering`、`document-demo` 两个 skill）。

**task spec 与 registry 的分工**：

- **task spec**（`tasks/<task>.yaml`）只写任务契约：给 Agent 的 prompt、输入输出格式与路径占位符（如 `{input_csv}`、`{output_csv}`）。**不写 metric，也不写 expected**。
- **registry 条目**引用一个 task spec，并提供具体数据路径、金标准路径、metric 与阈值。同一个 task spec 可以被多条 benchmark 复用（不同 level、不同数据集）。

一份 task spec 长这样（`benchmarks/csv-summary-skill/tasks/csv_summary.yaml`）：

```yaml
id: csv_summary
skill: csv-summary-skill
name: CSV Summary
description: 验证 csv-summary-skill 能否对 CSV 做描述性统计

prompt: |
  ## 任务
  对输入 CSV 进行统计摘要分析，并将结果保存到输出路径。

  ## 输入
  - 文件路径：{input_csv}

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

占位符名（`{input_csv}` / `{output_csv}`）由你自定义，不是引擎内置魔法——只要 prompt、`input.path`、`output.path` 三处一致即可。运行时它们被替换为真实路径：registry 条目的 `input.path`（或 `dataset` 缓存路径）填入输入占位符，输出占位符指向缓存目录下的输出文件。

对应的 registry 条目（`build-skill-test` 生成，也可以手改）：

```yaml
schema_version: "2.0"            # 必填，固定 "2.0"
cache_dir: ".benchmark_cache"    # 数据缓存目录，相对 registry 目录

benchmarks:
  csv_summary_sales:
    name: "CSV Summary: Sales"
    skill: csv-summary-skill
    task: csv_summary
    level: 1
    task_spec: tasks/csv_summary.yaml      # 可省略，默认 tasks/<task>.yaml
    input:
      path: data/level1/input/sales.csv    # 相对 registry 目录
    expected:
      format: csv
      path: expected/level1/sales_summary.csv
    metrics:
      - id: row_count
        type: min
        threshold: 8
```

!!! tip "expected 可以省略"
    如果只检查输出自身的指标（如 `n_spots:exact:10`、`n_clusters:range:3:8`），不需要金标准文件，省掉 `expected` 即可。依赖 expected 的 metric（如 `mean_rmse`、`ari`）在没有 expected 时取值为 `None` → 判 FAIL，别把两者混用。

**metric 从哪来**：

- 公共 metric 已经用 `@metric("id")` 注册在 `skillprism/benchmark/metrics.py`（清单见 [metrics 参考](../reference/metrics.md)），直接用 id 引用即可。
- skill 专属的私有 metric，写在 registry 同级的 `metrics.py` 里，随 registry 自动加载：

```python
# benchmarks/<skill>/metrics.py
from skillprism.benchmark.metrics import metric

@metric("revenue_sum")
def revenue_sum(actual_path, expected_path, task_spec):
    """返回单值；无法计算时返回 None（判 FAIL）。"""
    ...
```

签名固定为 `(actual_path, expected_path, task_spec)`：`actual_path` 是本次输出路径，`expected_path` 是金标准路径（可能为 `None`）。

!!! note "引擎按 `--skill` 名字匹配"
    registry 条目里的 `skill:` 字段必须与运行时的 `--skill` 一致，引擎靠它筛选要跑的 benchmark。一个 registry 只放一个 skill 的考题，是避免串题的简单办法。

## 4. 数据决策

回答问题②「用什么数据」时，按下面的优先级选：

| 优先级 | 来源 | registry 写法 | 适用场景 |
|---|---|---|---|
| 1 | `input.path` 直接指本地文件 | `input: {path: data/...}` | 数据已经在手边，最常见 |
| 2 | builtin 数据集 | `dataset: {source: scanpy.datasets.pbmc3k_processed, type: builtin}` | 快速原型、CI，零下载维护 |
| 3 | 本地路径走 dataset | `dataset: {source: data/x.h5ad, type: local}` | 需要引擎统一注入占位符时 |
| 4 | URL 下载 | `dataset: {source: "https://...", type: url, checksum: sha256:...}` | 数据不便进 Git 时 |

`input.path` 与 `dataset` 二选一；`input.path` 给了具体路径时优先使用。所有路径都相对 registry 目录，不要写绝对路径。

!!! note "什么进 Git，什么不进"
    task spec、registry、小样合成数据、expected、生成脚本都进 Git，保证任何人可复现。大型真实数据不要提交——放 `.benchmark_cache/`（记得加进 `.gitignore`）或用 `dataset.type: url` + checksum 按需下载。

**没有现成数据？让 Agent 造。** `skillprism.testing.mock_data` 提供三个生成器，固定 `seed` 即可复现：

```python
from pathlib import Path
from skillprism.testing.mock_data import generate_table_csv, generate_anndata, generate_visium_data

# 表格任务：10 行 3 列 CSV
generate_table_csv(rows=10, cols=3, output_path=Path("benchmarks/<skill>/data/level0/input/sales.csv"), seed=42)

# 聚类任务：返回 AnnData 对象，自行 write_h5ad
adata = generate_anndata(n_obs=100, n_vars=500, n_cell_types=3, seed=42)

# 空间/去卷积任务：返回 (spatial, reference) 两个 AnnData
spatial, reference = generate_visium_data(n_spots=10, n_cells_ref=50, n_cell_types=3, seed=42)
```

**expected 用参考实现生成**（回答问题③时 Agent 的做法，生成后你要审核）：

```python
import pandas as pd
from pathlib import Path

input_path = Path("benchmarks/<skill>/data/level0/input/sales.csv")
expected_path = Path("benchmarks/<skill>/expected/level0/sales_summary.csv")
expected_path.parent.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(input_path)
df.describe().to_csv(expected_path)
```

聚类类任务的金标准同理：用固定参数跑一遍参考流程（如 scanpy 的 neighbors → leiden），把结果存成 `expected/.../adata.h5ad`。同一份参考实现可以先生成 level 0-2 的金标准，再让 skill 去逼近它。

!!! important "边界与特殊场景必须入题"
    「正常数据能跑通」不等于 skill 可靠。至少把这几类单独注册成 benchmark：
    - **空输入 / 极小输入**：如 10 spots × 3 cell types 的 tiny 数据，验证不崩溃、输出形状正确。
    - **缺失列 / 格式错误**：故意给缺列的 CSV 或缺文件的目录，用负向测试验证报错是否明确（见下）。
    - **极端分布**：某类占比极小、全零行、缺失值——验证输出仍合法（无 NaN、比例和为 1 等）。

**真实数据：只验收，不评分。** 真实数据受样本质量、批次效应影响，不适合严格阈值。标记 `real_data: true` 后只做完成性检查（completion-only）：

```yaml
c2l_level3_real_data:
  skill: bio-spatial-deconvolution-cell2location
  task: deconvolution
  level: 3
  real_data: true          # 结果中标记为真实数据，报告与基线策略区分
  requires_gpu: true       # 无 GPU 环境自动跳过
  input:
    path: data/real_visium
  metrics:
    - id: n_spots
      type: min
      threshold: 100       # 只检查「输出了合理形状的结果」
```

**负向测试：期望它失败。** 验证 skill 遇到坏输入时给出明确错误、而不是静默返回错误结果：

```yaml
clustering_missing_x_pca:
  skill: bio-single-cell-clustering
  task: clustering
  level: 0
  input:
    path: data/no_pca.h5ad
  expected_result: fail
  expected_error: "X_pca"   # 错误信息需匹配的正则（re.search）
  metrics: []
```

判定逻辑：实际产生了非空错误、且错误匹配 `expected_error` 正则 → PASS；skill 意外跑通（无错误）→ FAIL。

## 5. metric 选型速查

回答问题④「怎么判分」时，先想清楚你的需求属于哪一类，再查表选 metric：

| 需求类型 | 你想验证什么 | 常用 metric（阈值示例） |
|---|---|---|
| **单值判断** | 输出自身的形状、规模、结构 | `row_count:min:2`、`col_count:min:2`、`n_spots:exact:10`、`n_clusters:range:3:8`、`has_required_columns` |
| **与金标准对比** | 输出与 expected 的数值一致性 | `mean_rmse:max:0.45`、`min_pearson:min:0.30`、`ari:min:0.5`、`silhouette_score:min:0.10` |
| **文本相似度** | 生成文档与参考答案的重合度 | `section_overlap:min:0.6`、`token_jaccard:min:0.3`、`length_ratio:range:0.5:2.0` |

阈值类型共五种，按需选用：

| 类型 | 判定 | 写法示例 | 适用场景 |
|---|---|---|---|
| `min` | 实际值 ≥ 阈值 | `row_count:min:8` | 至少达到下界 |
| `max` | 实际值 ≤ 阈值 | `mean_rmse:max:0.45` | 误差不超过上界 |
| `range` | 实际值在区间内 | `n_clusters:range:3:8` | 带随机性的结果 |
| `exact` | 实际值完全相等 | `n_spots:exact:10` | 确定性形状检查 |
| `tolerance` | 与参考值差距 ≤ 阈值 | `correlation:tolerance:0.05` | 近似相等 |

带随机性的算法（聚类、降维）优先用 `range` / `tolerance`，别用 `exact`——同一份数据换个 seed 结果就会动。

!!! tip "文本相似度想用 ROUGE-L / BERTScore / 语义相似度？"
    `rouge_l`、`bert_score_f1`、`semantic_similarity` **不是已注册 metric**，直接写进 registry 会因取值为 `None` 而判 FAIL。需要时在 registry 同级的 `metrics.py` 里自行用 `@metric` 注册（见 §3）。选型细节、完整 metric 清单与依赖 `expected` 的标注，见 [metrics 参考](../reference/metrics.md)。

判定规则记住一条就够：**只算 registry 里声明的 metric；任一为 None 或未注册 → 该指标 FAIL；全部通过 → `_all_pass: true`。**

## 6. level 与 suite：把考题组织起来

**level 0-3：失败优先的渐进设计。** 同一套 task spec，配不同规模的数据和松紧不同的阈值，按便宜→昂贵的顺序排：

| Level | 数据 | 目标 | 典型耗时 |
|---|---|---|---|
| 0 | 最小（10 行 / 10 spots） | 冒烟：不崩溃、输出形状正确 | 秒级 |
| 1 | 小（50-100 样本） | 基本逻辑正确（小数据数值回归） | 分钟级 |
| 2 | 中（200-500 样本） | 稳定性，更严格的阈值 | 十分钟级 |
| 3 | 真实数据 | 真实世界验收（completion-only） | 小时级 / GPU |

Level 1 和 2 的区别不是代码不同，而是**数据规模和阈值松紧不同**。level 低的先跑，失败即停，修好了再往上走——完整四级实例见 `examples/benchmark_cell2location/`。

**suite：给 benchmark 分组，方便 CI 选择。** 惯例三档：

- `smoke`：只放 level 0，PR 检查用，秒级出结果；
- `gradual`：level 0 → 2 的渐进全集，日常回归用；
- `release`：加上 level 3 真实数据验收，发版前跑。

suite 定义在 registry 顶层（`build-skill-test --suite` 注册时自动写入，也可手改）：

```yaml
suites:
  smoke:
    description: 轻量快速验证（PR 检查）
    benchmarks: [csv_summary_sales]
  gradual:
    description: 失败优先的渐进验证（level 0 → 2）
    benchmarks: [csv_summary_sales, csv_summary_medium]
```

运行时用 `test-skill --suite <name>` 只跑该组（见 [运行考试](./05-run-benchmark.md)）。

**落地命令。** 数据和 expected 准备好之后，Agent 用 `build-skill-test` 写 registry：

```bash
build-skill-test \
  --id csv_summary_sales \
  --name "CSV Summary: Sales" \
  --skill csv-summary-skill \
  --task csv_summary \
  --task-spec tasks/csv_summary.yaml \
  --input data/level1/input/sales.csv \
  --expected-path expected/level1/sales_summary.csv \
  --metric row_count:min:8 \
  --metric col_count:min:2 \
  --level 1 \
  --suite smoke \
  --suite gradual \
  --registry benchmarks/csv-summary-skill/registry.yaml
```

参数全集：`--id --name --skill --task [--task-spec] --input [--expected-path] [--metric id:type:args] [--description] [--registry] [--generate-expected] [--suite] [--level 0-3] [--gpu] [--real-data]`。`--metric` 可重复；`--suite` 可重复；`--task-spec` 省略时默认 `tasks/<task>.yaml`。更完整的 CLI 说明见 [CLI 参考](../reference/cli.md)。

!!! warning "三个常见错误"
    - **不存在 `--skill-type` / `--dataset-source` 参数。** 数据来源只通过 `--input`（本地路径）给；builtin / url 数据集请手写 registry 条目。
    - **`--generate-expected` 只对 csv task 做简单复制**——把输入复制到 expected 路径，不等于正确答案。要检查统计量的任务，必须用参考实现脚本生成 expected（§2 问题③）。
    - **`build-skill-test` 只写注册表**：不建目录、不下载数据、不生成代码、不跑测试。数据与 expected 要先备好；跑考试用 `test-skill`。

## 7. 领域专项建议：以生信为例

生物信息类 skill 数据大、依赖敏感、算法带随机性，「跑通了」不等于「生物学正确」。操作建议压缩为五条：

1. **每 skill 一个 registry**：`benchmarks/<skill>/registry.yaml`，不共用全局注册表。
2. **确定性 seed 生成数据**：合成数据用脚本（`generate_anndata` / `generate_visium_data` 或自定义）固定 seed 生成，连同生成脚本一起进 Git，任何人可复现。
3. **随机性约束写进 prompt**：task spec 的 prompt 里明确要求，如「聚类使用 `random_state=42`」；阈值用 `range` / `tolerance` 而非 `exact`。
4. **四级渐进**：level 0 形状与存在性（秒级）→ 1 小数据正确性 → 2 中数据稳定性 → 3 真实数据验收。参考 `examples/benchmark_cell2location/`。
5. **真实数据不评分只验收**：`real_data: true` + 宽松 metric；需要 GPU 再加 `requires_gpu: true`，无 GPU 环境自动跳过。

另有两条环境纪律：生成金标准的参考实现依赖版本要固定（scanpy / anndata 版本变更可能让 expected 漂移），CI 里用 lockfile 锁定；金标准一旦随环境漂移，考试就失去了基准。

其他领域一句话推广：

- **文档生成类**：看结构 + 相似度——`section_overlap` 验证章节齐全，`token_jaccard` / `length_ratio` 验证内容重合与篇幅，expected 用人工精选的「最佳答案」。
- **表格处理类**：看行列指标——`row_count` / `col_count` / `has_required_columns` 验证形状，统计量类需求写私有 metric 从 actual output 计算。
- **任何领域**：边界场景（空输入、缺失列、极小规模）和负向测试（`expected_result: fail`）都适用，别只测 happy path。

完整生信案例见 [生信 benchmark 走查](../cases/bio-benchmark-walkthrough.md)、[cell2location 案例](../cases/cell2location.md)；表格类端到端流程见 [CSV 摘要全流程](../cases/csv-summary-full-cycle.md)。

## 下一步

考题建好后：

- [运行考试](./05-run-benchmark.md)：用 `test-skill` 跑考题、看结果、存基线；
- [生产循环](./08-production-loop.md)：考试进基线回归，改动 skill 后自动重考；CI 里挂 smoke / gradual suite 的做法也在其中。
