#!/usr/bin/env python3
"""Dimension D4: Environment evaluator."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from ..utils import _any_file_exists, _dim_name
from ..utils import read_skill_md as _read_skill_md

if TYPE_CHECKING:
    from ..evaluate_skill_rubric import DimensionResult


def evaluate_d4_environment(
    skill_path: Path,
    skill_type: str,
    config: Dict[str, Any],
    verbose: bool = False,
    llm_judge: Optional[Any] = None,
) -> DimensionResult:
    from ..evaluate_skill_rubric import _score_from_checks

    type_cfg = config.get("skill_types", {}).get(skill_type, {})
    checks: List[Tuple[bool, str, str]] = []

    dep_candidates = (
        type_cfg.get("dimension_checks", {}).get("D1", {}).get("dependency_file_candidates", [])
    )
    has_dep_file = _any_file_exists(skill_path, dep_candidates)
    if dep_candidates:
        checks.append(
            (
                has_dep_file,
                "存在依赖/环境/资源说明文件",
                f"缺少依赖/环境/资源文件: {dep_candidates}",
            )
        )

    content = _read_skill_md(skill_path).lower()
    has_version = "version" in content or "兼容" in content or "api version" in content
    checks.append((has_version, "SKILL.md 包含版本/兼容性说明", "缺少版本兼容性说明"))

    if skill_type == "analysis":
        has_req = (skill_path / "requirements.txt").exists()
        if has_req:
            req_text = (skill_path / "requirements.txt").read_text(
                encoding="utf-8", errors="replace"
            )
            lines = [
                line.strip()
                for line in req_text.splitlines()
                if line.strip() and not line.startswith("#")
            ]
            pinned = any(re.search(r"[>=~]=", line) or "==" in line for line in lines)
            checks.append(
                (
                    pinned,
                    "requirements.txt 包含版本约束",
                    "requirements.txt 未指定版本或为空",
                )
            )
        else:
            checks.append((True, "无 requirements.txt，跳过版本约束检查", ""))

    elif skill_type == "cmd":
        has_ref_data = any(
            k in content for k in ["reference", "genome", "index", "参考基因组", "索引"]
        )
        checks.append((has_ref_data, "声明参考基因组/索引等必需输入", "缺少参考数据声明"))

    elif skill_type == "api":
        has_rate_limit = any(
            k in content for k in ["rate limit", "timeout", "retry", "速率限制", "超时"]
        )
        checks.append((has_rate_limit, "包含速率限制/超时/重试说明", "缺少 API 调用稳健性提示"))

    else:  # document / generic
        has_format = any(
            k in content
            for k in ["apa", "ama", "vancouver", "nature", "ieee", "gb/t", "format", "citation"]
        )
        checks.append((has_format, "包含引用/格式标准说明", "缺少引用格式标准说明"))

    # Optional docker bonus (look next to the skills directory)
    project_root = skill_path.parent.parent
    docker_present = (project_root / "docker").is_dir() and any(
        (project_root / "docker").glob("Dockerfile*")
    )
    checks.append(
        (
            docker_present,
            "项目提供 Docker 环境（可选加分）",
            "项目未提供 Docker 环境（非强制）",
        )
    )

    result = _score_from_checks(checks)
    result.code = "D4"
    result.name = _dim_name("D4", skill_type, config)
    return result
