"""Write daily discussion summary and raw archive artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").rstrip() + "\n"


def write_artifact(target: Path, text: str, mode: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if mode == "append" and target.exists():
        existing = target.read_text(encoding="utf-8").rstrip()
        target.write_text(existing + "\n\n" + text.rstrip() + "\n", encoding="utf-8")
    else:
        target.write_text(text.rstrip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write daily discussion archive artifacts.")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--summary-text-file", type=Path, required=True)
    parser.add_argument("--raw-text-file", type=Path, required=True)
    parser.add_argument("--summary-dir", default="docs/daily_discussion")
    parser.add_argument("--raw-dir", default="docs/daily_discussion/raw")
    parser.add_argument("--mode", choices=["overwrite", "append"], default="overwrite")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    summary_target = project_root / args.summary_dir / f"{args.date}.md"
    raw_target = project_root / args.raw_dir / f"{args.date}.md"

    write_artifact(summary_target, read_text(args.summary_text_file), args.mode)
    write_artifact(raw_target, read_text(args.raw_text_file), args.mode)

    print(f"summary={summary_target}")
    print(f"raw={raw_target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
