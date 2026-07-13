# API 参考

本页面由 [mkdocstrings](https://mkdocstrings.github.io/) 自动生成，展示 skillprism 核心模块的公开接口。

## 评估引擎

::: skillprism.evaluate_skill_rubric
    options:
      members:
        - evaluate_skill
        - load_config
        - SkillReport
        - DimensionResult

## 优化引擎

::: skillprism.optimize_skill
    options:
      members:
        - judge_candidate
        - JudgeResult
        - render_diff

## Baseline 与代码资产快照

::: skillprism._baseline
    options:
      members:
        - save_baseline
        - load_baseline
        - load_baseline_skill_md
        - clear_baseline
        - snapshot_code_assets
        - restore_code_assets

## LLM Judge

::: skillprism.llm_judge
    options:
      members:
        - LLMJudge
        - LLMJudgeResult
        - MultiJudgeResult

## Benchmark 运行器

::: skillprism.benchmark.runner
    options:
      members:
        - run_benchmarks
        - run_single_benchmark
        - load_registry

## Benchmark 插件

::: skillprism.benchmark.plugins
    options:
      members:
        - register
        - get_task
        - load_registry_plugins

## 渐进测试

::: skillprism.gradual
    options:
      members:
        - run_gradual_pipeline
        - run_gradual_stage

## CI 门控

::: skillprism.ci.cli
    options:
      members:
        - main

## Skill 编辑器

::: skillprism.skill_editor
    options:
      members:
        - SkillEditor
        - SkillEditorResult
        - build_editor_prompt

## 流水线编排

::: skillprism.orchestrator
    options:
      members:
        - main
