# 跑 Benchmark：给 Skill 考试

> `test-skill` 回答一个问题：Skill 做出的结果，在客观指标上达不达标？
>
> 本篇讲「考试」的操作：选哪种执行方式、怎么跑渐进测试、结果怎么看、报错怎么排。
> 前提是 benchmark 已经建好（registry + task spec + 数据），建题流程见 [04-build-benchmark.md](./04-build-benchmark.md)。

## 先选执行方式：三种入口

运行考试前，先确定**谁产出结果**。引擎本身不生成代码、不执行任务，只负责判卷；结果由以下三种途径之一产出：

| 方式 | 怎么触发 | 谁产出结果 | 什么时候用 |
|---|---|---|---|
| **results（默认）** | 不传 `--code`、不配 `SKILLPRISM_AGENT_COMMAND`，或显式 `--results` | 结果已经躺在输出路径上（Agent / 子 Agent / CI 产物 / 手工放置） | 最常用：Agent 刚做完题，直接判卷 |
| **`--code <path>`** | 显式传一个代码文件 | 引擎在沙箱子进程里执行该代码产出结果 | 需要可重复、无人值守的执行 |
| **外部 agent** | 设置环境变量 `SKILLPRISM_AGENT_COMMAND` | 引擎调用该命令：渲染后的 prompt 走 stdin，路径走环境变量，由命令产出结果 | 接入线上 agent 做批量执行 |

优先级（从高到低）：

```text
--code  >  显式 --results  >  SKILLPRISM_AGENT_COMMAND  >  默认 results
```

即：传了 `--code` 一定走代码执行；没传 `--code` 但显式传了 `--results`，即使配了 agent 命令也强制判卷。

!!! warning "`--results` 与 `--code` 互斥"
    同时传会直接报错退出（exit code 2）：`Error: --results cannot be used with --code`。

**外部 agent 模式的接口约定**（参考实现见 `examples/editor_wrappers/agent_caller.py`）：

- 命令从 stdin 读取 task prompt；
- 从 `SKILLPRISM_INPUT_PATH` 读输入路径，把结果写到 `SKILLPRISM_OUTPUT_PATH`；
- 成功时以退出码 0 结束；
- 默认**不透传**其他环境变量（防止泄露密钥和无关配置），确需放行时用逗号名单配置 `SKILLPRISM_AGENT_PASS_THROUGH_ENV`，例如：

```bash
export SKILLPRISM_AGENT_COMMAND="python examples/editor_wrappers/agent_caller.py"
export SKILLPRISM_AGENT_PASS_THROUGH_ENV="OPENAI_API_KEY,HTTPS_PROXY"
test-skill --skill my-skill --registry benchmarks/my-skill/registry.yaml
```

## results 模式详解：引擎只判卷

默认的 results 模式最容易被误解，单独说清楚：

**你要做什么**：先把结果产出到 benchmark 的输出路径上，再跑 `test-skill`（不带 `--code`）判分。

**引擎做什么**：检查输出路径上的文件是否存在，存在就按 registry 声明的 `metrics` 逐条计算、判定阈值。引擎从不出题、不做题。

**结果从哪来**——生产者无关，以下都算数：

- 主 Agent 按 task prompt 做完任务、把结果写到输出路径；
- 一个**干净上下文的子 Agent** 按 task prompt 产出结果（推荐做法：子 Agent 看不到主会话里的讨论，相当于闭卷考试，更贴近真实使用者拿到 SKILL.md 后的表现）；
- CI 里预先生成的产物、线上 agent 回灌的结果、甚至手工放置的文件。

!!! note "输出路径怎么定"
    `benchmark.output.path`（或 `expected_output.path`）→ 相对 `cache_dir` 解析；都没配时默认 `<cache_dir>/output/<benchmark_id>/output.<ext>`。results 模式下文件不存在会报 `results mode but output not found: <path>` 并判 FAIL。

典型操作流程（Agent 场景）：

1. 对 Agent 说："用子 Agent 按这个 task prompt 做一遍，结果写到输出路径。"
2. 子 Agent 拿到的是渲染后的 prompt（占位符已替换成真实路径），独立完成并落盘。
3. 回到主会话，跑判卷命令：

```bash
test-skill --skill my-skill \
  --registry benchmarks/my-skill/registry.yaml \
  --task clustering
```

4. 看 `[PASS]` / `[FAIL]` 与指标输出，没过就按「结果解读」一节排查。

为什么要走子 Agent 而不是主 Agent 直接做：主会话里往往已经讨论过这道题的解法，主 Agent 直接做等于开卷考试，分数再好也说明不了 SKILL.md 写得清不清楚。子 Agent 只拿到 prompt 和 SKILL.md，模拟的是真实使用者。

## 对 Agent 怎么说

各场景的自然语言说法与对应命令：

| 场景 | 对 Agent 说 | 对应命令 |
|---|---|---|
| 刚做完任务，判个分 | "结果已经生成好了，跑一下 benchmark 看看达不达标" | `test-skill --skill <skill> --registry <registry>`（默认 results） |
| 让引擎亲自跑代码 | "写个脚本跑出结果，然后用 `--code` 让引擎执行并评估" | `test-skill ... --code <script.py>` |
| 配了 agent 命令但想跳过 | "别走外部 agent，直接判已有的结果" | `test-skill ... --results` |
| 快速 gate | "先快速验证一下，别跑太重的数据" | `test-skill ... --mode quick` |
| 逐级放行 | "从简单到复杂逐步测试这个 skill" | `test-skill ... --mode gradual` |
| 只跑冒烟 | "只跑 smoke 测试，看核心路径会不会崩" | `test-skill ... --suite smoke` |

跑哪些 benchmark 由 `--skill` 匹配决定：registry 中 `skill` 字段等于该名字的条目（旧字段 `skills` 列表仍兼容），可再用 `--task` / `--level` / `--suite` 收窄。

## 渐进测试：失败优先，逐级放行

计算昂贵的 Skill 不适合每次全量重跑。渐进测试把考试分成四级，从便宜到昂贵逐级放行，某级失败就立即停，不浪费后续昂贵 stage 的资源：

| Level | 数据 | 检查什么 | 成本 |
|---|---|---|---|
| 0 | 最小数据 + 边界输入 | 形状 / 存在性：会不会崩、输出格式对不对 | 秒级 |
| 1 | 小数据 | 数值回归：与 golden 输出对比 | 低 |
| 2 | 中数据 | 稳定性 / 相关性 | 中 |
| 3 | 真实数据 | **completion-only 验收**：能跑通、输出形状合理即可，不设严格相似度阈值 | 高 |

两级别外规则：

- 标了 `requires_gpu: true` 的 benchmark 在无 GPU 环境自动 `[SKIP]`（可用 `--gpu` / `--no-gpu` 覆盖自动检测）；
- 标了 `real_data: true` 的 benchmark 在对比时只看 `_all_pass` 是否为 true，不做严格数值回归。

各级的数据来自 registry 条目的 `input.path`（直接指向数据路径，优先）或 `dataset` 声明（`builtin` / `local` / `url` 三种类型，引擎按需获取）。详见 [04-build-benchmark.md](./04-build-benchmark.md)。

Level 3 的真实数据验收题长这样（注意 `real_data` / `requires_gpu` 标记和宽松的形状指标）：

```yaml
  c2l_level3_real_data:
    name: "Level 3: real Visium acceptance"
    skill: bio-spatial-deconvolution-cell2location
    task: deconvolution
    level: 3
    real_data: true
    requires_gpu: true
    input:
      path: data/real_visium
    expected:
      path: expected/real_proportions.csv
    metrics:
      - id: n_spots
        type: min
        threshold: 100
```

### 三种 mode

| mode | 行为 |
|---|---|
| `single`（默认） | 跑一次，可用 `--level 0-3` 限定只跑某一级 |
| `gradual` | 从 level 0 跑到 `--max-level`（默认 3），逐级放行、失败即停 |
| `quick` | 只跑 level 0 + 1，最便宜的完整 gate |

```bash
# 逐级放行到 level 2
test-skill --skill my-skill \
  --registry benchmarks/my-skill/registry.yaml \
  --mode gradual --max-level 2

# 快速 gate
test-skill --skill my-skill \
  --registry benchmarks/my-skill/registry.yaml \
  --mode quick
```

gradual 模式的典型输出（逐级 stage，全部通过后给出总判定）：

```text
=== Gradual stage 0: unit ===
[PASS] Level 0: tiny smoke test
=== Gradual stage 1: component ===
[PASS] Level 1: small mock regression
=== Gradual stage 2: integration ===
[PASS] Level 2: medium mock integration

Overall: PASS
```

`skill-gradual` 是 gradual 流水线的便捷封装，参数与 `test-skill --mode gradual` 基本一致（`--skill` / `--registry` / `--max-level` / `--suite` / `--code` / `--results`），产物默认落在 `artifacts/<skill>/ci/gradual`。

### 与 suite 组合

suite 在 registry 的顶层 `suites` 字段里定义，惯例名三个：

| Suite | 典型范围 | 用途 |
|---|---|---|
| `smoke` | level 0 | 最快验证，每次必过 |
| `gradual` | level 0 → 2 | 失败优先的渐进验证 |
| `release` | level 0 → 3 | 发布门控，含真实数据验收 |

`--suite` 与 `--mode` 可组合：`--suite gradual --mode gradual` 按 gradual suite 逐级跑；`--suite smoke --mode single` 只跑 smoke。

### 每级独立 baseline 与 ratchet

gradual 模式每一级有独立 baseline，落盘在 skill 源码树之外：

```text
artifacts/<skill>/ci/gradual/.baselines/<skill>/gradual_baseline_level<N>.yaml
```

（带 `--suite` 时文件名为 `gradual_baseline_level<N>_<suite>.yaml`。）

**ratchet 默认开启**：某级全部通过时，把该级结果写进该级 baseline，防止后续回退；用 `--no-ratchet` 关闭。

## 结果解读

### pass / fail 与指标输出

每个 benchmark 输出一行 `[PASS]` / `[FAIL]` 加指标字典：

```text
[PASS] PBMC 3k Clustering: {'n_clusters': 8, 'silhouette_score': 0.12, '_metric_pass': {...}, '_all_pass': True, ...}
```

- 引擎只计算 registry `metrics` 里声明的指标；
- `_metric_pass` 显示每个指标是否过阈值，`_all_pass` 是总判定；
- metric 返回 `None`（缺 expected、metric id 未注册等）→ 该指标 FAIL。**没有「缺依赖就跳过」的机制**。

### 写结果文件

`--output` 把全量结果写成文件（仅 single 模式），格式由 `--output-format` 选 `yaml` / `json` / `markdown`（默认 yaml）：

```bash
test-skill --skill my-skill \
  --registry benchmarks/my-skill/registry.yaml \
  --output ./latest/my-skill.yaml
```

产物目录默认 `artifacts/<skill>/ci/test`（`--output-dir` 可改）。

第一次跑通后，把结果另存一份当基线：

```bash
test-skill --skill my-skill \
  --registry benchmarks/my-skill/registry.yaml \
  --output ./baselines/my-skill.yaml
```

结果文件长这样（节选）：

```yaml
skill: my-skill
benchmarks:
  pbmc3k_clustering:
    n_clusters: 8
    silhouette_score: 0.12
    _metric_pass: {n_clusters: true, silhouette_score: true}
    _all_pass: true
_all_pass: true
```

### 与基线对比

改了 Skill 之后重跑并存结果，用回归脚本对比基线：

```bash
python templates/regression_test.py \
    --results ./latest/my-skill.yaml \
    --baseline ./baselines/my-skill.yaml \
    --tolerance 0.03
```

- 每个数值指标按相对变化判定：`IMPROVED` / `PASS`（容差内）/ `REGRESSION`（变差超容差）；
- 任一 `REGRESSION` → `RESULT: REJECT`，退出码 1；否则 `RESULT: ACCEPT`，退出码 0；
- 随机性强的任务（如聚类）建议 3%–5% 容差，确定性任务可用 0%。

### 常见错误排查

| 报错 / 现象 | 原因 | 怎么办 |
|---|---|---|
| `No executor available` | 非 results 模式下没传 `--code`、也没配 `SKILLPRISM_AGENT_COMMAND` | 加 `--code <path>`，或加 `--results` 判已有结果，或配置 agent 命令 |
| `results mode but output not found: <path>` | results 模式下输出路径上没有结果文件 | 先让 Agent / 子 Agent / `--code` 把结果产出到该路径，再判卷 |
| `_all_pass: false` | 某指标没过阈值；或 metric 未注册 / 缺 expected 导致值为 `None` | 看 `_metric_pass` 定位失败指标，再决定改 skill 还是改题 |
| `[SKIP] ...: requires GPU` | `requires_gpu: true` 但当前无 GPU | 换 GPU 环境跑，或 `--gpu` 强制执行 |
| `RESULT: REJECT` | 相对基线退化超容差 | 检查改动是否引入回归；确认是提升后更新基线 |

!!! tip "指标不达标先定位，再动手"
    先看 `_metric_pass` 里**哪个指标差多少**：差一点通常是阈值或随机性问题（调阈值、加容差、固定 seed）；差很多才是 Skill 本身的问题（改 SKILL.md 或示例代码）。不要没过就直接改题。

## 负向测试：期望失败的题

有些题用来验证 Skill 在坏输入下**应当报错**，而不是静默返回错误结果。在 registry 条目里加两个字段：

```yaml
benchmarks:
  clustering_missing_x_pca:
    skill: bio-single-cell-clustering
    task: clustering
    level: 0
    input:
      path: data/no_pca.h5ad
    expected_result: fail
    expected_error: "X_pca"   # 错误信息需匹配的正则，默认 .+（任意非空错误）
    metrics: []
```

判定逻辑（`_evaluate_expected_result`，用 `re.search` 匹配）：

- 运行产生了**非空** error，且 error 匹配 `expected_error` 正则 → **PASS**；
- Skill 意外跑通（没有 error）→ **FAIL**。

**对 Agent 怎么说**："加一个负向测试：输入缺 X_pca 的数据，期望 skill 报错而不是静默通过。"

## 与效果抽查的关系

考试和抽查是互补的两件事，别混用：

| | 考试（benchmark，本篇） | 抽查（test-prompts，见 [03-quick-verify.md](./03-quick-verify.md)） |
|---|---|---|
| 测什么 | 客观产出：文件对不对、指标达不达标 | 行为质量：Agent 按 SKILL.md 做事的过程是否合理 |
| 能否自动化 | 能，可进 CI 做门控 | 需要 LLM judge 或人工复核 |
| 典型频率 | 每次改动必跑（至少 smoke） | 定期复核 |

成熟项目的搭配：**smoke 每次必过**（`--suite smoke` 或 `--mode quick` 接进 CI），**抽查定期复核**（改了 prompt 或收到用户投诉时重跑）。进 CI 的完整接法见 [06-ci-integration.md](./06-ci-integration.md)。

## 下一步

- 题还没建好 → [04-build-benchmark.md](./04-build-benchmark.md)
- 指标选型拿不准 → [metrics 参考](../reference/metrics.md)
- 完整实战案例 → [csv-summary 全周期](../cases/csv-summary-full-cycle.md) / [bio benchmark 走读](../cases/bio-benchmark-walkthrough.md)
