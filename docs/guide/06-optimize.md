# 优化闭环：把 Skill 一步步改好

打分告诉你哪里弱，考试告诉你做得对不对，这一篇讲第三件事：**怎么改**。

优化不是"让 Agent 把说明书改一遍"那么简单。它是一个**测量 → 改 → 再测量 → 决定保留还是回滚**的循环，每一轮都留痕、每一轮都可撤销。你全程只做两件事：**改之前批准计划，改之后确认保留**，其余的交给 Agent 和引擎。

对应命令是 `improve-skill`。你用自然语言驱动，Agent 替你翻译。

---

## 1. 闭环六步：你在回路的完整循环

这是整个优化流程的主干。下面六步构成**一轮**，跑完一轮要么进入下一轮，要么收尾。

### 第 1 步：记录 baseline（把当前成绩存档）

优化之前先把"现在是什么样"存下来，作为之后判断"有没有进步"的参照。

- **你说**："先记录这个 skill 的 baseline。"
- **Agent 做**：`improve-skill skills/<skill> --record-baseline`
- **得到什么**：当前分数被存档到 `artifacts/<skill>/baseline/`，全程不调用 LLM、不改任何文件。
- **注意**：baseline 是后面所有 keep/revert 判断的基准。没存 baseline 就 judge，引擎会提示你先 `--record-baseline`。

### 第 2 步：找出最弱维度 + 修改计划，停下等批准

让引擎指出当前最弱的维度，以及建议怎么改。**这一步是检查点，Agent 必须停下来等你批准**，而不是拿到建议就直接动手。

- **你说**："这个 skill 哪里最弱？给我优化建议。"
- **Agent 做**：`improve-skill skills/<skill> --suggest`
- **得到什么**：最弱维度、它所在的相关维度簇、按 P0-P3 排好序的优化策略（见下文"优化策略速查"）。
- **Agent 接着向你展示**：最弱维度是什么、打算按哪条策略改、**只动哪里**。然后停下等你点头。
- **注意**：这是你最重要的控制权之一。看清楚"改哪个维度、按什么策略改"再批准，不要直接放行。

### 第 3 步：批准后改 SKILL.md（默认只动说明书）

你批准后，Agent 用自己的 LLM 去改说明书。

- **你说**（举个例子）："按 P1 结构策略先改 D1，其他维度别动。"
- **Agent 做**：编辑 `skills/<skill>/SKILL.md`。
- **默认编辑范围**：**只改 `SKILL.md` 这份说明书**，不碰代码资产（`scripts/`、`examples/`、`requirements.txt` 等）。说明书改动回滚简单、风险低。

!!! warning "改代码资产要显式授权"
    如果这一轮确实要动代码资产（比如修 `scripts/` 里的脚本、更新 `requirements.txt`），必须你**显式授权**——对应 `--edit-code`，回滚时引擎会自动把代码资产快照一起恢复。而且这类改动要**附加 smoke test / benchmark gate** 才算数，不能只看 rubric 分数。

### 第 4 步：展示完整 diff，等你确认

改完之后，Agent 把**完整改动**摆给你看：加了什么、删了什么，一目了然。

- **得到什么**：一份可读的前后 diff（`--show-diff` 默认开启，`--diff-lines` 控制展示行数）。
- **需要你做什么**：读一遍 diff，确认改动确实是按批准的计划来的、没有夹带别的修改。

### 第 5 步：judge——进步了才保留，没进步自动回滚

让引擎重新打分，和 baseline 对比，给出"保留 / 回滚"的判断。

- **你说**："改完 judge 一下，看看要不要保留。"
- **Agent 做**：`improve-skill skills/<skill> --judge`

!!! note "dry-run 默认，--apply 才动文件"
    `--judge` 默认是 **dry-run**：只输出决策（keep / revert / human-decide），**不真正动文件**。
    确认无误后，加 `--apply` 才真正执行保留或回滚：

    ```bash
    improve-skill skills/<skill> --judge            # dry-run：只看决策
    improve-skill skills/<skill> --judge --apply    # 真正执行 keep/revert
    ```

judge 的判断逻辑（无 benchmark 时）：

| 情况 | 决策 |
|---|---|
| 总分提高 ≥ `--min-gain`（默认 1.0）且无 guard 触发 | **keep** |
| 总分下降、或触发反模式 guard | **revert** |
| D9 安全维度下降 | **revert（一票否决）** |
| SKILL.md 体积 > 150% baseline | **revert** |
| 其余模糊情况 | human-decide（交给你判断） |

- **注意**：如果决策是 revert，`--apply` 会把说明书**自动恢复**到改动前的样子。改不回来才算事故——而这里默认就能改回来。

### 第 6 步：下一轮，直到无提升或你喊停

一轮走完，回到第 2 步重新诊断。循环的退出条件有两个：**最弱维度已经没有明显提升空间**，或者**你喊停**。

- **你说**（收尾时）："这轮就到这里，不用再改了。"
- **得到什么**：一个分数更高、质量更好的说明书，外加每一轮的完整记录（见"复测确认"）。

---

## 2. 两个不要（先看这个再开工）

!!! warning "不要一轮改多个维度"
    一轮里只改一个维度。一次改好几处，分数涨了你也**不知道是哪个改动起的作用**，下一轮就没法决策。反模式 guard 也会对"一轮改多个维度"发出告警。想让多处一起变好，靠的是**多轮**，不是一轮塞满。

!!! warning "不要在没有考题时盲目优化"
    只看打分（rubric）优化，容易把说明书写成"**应试作文**"：分数涨了，实际照着做的效果没变，甚至更差。**打分和考试一起进步，才是真进步。** 还没有考题的话，先去 [构建 Benchmark](04-build-benchmark.md) 建一套，再回来优化。

---

## 3. 两种优化模式

编辑说明书这件事，有两种做法，选一种即可：

| 模式 | 怎么触发 | 适用场景 |
|---|---|---|
| **手动 / Agent 编辑**（默认） | Agent 或你手动改 `SKILL.md`，引擎负责测量、judge、回滚 | 需要人工审阅每一轮 diff，**推荐默认用这个** |
| **自动编辑** | `improve-skill ... --auto-edit --apply` | 一键跑"分析 → 改 → judge → 保留/回滚"，无人值守 |

两种模式**共用同一套安全机制**（dry-run、ratchet、guard、benchmark gate），区别只在"谁来动笔、要不要每轮停下来等人审"。

### 手动 / Agent 编辑（默认）

就是第 1 节那套六步。引擎不替你改，只负责量、判、回滚；动笔的是 Agent（或你自己），每轮 diff 都由你人工审。完整命令序列：

```bash
improve-skill skills/<skill> --record-baseline   # 1. 记录 baseline
improve-skill skills/<skill> --suggest           # 2. 诊断 + 修改计划（停下等批准）
# 3-4. Agent 改 SKILL.md，展示 diff 等你确认
improve-skill skills/<skill> --judge             # 5. dry-run：只给决策
improve-skill skills/<skill> --judge --apply     # 5. 确认后真正保留/回滚
```

### 自动编辑（`--auto-edit`）

不想每轮都手动确认，可以把"改"也交给一个外部 editor 命令，让引擎自动循环：**分析 → 改 → judge → 保留/回滚**。

```bash
export SKILLPRISM_EDITOR_COMMAND="python examples/editor_wrappers/openai_editor.py"

improve-skill skills/<skill> \
  --record-baseline \
  --benchmark-registry benchmarks/<skill>/registry.yaml \
  --auto-edit --apply --max-rounds 3
```

行为约定：

- **`--max-rounds N`** 自动迭代最多 N 轮（默认 1）。每轮若保留，就**把保留后的改进版当作新的 baseline**，下一轮从更好的起点继续往上爬。
- **遇回滚默认停止**：某一轮被 judge 回滚，循环就停下来（这是正常信号，说明这个方向到顶了）。想让它跳过回滚继续后面几轮，加 `--no-stop-on-regression`。
- `--auto-edit` 不带 `--apply` 时不会真正改写，只会提示你要加 `--apply` 才跑完整的"改 + judge + 保留/回滚"。
- 想动代码资产，加 `--edit-code`（回滚时自动恢复快照），并应配合 `--benchmark-registry` 做 gate。

#### editor 命令契约

editor 命令要遵守一个简单契约，任何符合它的脚本都能接进来：

- 从 **stdin** 读 prompt；
- 把**完整的、更新后的 `SKILL.md` 内容**输出到 **stdout**；
- 输出**不要**包 Markdown 代码围栏（```` ``` ````）。

skillPrism 发给 editor 的 prompt 里包含：skill 名字与当前 rubric 分数、最弱维度及其分数、针对该维度的具体编辑策略、当前 `SKILL.md` 全文。所以 editor 拿到的是"问题诊断 + 原文 + 改法"，只需返回改好的全文。

#### 现成 wrapper

`examples/editor_wrappers/` 里已经备好常用 provider 的 wrapper，挑一个、装上依赖、设好 key 和模型即可：

| 脚本 | 适用 |
|---|---|
| `openai_editor.py` | OpenAI |
| `anthropic_editor.py` | Anthropic |
| `ollama_editor.py` | 本地 Ollama |
| `openai_compatible_editor.py` | OpenAI 兼容接口（Moonshot/Kimi、DeepSeek、智谱 GLM、阿里通义 Qwen 等，只改 `OPENAI_BASE_URL` / `OPENAI_MODEL`） |

详见 `examples/editor_wrappers/README.md`。你也可以写一个**确定性**（不调 LLM）的 wrapper，用于可复现的测试场景。

---

## 4. 安全机制清单

整个优化闭环默认"不动手、可撤销、防退化"。下面是它提供的保护，按你要不要主动开来分：

**默认就有（不用配）：**

- **dry-run 默认**：`--judge` 只输出决策，不真正动文件。
- **`--apply` 才动文件**：所有 keep/revert 的实际执行都要显式加 `--apply`。
- **改坏自动回滚**：每轮先存 baseline，没进步或触发 guard 就把说明书恢复原样。
- **反模式 guard**：自动检查下列行为并告警，严重的直接 block。

**需要你主动开启：**

- **`--ratchet`**：分数**不低于历史最高**才接受，像棘轮一样只进不退，防止越改越差。
- **`--min-gain`**：最小可接受提升（默认 1.0），低于这个涨幅不算进步。
- **`--allow-regression`**：当 benchmark 改善时，允许的 rubric 最大降幅（默认 0.5，见下节）。

**反模式 guard 检查项：**

| 检查项 | 说明 |
|---|---|
| 一轮改多个维度 | 不知道是哪个改动起的效，告警 |
| 干跑（dry-run）比例 > 30% | 光量不改、刷测量次数，告警 |
| `git reset --hard` | 试图绕过回滚机制，**发现即 block** |
| 堆冗余凑分 | 靠塞关键词/堆字数骗 rubric，告警 |
| 同一模型又改又评 | 用 `--editor-model` / `--judge-model` 暴露，避免自评自 |
| 静默跳过异常 | 出错却不声不响地跳过，告警 |

!!! danger "不要用 git reset --hard 跳过回滚"
    guard 对 `git reset --hard` **发现即 block**。回滚要走引擎自己的机制（baseline 快照），这样才能保证历史记录和状态一致。手动硬重置会破坏这条线索。

---

## 5. benchmark 驱动优化

第 2 节说过"打分和考试一起进步才是真进步"。落到操作上，就是给 judge 接上 benchmark：**提供 `--benchmark-registry` 后，judge 时会同时跑 benchmark**，两条线一起看。

```bash
improve-skill skills/<skill> \
  --judge \
  --benchmark-registry benchmarks/<skill>/registry.yaml \
  --apply
```

接入 benchmark 后的决策规则：

| 情况 | 决策 |
|---|---|
| rubric 涨 + benchmark 通过/改善 | keep |
| **rubric 涨，但 benchmark 退步** | **revert**（应试作文，打掉） |
| benchmark 通过或严格改善，即使 rubric 提升未达 `--min-gain` | 仍可接受 |
| rubric 降幅超过 `--allow-regression`（默认 0.5），即便 benchmark 改善 | revert |

要点：

- **benchmark 是"防止应试作文"的闸门**。rubric 涨但真实考题退步，说明这轮优化在骗分，直接回滚。
- `--allow-regression` 给了一个权衡空间：benchmark 实实在在变好的情况下，允许 rubric 小幅回落（默认最多降 0.5 分）。想收紧就调小，想放宽就调大。
- 没接 benchmark 时，judge 只看 rubric 和 guard，回到第 1 节那张表。

---

## 6. 优化策略速查

`--suggest` 给出的建议按 **P0-P3 优先级**组织，并附带**维度簇**信息。这里给个速查，细节不展开。

### P0-P3 优先级表

优先级越靠前越该先修。P0 是"必须先处理"的红线问题，P3 是"锦上添花"。

| 优先级 | 触发条件 | 建议动作 |
|---|---|---|
| **P0** | Runtime 特定措辞命中红灯扫描 | 换成 runtime-neutral 措辞 |
| **P0** | test-prompts 验证失败，或 with-skill 比 without-skill 更差 | 修核心指令，减少过度约束 |
| **P0** | D9 安全维度 ≤ 2 | 加高风险操作黑名单 |
| **P1** | 结构维度（D1-D4）最弱 | 重组 workflow、补 frontmatter、加检查点 |
| **P2** | 具体性维度（D3、D5）最弱 | 补参数、示例、输入/输出格式、异常处理表 |
| **P2** | 没有显式失败模式编码 | 加 if-then 三段式 fallback 表 |
| **P3** | 可读性维度（D2、D7、D8）最弱 | 拆段落、去重、加 TL;DR |
| **P3** | SKILL.md 体积 > 130% baseline | 精简冗余 |

跑 `improve-skill skills/<skill> --suggest`，输出会按优先级列出当前适用的策略。

### 维度簇：修一个会带动一串

九个维度不是孤立的。**修一个维度，常常会带动同簇的其他维度一起涨**。识别这种相关性，能避免无效的单维度编辑，也能抓住"一改多得"的机会。

默认三簇：

| 簇 | 维度 | 说明 |
|---|---|---|
| 结构簇 | D1、D2、D3、D4 | frontmatter、workflow、失败模式、检查点 |
| 执行簇 | D3、D5、D6 | 可执行性、具体性、LLM 调用能力 |
| 维护簇 | D7、D8、D9 | 可读性、可维护性、安全性 |

例如：补 if-then fallback 表（D3）时，文档清晰度（D2）、依赖说明（D4）往往也跟着改善。`--suggest` 会告诉你最弱维度落在哪个簇、同簇还有哪些维度——这意味着改这一处时，可以顺带检查同簇维度是否一起提升了。

实践含义：如果同簇里好几个维度都偏低，**一次更全面的重写可能比多轮单维度编辑更高效**；但每轮仍只针对一个维度动手，靠多轮推进（呼应第 2 节的"不要一轮改多个维度"）。

---

## 7. 复测确认：改完要回头验证

优化收尾后，重跑一遍评估和考试，跟 baseline 对比，确认没有副作用。

- **你说**："再考一遍，确认优化没有副作用。"
- **Agent 做**：重跑评估 + benchmark，和优化前的 baseline 对比分数与考题通过情况。
- **得到什么**：优化前后的对比结论——分数是否保持、考题是否全部仍通过。

!!! warning "警惕「分涨题退」"
    如果发现"说明书分数涨了，但考题反而退步"，说明这一轮优化有问题（多半是在骗 rubric 分）。这时应当回滚——这正是第 5 节 benchmark gate 要拦的情况。

**每一轮都可查、可回滚。** 所有尝试都记在 `artifacts/<skill>/history.jsonl`，随时能看：

```bash
improve-skill skills/<skill> --history
```

```text
| Timestamp           | Status   | Dim | Old  | New  | Δ    | Note                        | Mode   |
|---------------------|----------|-----|------|------|------|-----------------------------|--------|
| 2026-06-22 12:00:00 | baseline | all | 39.4 | 39.4 | +0.0 | baseline evaluation         | static |
| 2026-06-22 12:05:00 | keep     | D4  | 39.4 | 45.8 | +6.4 | Added version compatibility | static |
```

如果发现某一版更好，可以让 Agent 依据历史记录回滚到任意一轮。配合每轮的 diff 确认权，这就是"改得放心"的三重保险：baseline 存档、自动回滚、历史可查。

---

## 接下来去哪

- 还没有考题，想先建一套：→ [构建 Benchmark](04-build-benchmark.md)
- 想查 `improve-skill` 的完整参数：→ [CLI 参考](../reference/cli.md)
- 想理解九个维度怎么打分：→ [Rubric 参考](../reference/rubric.md)
- 想把优化接入日常迭代与 CI 门禁：→ [生产循环](08-production-loop.md)
- 想看一个从头到尾的完整优化案例：→ [CSV 摘要全流程](../cases/csv-summary-full-cycle.md)
