# 🙌 手把手教程：用 skillPrism 评估并改进一个 Skill

> 本教程以 Agent 自然语言交互为主线，演示 skillPrism 的四个核心命令。

## 前置条件

- 已安装 skillPrism：`pip install -e ".[dev]"`
- Agent 已加载 `skills/skill-prism/SKILL.md`
- 有一个 skill 目录，例如 `skills/csv-summary-skill/`

## 0.1 先看文档质量

**用户目标**：了解 `csv-summary-skill` 的 SKILL.md 作为教练文档够不够好。

**对 Agent 说**：

> "先看看这个 csv-summary skill 的 SKILL.md 质量如何，告诉我哪里扣分最多。"

**Agent 执行**：

```bash
evaluate-skill skills/csv-summary-skill --detailed
```

**预期输出**：

```text
## csv-summary-skill
- Skill 类型: analysis
- Rubric 总分: 72.3 / 100
- 等级: C
- 最弱维度: D3 代码正确性 (1/5)
```

**解读**：

- 总分 72.3，等级 C，说明 SKILL.md 还有改进空间。
- 最弱维度是 D3 代码正确性，意味着 SKILL.md 里可能缺少可运行的代码示例或参数说明。

## 0.2 生成代码并快速验证

**用户目标**：让 Agent 按 SKILL.md 生成最小示例，看能不能跑通。

**对 Agent 说**：

> "按这个 SKILL.md 生成一份最小示例代码，然后用 quick gate 验证一下。"

**Agent 的工作流程**：

1. 读取 `skills/csv-summary-skill/SKILL.md`
2. 生成代码文件，例如 `skills/csv-summary-skill/examples/minimal_example.py`
3. 运行 quick gate（level 0 + level 1）

**Agent 执行**：

```bash
test-skill --skill csv-summary-skill \
  --registry benchmarks/csv-summary-skill/registry.yaml \
  --code skills/csv-summary-skill/examples/minimal_example.py \
  --mode quick
```

**预期输出**：

```text
Running 2 benchmarks (skill: csv-summary-skill)
[PASS] level_0_smoke: ...
[FAIL] level_1_regression: row_count 2 < 3

Overall: FAIL
```

**解读**：

- Level 0 通过：代码没有崩溃。
- Level 1 失败：输出结构或数值不满足预期。
- 下一步：回到 SKILL.md 改进代码示例或参数说明。

## 0.3 针对短板优化

**用户目标**：针对 D3 代码正确性做结构化改进，并判断改动是否保留。

**对 Agent 说**：

> "D3 代码正确性只有 1 分，帮我优化到能通过 level 1 测试。先记录 baseline，然后只改 D3 相关部分，改完 judge 一下。"

**Agent 执行**：

```bash
# 1. 记录 baseline
improve-skill skills/csv-summary-skill \
  --record-baseline \
  --benchmark-registry benchmarks/csv-summary-skill/registry.yaml

# 2. 查看优化策略（P0-P3）和最弱维度
improve-skill skills/csv-summary-skill --suggest

# 3. Agent 按策略编辑 SKILL.md（每轮只改一个维度），然后 judge
improve-skill skills/csv-summary-skill \
  --judge \
  --benchmark-registry benchmarks/csv-summary-skill/registry.yaml

# 4. 如果 judge 建议 keep，确认应用
improve-skill skills/csv-summary-skill --apply

# 5. 查看优化历史
improve-skill skills/csv-summary-skill --history
```

**judge 输出示例**：

```text
Current: 78.5 / 100 (Grade C)
Baseline: 72.3 / 100
Delta: +6.2

Dimension changes (current - baseline):
  D2: 0
  D3: +1

Benchmark gate: PASS
Decision: KEEP (Rubric score improved)
Edit kept and baseline updated.
```

**如果 hill-climbing 触顶**：

```bash
improve-skill skills/csv-summary-skill \
  --explore-rewrite \
  --apply \
  --benchmark-registry benchmarks/csv-summary-skill/registry.yaml
```

## 0.4 跑完整流水线

**用户目标**：验证单个 skill 改进后，在整体项目中的位置，以及下一步做什么。

**对 Agent 说**：

> "现在跑完整流水线，看看所有 skills 里这个是不是最差的，以及下一步推荐做什么。"

**Agent 执行**：

```bash
skill-pipeline \
  --intent "run full quality pipeline" \
  --skills-dir ./skills \
  --benchmark-registry benchmarks/csv-summary-skill/registry.yaml
```

**预期输出**：

```text
Rubric: 78.5 / 100
Benchmark: PASS
Weakest dimension: D2
Next recommended action: improve-skill skills/csv-summary-skill --judge
```

## 0.5 可选：主观维度第二意见

**用户目标**：对 D2 可读性、D5 领域准确性做更细致的判断。

**对 Agent 说**：

> "再帮我深入看看 D2 可读性和 D5 领域准确性，有没有文档写得不够清楚的地方。"

**Agent 执行**：

```bash
# 1. Agent 调用 LLM 多次，生成 judgments 文件
# 2. 引擎消费 judgments 文件
evaluate-skill skills/csv-summary-skill \
  --llm-judgments artifacts/csv-summary-skill/llm_judgments.json
```

## 0.6 可选：验证 test-prompts

**用户目标**：验证 skill 的 prompts 在不同场景下是否有效。

**对 Agent 说**：

> "验证一下 test-prompts.json 里的 prompts，看看这个 skill 在实际调用时效果稳不稳。"

**Agent 执行**：

```bash
# 1. Agent 读取 test-prompts.json
# 2. 对每个 prompt 做 with/without skill 执行
# 3. 生成 verification 文件
# 4. 引擎消费
evaluate-skill skills/csv-summary-skill \
  --prompts-verification artifacts/csv-summary-skill/prompts_verification.json
```

## 下一步

- 阅读 [评估一个 Skill](./evaluate.md) 了解 `evaluate-skill` 全部参数。
- 阅读 [测试一个 Skill](./test.md) 了解三种测试模式。
- 阅读 [改进一个 Skill](./improve.md) 了解 judge 逻辑。
