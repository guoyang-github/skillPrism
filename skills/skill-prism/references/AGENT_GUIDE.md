# Agent-Native Interaction Guide for skillPrism

This guide standardizes how an AI agent should behave when using `skills/skill-prism/SKILL.md` as the unified interface. It complements SKILL.md: SKILL.md maps user intents to engine commands; this guide defines the Agent's tone, approval checkpoints, and reporting conventions.

---

## 1. Greeting & Plan

When the user invokes skillPrism, always:

1. Confirm the intent in your own words.
2. State what you will do and what you will **not** do without approval.
3. List the exact commands you are about to run.

**Template:**

> I'll run the skill quality pipeline for you. This will:
> 1. Evaluate all skills with the rubric.
> 2. Run benchmarks against the registry.
> 3. Identify the lowest-scoring skill and prepare an optimization baseline.
>
> I will **not** edit any SKILL.md or code files without your explicit approval.

---

## 2. Command Blocks

Always present engine commands in a fenced code block so the user can copy/paste or audit them. Prefer the installed CLI form:

```bash
evaluate-skill --all --skills-dir ./skills --run-smoke
```

---

## 3. Approval Checkpoints

Pause and ask for approval before:

- Editing a `SKILL.md`.
- Editing code assets (`scripts/`, `examples/`, `requirements.txt`).
- Running `--apply` after `--judge`.
- Updating a benchmark baseline via `--ratchet`.
- Overwriting an existing scorecard or benchmark baseline.

**Confirmation prompt template:**

> I plan to edit `skills/bio-single-cell-clustering/SKILL.md` to improve D4
> (dependency reproducibility) by adding a `requirements.txt` section.
> The predicted score gain is +3.2. Proceed? (yes/no/show diff first)

---

## 4. Showing Diff

After any edit and before `--judge --apply`, show a concise diff summary:

```bash
git diff -- skills/<skill>/SKILL.md
```

If the directory is not a git repo, show the first 20 changed lines and warn the user that automatic revert is unavailable.

---

## 5. Interpreting `--judge` Output

`--judge` is dry-run by default. When you show the output to the user, translate the engine decision into natural language:

- `Decision: KEEP` → "The edit improves the rubric score and benchmark does not regress. Say 'apply' to keep it."
- `Decision: REVERT` → "The edit does not improve the score or benchmark regresses. I recommend reverting. Say 'apply' to confirm the revert, or 'try another edit'."
- Any `guard block` line → "This edit triggers a safety guard. I will not apply it without your explicit override."

Never silently add `--apply` unless the user explicitly says "auto", "无需确认", or similar.

---

## 6. Failure Recovery

If a command fails:

1. Print the last 5 lines of stderr (no full trace unless asked).
2. Propose the most likely fix.
3. Ask before retrying.

**Template:**

> The benchmark failed because `scanpy` is not installed. I can:
> - (a) skip the benchmark and run rubric only, or
> - (b) create a fresh virtual environment and install the benchmark dependencies.
> Which would you prefer?

---

## 7. Final Report Format

End every skill invocation with a short, structured summary:

```markdown
## Summary
- Skill evaluated: `bio-single-cell-clustering`
- Rubric score: 62.3 / 100 (Grade C)
- Benchmark: PASS (1/1)
- Weakest dimension: D4
- Next step: Add a `requirements.txt` and re-run `--judge`.
- Action required by user: approve the proposed edit.
```

---

## 8. Gradual Test Mode

When invoking `test-skill --mode gradual`:

1. **Default to `--max-level 2`** unless the user explicitly asks for real-data acceptance.
2. **Explain the cost** before level 3: GPU time, data size, runtime.
3. **Stop and diagnose** on first failure; never proceed to later levels automatically.
4. **Real-data benchmarks are completion-only**: report `_all_pass`, not numerical scores.
5. **Failure diagnosis order**:
   - Read `artifacts/<skill>/ci/test/level<N>/results.yaml`.
   - Identify failing benchmark and whether `_real_data` is true.
   - Check `error` (runtime), `_metric_pass` (regression), or missing benchmark (registry mismatch).
   - Map level to likely cause (level 0 = syntax/shape, level 1 = logic, level 2 = stability, level 3 = real-data/resource).
6. **Recovery flow**:
   - Level 0/1/2 fail → recommend `improve-skill` or manual edit, then re-run `test-skill --mode gradual`.
   - Level 3 fail → inspect logs for OOM/GPU/data issues, fix environment, then re-run level 3 only.

---

## 9. Natural-Language First

Do not expose the user to engine internals unless they ask. Map their request to the canonical command and present it concisely:

```text
User: 给所有 skills 打个分
Agent: 我来对所有 skills 做 Rubric 评估并生成 scorecard。
       执行：evaluate-skill --all --skills-dir ./skills --output reports/SKILL_SCORECARD.md
```

If the user's phrasing is ambiguous, confirm the interpreted intent before running the command.

## 10. Tone and Safety Defaults

- Be concise; avoid over-explaining.
- Never claim the engine uses an LLM unless `--llm-judge` is explicitly enabled.
- Never run destructive git operations (`reset --hard`, force-push) or `rm -rf`.
- Prefer `--judge` (dry-run) over `--judge --apply`.
- When in doubt, ask the user before mutating files.
