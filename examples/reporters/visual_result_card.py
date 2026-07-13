#!/usr/bin/env python3
"""Generate a visual result card for a skill optimization run.

Usage:
    python examples/reporters/visual_result_card.py \
        --input artifacts/<skill>/baseline/optimization_result.json \
        --output result-card.html

Optional:
    --screenshot    Capture a PNG screenshot using playwright (if installed)
"""

from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

TEMPLATE = Path(__file__).parents[2] / "templates" / "skill_standard" / "result-card.html"


def load_result(result_path: Path) -> Dict[str, Any]:
    return json.loads(result_path.read_text(encoding="utf-8"))


def _extract_dimension_bars(dimensions: List[Dict[str, Any]]) -> str:
    lines = []
    for dim in dimensions:
        code = dim.get("code", "D?")
        name = dim.get("name", code)
        before = dim.get("baseline_score", 0)
        after = dim.get("current_score", before)
        before_pct = max(5, int(before * 20))
        after_pct = max(5, int(after * 20))
        lines.append(
            f'<div class="dim-row">'
            f'<div class="dim-label">{code} {name}</div>'
            f'<div class="dim-bars">'
            f'<div class="bar bar-before" style="width: {before_pct}%"></div>'
            f'<div class="bar bar-after" style="width: {after_pct}%"></div>'
            f"</div></div>"
        )
    return "\n".join(lines)


def _extract_improvements(result: Dict[str, Any]) -> List[str]:
    improvements = []
    dimension_changes = result.get("dimension_changes", {})
    for code, delta in sorted(dimension_changes.items(), key=lambda x: -x[1]):
        if delta > 0:
            improvements.append(f"{code}: improved by +{delta}")
    if not improvements:
        improvements.append("Optimization completed")
    return improvements[:3]


def generate_card(result_path: Path, output_path: Path, theme: Optional[str] = None) -> Path:
    result = load_result(result_path)
    html = TEMPLATE.read_text(encoding="utf-8")

    skill_name = result.get("skill", "my-skill")
    before = result.get("baseline_score", 0.0)
    after = result.get("current_score", 0.0)
    delta = after - before

    html = re.sub(r'data-field="skill-name">[^<]*<', f'data-field="skill-name">{skill_name}<', html)
    html = re.sub(
        r'data-field="score-before">[^<]*<', f'data-field="score-before">{before:.1f}<', html
    )
    html = re.sub(
        r'data-field="score-after">[^<]*<', f'data-field="score-after">{after:.1f}<', html
    )
    html = re.sub(
        r'data-field="score-delta">[^<]*<',
        f'data-field="score-delta">{"+" if delta >= 0 else ""}{delta:.1f}<',
        html,
    )

    dimensions = result.get("current_report", {}).get("dimensions", [])
    bars_html = _extract_dimension_bars(dimensions)
    html = re.sub(
        r'(<div data-field="dimensions">).*?(</div>)',
        r"\1\n" + bars_html + r"\n\2",
        html,
        flags=re.DOTALL,
    )

    improvements = _extract_improvements(result)
    for i, imp in enumerate(improvements, start=1):
        html = re.sub(
            rf'data-field="improvement-{i}">[^<]*<',
            f'data-field="improvement-{i}">{imp}<',
            html,
        )

    # Theme hash
    if theme is None:
        theme = random.choice(["swiss", "terminal", "newspaper"])
    # For now we use the single template; future versions can load theme CSS.

    output_path.write_text(html, encoding="utf-8")
    return output_path


def capture_screenshot(html_path: Path, png_path: Path) -> None:
    """Try to capture a screenshot using playwright CLI."""
    try:
        subprocess.run(
            [
                "python",
                "-m",
                "playwright",
                "screenshot",
                f"file://{html_path.absolute()}",
                str(png_path),
                "--viewport-size=960,1280",
                "--wait-for-timeout=2000",
            ],
            check=True,
            capture_output=True,
        )
        print(f"Screenshot saved: {png_path}")
    except FileNotFoundError:
        print(
            "playwright CLI not found; install with 'pip install playwright' and run 'playwright install'"
        )
    except subprocess.CalledProcessError as e:
        print(f"Screenshot failed: {e}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a visual skill optimization result card")
    parser.add_argument("--input", required=True, help="Path to optimization result JSON")
    parser.add_argument("--output", required=True, help="Output HTML path")
    parser.add_argument("--screenshot", action="store_true", help="Also capture PNG screenshot")
    parser.add_argument("--theme", choices=["swiss", "terminal", "newspaper"], help="Card theme")
    args = parser.parse_args()

    output = Path(args.output)
    generate_card(Path(args.input), output, theme=args.theme)
    print(f"Card saved: {output}")

    if args.screenshot:
        png_path = output.with_suffix(".png")
        capture_screenshot(output, png_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
