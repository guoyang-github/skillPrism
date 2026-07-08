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
        - save_baseline
        - load_baseline
        - JudgeResult
        - render_diff
        - snapshot_code_assets
        - restore_code_assets

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
