"""Generate a local workflow preview for questionnaire and UX refinement."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path



PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from jobs_skills.workflow_preview import WorkflowPreviewConfig, build_local_workflow_preview


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a local questionnaire/workflow preview Markdown file.")
    parser.add_argument("--current-role", default="Data Analyst", help="Current baseline job role.")
    parser.add_argument("--current-sector", default="Financial Services", help="Current baseline sector.")
    parser.add_argument("--current-track", default="Digital and Data Analytics", help="Current baseline track.")
    parser.add_argument("--target-role", default="Data Scientist", help="Target pathway job role.")
    parser.add_argument("--target-sector", default="Financial Services", help="Target pathway sector.")
    parser.add_argument("--target-track", default="Digital and Data Analytics", help="Target pathway track.")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data" / "processed" / "local_workflow_preview.md")
    args = parser.parse_args()

    config = WorkflowPreviewConfig(
        current_job_role=args.current_role,
        current_sector=args.current_sector,
        current_track=args.current_track,
        target_job_role=args.target_role,
        target_sector=args.target_sector,
        target_track=args.target_track,
    )
    preview = build_local_workflow_preview(PROJECT_ROOT, output_path=args.output, config=config)
    print("Local workflow preview generated")
    print(f"output={preview.output_path}")
    print(f"ux_flags={preview.issue_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
