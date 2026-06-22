"""Validate the live Telegram adapter without using a real bot token."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from jobs_skills.telegram_bot import BotResponse, InlineButton


RUNNER_PATH = PROJECT_ROOT / "scripts" / "run_telegram_bot.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_runner_module():
    spec = importlib.util.spec_from_file_location("run_telegram_bot", RUNNER_PATH)
    require(spec is not None and spec.loader is not None, "Unable to load run_telegram_bot.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeClock:
    def __init__(self) -> None:
        self.value = 1000.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def main() -> int:
    runner = load_runner_module()

    result = runner.smoke_test_adapter(PROJECT_ROOT)
    require(result["question_text"] == "v2 start", "Smoke test must start the v2 entry menu")
    require(result["button_count"] == 3, "Start response must expose guide, resume, and role-search buttons")

    encoded = runner.callback_data("answer_question", "3.0")
    require(encoded == "answer_question|3.0", "Callback data must use action|value format")
    require(runner.parse_callback_data(encoded) == ("answer_question", "3.0"), "Callback parser must round-trip action and value")
    require(runner.parse_callback_data("explain_score|") == ("explain_score", ""), "Empty callback value must be supported")

    markup = runner.build_reply_markup(
        BotResponse(
            "Choose an action",
            (
                InlineButton("Why this score?", "explain_score", ""),
                InlineButton("Show skill gaps", "show_gaps", ""),
            ),
        )
    )
    require(markup is not None, "BotResponse buttons must convert to Telegram inline markup")
    require(len(markup.inline_keyboard) == 2, "Default MVP buttons should be rendered as full-width rows")
    require(markup.inline_keyboard[0][0].callback_data == "explain_score|", "Button callback data must preserve action")

    review_markup = runner.build_reply_markup(
        BotResponse(
            "Review skills",
            (
                InlineButton("Edit 1", "resume_edit_skill", "0"),
                InlineButton("Remove 1", "resume_remove_skill", "0"),
                InlineButton("Next", "resume_review_page", "1"),
            ),
        )
    )
    require(review_markup is not None, "Review buttons must render")
    require(len(review_markup.inline_keyboard[0]) == 2, "Edit and remove buttons for the same skill must share one row")

    level_markup = runner.build_reply_markup(
        BotResponse("Choose level", tuple(InlineButton(f"Level {level}", "resume_set_level", f"0:{level}") for level in range(0, 7)))
    )
    require(level_markup is not None, "Level buttons must render")
    require(len(level_markup.inline_keyboard[0]) == 3, "Level buttons should be grouped into rows of three")
    recovery_markup = runner.build_reply_markup(runner.BotResponse(runner.USER_ERROR_TEXT, runner.RECOVERY_BUTTONS))
    require(recovery_markup is not None, "Recovery response must expose a start button")
    require(recovery_markup.inline_keyboard[0][0].callback_data == "start|", "Recovery button must restart v2 flow")

    application = runner.build_application("123:ABC", PROJECT_ROOT)
    require("career_bot_service" in application.bot_data, "Application must hold the career bot service")
    require("rate_limiter" in application.bot_data, "Application must initialize the rate limiter")
    require(isinstance(application.bot_data["rate_limiter"], runner.InMemoryRateLimiter), "Rate limiter must use the adapter-local limiter")
    handler_count = sum(len(group) for group in application.handlers.values())
    require(handler_count >= 8, "Application must register command and callback handlers")

    clock = FakeClock()
    limiter = runner.InMemoryRateLimiter(clock=clock)
    general_rule = runner.RateLimitRule(limit=2, window_seconds=10)
    require(limiter.check_window("s1", "general", general_rule).allowed, "General throttle should allow first action")
    require(limiter.check_window("s1", "general", general_rule).allowed, "General throttle should allow action below limit")
    blocked = limiter.check_window("s1", "general", general_rule)
    require(not blocked.allowed and blocked.retry_after_seconds == 10, "General throttle should block above limit")
    clock.advance(10)
    require(limiter.check_window("s1", "general", general_rule).allowed, "General throttle should reopen after the window")

    resume_first = limiter.start_expensive("s1", "resume_upload", 60)
    require(resume_first.allowed, "Resume upload should be allowed initially")
    locked = limiter.start_expensive("s1", "resume_upload", 60)
    require(not locked.allowed and locked.reason == "processing", "Active expensive lock should block concurrent work")
    limiter.finish_expensive("s1", "resume_upload")
    cooldown = limiter.start_expensive("s1", "resume_upload", 60)
    require(not cooldown.allowed and cooldown.reason == "cooldown" and cooldown.retry_after_seconds == 60, "Resume cooldown should block repeated parse")
    clock.advance(60)
    require(limiter.start_expensive("s1", "resume_upload", 60).allowed, "Resume cooldown should reopen after 60 seconds")

    jd_limiter = runner.InMemoryRateLimiter(clock=clock)
    require(jd_limiter.start_expensive("s1", "jd_score", 30).allowed, "JD scoring should be allowed initially")
    jd_limiter.finish_expensive("s1", "jd_score")
    jd_blocked = jd_limiter.start_expensive("s1", "jd_score", 30)
    require(not jd_blocked.allowed and jd_blocked.retry_after_seconds == 30, "JD cooldown should block repeated scoring")

    report_limiter = runner.InMemoryRateLimiter(clock=clock)
    require(report_limiter.start_expensive("s1", "generate_action_plan", 15).allowed, "Report/action plan should be allowed initially")
    report_limiter.finish_expensive("s1", "generate_action_plan")
    report_blocked = report_limiter.start_expensive("s1", "generate_action_plan", 15)
    require(not report_blocked.allowed and report_blocked.retry_after_seconds == 15, "Report/action plan cooldown should block repeated generation")

    stale_limiter = runner.InMemoryRateLimiter(clock=clock)
    require(stale_limiter.start_expensive("s1", "resume_report", 15).allowed, "Stale lock setup should start allowed")
    clock.advance(runner.LOCK_STALE_SECONDS + 1)
    require(stale_limiter.start_expensive("s1", "resume_report", 15).allowed, "Stale locks should be ignored after expiry")

    event_log = PROJECT_ROOT / "data" / "processed" / "adapter_events.jsonl"
    if event_log.exists():
        event_log.unlink()
    runner.write_event_log(event_log, "start", BotResponse("Question", (InlineButton("A", "start_resume", ""),)))
    runner.write_event_log(
        event_log,
        "resume_upload",
        BotResponse("Please wait 60s before trying this again."),
        rate_limited=True,
        rate_limit_bucket="expensive",
        rate_limit_action="resume_upload",
        retry_after_seconds=60,
    )
    event_text = event_log.read_text(encoding="utf-8")
    event_log.unlink()
    require("start" in event_text and "resume_upload" in event_text, "Event log must include action names")
    require("rate_limited" in event_text and "retry_after_seconds" in event_text, "Event log must include rate-limit metadata")
    require("Question" not in event_text and "Please wait" not in event_text, "Event log must not store response text")

    print("Telegram adapter validation passed")
    print(f"question={result['question_text']}")
    print(f"buttons={result['button_count']}")
    print(f"first_callback={result['first_callback']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
