# 08 · 生产闭环：从线上任务到本地考题

> 场景：你的 Agent 已经在生产运行，调用日志沉淀在 Langfuse；skillPrism 跑在本地/CI。
> 这一篇教你把**线上真实任务**变成**本地 benchmark 考题**，形成
> **线上采集 → 本地评估 → 优化 → 回灌** 的闭环。

前置：本地已完成 [01 · 安装与初始化](./01-install-and-setup.md)，且至少完成过一次 [05 · 运行 Benchmark](./05-run-benchmark.md)。

---

## 闭环在做什么

```
线上 Agent 处理用户请求（已在生产运行）
      │
      ▼
Langfuse 记录 trace（用了哪个 skill、输入/输出）
      │
      ▼
① 挑有价值的 trace → 转成本地 benchmark 条目
      ▼
② 人工审核输入与期望输出（金标准）
      ▼
③ 本地跑考试（test-skill）
      ▼
④ 优化 skill（improve-skill），回归门禁把关
      ▼
⑤ 提交并回灌线上；下一批 trace 进来，循环继续
```

一句话：**线上日志提供「真实题目」，本地引擎负责「判分」，人负责「审核与拍板」。**

---

## 前置准备

### 1. Langfuse 凭据

把三个环境变量放进 shell 或 CI secret（不要写进仓库）：

```bash
export LANGFUSE_HOST=https://your-langfuse.com
export LANGFUSE_PUBLIC_KEY=pk-...
export LANGFUSE_SECRET_KEY=sk-...
```

并安装 SDK：

```bash
pip install langfuse
```

### 2. 转换脚本 `scripts/langfuse_to_benchmark.py`

项目自带的辅助脚本，把一条 Langfuse trace 转成 `test-skill` 能跑的 benchmark 材料：task spec、输入文件、期望文件，并在 registry 里追加条目。

```bash
python scripts/langfuse_to_benchmark.py \
  --trace-id <trace-id> \
  --registry benchmarks/<skill>/registry.yaml \
  --suite smoke
```

要求 trace 的 metadata 里带 `skill_name` 和 `task`（或 `task_id`）。可用参数：

| 参数 | 作用 |
|---|---|
| `--trace-id` | 要转换的 trace（与 `--dataset-item-id` 二选一） |
| `--dataset-item-id` | 从 Langfuse Dataset item 转换 |
| `--registry` | benchmark registry 路径（默认 `benchmark_registry.yaml`） |
| `--suite` | 加入哪个 suite，可重复 |
| `--benchmark-id` | 覆盖自动生成的 benchmark id |
| `--task` | 覆盖 task id |
| `--input-format` / `--output-format` | 强制输入/期望文件格式 |
| `--dry-run` | 只打印将要写入什么，不落盘 |

脚本会生成：

- `benchmarks/<skill>/tasks/<task>.yaml`
- `benchmarks/<skill>/data/<task>/input.<fmt>`
- `benchmarks/<skill>/expected/<task>.<fmt>`
- 在 `benchmarks/<skill>/registry.yaml` 追加 benchmark 条目

### 3. trace metadata 要求

线上 Agent 接入 Langfuse 时，在 trace metadata 里带上这几个字段，本地脚本才能工作：

| 字段 | 是否必须 | 作用 |
|---|---|---|
| `skill_name` | 必须 | 本地靠它找到对应 skill 目录 |
| `task` / `task_id` | 必须 | 决定 benchmark 条目的 task 名 |
| `skill_version` | 建议 | 对比「哪个版本的 skill 表现更好」 |

接入只需在 Agent 调用处给 trace 写 metadata，几行代码即可；已接入 Langfuse 的 Agent 改动成本很低。

---

## 步骤 ①：从 Langfuse 挑 trace 转成 benchmark

**做什么**：在 Langfuse UI 里找出有代表性的真实任务——高频请求、出过错、边界输入都是好考题。先 dry-run 预览：

```bash
python scripts/langfuse_to_benchmark.py --trace-id <trace-id> --dry-run
```

确认输入、期望、task 命名都合理后，正式转换：

```bash
python scripts/langfuse_to_benchmark.py \
  --trace-id <trace-id> \
  --registry benchmarks/<skill>/registry.yaml \
  --suite smoke
```

**得到什么**：`benchmarks/<skill>/` 下多出 task spec、输入文件、期望文件，registry 里多了一条 benchmark。

!!! tip
    如果你已经在 Langfuse 里维护评估 Dataset，也可以直接用 `--dataset-item-id` 转换 Dataset item，效果相同。

---

## 步骤 ②：人工审核输入与期望输出

**做什么**：打开刚生成的 `benchmarks/<skill>/expected/<task>.<fmt>` 和 input 文件，逐条检查：

- 输入是不是完整、可复现的真实任务；
- 期望输出是不是你**真的想锁定**的行为。

!!! warning "金标准必须人工审核"
    如果 trace 没有 expected output，脚本会把 trace 当前的 output 当作 completion-only 金标准。
    **线上输出不等于正确输出**——未经人工确认就把坏答案写成金标准，等于把错误固化进回归测试。

确认无误后再把 `benchmarks/<skill>/` 的改动提交 Git。

---

## 步骤 ③：本地跑考试

**做什么**：对更新后的 registry 跑 benchmark。按你的场景三选一（细节见 [05 · 运行 Benchmark](./05-run-benchmark.md)）：

| 场景 | 命令方式 |
|---|---|
| 已有 Agent 产出，只验证结果 | `test-skill ... --results <结果yaml>` |
| 已有生成的代码，要跑 benchmark | `test-skill ... --code <code.py>` |
| 要让外部 agent 现场生成再验证 | `test-skill ... --agent-command <命令>` |

例如验证预生成的代码：

```bash
test-skill --mode single --skill <skill> \
  --registry benchmarks/<skill>/registry.yaml \
  --code artifacts/generated_code.py
```

**得到什么**：每条 benchmark 的通过/失败与指标值；失败项就是要优化的点。

---

## 步骤 ④：优化闭环

**做什么**：对表现差的 skill 走优化循环（细节见 [06 · 优化 Skill](./06-optimize.md)）：

```bash
# 记录 baseline（第一刀之前）
improve-skill skills/<skill> --record-baseline \
  --benchmark-registry benchmarks/<skill>/registry.yaml

# 改完 SKILL.md 后 dry-run 判断保留还是回滚
improve-skill skills/<skill> --judge

# 确认后真正应用
improve-skill skills/<skill> --judge --apply
```

**得到什么**：只有分数提升的编辑被保留，其余自动回滚；优化历史写入 `artifacts/<skill>/history.jsonl`。

---

## 步骤 ⑤：回灌与回归门禁

**做什么**：

1. 提交 `skills/<skill>` 与 `benchmarks/<skill>` 的改动，部署回线上 Agent（Git push 触发部署，或管理后台重载 skill）；
2. 在 CI 里钉住质量门禁，防止下次回退——命令与 GitHub Actions 配置见 [07 · 质量报告与 CI](./07-report-and-ci.md)。

关键门禁（来自 07）：

```bash
# 静态门禁：默认不调 LLM，任何红灯即 fail
skill-ci --skill <skill>

# 回归即 fail CI；baseline 只在全过后由 --ratchet 刷新
skill-ci --skill <skill> \
  --run-benchmark --code code.py \
  --registry benchmarks/<skill>/registry.yaml \
  --ratchet
```

**得到什么**：优化后的 skill 上线，同时 baseline 前进一格——棘轮保证质量只能前进不能后退。

---

## 批量与定时采集

单条 trace 用上面的命令即可。要把采集变成例行工作，写一个批量脚本：从 Langfuse 拉最近一段时间内带 `skill_name` metadata 的 trace，逐条调用转换逻辑。骨架如下（按 Langfuse Python SDK v3 编写，v2 写法略有差异）：

```python
from datetime import datetime, timedelta
from langfuse import Langfuse

langfuse = Langfuse()  # 读取 LANGFUSE_HOST / PUBLIC_KEY / SECRET_KEY

traces = langfuse.fetch_traces(
    limit=100,
    from_timestamp=datetime.utcnow() - timedelta(hours=24),
    to_timestamp=datetime.utcnow(),
)

for trace in traces.data:
    meta = trace.metadata or {}
    if not meta.get("skill_name") or not trace.input:
        continue
    # 对每条 trace 调用 scripts/langfuse_to_benchmark.py 的同等逻辑，
    # 或直接用 subprocess 调用该脚本
    print("candidate:", trace.id, meta["skill_name"])
```

用 GitHub Actions 定时跑（每天凌晨采集一次，生成候选题供人工审核）：

```yaml
name: Langfuse Skill Sync
on:
  schedule:
    - cron: '0 2 * * *'   # 每天凌晨 2 点
  workflow_dispatch:       # 也支持手动触发
jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install
        run: |
          pip install -e ".[dev]"
          pip install langfuse
      - name: Collect candidate benchmarks
        env:
          LANGFUSE_HOST: ${{ secrets.LANGFUSE_HOST }}
          LANGFUSE_PUBLIC_KEY: ${{ secrets.LANGFUSE_PUBLIC_KEY }}
          LANGFUSE_SECRET_KEY: ${{ secrets.LANGFUSE_SECRET_KEY }}
        run: python scripts/langfuse_collect_candidates.py  # 你的批量采集脚本
      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: langfuse-sync-report
          path: artifacts/
```

!!! tip
    定时采集只负责**生成候选**，不要让它自动提交 benchmark——候选必须经过步骤 ② 的人工审核才能进 registry。

### 可选：把评估结果回写 Langfuse

同步脚本里可以用 SDK 把判定结果作为 score 写回对应 trace，在 Langfuse UI 里直接看到「这次线上调用按本地标准是否通过」：

```python
langfuse.score(trace_id=trace.id, name="skillprism_test_pass", value=1)  # 或 0
```

这一步纯锦上添花：不回写，闭环照样成立。

---

## 注意事项

!!! danger "隐私与数据脱敏"
    - 转换下来的输入/期望文件可能含用户隐私或机密数据，落盘前在 Agent 端或转换后**手动脱敏**；
    - `artifacts/` 默认已被 `.gitignore` 忽略，不要把含原始用户数据的中间产物提交 Git；
    - `LANGFUSE_*` 凭据一律走环境变量 / CI secret，不硬编码、不入库。

- **金标准必须人工审核**（见步骤 ②）：自动生成的 expected 只是初稿。
- **定期补题**：线上任务分布会变化。建议周期性（如每周）回顾 Langfuse 里的新失败案例与高频新场景，重复步骤 ①② 把考题库补上，benchmark 才始终代表「现在的线上」。
- **版本可追溯**：每次改 SKILL.md 都提交 Git；trace metadata 里带 `skill_version`（如 commit sha），方便事后对比「哪个版本表现更好」。

## 常见问题

**Q：Langfuse 挂了，skillPrism 还能用吗？**
能。skillPrism 完全本地运行，Langfuse 只是数据来源；新考题采集会暂停，已转好的 benchmark 照常跑。

**Q：线上 Agent 必须改代码才能接入吗？**
只需要在 trace 上写 `skill_name` / `task` metadata。已接入 Langfuse 的 Agent 通常只需几行代码。

**Q：一个 skill 可以对应多个 task 吗？**
可以。不同 trace 带不同的 `task` / `task_id`，本地按 task 生成多条 benchmark 即可。

---

## 相关阅读

- [05 · 运行 Benchmark](./05-run-benchmark.md)：benchmark 的三种跑法与渐进测试
- [06 · 优化 Skill](./06-optimize.md)：improve-skill 的完整优化循环
- [07 · 质量报告与 CI](./07-report-and-ci.md)：pipeline 报告、棘轮与 CI 门禁
