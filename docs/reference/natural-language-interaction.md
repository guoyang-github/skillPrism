# Natural-Language Interaction Best Practices

This document defines the recommended natural-language-driven workflow for
skillPrism. It is designed to be **minimal, Agent-native, and non-intrusive to
the engine**.

---

## 1. Goal

Let users interact with skillPrism through a single Skill entry
(`skills/skill-prism/SKILL.md`) using plain language, while keeping the engine
fully deterministic and LLM-free.

---

## 2. Core Principles

1. **Engine measures, Agent orchestrates.**
   - The `skillprism` package never calls an LLM.
   - The Agent interprets intent, generates artifacts, and invokes engine CLI commands.

2. **Single entry point.**
   - All requests flow through `skills/skill-prism/SKILL.md`.
   - No per-command chat wrappers, no extra REST API, no new abstraction layer.

3. **Default read-only, write only with approval.**
   - Evaluation, CI, and report generation are non-destructive.
   - Edits, `--apply`, ratchet updates, and code-asset changes require explicit
     user confirmation.

---

## 3. Minimal Architecture

```text
User natural language
        │
        ▼
Agent loads skills/skill-prism/SKILL.md
        │
        ├── Evaluate   → evaluate-skill
        ├── Test       → test-skill / skill-ci
        ├── Improve    → improve-skill
        └── Pipeline   → skill-pipeline
        │
        ▼
skillprism engine (no LLM)  → measurement, reports, rollback
```

---

## 4. Intent Mapping

The Agent only needs to recognize these high-frequency intents:

| User says | Agent runs |
|---|---|
| "Evaluate this skill" / "Score this skill" | `evaluate-skill skills/<skill>` |
| "Evaluate all skills" / "Grade everything" | `evaluate-skill --all --skills-dir ./skills --output docs/SKILL_SCORECARD.md` |
| "Detailed evaluation" | `evaluate-skill skills/<skill> --detailed` |
| "Run benchmark" / "Test this skill" | `test-skill --mode single --skill <skill> --registry benchmarks/<skill>/registry.yaml` |
| "Run benchmark with code" | `test-skill --skill <skill> --registry benchmarks/<skill>/registry.yaml --code <path>` |
| "Run CI gate" / "Static check" | `skill-ci --skill <skill> --registry benchmarks/<skill>/registry.yaml` |
| "Improve this skill" | `improve-skill skills/<skill> --record-baseline --suggest` |
| "Judge my edit" | `improve-skill skills/<skill> --judge` |
| "Keep the edit" | `improve-skill skills/<skill> --judge --apply` |
| "Run full pipeline" | `skill-pipeline --intent "run full quality pipeline" --skills-dir ./skills --benchmark-registry benchmarks/<skill>/registry.yaml` |
| "Check regression" / "Ratchet check" | `evaluate-skill --all --skills-dir ./skills --ratchet` |

---

## 5. Human-in-the-Loop Rules

| Action | Requires user approval |
|---|---|
| Read-only evaluation | No |
| Report / scorecard generation | No |
| CI static gate | No |
| Benchmark run (no ratchet) | No |
| Edit `SKILL.md` | **Yes** |
| `--apply` keep/revert | **Yes** |
| Ratchet baseline update | **Yes** |
| Edit code assets (`scripts/`, `examples/`, `requirements.txt`) | **Yes, and discouraged by default** |
| D5 / D9 critical or high findings | **Yes, must be handled manually** |

---

## 6. File Conventions

```text
project/
├── skills/
│   ├── skill-prism/              # Copied from skillPrism repo
│   │   └── SKILL.md
│   └── <your-skill>/
│       └── SKILL.md
├── benchmarks/
│   └── <your-skill>/
│       ├── registry.yaml
│       └── tasks/
│           └── <task>.yaml
├── docs/
│   └── SKILL_SCORECARD.md        # Auto-generated report
└── ci-output/                    # CI artifacts (gitignored)
```

Generated measurement files stay **beside the report**, not inside the skill
source tree:

- `.skillprism_llm_judgments.json`
- `.skillprism_prompts_verification.json`
- `.skillprism_history.jsonl`

---

## 7. LLM Judge Decision Rule

When the user asks for an LLM judge (e.g. "用 LLM judge 再看看"):

1. If `SKILLPRISM_LLM_JUDGE_COMMAND` or `llm_judge.command` in config is set:
   ```bash
   evaluate-skill skills/<skill> --llm-judge --detailed
   ```
2. Otherwise, the Agent generates `.skillprism_llm_judgments.json` and the
   engine consumes it:
   ```bash
   evaluate-skill skills/<skill> --llm-judgments .skillprism_llm_judgments.json --detailed
   ```

The same rule should apply to `improve-skill` once `--llm-judgments` is
implemented there.

---

## 8. Standard Conversation Flows

### 8.1 Evaluate

```text
User: 评估一下 bio-single-cell-clustering
Agent: 好的，我对 bio-single-cell-clustering 做一次 Rubric 评估，不修改任何文件。
       执行：evaluate-skill skills/bio-single-cell-clustering
Agent: 评估完成。总分 68.8/100，等级 C。最弱维度是 D4（依赖可复现，1/5）。
       需要我给出改进建议吗？
```

### 8.2 Improve

```text
User: 优化 bio-single-cell-clustering
Agent: 好的，流程如下：
       1. 记录 baseline
       2. 识别最弱维度
       3. 提出修改计划并等您确认
       4. 修改 SKILL.md
       5. 展示 diff 和分数变化
       执行：improve-skill skills/bio-single-cell-clustering --record-baseline --suggest
Agent: 最弱维度是 D4。计划添加 requirements.txt，列出 scanpy、anndata、scikit-learn。
       是否批准？
User: 批准
Agent: [修改文件] 执行：improve-skill skills/bio-single-cell-clustering --judge
Agent: D4 从 1 提升到 4，总分从 68.8 提升到 78.2。是否保留？（保留/回滚）
```

---

## 9. What NOT to Do

- Do not build a chatbot wrapper or REST API around skillPrism.
- Do not let the engine parse natural language intent.
- Do not embed LLM judge logic into the engine.
- Do not default to `--apply`.
- Do not optimize multiple dimensions in one round.

---

## 10. Quick Start

```bash
# Install
pip install /path/to/Skills_Validation

# Copy the Agent entry
cp -r /path/to/Skills_Validation/skills/skill-prism ./skills/skill-prism
cp /path/to/Skills_Validation/skills/skill-prism/references/AGENT_GUIDE.md ./skills/skill-prism/references/AGENT_GUIDE.md

# First evaluation
evaluate-skill --all --skills-dir ./skills --output docs/SKILL_SCORECARD.md
```

From this point on, all interaction happens through the Agent and
`skills/skill-prism/SKILL.md`.
