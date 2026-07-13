# 新增 Benchmark 任务类型

> **本文是 skillPrism 扩展机制（任务插件）的唯一权威文档。**
>
> skillPrism 引擎**没有内置的 benchmark 任务类型**。`table`、`clustering`、`document`、`deconvolution` 只是 examples 随附的 task spec（`benchmarks/<skill>/tasks/<task>.yaml`）所用的名字，不是引擎里的实现分支——`skillprism/benchmark/tasks/` 是空目录，引擎也不会加载 `benchmarks/<skill>/runner.py`。
>
> 引擎主路径（`skillprism/benchmark/runner.py` 的 `run_single_benchmark`）只有三条：任务插件命中 → 插件接管；否则加载 task spec，用 `CodeExecutor`（`--code`）或 `AgentExecutor` 执行；`--results` 模式则只评估已有输出。如果声明式 task spec 满足不了你的执行需求，可以通过插件机制扩展新的任务类型，而无需修改引擎源码。

## task spec（声明式契约）vs 插件（可调用 harness）

两者解决不同层面的问题，先选对工具再动手：

| | task spec | 任务插件 |
|---|---|---|
| 本质 | YAML 声明：`id/skill/name/description/prompt/input/output`，prompt 用 `{placeholder}` 注入真实路径 | Python 可调用对象，完全接管单个 benchmark 的执行 |
| 适用 | 执行方式通用（跑 `--code` 生成的代码或 Agent），只需换 prompt/输入输出格式 | 执行方式特殊：外部 CLI、复杂多步流程、自定义评估逻辑 |
| 评估 | 一律走 `GenericEvaluator` + 已注册 metric | 插件自行计算并返回结果字典（可复用 `metric_passes`） |
| 注册 | 放进 `benchmarks/<skill>/tasks/<task>.yaml`，registry 条目用 `task: <task>` 引用 | registry `plugins` 字段或 `skillprism.benchmark.task` entry point |

优先级：benchmark 的 `task` 字段先查插件注册表；**未命中时才回退到 task spec 驱动的通用执行**（不是回退到某个"内置任务"）。因此一个与 task spec 同名的插件会静默接管该 task 名下所有 benchmark。

## 两种扩展方式

| 方式 | 适用场景 | 优点 | 缺点 |
|---|---|---|---|
| **Registry 插件** | 某个项目独有的任务类型 | 无需打包、随 registry 一起分发 | 只对当前 registry 生效 |
| **Entry-point 插件** | 通用任务类型，想在多个项目复用 | 安装包后全局生效 | 需要单独打包/安装 |

## 插件接口约定

一个任务插件必须是一个可调用对象，签名如下：

```python
from pathlib import Path
from typing import Any, Dict, Optional


def my_task(
    benchmark: Dict[str, Any],
    skill: str,
    code_path: Optional[Path],
    registry: Dict[str, Any],
    registry_dir: Path,
) -> Dict[str, Any]:
    """Run a single benchmark of a custom task type.

    Args:
        benchmark: 当前 benchmark 的注册表字典（已注入 ``_id``）。
        skill: 当前跑的 skill name（即 skill type）。
        code_path: Skill 生成的代码文件路径，可能为 None。
        registry: 完整注册表字典。
        registry_dir: 注册表文件所在目录，用于解析相对路径。

    Returns:
        必须包含 ``_all_pass`` (bool)。建议包含具体指标、``_metric_pass``、
        ``error`` 等字段，与引擎的结果格式保持一致。
    """
    ...
```

返回值最小示例：

```python
return {
    "my_metric": 0.95,
    "_metric_pass": {"my_metric": True},
    "_all_pass": True,
}
```

## 方式一：Registry 插件（推荐，项目内使用）

### 1. 编写插件模块

在 benchmark 目录下创建 `plugins/my_task.py`：

```python
#!/usr/bin/env python3
"""Custom benchmark task: time-series anomaly detection."""

from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd


def run(
    benchmark: Dict[str, Any],
    skill: str,
    code_path: Optional[Path],
    registry: Dict[str, Any],
    registry_dir: Path,
) -> Dict[str, Any]:
    """Run anomaly detection benchmark."""
    # 1. 加载数据
    dataset_spec = benchmark["dataset"]
    source = dataset_spec["source"]
    if dataset_spec.get("type", "local") == "local":
        input_path = registry_dir / source
    else:
        input_path = Path(source)

    df = pd.read_csv(input_path, parse_dates=["timestamp"])

    # 2. 加载 skill 代码（可选）
    skill_code = ""
    if code_path and code_path.exists():
        skill_code = code_path.read_text(encoding="utf-8")

    # 3. 执行 skill 代码
    output_dir = Path(registry.get("cache_dir", ".benchmark_cache")) / "output" / benchmark["_id"]
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "anomalies.csv"

    namespace = {
        "df": df,
        "output_csv": str(output_path),
        "output_dir": str(output_dir),
    }
    exec(skill_code, namespace)

    # 4. 评估
    output_df = pd.read_csv(output_path)
    n_anomalies = int(output_df["is_anomaly"].sum())
    precision = float(n_anomalies / len(output_df))  # 示例指标

    from skillprism.benchmark.metrics import metric_passes

    metrics_spec = benchmark.get("metrics", [])
    passed = {}
    for spec in metrics_spec:
        metric_id = spec["id"]
        value = {"n_anomalies": n_anomalies, "precision": precision}.get(metric_id)
        passed[metric_id] = metric_passes(value, spec)

    return {
        "n_anomalies": n_anomalies,
        "precision": precision,
        "_metric_pass": passed,
        "_all_pass": all(passed.values()),
    }
```

### 2. 在注册表中声明插件

```yaml
schema_version: "2.0"

plugins:
  # 字典形式：显式指定注册名（benchmark 的 task 字段按此名命中）
  - name: anomaly_detection
    source: plugins.anomaly_detection.run
  # 字符串形式：注册名取模块的 TASK_NAME 属性，缺省取路径最后一段（这里是 run）
  # - plugins.anomaly_detection.run

benchmarks:
  sales_anomaly:
    name: Sales Anomaly Detection
    skill: anomaly-detection-skill
    task: anomaly_detection
    dataset:
      source: data/sales/input/sales.csv
      type: local
    expected:
      format: csv
      path: expected/sales/anomalies.csv
    metrics:
      - id: precision
        type: min
        threshold: 0.80
```

注意：插件模块按标准 Python import 解析（`importlib.import_module`），引擎**不会**把 registry 目录加入 `sys.path`。请保证从项目根目录运行（模块可从此处 import）或将插件打包安装，否则加载会静默失败、benchmark 回退到 task spec 路径。

### 3. 运行

```bash
test-skill --mode single \
  --skill anomaly-detection-skill \
  --registry benchmarks/anomaly-detection-skill/registry.yaml \
  --code sample_skill_code.py
```

## 方式二：Entry-point 插件（跨项目复用）

### 1. 创建一个 Python 包

```text
skillprism_anomaly/
├── pyproject.toml
└── skillprism_anomaly/
    ├── __init__.py
    └── task.py
```

`skillprism_anomaly/task.py`：

```python
from pathlib import Path
from typing import Any, Dict, Optional


def run(
    benchmark: Dict[str, Any],
    skill: str,
    code_path: Optional[Path],
    registry: Dict[str, Any],
    registry_dir: Path,
) -> Dict[str, Any]:
    ...  # 同上
```

### 2. 在 pyproject.toml 注册 entry point

```toml
[project.entry-points."skillprism.benchmark.task"]
anomaly_detection = "skillprism_anomaly.task:run"
```

### 3. 安装包

```bash
pip install -e ./skillprism_anomaly
```

安装后，任何 skillPrism benchmark registry 都可以直接使用 `task: anomaly_detection`，无需在 registry 里声明 `plugins`。

## 插件可用的内置能力

插件不需要从零开始。skillPrism 提供了一些可复用工具：

| 工具 | 用途 | 导入路径 |
|---|---|---|
| `fetch_dataset` | 加载 `builtin` / `local` / `url` 数据集 | `skillprism.benchmark.download.fetch_dataset` |
| `metric_passes` | 判断单个指标是否通过阈值 | `skillprism.benchmark.metrics.metric_passes` |
| `run_task_boundary_tests` | 自动跑边界测试 | `skillprism.testing.boundary.run_task_boundary_tests` |

### 使用 `fetch_dataset` 的示例

```python
from skillprism.benchmark.download import fetch_dataset

cache_dir = Path(registry.get("cache_dir", ".benchmark_cache"))
input_data = fetch_dataset(benchmark["dataset"], cache_dir)
```

`input_data` 的类型取决于 `dataset.type`：

- `builtin`：Python 对象（如 AnnData）。
- `local` / `url`：`Path` 对象。

### 使用 `metric_passes` 的示例

```python
from skillprism.benchmark.metrics import metric_passes

passed = {}
for spec in benchmark.get("metrics", []):
    metric_id = spec["id"]
    value = results.get(metric_id)
    passed[metric_id] = metric_passes(value, spec)
```

## 为插件增加边界测试

如果你想让 level 0 benchmark 自动跑边界测试，需要两步：

1. 在插件里调用边界测试：

   ```python
   from skillprism.testing.boundary import run_task_boundary_tests, format_boundary_report

   boundary_dir = output_dir / ".boundary"
   report = run_task_boundary_tests("anomaly_detection", skill_code, boundary_dir)
   result["_boundary_report"] = format_boundary_report(report)
   ```

2. 在 `skillprism/testing/boundary.py` 或你的项目里为 `anomaly_detection` 注册边界 case（如果通用，建议提交到 skillPrism 上游）。

## 插件编写 checklist

- [ ] 函数签名与 `benchmark, skill, code_path, registry, registry_dir` 一致。
- [ ] 返回值包含 `_all_pass`。
- [ ] 指标与 `metrics` 规范对应，包含 `_metric_pass`。
- [ ] 异常时返回 `{"error": "...", "_all_pass": False}`。
- [ ] 如果 task 需要 runner，约定 `run(skill_code, input_data, output_dir) -> Path`。
- [ ] level 0 建议接入边界测试。
- [ ] 如果依赖重型包，在失败时给出安装提示，而不是直接崩溃。

## 示例：把 examples 里的 deconvolution 任务换成插件

examples 中的 `deconvolution`（如 `examples/benchmark_cell2location/`）不是引擎内置实现，只是一份 task spec（`tasks/deconvolution.yaml`）加上通用执行路径。如果你需要自定义执行逻辑（例如调用外部 R 脚本、多步 pipeline）：

1. 新建一个模块，实现 `run(benchmark, skill, code_path, registry, registry_dir)`。
2. 在 registry 里声明 `plugins`，注册名与 benchmark 的 `task` 字段一致（如 `deconvolution`）。
3. 引擎会优先匹配插件任务；插件未命中时才回退到 task spec 驱动的通用执行。

## 常见误区

1. **没有"内置任务"可回退。** 引擎不存在内置的 `table`/`clustering`/`document`/`deconvolution` 实现，那些只是 examples 自带的 task spec 名。插件未命中时回退的是 task spec 驱动的通用执行（task spec + `CodeExecutor`/`AgentExecutor`/`--results`），不是某个内置 harness。
2. **插件名必须与 `task` 字段完全一致。** Registry 插件的注册名来自字典形式的 `name`，或字符串形式的 `TASK_NAME` 属性 / 模块路径最后一段；`task` 字段写错名字会静默走 task spec 路径。
3. **插件不会自动出现在 `list_tasks()` 中。** `list_tasks()` 返回四个示例任务名与已加载插件的并集；registry 插件要先加载对应 registry（`run_benchmarks` 启动时调用 `load_registry_plugins`）才可见。
4. **插件里不要做 LLM 调用。** 保持引擎确定性；需要 LLM 生成代码时，在 `--code` 传入或在 Agent 侧完成。

## 相关扩展：自定义 Skill 模板

任务插件扩展的是 benchmark 执行；如果还想沉淀某类 skill 的脚手架，可以复制现有模板并修改：

```bash
cp -r templates/analysis templates/my-domain-analysis
```

仓库自带 `templates/` 下有 `analysis`、`api`、`cmd`、`document`、`skill_standard` 等模板，每个包含 `SKILL.md`、示例代码和 `requirements.txt`。修改 `SKILL.md` 的 frontmatter 和示例代码，使其符合你的领域即可。

## 向上游贡献

如果你的任务插件或边界 case 具有通用性，欢迎贡献到 skillPrism 上游：

1. 运行 `make test` 和 `make lint`，确保全部通过。
2. 新功能必须附带测试。
3. 更新相关文档（`docs/` 和 `README.md`）。
4. 提交 Pull Request。

## 延伸阅读

- [Benchmark 构造指南](./benchmark-guide.md)：从零创建 benchmark 的完整流程。
- [数据构建决策速查表](./data-building-decisions.md)：哪些数据能自动生成、哪些需要手动准备。
- `skillprism/benchmark/plugins.py`：插件加载机制的源码。
- `skillprism/benchmark/runner.py`：插件分发与 task spec 驱动执行路径的源码。
