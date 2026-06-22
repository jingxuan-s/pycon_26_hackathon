"""Validate privacy-safe live Telegram event log acceptance evidence."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


REQUIRED_ACTIONS = {
    "start_assessment",
    "select_current_role",
    "recommend_roles",
    "choose_pathway",
    "explain_score",
    "show_gaps",
    "show_pathway",
    "generate_action_plan",
}


class LiveEventValidationError(AssertionError):
    """Raised when the live Telegram event log does not prove the N1 flow."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LiveEventValidationError(message)


def load_events(path: Path) -> list[dict[str, Any]]:
    require(path.exists(), f"Missing live event log: {path}")
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LiveEventValidationError(f"Invalid JSON on line {line_number}: {exc}") from exc
        require(isinstance(event, dict), f"Event line {line_number} must be a JSON object")
        events.append(event)
    require(events, f"Live event log is empty: {path}")
    return events


def validate_events(events: list[dict[str, Any]]) -> Counter[str]:
    actions = Counter(str(event.get("action", "")) for event in events)
    missing = sorted(action for action in REQUIRED_ACTIONS if actions[action] == 0)
    require(not missing, f"Missing required live actions: {missing}")
    require(actions["answer_question"] >= 10, "Live flow must include at least 10 baseline answer callbacks")
    require(actions["answer_gap_question"] >= 5, "Live flow must include at least 5 target-gap answer callbacks")

    generate_events = [event for event in events if event.get("action") == "generate_action_plan"]
    require(any(event.get("has_attachment") is True for event in generate_events), "Action plan event must report an attachment")

    for index, event in enumerate(events, start=1):
        keys = set(event)
        forbidden = {"chat_id", "session_id", "message_text", "response_text", "answer", "token"}
        leaked = sorted(keys & forbidden)
        require(not leaked, f"Event {index} contains forbidden private fields: {leaked}")
        require("timestamp_utc" in event, f"Event {index} missing timestamp_utc")
        require("button_count" in event, f"Event {index} missing button_count")
        require("has_attachment" in event, f"Event {index} missing has_attachment")

    return actions


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate live Telegram event-log evidence for N1.")
    parser.add_argument(
        "event_log",
        type=Path,
        nargs="?",
        default=Path("C:/tmp/pycon_telegram_bot.events.jsonl"),
        help="Path to privacy-safe live Telegram JSONL event log.",
    )
    args = parser.parse_args()

    events = load_events(args.event_log)
    actions = validate_events(events)
    print("Live Telegram event validation passed")
    print(f"events={len(events)}")
    print(f"answer_question={actions['answer_question']}")
    print(f"answer_gap_question={actions['answer_gap_question']}")
    print(f"generate_action_plan={actions['generate_action_plan']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
