# 07 · 质量报告与 CI 门禁

> 前面几步针对单个 skill；这一篇回答批量场景的两个问题：
> **整体质量怎么样？下一步做什么？** 以及 **怎么把它钉在 CI 里，不让质量倒退？**

前置：你已经按 [02](./02-evaluate.md) 评过分、按 [05](./05-run-benchmark.md) 跑过 benchmark。

---

## 批量质量报告

### 你要做什么

对 `./skills` 下所有 skill 一次性跑评估 + benchmark，拿到一份合并报告。

### 对 Agent 怎么说

> "跑完整质量流水线，给我一份总报告"

Agent 会执行：

```bash
skill-pipeline \
  --intent "run full quality pipeline" \
  --skills-dir ./skills \
  --benchmark-registry benchmarks/<skill>/registry.yaml
```

### 得到什么

默认输出 `reports/SKILL_QUALITY_REPORT.md`，一份合并报告，包含：

- **scorecard**：所有 skill 的 Rubric 分数与等级；
- **benchmark 结果**：通过/失败、回归对比；
- **最差 skill**：得分最低、最弱维度是哪一个；
- **下一步优化命令**：报告末尾直接给出可以复制执行的 `improve-skill` 命令。

输出路径可以用 `--output` 覆盖；加 `--run-smoke` 可同时把 smoke test 结果并入报告。

```text
Rubric: 78.5 / 100 (Grade C)
Test: PASS
Weakest dimension: D2
Next step: improve-skill skills/my-skill --record-baseline \
  --benchmark-registry benchmarks/my-skill/registry.yaml
```

### 历史趋势

每次评估会追加一行到 `artifacts/<skill>/history.jsonl`，用于看单个 skill 的分数随时间的变化：

```bash
improve-skill skills/<skill> --history   # 查看优化历史
```

想把多个 skill 的评估记录汇总到一个文件做趋势图，用 `--output-history`：

```bash
evaluate-skill --all --skills-dir ./skills \
  --output reports/SKILL_SCORECARD.md \
  --output-history artifacts/skill_history.jsonl
```

每次运行向 `artifacts/skill_history.jsonl` 追加记录（不会覆盖），可以交给外部工具画趋势。

---

## 批量操作：`skill-pipeline` 的四种意图

`skill-pipeline` 把「评估 → benchmark → 找最差 → 准备优化」串成一条命令。你只用表达意图，Agent 翻译成 `--intent`：

| 你想做什么 | 对 Agent 说 | `--intent` |
|---|---|---|
| 只看所有 skill 的文档分数 | "给所有 skills 打个分" | `evaluate all skills` |
| 只跑 benchmark 并对比基线 | "跑一下所有 benchmark" | `run benchmarks` |
| 完整检查一遍，要总报告 | "跑完整质量流水线" | `run full quality pipeline` |
| 找出最差的并准备优化 | "哪个 skill 最差？帮我准备优化" | `optimize skills` |

何时用哪种：

- **日常自检**：`evaluate all skills`，最快，只出分数。
- **发布前把关**：`run full quality pipeline`，分数 + benchmark + 最差项 + 下一步命令一次到位。
- **排期优化**：`optimize skills`，在完整流水线之上为最差 skill 记录 baseline 并输出 judge 命令；加 `--apply` 会自动应用优化决策（`--apply` 只在 optimize 意图下有效）。

### 常用参数

| 参数 | 说明 |
|---|---|
| `--skills-dir` | skill 目录（默认 `./skills`） |
| `--benchmark-registry` | benchmark 注册表路径 |
| `--benchmark-suite` | 只跑指定 suite |
| `--output` | 综合报告输出路径（默认 `reports/SKILL_QUALITY_REPORT.md`） |
| `--run-smoke` | 同时跑 smoke test |
| `--apply` | 自动应用优化决策（需 optimize 意图） |
| `--max-rounds` | 最大优化轮数（需 optimize 意图） |

!!! note "渐进测试"
    长耗时、计算密集的 benchmark 另有 `run gradual pipeline` 意图，配合 `--max-level` 使用（`--max-level` 只在 gradual 意图下有效）：

    ```bash
    skill-pipeline \
      --intent "run gradual pipeline" \
      --skills-dir ./skills \
      --benchmark-registry benchmarks/<skill>/registry.yaml \
      --max-level 2
    ```

    渐进测试按失败模式分级（level 0→3）逐级跑，细节见 [05 · 运行 Benchmark](./05-run-benchmark.md)。

### 什么时候不用 pipeline，用单独命令

| 场景 | 用什么 |
|---|---|
| 只想看一个 skill 的 Rubric 分数 | `evaluate-skill` |
| 只想验证某个 skill 的 benchmark | `test-skill --mode single --skill ... --code <path>` |
| 想要一次性的完整质量报告 | `skill-pipeline --intent "run full quality pipeline"` |
| 想从最差的 skill 开始优化 | `skill-pipeline --intent "optimize skills"` |

原则：目标越单一，用越小的命令；要「批量 + 找最差 + 下一步」才上 pipeline。

---

## 棘轮（ratchet）：只能前进，不能后退

棘轮是 skillPrism 的质量门禁：**新版本分数不能低于历史最好分数，否则命令返回非 0**。

两个命令都有 `--ratchet`，作用不同：

- `evaluate-skill --ratchet`：与历史 scorecard 对比，**任何一个 skill 分数回退就 fail**——用于 CI / 定时任务的回归告警；
- `improve-skill --ratchet`：优化循环里**分数低于历史最好就拒绝保留这次编辑**——用于本地优化时不接受倒退的改动。

一句话：**`evaluate-skill --ratchet` 管「这个版本能不能上线」，`improve-skill --ratchet` 管「这次编辑要不要留」。**

### `evaluate-skill --ratchet`：回归告警

与历史 scorecard 对比，任何一个 skill 分数回退，退出码非 0：

```bash
evaluate-skill skills/<skill> \
  --output artifacts/<skill>/scorecard.md \
  --ratchet \
  --ratchet-baseline artifacts/<skill>/baseline_scorecard.md
```

baseline scorecard 由你自己生成和保管（默认取 `--output` 文件本身）。建议的 baseline 策略：

| 场景 | 做法 |
|---|---|
| 首次评估 | `evaluate-skill --all --output baseline_scorecard.md` 作为初始 baseline |
| 日常运行 | 每次跑完把新 scorecard 复制成 baseline，或用 Git 管理 baseline 文件 |
| 多人/多机 | 把 baseline 提交到 Git，保证大家用同一份 |

### `improve-skill --ratchet`：拒绝倒退的编辑

优化循环里加 `--ratchet`，任何低于历史最好分数的编辑都不会被保留——即使它超过了当前 baseline：

```bash
improve-skill skills/<skill> --judge --ratchet
```

历史最好分数由 `improve-skill` 自动维护在 `artifacts/<skill>/baseline/` 下，无需手工管理。

---

## CI 接入：`skill-ci`

`skill-ci` 是 CI 门控入口。**默认只做静态检查，不调用 LLM**，因此可以直接放进任意 CI runner。

### 默认行为

```bash
skill-ci --skill my-skill
```

默认执行：

- Rubric 静态评分（含规则增强检查）
- Smoke test
- 依赖可复现性检查
- 安全扫描
- Runtime neutrality 红灯扫描

产物（报告、测试结果）默认写入 `artifacts/<skill>/ci/`，可用 `--output-dir` 覆盖；**不会写入 skill 树**。可用 `--no-smoke` / `--no-deps` 跳过对应检查。

### 在 CI 里跑 benchmark（可选）

`--run-benchmark` 必须搭配 `--code`——CI 不负责生成代码，你要在流水线里预先生成好代码 artifact，再交给 `skill-ci` 验证：

```bash
skill-ci --skill my-skill \
  --run-benchmark \
  --code artifacts/generated_code.py \
  --registry benchmarks/my-skill/registry.yaml

# 限定范围：只跑 level 0，或只跑 smoke suite
skill-ci --skill my-skill \
  --run-benchmark --code code.py \
  --registry benchmarks/my-skill/registry.yaml --level 0
```

### 刷新 baseline：`--ratchet`

```bash
skill-ci --skill my-skill \
  --run-benchmark --code code.py \
  --registry benchmarks/my-skill/registry.yaml \
  --ratchet
```

**只有全部检查通过，才把当前结果写成新的 benchmark baseline**。这保证 baseline 只记录「已知好」的状态——质量倒退时 CI 直接失败，baseline 不会被污染。

### 回归语义：`--no-stop-on-regression`

默认行为是**回归即 fail CI**（benchmark 指标低于 baseline，退出码非 0，门禁拦住合并）。如果你只是想在报告里看到回归但不拦流程，显式加 `--no-stop-on-regression`。

!!! warning
    不要在生产 CI 里常驻 `--no-stop-on-regression`。它适合临时迁移、数据漂移排查期使用；排查完应去掉。

### GitHub Actions 示例

```yaml
name: Skill Quality
on: [push, pull_request]
jobs:
  skill-ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install
        run: pip install -e ".[dev]"
      - name: Lint & Test
        run: |
          make lint
          make test
      - name: Evaluate skills
        run: |
          evaluate-skill --all --skills-dir ./skills \
            --output reports/SKILL_SCORECARD.md --run-smoke
      - name: CI gate
        run: skill-ci --skill my-skill
```

### CI 不做什么

- 不调用 LLM 生成代码；
- 不自动编辑 SKILL.md；
- 不跑渐进测试 level 3（除非显式配置）。

这些动作需要人/Agent 介入，CI 只负责判定「能不能过」。

---

## 成果卡片：把优化结果做成可分享的图

优化完成后，可以把优化结果 JSON 渲染成一张 HTML/PNG 卡片，放进 PR 描述或周报：

```bash
python examples/reporters/visual_result_card.py \
  --input artifacts/<skill>/baseline/optimization_result.json \
  --output result-card.html \
  --theme swiss        # 可选 swiss / terminal / newspaper，不指定则随机
```

需要 PNG 截图时加 `--screenshot`（先 `pip install playwright && playwright install`）：

```bash
python examples/reporters/visual_result_card.py \
  --input artifacts/<skill>/baseline/optimization_result.json \
  --output result-card.html \
  --screenshot
```

!!! note
    卡片是可选 reporter，读取优化结果 JSON 生成可分享的 HTML/PNG，不影响评估流程本身。

---

## 下一步

本地质量门禁就绪后，进入 [08 · 生产闭环](./08-production-loop.md)：把线上 Agent 的真实任务转成本地考题，形成「采集 → 评估 → 优化 → 回灌」的持续迭代。
