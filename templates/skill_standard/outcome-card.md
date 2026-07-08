# Outcome Card: {{skill_name}}

> This card summarizes a completed skill optimization or evaluation run. It is meant to be shared with users or posted in a pull request.

## Skill Metadata

| Field | Value |
|---|---|
| **Name** | `{{skill_name}}` |
| **Path** | `{{skill_path}}` |
| **Type** | `{{skill_type}}` |
| **Version** | `{{version}}` |
| **Date** | `{{date}}` |

## Summary

- **Objective**: {{objective}}
- **Approach**: {{approach}}
- **Key changes**: {{key_changes}}

## Rubric Scores

| Dimension | Before | After | Delta |
|---|---|---|---|
| D1 Structure | {{d1_before}} | {{d1_after}} | {{d1_delta}} |
| D2 Documentation | {{d2_before}} | {{d2_after}} | {{d2_delta}} |
| D3 Executability | {{d3_before}} | {{d3_after}} | {{d3_delta}} |
| D4 Environment | {{d4_before}} | {{d4_after}} | {{d4_delta}} |
| D5 Domain accuracy | {{d5_before}} | {{d5_after}} | {{d5_delta}} |
| D6 LLM callability | {{d6_before}} | {{d6_after}} | {{d6_delta}} |
| D7 Robustness | {{d7_before}} | {{d7_after}} | {{d7_delta}} |
| D8 Maintainability | {{d8_before}} | {{d8_after}} | {{d8_delta}} |
| D9 Security | {{d9_before}} | {{d9_after}} | {{d9_delta}} |
| **Total** | **{{score_before}}** | **{{score_after}}** | **{{score_delta}}** |
| **Grade** | {{grade_before}} | {{grade_after}} | {{grade_delta}} |

## Benchmark Gate

- **Registry**: `{{benchmark_registry}}`
- **Status**: {{benchmark_status}}
- **Key metrics**: {{benchmark_metrics}}

## SkillLens Checks

- Failure mechanism encoding: {{lens_failure}}/5
- Actionable specificity: {{lens_specificity}}/5
- High-risk action blacklist: {{lens_risk}}/5
- Explicit checkpoints: {{lens_checkpoint}}/5

## Test Prompts

- `test-prompts.json`: {{test_prompts_status}}
- Count: {{test_prompts_count}}

## Runtime Neutrality

- Status: {{runtime_neutrality_status}}

## Guard Report

| Guard | Status | Notes |
|---|---|---|
| Self-judge | {{guard_self_judge}} | {{guard_self_judge_notes}} |
| Hard-reset block | {{guard_hard_reset}} | {{guard_hard_reset_notes}} |
| Bloat check | {{guard_bloat}} | {{guard_bloat_notes}} |
| Benchmark gate | {{guard_benchmark}} | {{guard_benchmark_notes}} |
| Multi-dimension alert | {{guard_multi_dim}} | {{guard_multi_dim_notes}} |
| Dry-run ratio | {{guard_dry_run}} | {{guard_dry_run_notes}} |
| Error silence | {{guard_error_silence}} | {{guard_error_silence_notes}} |
| Dimension cluster | {{guard_cluster}} | {{guard_cluster_notes}} |

## Artifacts

- Updated `SKILL.md`: `{{skill_md_path}}`
- Diff: `{{diff_path}}`
- Scorecard: `{{scorecard_path}}`
- History record: `{{history_path}}`

## Next Steps

- {{next_step_1}}
- {{next_step_2}}
- {{next_step_3}}

## Declaration

- [ ] I have reviewed the diff.
- [ ] I have run `make lint && make test && make docs-build`.
- [ ] I have confirmed no regression in benchmark gate.
- [ ] I have updated related documentation if needed.
