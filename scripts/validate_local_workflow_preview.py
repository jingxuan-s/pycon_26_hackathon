"""Validate local workflow preview tooling for questionnaire UX refinement."""

from __future__ import annotations

import sys
from pathlib import Path



PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from jobs_skills.workflow_preview import WorkflowPreviewConfig, build_local_workflow_preview, compact_skill_description
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "local_workflow_preview.md"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    preview = build_local_workflow_preview(PROJECT_ROOT, output_path=OUTPUT_PATH, config=WorkflowPreviewConfig())
    text = preview.output_path.read_text(encoding="utf-8")

    require(preview.output_path.exists(), "Local workflow preview file must be generated")
    require("# Local Workflow Preview" in text, "Preview must have the expected title")
    require("Telegram compact:" in text, "Preview must include Telegram compact prompts")
    require("Full dataset detail:" in text, "Preview must preserve full dataset detail outside Telegram")
    require("## Recommendation Presentation" in text, "Preview must include recommendation presentation")
    require("## UX Flags" in text, "Preview must include UX flags")
    require("Scoring formulas are unchanged" in text, "Preview must state scoring is unchanged")

    compact = compact_skill_description(
        "Construct solutions based upon logic, imagination, intuition and systemic reasoning to explore possibilities of what can be and create desired outcomes that benefit the organisation and customers when designing logistics solutions.",
        limit=118,
    )
    require(len(compact) <= 118, "Compact description must respect the local character limit")
    require("..." not in compact, "Compact description must avoid ellipsis-style Telegram cutoff")

    print("Local workflow preview validation passed")
    print(f"output={preview.output_path}")
    print(f"ux_flags={preview.issue_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
