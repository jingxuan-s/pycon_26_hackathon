#!/usr/bin/env python3
"""Write daily discussion summary and raw archive files."""

from __future__ import annotations

import argparse
from pathlib import Path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip() + "\n"


def write_file(path: Path, content: str, mode: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode == "append" and path.exists():
        existing = path.read_text(encoding="utf-8")
        separator = "\n\n---\n\n"
        path.write_text(existing.rstrip() + separator + content.lstrip(), encoding="utf-8")
    else:
        path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Write daily discussion summary and raw markdown archive.")
    parser.add_argument("--project-root", required=True, help="Project/repository root directory.")
    parser.add_argument("--date", required=True, help="Archive date in YYYY-MM-DD format.")
    parser.add_argument("--summary-text-file", required=True, help="Markdown file containing compact summary content.")
    parser.add_argument("--raw-text-file", required=True, help="Markdown file containing raw archive content.")
    parser.add_argument("--summary-dir", default="docs/daily_discussion", help="Summary directory relative to project root.")
    parser.add_argument("--raw-dir", default="docs/daily_discussion/raw", help="Raw archive directory relative to project root.")
    parser.add_argument("--mode", choices=["overwrite", "append"], default="overwrite", help="Write mode for existing files.")
    args = parser.parse_args()

    project_root = Path(args.project_root).expanduser().resolve()
    summary_source = Path(args.summary_text_file).expanduser().resolve()
    raw_source = Path(args.raw_text_file).expanduser().resolve()

    if not project_root.exists():
        raise SystemExit(f"Project root does not exist: {project_root}")
    if not summary_source.exists():
        raise SystemExit(f"Summary text file does not exist: {summary_source}")
    if not raw_source.exists():
        raise SystemExit(f"Raw text file does not exist: {raw_source}")

    summary_path = project_root / args.summary_dir / f"{args.date}.md"
    raw_path = project_root / args.raw_dir / f"{args.date}.md"

    write_file(summary_path, read_text(summary_source), args.mode)
    write_file(raw_path, read_text(raw_source), args.mode)

    print(f"summary={summary_path}")
    print(f"raw={raw_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())