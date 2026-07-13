# 手把手：用 Langfuse + skillPrism 搭建线上 Skill 同步评估优化闭环

> 目标：把「线上 Agent 的真实任务轨迹」自动同步到本地 skillPrism，评估完再把优化建议反馈给 Agent，形成持续迭代的闭环。
>
> 读完本文你能做到：
> - 理解闭环里每个组件是干嘛的；
> - 把线上 Agent 的轨迹接入 Langfuse；
> - 写一条同步脚本，把 Langfuse 上的任务拉回本地跑 skillPrism；
> - 把评估结果变成下一轮 Skill 改动的输入；
> - 安全、可回滚地更新线上 Skill。

---

## 重要概念（用大白话解释）

| 概念 | 它是什么 | 在闭环里扮演的角色 |
|---|---|---|
| **skillPrism（本地引擎）** | 你电脑/CI 里的 Python 包。只做客观测量：9 维 Rubric 评分、benchmark 跑分、回归判断、保留/回滚。 | 闭环的「裁判」：不直接改 Skill，只告诉你改得好不好。 |
| **Langfuse** | 线上可观测平台。记录 Agent 每次调用用了什么 Skill、输入/输出、延迟、成本、人类反馈。 | 闭环的「数据集散地」：线上轨迹在这里汇总，再被本地拉走评估。 |
| **线上 Agent** | 生产环境里回答用户问题的 Agent。它读取 `skills/xxx/SKILL.md` 来决定怎么做事。 | 闭环的「运动员」：按 Skill 行动，产生真实轨迹。 |
| **Skill 仓库** | 一个 Git 仓库，里面每个子目录是一个 Skill，核心文件是 `SKILL.md`。 | 闭环的「单一真相源」：Agent 从这里读 Skill，skillPrism 也评估这里的 Skill。 |
| **Trace（轨迹）** | Langfuse 里的一条记录，对应 Agent 处理的一次用户请求。 | 闭环的「原材料」：一次真实任务 = 一次潜在评估样本。 |
| **Dataset（数据集）** | Langfuse 里的一类数据，通常放「输入 + 期望输出」。 | 闭环的「测试用例池」：skillPrism 的 benchmark 可以对照 Dataset 跑。 |
| **Ratchet（棘轮）** | skillPrism 的机制：新版本的分数不能低于历史最好分数。 | 闭环的「保险丝」：防止越优化越差。 |
| **Dry-run / Apply** | skillPrism 默认只看不改（dry-run），必须加 `--apply` 才会真正回滚或保留修改。 | 闭环的「人工确认点」：Agent/人先审稿，再决定要不要应用。 |

**核心原则再强调一遍**：
- skillPrism 不调用 LLM，只做测量；
- Skill 的编辑权在线上 Agent 或人手里，skillPrism 只给反馈；
- 线上数据下来后要在本地/内网处理，避免把用户隐私送出去。

---

## 闭环总览

```
线上 Agent 处理用户请求
       │
       ▼
Langfuse 记录 Trace（用了哪个 Skill、输入输出、结果）
       │
       │  定时/触发拉取
       ▼
本地同步脚本：把 Trace → 转成 skillPrism 输入
       │
       ▼
本地 skillPrism：evaluate + test + judge
       │
       ▼
生成报告：分数变化、最弱维度、是否 regress、优化建议
       │
       ▼
人 / Agent 编辑 SKILL.md
       │
       ▼
提交 Skill 仓库 → 部署到线上 Agent
       │
       ▼
下一批真实 Trace 进来，循环继续
```

---

## 前置条件

1. **本地已装好 skillPrism**
   ```bash
   cd /path/to/Skills_Validation
   pip install -e ".[dev]"
   ```
   确认命令可用：
   ```bash
   evaluate-skill --help
   test-skill --help
   improve-skill --help
   ```

2. **有一个 Langfuse 实例**
   - 可以是 [Langfuse Cloud](https://cloud.langfuse.com)（公网）；
   - 也可以自建（推荐生产用，数据不出内网）。
   拿到：
   - `LANGFUSE_HOST`
   - `LANGFUSE_PUBLIC_KEY`
   - `LANGFUSE_SECRET_KEY`

3. **线上 Agent 已接入 Langfuse**
   通常用对应语言的 SDK，例如 Python：
   ```python
   from langfuse import Langfuse

   langfuse = Langfuse(
       public_key="pk-...",
       secret_key="sk-...",
       host="https://your-langfuse.com",
   )
   ```

4. **Skill 仓库能被本地和线上同时访问**
   - 推荐用一个私有 Git 仓库（GitHub/GitLab/自托管）；
   - 线上 Agent 启动时从仓库拉最新 Skill；
   - 本地 skillPrism 也 clone 同一份仓库。

---

## 第一步：让 Langfuse 知道「这次调用用了哪个 Skill」

这一步最关键。如果 Trace 里没有 Skill 名字，本地就不知道该用哪个 Skill 来评估。

### 在 Agent 代码里给 Trace 打标签

以 Python 为例，在调用 Agent 的地方加 `metadata`：

```python
from langfuse.decorators import observe

@observe(as_type="generation")
def agent_run(user_input: str, skill_name: str):
    # 你的 Agent 逻辑
    response = my_agent.run(user_input, skill=skill_name)

    # 关键：把 Skill 信息写到当前 trace 的 metadata 里
    langfuse_context.update_current_trace(
        metadata={
            "skill_name": skill_name,          # 例如 "bio-single-cell-clustering"
            "skill_version": "v1.2.3",         # 可选：git tag / commit
            "skill_path": f"skills/{skill_name}",
            "task_type": "user_request",       # 可选：区分用户任务类型
        }
    )
    return response
```

如果你用其他语言（JS/TS），思路一样：在 trace 或 span 的 metadata 里塞 `skill_name`。

### 哪些字段建议带上？

| 字段 | 作用 |
|---|---|
| `skill_name` | **必须**。本地靠它找到对应 Skill 目录。 |
| `skill_version` | 可选。用来对比「哪个版本的 Skill 表现更好」。 |
| `task_type` / `task_id` | 可选。用来过滤哪些 Trace 值得评估。 |
| `output_path` | 可选。如果 Agent 生成了文件（如代码、报告），把相对路径写这里，本地可以拉下来跑 benchmark。 |

---

## 第二步：在 Langfuse 里建立「评估 Dataset」

skillPrism 需要知道「这次任务应该产出什么」。你可以把高价值的用户请求整理成 Dataset。

### 手动创建 Dataset（起步阶段）

1. 打开 Langfuse UI → 进入你的 Project。
2. 左侧菜单选 **Datasets** → **New dataset**。
3. 命名：`skill:<skill-name>:eval`（例如 `skill:bio-single-cell-clustering:eval`）。
4. 添加 item：
   - **Input**：用户原始请求（尽量完整）。
   - **Expected output**：你期望 Agent 产出的行为描述或金标准文件路径。
   - **Metadata**：`{"task_id": "xxx", "skill_name": "bio-single-cell-clustering"}`。

### 自动从线上 Trace 生成 Dataset（成熟阶段）

写一个小脚本，把满足条件的 Trace 转成 Dataset item：

```python
# scripts/trace_to_dataset.py
from langfuse import Langfuse
from datetime import datetime, timedelta

langfuse = Langfuse()

# 拉过去 24 小时、有 skill_name 的 trace
traces = langfuse.fetch_traces(
    limit=100,
    from_timestamp=datetime.utcnow() - timedelta(days=1),
    to_timestamp=datetime.utcnow(),
)

for trace in traces.data:
    skill = trace.metadata.get("skill_name") if trace.metadata else None
    if not skill:
        continue

    # 只把有明确输入、且结果看起来值得评估的 trace 放进去
    if trace.input:
        langfuse.create_dataset_item(
            dataset_name=f"skill:{skill}:eval",
            input=trace.input,
            expected_output="",  # 第一次可以空，后续人工补
            metadata={
                "trace_id": trace.id,
                "skill_version": trace.metadata.get("skill_version", "unknown"),
            },
        )
```

### 从 Langfuse trace 自动生成 benchmark（推荐）

项目提供了一个辅助脚本，能把一条 trace 直接转成 `build-skill-test` 需要的 registry 条目、task spec 和 input/expected 文件：

```bash
export LANGFUSE_HOST=https://your-langfuse.com
export LANGFUSE_PUBLIC_KEY=pk-...
export LANGFUSE_SECRET_KEY=sk-...

python scripts/langfuse_to_benchmark.py \
  --trace-id <trace-id> \
  --registry benchmarks/<skill>/registry.yaml \
  --suite smoke
```

要求 trace 的 metadata 里必须有 `skill_name` 和 `task`（或 `task_id`）。脚本会生成：

- `benchmarks/<skill>/tasks/<task>.yaml`
- `benchmarks/<skill>/data/<task>/input.<fmt>`
- `benchmarks/<skill>/expected/<task>.<fmt>`
- 在 `benchmarks/<skill>/registry.yaml` 里追加 benchmark 条目

> 如果没有 `expected_output`，脚本会把 trace 的当前 `output` 作为 completion-only 金标准。**生成后务必人工复核 expected 文件**，确认它真的是你想要锁定的行为。

也可以用 `--dry-run` 预览会生成什么：

```bash
python scripts/langfuse_to_benchmark.py --trace-id <trace-id> --dry-run
```

---

## 第三步：写本地同步评估脚本

这是闭环的心脏。脚本做三件事：
1. 从 Langfuse 拉最近一批 Trace / Dataset item；
2. 把它们转成 skillPrism 能跑的输入（代码、任务文件、输出文件）；
3. 调用 skillPrism 评估，生成报告。

### 推荐脚本位置

在你的 Skill 仓库或 skillPrism 仓库里新建：

```
scripts/
  langfuse_sync_eval.py
```

### 最小可用版本

> **SDK 版本说明**：以下脚本按 **Langfuse Python SDK v3** 编写（`langfuse.fetch_traces()`）。
> 如果你仍在 v2，对应写法是 `langfuse.client.trace.list(...)`；`create_dataset_item`、
> `score` 等调用在两个大版本间也有差异，请按你安装的版本查阅 SDK 文档。

```python
#!/usr/bin/env python3
"""从 Langfuse 拉线上 Trace，调用本地 skillPrism 评估 Skill。"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from langfuse import Langfuse

# ----------------------------- 配置区 ----------------------------- #
LANGFUSE_HOST = os.environ["LANGFUSE_HOST"]
LANGFUSE_PUBLIC_KEY = os.environ["LANGFUSE_PUBLIC_KEY"]
LANGFUSE_SECRET_KEY = os.environ["LANGFUSE_SECRET_KEY"]

SKILLS_DIR = Path(os.environ.get("SKILLPRISM_SKILLS_DIR", "./skills"))
# 注意：registry 现在是 per-skill 的，这里用 {skill} 作为占位符，由 run_test_skill 注入。
BENCHMARK_REGISTRY_TEMPLATE = os.environ.get("SKILLPRISM_BENCHMARK_REGISTRY", "benchmarks/{skill}/registry.yaml")
OUTPUT_DIR = Path(os.environ.get("SKILLPRISM_OUTPUT_DIR", "./artifacts/langfuse-sync"))

# 多久拉一次 trace
LOOKBACK_HOURS = int(os.environ.get("SKILLPRISM_LOOKBACK_HOURS", "24"))

# 只评估这些 skill（空列表表示全量）
SKILL_FILTER = os.environ.get("SKILLPRISM_SKILL_FILTER", "").split(",")
SKILL_FILTER = [s.strip() for s in SKILL_FILTER if s.strip()]


# ----------------------------- 工具函数 ----------------------------- #

def get_langfuse_client() -> Langfuse:
    return Langfuse(
        public_key=LANGFUSE_PUBLIC_KEY,
        secret_key=LANGFUSE_SECRET_KEY,
        host=LANGFUSE_HOST,
    )


def fetch_recent_traces(client: Langfuse) -> List[Dict[str, Any]]:
    """拉取最近 N 小时带有 skill_name 的 trace。"""
    since = datetime.utcnow() - timedelta(hours=LOOKBACK_HOURS)
    traces = client.fetch_traces(
        limit=100,
        from_timestamp=since,
        to_timestamp=datetime.utcnow(),
    )

    results: List[Dict[str, Any]] = []
    for trace in traces.data:
        meta = trace.metadata or {}
        skill_name = meta.get("skill_name")
        if not skill_name:
            continue
        if SKILL_FILTER and skill_name not in SKILL_FILTER:
            continue
        results.append({
            "trace_id": trace.id,
            "skill_name": skill_name,
            "skill_version": meta.get("skill_version", "unknown"),
            "input": trace.input,
            "output": trace.output,
            "metadata": meta,
        })
    return results


def materialize_trace_output(trace: Dict[str, Any], workdir: Path) -> Optional[Path]:
    """把 Trace 的输出落地成文件，供 skillPrism benchmark 使用。

    如果 Agent 生成的是代码，建议把代码写到 workdir；
    如果生成的是文本/文件路径，这里按实际情况扩展。
    """
    output = trace.get("output")
    if not output:
        return None

    # 示例：假设 Agent 输出的是 Python 代码块
    code_path = workdir / "generated_code.py"
    code_path.write_text(str(output), encoding="utf-8")
    return code_path


def run_evaluate_skill(skill_path: Path) -> Dict[str, Any]:
    """跑 Rubric 评估，返回 JSON 结果。"""
    cmd = [
        "evaluate-skill",
        str(skill_path),
        "--detailed",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "command": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def run_test_skill(skill_name: str, code_path: Optional[Path]) -> Dict[str, Any]:
    """跑 benchmark。"""
    registry_path = BENCHMARK_REGISTRY_TEMPLATE.format(skill=skill_name)
    cmd = [
        "test-skill",
        "--mode", "single",
        "--skill", skill_name,
        "--registry", registry_path,
    ]
    if code_path:
        cmd.extend(["--code", str(code_path)])
    else:
        cmd.append("--results")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "command": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def main() -> int:
    client = get_langfuse_client()
    traces = fetch_recent_traces(client)
    print(f"拉取到 {len(traces)} 条带 skill_name 的 trace")

    if not traces:
        print("没有需要评估的 trace，退出")
        return 0

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary: List[Dict[str, Any]] = []

    for trace in traces:
        skill_name = trace["skill_name"]
        skill_path = SKILLS_DIR / skill_name
        if not skill_path.is_dir():
            print(f"跳过：本地找不到 Skill 目录 {skill_path}")
            continue

        workdir = OUTPUT_DIR / skill_name / trace["trace_id"]
        workdir.mkdir(parents=True, exist_ok=True)

        # 1. 把 trace 输出落地
        code_path = materialize_trace_output(trace, workdir)

        # 2. Rubric 评估
        rubric_result = run_evaluate_skill(skill_path)

        # 3. Benchmark / 验证
        test_result = run_test_skill(skill_name, code_path)

        record = {
            "trace_id": trace["trace_id"],
            "skill_name": skill_name,
            "skill_version": trace["skill_version"],
            "rubric": rubric_result,
            "test": test_result,
            "workdir": str(workdir),
        }
        summary.append(record)

        # 把结果写回 Langfuse（可选）
        # 这里示例只把 returncode 作为 observation 写回
        client.score(
            trace_id=trace["trace_id"],
            name="skillprism_rubric_pass",
            value=1 if rubric_result["returncode"] == 0 else 0,
        )
        client.score(
            trace_id=trace["trace_id"],
            name="skillprism_test_pass",
            value=1 if test_result["returncode"] == 0 else 0,
        )

    # 4. 生成总报告
    report_path = OUTPUT_DIR / f"report_{datetime.utcnow():%Y%m%d_%H%M%S}.json"
    report_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n报告已保存：{report_path}")

    # 5. 如果有失败，返回非 0（方便 CI/定时任务告警）
    any_fail = any(
        r["rubric"]["returncode"] != 0 or r["test"]["returncode"] != 0
        for r in summary
    )
    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### 运行前准备

```bash
export LANGFUSE_HOST="https://your-langfuse.com"
export LANGFUSE_PUBLIC_KEY="pk-..."
export LANGFUSE_SECRET_KEY="sk-..."
export SKILLPRISM_SKILLS_DIR="./skills"
export SKILLPRISM_BENCHMARK_REGISTRY="benchmarks/{skill}/registry.yaml"

pip install langfuse
python scripts/langfuse_sync_eval.py
```

---

## 第四步：把评估结果变成优化动作

同步脚本跑完后，你有两种做法：

### 做法 A：人工 review（推荐起步）

1. 看报告 `artifacts/langfuse-sync/report_xxx.json`；
2. 对分数低的 Skill，先记录 baseline：
   ```bash
   improve-skill skills/<skill-name> --record-baseline
   ```
3. 让 Agent 或人编辑 `skills/<skill-name>/SKILL.md`；
4. 本地 dry-run 评估改动：
   ```bash
   improve-skill skills/<skill-name> --judge
   ```
5. 如果决定保留：
   ```bash
   improve-skill skills/<skill-name> --judge --apply
   ```
6. 提交 Git，部署到线上 Agent。

### 做法 B：自动优化（需要配置 editor）

如果你已经配置了外部 editor 命令（例如一个调用 LLM 的脚本）：

```bash
export SKILLPRISM_EDITOR_COMMAND="python scripts/my_skill_editor.py"

improve-skill skills/<skill-name> \
  --record-baseline \
  --benchmark-registry benchmarks/<skill-name>/registry.yaml

improve-skill skills/<skill-name> \
  --auto-edit --apply --max-rounds 3 \
  --benchmark-registry benchmarks/<skill-name>/registry.yaml
```

这会自动：
- 评估当前 Skill；
- 找最弱维度；
- 调用 editor 改 SKILL.md；
- 再评估；
- 分数提升就保留，否则回滚。

**注意**：`--auto-edit --apply` 会真的改文件。生产环境建议先不加 `--apply`，看一轮 dry-run 再决定。

---

## 第五步：用 Ratchet 防止回退

每次评估都加上 `--ratchet`：

```bash
evaluate-skill skills/<skill-name> \
  --output artifacts/<skill-name>/scorecard.md \
  --ratchet \
  --ratchet-baseline artifacts/<skill-name>/baseline_scorecard.md
```

含义：
- 如果新分数低于 baseline 分数，skillPrism 返回非 0；
- CI/同步任务就能告警，阻止这次 Skill 版本上线。

### 两套 baseline 体系的关系

skillPrism 里有两套互不干扰的 ratchet/baseline：

| | `improve-skill` 的 baseline | `evaluate-skill --ratchet-baseline` |
|---|---|---|
| 落盘位置 | `artifacts/<skill>/baseline/baseline.json`（+ `.bak` 回退） | 用户指定的 scorecard markdown（如 `artifacts/<skill>/baseline_scorecard.md`） |
| 维护方式 | **自动**：`--record-baseline` / keep 时原子写更新，含 `historical_best_score` | **手动**：你负责生成并保管对比用的 scorecard 文件 |
| 比较对象 | Rubric 分数 + benchmark gate，驱动 keep/revert | 整份 scorecard 的逐 skill 分数，回归即非 0 退出 |
| 适用场景 | 本地优化循环（每轮编辑后自动判断是否保留） | CI 门禁 / 定时同步任务（告警、阻止上线） |

简单说：本地调 skill 用前者，CI 卡质量用后者；本闭环里两者可以并存——
`improve-skill` 管「这次编辑要不要留」，`evaluate-skill --ratchet` 管「这个版本能不能上线」。

### 建议的 baseline 策略

| 场景 | 推荐做法 |
|---|---|
| 首次评估 | `evaluate-skill --all --output baseline_scorecard.md` 作为初始 baseline。 |
| 日常同步 | 每次跑完把 `scorecard.md` 复制成 `baseline_scorecard.md`，或 Git 管理 baseline。 |
| 多机器/多人 | 把 baseline 文件也提交到 Git，保证大家用同一份。 |

---

## 第六步：把同步脚本变成定时任务或 Webhook

### 方案 1：定时任务（最简单）

用 cron 或 GitHub Actions 定时跑。

**GitHub Actions 示例**（`.github/workflows/langfuse-sync.yaml`）：

```yaml
name: Langfuse Skill Sync

on:
  schedule:
    - cron: '0 2 * * *'   # 每天凌晨 2 点跑
  workflow_dispatch:      # 也支持手动触发

jobs:
  sync-eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install skillPrism + langfuse
        run: |
          pip install -e ".[dev]"
          pip install langfuse

      - name: Pull latest skills
        run: git submodule update --init --recursive   # 如果 Skill 仓库是 submodule

      - name: Run sync evaluation
        env:
          LANGFUSE_HOST: ${{ secrets.LANGFUSE_HOST }}
          LANGFUSE_PUBLIC_KEY: ${{ secrets.LANGFUSE_PUBLIC_KEY }}
          LANGFUSE_SECRET_KEY: ${{ secrets.LANGFUSE_SECRET_KEY }}
          SKILLPRISM_SKILLS_DIR: ./skills
        run: |
          python scripts/langfuse_sync_eval.py

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: langfuse-sync-report
          path: artifacts/langfuse-sync/
```

### 方案 2：Webhook（实时性更好）

Langfuse 目前不直接支持 webhook，但你可以：
1. 在 Agent 代码里，每次完成一次重要任务后，调用一个你自己部署的 HTTP 服务；
2. 这个服务把任务信息塞进一个队列（Redis/RabbitMQ）；
3. 本地消费者从队列里读消息，触发 `scripts/langfuse_sync_eval.py` 里类似的逻辑。

这种方案实时性高，但需要自己维护一个中转服务。

### 方案 3：Langfuse API 轮询 + 事件驱动

如果你的部署环境里能跑常驻进程，可以写一个简单的 daemon：

```python
# scripts/langfuse_sync_daemon.py
import time
from langfuse_sync_eval import fetch_recent_traces, main as run_once

SEEN_TRACE_IDS = set()

while True:
    client = get_langfuse_client()
    traces = fetch_recent_traces(client)
    new_traces = [t for t in traces if t["trace_id"] not in SEEN_TRACE_IDS]

    if new_traces:
        run_once(new_traces)
        SEEN_TRACE_IDS.update(t["trace_id"] for t in new_traces)

    time.sleep(60)  # 每分钟检查一次
```

---

## 第七步：把优化后的 Skill 同步回线上 Agent

评估优化完成后，你需要让线上 Agent 用上最新 Skill。常见做法：

### 做法 A：Git 触发部署（推荐）

1. 本地/CI 提交改动到 Skill 仓库的 `main` 分支；
2. 线上 Agent 服务监听 Git webhook；
3. 收到 push 后，Agent 重新拉取 Skill 目录；
4. 新 Skill 生效。

### 做法 B：手动部署

1. 本地改完 SKILL.md；
2. `git commit && git push`；
3. 登录线上 Agent 管理后台，点「重新加载 Skill」；
4. 或重启 Agent 服务。

---

## 第八步：在 Langfuse 里看闭环效果

打开 Langfuse UI，进入对应 trace：

1. 你会看到 skillPrism 回写的 score：
   - `skillprism_rubric_pass`：Rubric 是否通过；
   - `skillprism_test_pass`：benchmark 是否通过。
2. 点击 trace 的 Dataset item，可以看到输入和期望输出。
3. 对比不同 `skill_version` 的 trace，就能看到 Skill 升级前后的指标变化。

---

## 隐私与安全注意事项

1. **不要把用户原始数据写进公开仓库**
   - `scripts/langfuse_sync_eval.py` 落地到本地的文件，只在本地/CI 临时目录；
   - 不要把 `artifacts/langfuse-sync/` 提交到 Git（`artifacts/` 已默认被 `.gitignore` 忽略）。

2. **Langfuse 上的 trace 也可能含敏感信息**
   - 如果担心，可以在 Agent 端对 input/output 做脱敏；
   - 或者只把「 skill 名 + 元数据」写到 Langfuse，把用户输入留在自己的日志系统。

3. **API Key 不要硬编码**
   - 一律走环境变量或 CI secret；
   - 本地开发用 `.env` 文件，但不要提交它。

4. **Skill 版本要可追溯**
   - 每次改动 SKILL.md 都提交 Git；
   - 在 Langfuse metadata 里带 `skill_version`（如 commit sha），方便事后定位。

---

## 常见问题

**Q：skillPrism 会调用 LLM 吗？**
A：不会。skillPrism 只做确定性评分。只有当你显式配置 `SKILLPRISM_EDITOR_COMMAND` 或 `SKILLPRISM_LLM_JUDGE_COMMAND` 时，才会调用外部命令，那些命令里可以调用 LLM。

**Q：线上 Agent 必须改代码才能接入吗？**
A：只需要在 Langfuse 的 trace/spna 上加 `skill_name` 等 metadata。如果 Agent 已经接入了 Langfuse，这一步通常只需几行代码。

**Q：如果 Langfuse 挂了，skillPrism 还能工作吗？**
A：能。skillPrism 完全本地运行，Langfuse 只是数据源。脚本里已经用 `try/except` 隔离了 Langfuse 调用（你可以按需加强）。

**Q：一个 Skill 可以对应多个 task 吗？**
A：可以。trace metadata 里加 `task_id` 或 `task_type`，本地脚本按 task 分组评估即可。

**Q：怎么判断要不要自动 apply 优化结果？**
A：建议起步阶段全部人工确认。等 benchmark 覆盖足够、Rubric 分数稳定后，再考虑自动 apply 低风险改动（如纯文档措辞）。

---

## 下一步可以做什么

1. **把评估结果自动回写 Langfuse score**：本文脚本已经做了基础版，可以扩展成回写 9 维分数、benchmark metrics、decision 等。
2. **用 Langfuse Dataset 做回归测试**：把 Dataset item 导出成本地 benchmark 任务，跑 `test-skill`。
3. **接入通知**：同步任务失败时发 Slack/飞书/邮件告警。
4. ** ratchet 真相源迁到 Langfuse**：参考 `docs/reference/langfuse-integration.md` 的 R1→R2→R3 迁移策略，把 baseline 从本地文件逐步迁到服务端。
