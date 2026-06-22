"""Validate future-work evidence for live adapter, parser stretch, and policy hooks."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "data" / "processed" / "future_work_validation_report.md"
DEFAULT_LIVE_EVENT_LOG = Path("C:/tmp/pycon_telegram_bot.events.jsonl")

VALIDATORS = [
    "scripts/validate_telegram_adapter.py",
    "scripts/validate_f1_f3_parser_agents.py",
    "scripts/validate_f4_f5_policy_options.py",
]
REQUIRED_ARTIFACTS = [
    "scripts/run_telegram_bot.py",
    "docs/telegram_live_testing.md",
    "src/jobs_skills/parser_agents.py",
    "scripts/validate_f1_f3_parser_agents.py",
    "scripts/validate_f4_f5_policy_options.py",
    "data/processed/f3_resume_jd_suitability_demo.md",
    "data/processed/f4_f5_policy_options_demo.md",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_validator(script: str, *extra_args: str) -> dict[str, object]:
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    start = time.perf_counter()
    completed = subprocess.run(
        [sys.executable, script, *extra_args],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "script": script,
        "returncode": completed.returncode,
        "duration_seconds": time.perf_counter() - start,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate future-work evidence for the jobs-skills MVP.")
    parser.add_argument("--live-event-log", type=Path, default=DEFAULT_LIVE_EVENT_LOG, help="Privacy-safe live Telegram event log path.")
    parser.add_argument("--require-live-event-log", action="store_true", help="Fail if the live Telegram event log is missing.")
    args = parser.parse_args()

    missing = [artifact for artifact in REQUIRED_ARTIFACTS if not (PROJECT_ROOT / artifact).exists()]
    require(not missing, f"Missing future-work artifacts: {missing}")

    results = [run_validator(script) for script in VALIDATORS]
    live_event_result: dict[str, object] | None = None
    live_event_warning: str | None = None
    if args.live_event_log.exists():
        live_event_result = run_validator("scripts/validate_telegram_live_events.py", str(args.live_event_log))
        if live_event_result["returncode"] == 0:
            results.append(live_event_result)
        elif args.require_live_event_log:
            results.append(live_event_result)
        else:
            live_event_warning = str(live_event_result["stderr"] or live_event_result["stdout"] or "Live event validation failed.")
    elif args.require_live_event_log:
        raise AssertionError(f"Missing required live Telegram event log: {args.live_event_log}")

    failures = [result for result in results if result["returncode"] != 0]
    require(not failures, f"Future-work validation failures: {[failure['script'] for failure in failures]}")

    lines = [
        "# Future Work Validation Report",
        "",
        "## Scope",
        "",
        "This report validates the implemented future-work pieces: live Telegram adapter mechanics, parser evidence extraction, deterministic resume-to-JD suitability, optional weighting policy hooks, and sector constraint modes.",
        "",
        "## Validation Results",
        "",
        "| Validator | Status | Duration Seconds | Key Output |",
        "| --- | --- | --- | --- |",
    ]
    for result in results:
        first_line = result["stdout"].splitlines()[0] if result["stdout"] else ""
        lines.append(f"| `{result['script']}` | PASS | {result['duration_seconds']:.2f} | {first_line} |")

    lines.extend(["", "## Live Telegram Evidence", ""])
    if live_event_result is None:
        lines.append(f"No privacy-safe live event log was present at `{args.live_event_log}` during this validation run. The adapter is validated without a token; run the manual Telegram flow with `--event-log` to capture live button evidence. Use `--require-live-event-log` for final strict completion checks.")
    elif live_event_result["returncode"] == 0:
        lines.append("Privacy-safe live event evidence was found and validated.")
    else:
        lines.append("Privacy-safe live event evidence exists but is incomplete in non-strict mode.")
        lines.append("")
        lines.append("```text")
        lines.append(live_event_warning or "Live event validation failed.")
        lines.append("```")

    lines.extend(["", "## Required Artifacts", ""])
    for artifact in REQUIRED_ARTIFACTS:
        lines.append(f"- `{artifact}`")

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("Future-work validation passed")
    print(f"validators={len(results)}")
    print(f"live_event_log={'present' if live_event_result else 'missing'}")
    print(f"output={REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
