# Build a Benchmark：逐步引导 Runbook

> 本文件是 `skills/skill-prism/SKILL.md` §2 的附属参考。复制 `skill-prism` Skill 时，应同时复制本文件。

`build-skill-test` **只把一条 benchmark 写进 `benchmarks/<skill>/registry.yaml`**。它**不**创建目录、**不**写 task spec、**不**生成/复制数据（`--generate-expected` 仅对 csv 做简单拷贝）、**不**写 `metrics.py`、**不**写执行代码。这些都要在调用前由 Agent 与用户一起准备好。

下面是可以**照抄执行**的 runbook。每步给你三块：**Agent 说**（复制给用户的话术）、**收集/判断**（这一步在要什么、怎么分支）、**落地**（复制运行的命令或写入的文件）。
全程遵循 [`AGENT_GUIDE.md`](AGENT_GUIDE.md)：写文件前先展示并获确认，不编造不安全默认。

占位符：`<skill>` 技能名，`<task>` 任务 id，`<fmt>` 格式（`csv`/`h5ad`/`markdown`/`directory`），`<id>` benchmark id。所有相对路径都相对 `benchmarks/<skill>/`。

---

**Step 0 — 定界**

Agent 说：
> "我来为 `<skill>` 建 benchmark。先确认两件事：① skill 名是 `<skill>` 吗？② benchmark 目录用 `benchmarks/<skill>/` 可以吗？确认后我建目录骨架。"

落地（用户确认后）：
```bash
mkdir -p benchmarks/<skill>/{tasks,data,expected}
```

---

**Step 1 — Task spec**

Agent 说：
> "定义任务契约。请给我：任务描述一句话、输入格式（csv/h5ad/markdown/directory）、输出格式。输入占位符我叫 `{input}`、输出叫 `{output}`，可以吗？若输出是 h5ad，要比较的标签列名是什么（设 `label_column`）？若是 csv，有哪些必需列（设 `required_columns`）？我起草后给你看完整 YAML 再写入。"

落地（确认后写 `benchmarks/<skill>/tasks/<task>.yaml`）：
```yaml
id: <task>
skill: <skill>
name: <Human name>
description: <what this task verifies>
# 仅 h5ad 需要比较标签列时加：label_column: <col>
prompt: |
  ## 角色
  <role>
  ## 任务
  <one-line task>
  ## 输入
  - 文件路径：{input}
  - 格式：<fmt>
  ## 输出要求
  - 文件路径：{output}
  - 格式：<fmt>
input:
  format: <fmt>
  path: "{input}"
output:
  format: <fmt>
  path: "{output}"
```
> 占位符 `{input}`/`{output}` 的名字自由取，但必须和 `input.path`/`output.path` 一致；引擎会把它们解析成同名全局变量注入 `--code` 脚本。

---

**Step 2 — 数据**

Agent 说：
> "准备输入数据，放 `benchmarks/<skill>/data/<level>/`。数据来源三选一：A 你已有文件（给我路径）；B 用库内置数据集（如 `scanpy.datasets.pbmc3k_processed`）；C 我写脚本合成（用 `skillprism.testing.mock_data` 或 `scripts/generate_data.py`，固定 seed 可复现）。你选哪个？规模多大？我先做成 level 0（极小，冒烟）和 level 1（小，回归）两份，生成后给你看 shape/前几行再确认。"

落地分支：
- A：`cp <user-file> benchmarks/<skill>/data/level1/`
- B：在 registry 条目用 `dataset: {source: <builtin>, type: builtin}`（Step 6 处理），此处无需落文件。
- C：写并运行 `scripts/generate_data.py`，产物落到 `data/level0/`、`data/level1/`，固定 `random_state`。

---

**Step 3 — Expected（可选，先判断）**

Agent 说：
> "这条 benchmark 要不要和『金标准』对比？"
> - 不要（只检查输出自身是否合理）→ 跳过 expected，Step 4 选自洽性 metric。
> - 要（比对一致性）→ 金标准从哪来：A 你已有文件；B 我写参考实现生成。生成后放 `benchmarks/<skill>/expected/`，并和金标准的细胞/行顺序保持一致（按位置对齐比较）。"

落地（仅"要"时）：A `cp <gold> benchmarks/<skill>/expected/`；B 写参考实现生成到 `expected/<file>`。

---

**Step 4 — Metrics**

Agent 说：
> "选指标。先复用内置，不够再写私有。我列一下当前可用内置 metric，你挑；阈值我提议默认，你确认。"

落地（发现内置）：
```bash
python -c "from skillprism.benchmark.metrics import list_metrics; print(list_metrics())"
```

落地（需私有 metric 时写 `benchmarks/<skill>/metrics.py`，随 registry 自动加载；签名固定）：
```python
from skillprism.benchmark.metrics import metric

@metric("my_metric")                 # id 供 registry 引用
def my_metric(actual_path, expected_path, task_spec):
    # 返回一个单值。无需 expected 时忽略 expected_path；需要但缺失时返回 None（判失败）。
    ...
```
> metric 是**单值判断**：函数算一个数，registry 里用 `type/threshold` 判定。自洽性指标（无 expected）：`n_clusters`、`row_count`、`has_required_columns`；一致性指标（需 expected）：`ari`、`nmi`、`mean_rmse`、私有 `*_accuracy`。

---

**Step 5 — 执行方式**

Agent 说：
> "输出由谁产出？三选一：① `--code <path>`：引擎在沙箱里执行被测代码（最适合 CI/回归）；② agent 模式：配置 `SKILLPRISM_AGENT_COMMAND`，引擎调外部 agent；③ results 模式：只评估已存在的输出（Agent 已产出结果）。你选哪个？选①的话我现在起草 `sample_skill_code.py`。"

落地（选①时写 `sample_skill_code.py`，全局变量名 = Step 1 占位符）：
```python
# 全局变量 input / output 由引擎从 task spec 占位符注入
...  # 读 input，写 output
```

---

**Step 6 — 注册（此时才调 build-skill-test）**

Agent 说：
> "我把上面收集到的值注册进 `benchmarks/<skill>/registry.yaml`。拟用 id=`<id>`、level=`<0|1|2|3>`、suite 加 `smoke` 和 `gradual`。注册命令如下，确认后我执行，并给你看生成的条目。"

落地：
```bash
build-skill-test \
  --id <id> --name "<name>" \
  --skill <skill> --task <task> \
  --task-spec tasks/<task>.yaml \
  --level <0|1|2|3> \
  --input data/<level>/... \
  `# 仅 Step 3 要金标准时加：` [--expected-path expected/<file>] \
  --metric <id:type:args> [--metric ...] \
  --suite smoke --suite gradual \
  --registry benchmarks/<skill>/registry.yaml
```
> `--metric` 的 `type`：`min`/`max`/`range`/`exact`/`tolerance`。例：`row_count:min:8`、`ari:min:0.4`、`n_clusters:range:3:12`。

---

**Step 7 — 验证**

Agent 说：
> "先跑冒烟，再跑渐进。失败我带你回到对应步骤修。"

落地：
```bash
# 冒烟
test-skill --skill <skill> --registry benchmarks/<skill>/registry.yaml --suite smoke --code <path>
# 渐进（level 0 → 1）
test-skill --skill <skill> --registry benchmarks/<skill>/registry.yaml --suite gradual --code <path>
```

---

**一页信息收集表（Agent 开场可一次性贴出，逐项打勾）**

| 项 | 谁来填 | 示例 |
|---|---|---|
| skill 名 | 用户必填 | `<skill>` |
| task id | 用户必填 | `<task>` |
| 输入/输出格式 | 用户必填 | `h5ad` → `h5ad` |
| 输入数据来源 | 用户必填 | A 文件 / B builtin / C 合成 |
| 是否对比金标准 | 用户必填 | 是 / 否 |
| metrics 与阈值 | Agent 提议，用户确认 | `ari:min:0.4` |
| level / suite | Agent 提议，用户确认 | level0+1；smoke+gradual |
| 执行方式 | 用户必填 | `--code` / agent / results |

**用户必须提供的最少信息**（Agent 不得编造不安全默认）：skill 名、task id、输入/输出格式、输入数据、是否做金标准对比、执行方式。
**Agent 可提议但须确认的默认**：level 0/1 划分、suite 名（smoke/gradual/release）、`cache_dir`、默认阈值、占位符名（`{input}`/`{output}`）。

**参数对照（收集到的答案如何映射到 `build-skill-test`）**：

| User intent clue | Parameter | Purpose |
|---|---|---|
| （直接指定） | `--id` | Benchmark 唯一 id |
| （直接指定） | `--name` | 人类可读名称 |
| （直接指定） | `--skill` | 关联的 skill 名 |
| （直接指定） | `--task` | Task id |
| "task spec 在别处" | `--task-spec <path>` | task spec 路径（相对 registry 目录，默认 `tasks/<task>.yaml`） |
| "level N" | `--level N` | 难度等级 0–3 |
| （直接指定） | `--input <path>` | 输入数据路径（相对 registry 目录） |
| "有金标准" | `--expected-path <path>` | 金标准路径（相对 registry 目录） |
| "定义指标" | `--metric id:type:args` | 指标阈值（可重复；type ∈ min/max/range/exact/tolerance） |
| "加入 smoke/gradual suite" | `--suite <name>` | 加入 suite（可重复） |
| （直接指定） | `--registry <path>` | 注册表文件（必填；约定 `benchmarks/<skill>/registry.yaml`） |
| "自动生成金标准" | `--generate-expected` | 仅对 csv 做简单拷贝 |
| "需要 GPU" | `--gpu` | 标记需要 GPU |
| "真实数据" | `--real-data` | 真实数据，completion-only |
