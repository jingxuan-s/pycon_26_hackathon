"""Run the full M7 demo validation package."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALIDATORS = [
    "scripts/validate_m1_data.py",
    "scripts/validate_m2_scoring.py",
    "scripts/validate_m3_questionnaire.py",
    "scripts/validate_m4_pathway.py",
    "scripts/validate_m5_report.py",
    "scripts/validate_m6_telegram.py",
    "scripts/validate_explainer_agent.py",
]
REQUIRED_ARTIFACTS = [
    "data/processed/data_quality_report.md",
    "data/processed/m2_scoring_example.md",
    "data/processed/m3_questionnaire_demo.md",
    "data/processed/m4_pathway_graph_demo.md",
    "data/processed/m5_explainability_action_plan.md",
    "data/processed/m6_telegram_flow_demo.md",
    "docs/daily_discussion/2026-06-19.md",
    "docs/daily_discussion/raw/2026-06-19.md",
    "docs/project_brief.md",
    "docs/roadmap.md",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_validator(script: str) -> dict[str, object]:
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    start = time.perf_counter()
    completed = subprocess.run(
        [sys.executable, script],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    duration = time.perf_counter() - start
    return {
        "script": script,
        "returncode": completed.returncode,
        "duration_seconds": duration,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def main() -> int:
    missing = [artifact for artifact in REQUIRED_ARTIFACTS if not (PROJECT_ROOT / artifact).exists()]
    require(not missing, f"Missing required M7 artifacts: {missing}")

    results = [run_validator(script) for script in VALIDATORS]
    failures = [result for result in results if result["returncode"] != 0]
    require(not failures, f"Validation failures: {[failure['script'] for failure in failures]}")

    report_lines = [
        "# M7 Demo Validation Report",
        "",
        "## End-to-End Scenario",
        "",
        "Current role: Financial Services / Digital and Data Analytics / Data Analyst",
        "Target pathway: Financial Services / Digital and Data Analytics / Data Scientist",
        "Interface surface: Telegram-style command/button flow plus generated Markdown report",
        "",
        "## Validation Results",
        "",
        "| Validator | Status | Duration Seconds | Key Output |",
        "| --- | --- | --- | --- |",
    ]
    for result in results:
        first_line = result["stdout"].splitlines()[0] if result["stdout"] else ""
        report_lines.append(
            f"| `{result['script']}` | PASS | {result['duration_seconds']:.2f} | {first_line} |"
        )

    report_lines.extend(
        [
            "",
            "## Required Artifacts",
            "",
        ]
    )
    for artifact in REQUIRED_ARTIFACTS:
        report_lines.append(f"- `{artifact}`")

    report_lines.extend(
        [
            "",
            "## Acceptance Summary",
            "",
            "- One complete end-to-end demo path works from questionnaire baseline to generated action plan.",
            "- Data integrity checks are visible through M1 data quality report and validation script.",
            "- Explainability checks pass through M5 report validation.",
            "- Telegram MVP flow is validated without requiring a live token.",
            "- Process artifacts are ready under `docs/daily_discussion/`.",
            "",
        ]
    )

    output_path = PROJECT_ROOT / "data" / "processed" / "m7_demo_validation_report.md"
    output_path.write_text("\n".join(report_lines), encoding="utf-8")

    print("M7 validation passed")
    print(f"validators={len(results)}")
    print(f"artifacts={len(REQUIRED_ARTIFACTS)}")
    print(f"output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
