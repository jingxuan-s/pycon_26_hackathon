"""Run the live Telegram bot adapter for the career pathway MVP.

The business logic stays in jobs_skills.telegram_bot.TelegramCareerBotService.
This script only adapts Telegram commands and callback buttons to that service.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import deque
from io import BytesIO
from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import json
import logging
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from jobs_skills.telegram_bot import BotResponse, InlineButton, TelegramCareerBotService

try:
    from dotenv import load_dotenv
except ImportError as exc:  # pragma: no cover - exercised when dependency is missing
    raise SystemExit("Missing dependency: python-dotenv. Run: python -m pip install -r requirements.txt") from exc

try:
    from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.constants import ParseMode
    from telegram.error import BadRequest
    from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
except ImportError as exc:  # pragma: no cover - exercised when dependency is missing
    raise SystemExit("Missing dependency: python-telegram-bot. Run: python -m pip install -r requirements.txt") from exc


CALLBACK_SEPARATOR = "|"
USER_ERROR_TEXT = "I could not complete that step. Start a fresh assessment to continue."
RECOVERY_BUTTONS = (InlineButton("Start", "start", ""),)


ServiceCall = Callable[[TelegramCareerBotService, str], BotResponse]

GENERAL_RATE_LIMIT = "general"
SEARCH_RATE_LIMIT = "search"
RATE_LIMITED_PROCESSING_TEXT = "I am still processing your previous request. Please wait a moment before trying again."
EXPENSIVE_ACTION_COOLDOWNS = {
    "resume_upload": 60,
    "jd_score": 30,
    "resume_report": 15,
    "resume_debug_report": 15,
    "generate_action_plan": 15,
}
LOCK_STALE_SECONDS = 180


@dataclass(frozen=True)
class RateLimitRule:
    limit: int
    window_seconds: int


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int = 0
    reason: str = ""
    bucket: str = ""
    action: str = ""


class InMemoryRateLimiter:
    """Process-local per-session limiter for the live Telegram adapter."""

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        self.clock = clock or time.monotonic
        self.events: dict[tuple[str, str], deque[float]] = {}
        self.cooldowns: dict[tuple[str, str], float] = {}
        self.locks: dict[tuple[str, str], float] = {}

    def check_window(self, session_id: str, bucket: str, rule: RateLimitRule) -> RateLimitDecision:
        now = self.clock()
        key = (session_id, bucket)
        events = self.events.setdefault(key, deque())
        cutoff = now - float(rule.window_seconds)
        while events and events[0] <= cutoff:
            events.popleft()
        if len(events) >= rule.limit:
            retry_after = max(1, math.ceil(events[0] + rule.window_seconds - now))
            return RateLimitDecision(False, retry_after, "window", bucket=bucket)
        events.append(now)
        return RateLimitDecision(True, bucket=bucket)

    def start_expensive(self, session_id: str, action: str, cooldown_seconds: int) -> RateLimitDecision:
        now = self.clock()
        key = (session_id, action)
        lock_started = self.locks.get(key)
        if lock_started is not None:
            if now - lock_started < LOCK_STALE_SECONDS:
                return RateLimitDecision(False, 0, "processing", bucket="expensive", action=action)
            self.locks.pop(key, None)

        last_started = self.cooldowns.get(key)
        if last_started is not None and now - last_started < cooldown_seconds:
            retry_after = max(1, math.ceil(last_started + cooldown_seconds - now))
            return RateLimitDecision(False, retry_after, "cooldown", bucket="expensive", action=action)

        self.locks[key] = now
        self.cooldowns[key] = now
        return RateLimitDecision(True, bucket="expensive", action=action)

    def finish_expensive(self, session_id: str, action: str) -> None:
        self.locks.pop((session_id, action), None)


GENERAL_RULE = RateLimitRule(limit=40, window_seconds=60)
SEARCH_RULE = RateLimitRule(limit=12, window_seconds=60)


class RedactTokenFilter(logging.Filter):
    """Prevent accidental token exposure in runtime logs."""

    def __init__(self, token: str) -> None:
        super().__init__()
        self.token = token

    def filter(self, record: logging.LogRecord) -> bool:
        if self.token:
            record.msg = str(record.msg).replace(self.token, "[redacted-token]")
            if isinstance(record.args, tuple):
                record.args = tuple(str(arg).replace(self.token, "[redacted-token]") for arg in record.args)
            elif isinstance(record.args, dict):
                record.args = {key: str(value).replace(self.token, "[redacted-token]") for key, value in record.args.items()}
        return True


def configure_logging(token: str) -> None:
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    token_filter = RedactTokenFilter(token)
    for handler in logging.getLogger().handlers:
        handler.addFilter(token_filter)
    for logger_name in ("httpx", "httpcore", "telegram", "telegram.ext"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def event_log_path_from_context(context: ContextTypes.DEFAULT_TYPE) -> Path | None:
    value = context.application.bot_data.get("event_log_path")
    return value if isinstance(value, Path) else None


def write_event_log(
    path: Path | None,
    action: str,
    response: BotResponse,
    *,
    rate_limited: bool = False,
    rate_limit_bucket: str = "",
    rate_limit_action: str = "",
    retry_after_seconds: int = 0,
) -> None:
    """Write privacy-safe live test evidence without chat ids, answers, or text."""
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "action": action,
        "button_count": len(response.buttons),
        "has_attachment": response.attachment_path is not None or response.attachment_content is not None,
        "rate_limited": bool(rate_limited),
    }
    if rate_limit_bucket:
        event["rate_limit_bucket"] = rate_limit_bucket
    if rate_limit_action:
        event["rate_limit_action"] = rate_limit_action
    if retry_after_seconds:
        event["retry_after_seconds"] = int(retry_after_seconds)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def callback_data(action: str, value: str) -> str:
    """Build compact callback data for Telegram inline buttons."""
    data = f"{action}{CALLBACK_SEPARATOR}{value}"
    if len(data.encode("utf-8")) > 64:
        raise ValueError(f"Callback data too long for Telegram: action={action!r}")
    return data


def parse_callback_data(data: str) -> tuple[str, str]:
    """Split callback payloads in the action|value format."""
    if CALLBACK_SEPARATOR not in data:
        return data, ""
    action, value = data.split(CALLBACK_SEPARATOR, 1)
    return action, value


def build_reply_markup(response: BotResponse) -> InlineKeyboardMarkup | None:
    """Convert service buttons into Telegram inline keyboard rows."""
    if not response.buttons:
        return None
    rows: list[list[InlineKeyboardButton]] = []
    pending_level_row: list[InlineKeyboardButton] = []
    index = 0
    buttons = list(response.buttons)

    def flush_level_row() -> None:
        if pending_level_row:
            rows.append(list(pending_level_row))
            pending_level_row.clear()

    while index < len(buttons):
        button = buttons[index]
        if button.action in {"resume_set_level", "resume_add_level"}:
            pending_level_row.append(InlineKeyboardButton(button.label, callback_data=callback_data(button.action, button.value)))
            if len(pending_level_row) == 3:
                flush_level_row()
            index += 1
            continue

        flush_level_row()
        if (
            button.action == "resume_edit_skill"
            and index + 1 < len(buttons)
            and buttons[index + 1].action == "resume_remove_skill"
            and buttons[index + 1].value == button.value
        ):
            remove_button = buttons[index + 1]
            rows.append(
                [
                    InlineKeyboardButton(button.label, callback_data=callback_data(button.action, button.value)),
                    InlineKeyboardButton(remove_button.label, callback_data=callback_data(remove_button.action, remove_button.value)),
                ]
            )
            index += 2
            continue

        rows.append([InlineKeyboardButton(button.label, callback_data=callback_data(button.action, button.value))])
        index += 1

    flush_level_row()
    return InlineKeyboardMarkup(rows)


def load_bot_token(project_root: Path) -> str:
    """Load Telegram token from .env without printing it."""
    load_dotenv(project_root / ".env")
    token = os.getenv("telegram_api_token") or os.getenv("TELEGRAM_API_TOKEN")
    if not token:
        raise SystemExit("Missing telegram_api_token in .env or TELEGRAM_API_TOKEN in the environment.")
    return token


async def check_bot_token(project_root: Path = PROJECT_ROOT) -> str:
    """Verify the configured token with Telegram without printing the token."""
    token = load_bot_token(project_root)
    async with Bot(token=token) as bot:
        me = await bot.get_me()
    username = me.username or "unknown"
    return f"@{username}" if not username.startswith("@") else username


def session_id_from_update(update: Update) -> str:
    if update.effective_chat is None:
        raise ValueError("Telegram update has no chat context")
    digest = hashlib.sha256(str(update.effective_chat.id).encode("utf-8")).hexdigest()[:16]
    return f"tg_{digest}"


def service_from_context(context: ContextTypes.DEFAULT_TYPE) -> TelegramCareerBotService:
    service = context.application.bot_data.get("career_bot_service")
    if not isinstance(service, TelegramCareerBotService):
        raise RuntimeError("TelegramCareerBotService is not configured")
    return service


def rate_limiter_from_context(context: ContextTypes.DEFAULT_TYPE) -> InMemoryRateLimiter:
    limiter = context.application.bot_data.get("rate_limiter")
    if not isinstance(limiter, InMemoryRateLimiter):
        limiter = InMemoryRateLimiter()
        context.application.bot_data["rate_limiter"] = limiter
    return limiter


def rate_limited_response(decision: RateLimitDecision) -> BotResponse:
    if decision.reason == "processing":
        return BotResponse(RATE_LIMITED_PROCESSING_TEXT)
    retry_after = max(1, int(decision.retry_after_seconds))
    return BotResponse(f"Please wait {retry_after}s before trying this again.")


def log_rate_limit_decision(
    context: ContextTypes.DEFAULT_TYPE,
    action_name: str,
    response: BotResponse,
    decision: RateLimitDecision,
) -> None:
    write_event_log(
        event_log_path_from_context(context),
        action_name,
        response,
        rate_limited=not decision.allowed,
        rate_limit_bucket=decision.bucket,
        rate_limit_action=decision.action,
        retry_after_seconds=decision.retry_after_seconds,
    )


async def send_bot_response(update: Update, response: BotResponse) -> None:
    """Send text, buttons, and optional report attachment back to Telegram."""
    message = update.effective_message
    if update.callback_query is not None:
        message = update.callback_query.message
    if message is None:
        raise ValueError("Telegram update has no message context")

    try:
        await message.reply_text(response.text, reply_markup=build_reply_markup(response), parse_mode=ParseMode.HTML)
    except BadRequest:
        logging.exception("Telegram HTML rendering failed; retrying without parse mode")
        await message.reply_text(response.text, reply_markup=build_reply_markup(response))

    if response.attachment_content is not None:
        payload = response.attachment_content
        if isinstance(payload, str):
            payload_bytes = payload.encode("utf-8")
        else:
            payload_bytes = payload
        document = BytesIO(payload_bytes)
        document.name = response.attachment_name or "career_report.md"
        await message.reply_document(document=document, filename=document.name)
        return

    if response.attachment_path:
        attachment_path = Path(response.attachment_path)
        if attachment_path.exists():
            with attachment_path.open("rb") as handle:
                await message.reply_document(document=handle, filename=attachment_path.name)
        else:
            await message.reply_text(f"Report path: {attachment_path}")

async def run_service_call(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    action_name: str,
    call: ServiceCall,
    progress_message: str | None = None,
) -> None:
    service = service_from_context(context)
    session_id = session_id_from_update(update)
    limiter = rate_limiter_from_context(context)

    general_decision = limiter.check_window(session_id, GENERAL_RATE_LIMIT, GENERAL_RULE)
    if not general_decision.allowed:
        response = rate_limited_response(general_decision)
        log_rate_limit_decision(context, action_name, response, general_decision)
        await send_bot_response(update, response)
        return

    expensive_started = False
    if action_name in EXPENSIVE_ACTION_COOLDOWNS:
        expensive_decision = limiter.start_expensive(session_id, action_name, EXPENSIVE_ACTION_COOLDOWNS[action_name])
        if not expensive_decision.allowed:
            response = rate_limited_response(expensive_decision)
            log_rate_limit_decision(context, action_name, response, expensive_decision)
            await send_bot_response(update, response)
            return
        expensive_started = True

    if progress_message and update.callback_query is not None and update.callback_query.message is not None:
        await update.callback_query.message.reply_text(progress_message)

    try:
        try:
            response = call(service, session_id)
        except Exception:  # pragma: no cover - defensive runtime guard for live bot use
            logging.exception("Telegram service call failed")
            response = BotResponse(USER_ERROR_TEXT, RECOVERY_BUTTONS)
    finally:
        if expensive_started:
            limiter.finish_expensive(session_id, action_name)

    write_event_log(event_log_path_from_context(context), action_name, response)
    await send_bot_response(update, response)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_service_call(update, context, "start", lambda service, session_id: service.start(session_id))


async def first_time_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_service_call(update, context, "first_time_user", lambda service, session_id: service.first_time_user(session_id))


async def start_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_service_call(update, context, "start_resume", lambda service, session_id: service.start_resume_flow(session_id))


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None or message.document is None:
        return
    service = service_from_context(context)
    session_id = session_id_from_update(update)
    document = message.document
    suffix = Path(document.file_name or "resume").suffix.casefold()
    if suffix not in {".pdf", ".docx"}:
        await send_bot_response(update, BotResponse("Please upload a PDF or DOCX resume."))
        return

    limiter = rate_limiter_from_context(context)
    decision = limiter.start_expensive(session_id, "resume_upload", EXPENSIVE_ACTION_COOLDOWNS["resume_upload"])
    if not decision.allowed:
        response = rate_limited_response(decision)
        log_rate_limit_decision(context, "resume_upload", response, decision)
        await send_bot_response(update, response)
        return

    await message.reply_text("Resume received. Parsing skills now...")
    upload_dir = PROJECT_ROOT / ".runtime" / "telegram_uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    local_path = upload_dir / f"{session_id}_{document.file_unique_id}{suffix}"
    try:
        try:
            telegram_file = await document.get_file()
            await telegram_file.download_to_drive(custom_path=local_path)
            response = service.parse_resume_upload(session_id, local_path)
        except Exception:
            logging.exception("Telegram resume upload failed")
            response = BotResponse(USER_ERROR_TEXT, RECOVERY_BUTTONS)
    finally:
        limiter.finish_expensive(session_id, "resume_upload")
    write_event_log(event_log_path_from_context(context), "resume_upload", response)
    await send_bot_response(update, response)


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None or not message.text or message.text.startswith("/"):
        return
    service = service_from_context(context)
    session_id = session_id_from_update(update)
    session = service.get_session(session_id)
    limiter = rate_limiter_from_context(context)

    if session.waiting_for_jd_text:
        decision = limiter.start_expensive(session_id, "jd_score", EXPENSIVE_ACTION_COOLDOWNS["jd_score"])
        if not decision.allowed:
            response = rate_limited_response(decision)
            log_rate_limit_decision(context, "jd_score", response, decision)
            await send_bot_response(update, response)
            return
        await message.reply_text("JD received. Comparing against your confirmed skills...")
        try:
            try:
                response = service.handle_text_message(session_id, message.text)
            except Exception:
                logging.exception("Telegram JD scoring failed")
                response = BotResponse(USER_ERROR_TEXT, RECOVERY_BUTTONS)
        finally:
            limiter.finish_expensive(session_id, "jd_score")
        write_event_log(event_log_path_from_context(context), "jd_score", response)
        await send_bot_response(update, response)
        return

    if session.pending_text_mode == "add_skill_search":
        decision = limiter.check_window(session_id, SEARCH_RATE_LIMIT, SEARCH_RULE)
        if not decision.allowed:
            response = rate_limited_response(decision)
            log_rate_limit_decision(context, "skill_search", response, decision)
            await send_bot_response(update, response)
            return
        await message.reply_text("Searching SkillsFuture skills...")
        try:
            response = service.handle_text_message(session_id, message.text)
        except Exception:
            logging.exception("Telegram skill search failed")
            response = BotResponse(USER_ERROR_TEXT, RECOVERY_BUTTONS)
        write_event_log(event_log_path_from_context(context), "skill_search", response)
        await send_bot_response(update, response)
        return

    if session.pending_text_mode == "role_search":
        decision = limiter.check_window(session_id, SEARCH_RATE_LIMIT, SEARCH_RULE)
        if not decision.allowed:
            response = rate_limited_response(decision)
            log_rate_limit_decision(context, "role_search", response, decision)
            await send_bot_response(update, response)
            return
        await message.reply_text("Searching SkillsFuture roles...")
        try:
            response = service.handle_text_message(session_id, message.text)
        except Exception:
            logging.exception("Telegram role search failed")
            response = BotResponse(USER_ERROR_TEXT, RECOVERY_BUTTONS)
        write_event_log(event_log_path_from_context(context), "role_search", response)
        await send_bot_response(update, response)
        return

    await run_service_call(update, context, "text_message", lambda service, session_id: service.handle_text_message(session_id, message.text))

async def start_assessment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_service_call(update, context, "start_assessment", lambda service, session_id: service.start_assessment(session_id))


async def search_roles(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args or [])
    session_id = session_id_from_update(update)
    decision = rate_limiter_from_context(context).check_window(session_id, SEARCH_RATE_LIMIT, SEARCH_RULE)
    if not decision.allowed:
        response = rate_limited_response(decision)
        log_rate_limit_decision(context, "search_roles", response, decision)
        await send_bot_response(update, response)
        return
    await run_service_call(update, context, "search_roles", lambda service, session_id: service.search_roles_entry(session_id, query))

async def recommend_roles(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_service_call(update, context, "recommend_roles", lambda service, session_id: service.recommend_roles(session_id))


async def explain_score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_service_call(update, context, "explain_score", lambda service, session_id: service.explain_score(session_id))


async def show_gaps(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_service_call(update, context, "show_gaps", lambda service, session_id: service.show_gaps(session_id))


async def show_pathway(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_service_call(update, context, "show_pathway", lambda service, session_id: service.show_pathway(session_id))


async def generate_action_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_service_call(update, context, "generate_action_plan", lambda service, session_id: service.generate_action_plan(session_id))


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    try:
        await query.answer()
    except BadRequest:
        logging.warning("Ignoring expired Telegram callback acknowledgement")

    action, value = parse_callback_data(query.data or "")
    def dispatch(service: TelegramCareerBotService, session_id: str) -> BotResponse:
        if action == "start":
            return service.start(session_id)
        if action == "first_time_user":
            return service.first_time_user(session_id)
        if action == "start_resume":
            return service.start_resume_flow(session_id)
        if action == "start_role_search":
            return service.search_roles_entry(session_id, "")
        if action == "answer_question":
            return service.answer_question(session_id, float(value))
        if action == "select_current_role":
            return service.select_current_role(session_id, value)
        if action == "select_current_role_id":
            return service.select_current_role_id(session_id, value)
        if action == "choose_pathway":
            return service.choose_pathway(session_id, value)
        if action == "answer_gap_question":
            return service.answer_gap_question(session_id, float(value))
        if action == "start_assessment":
            return service.start_assessment(session_id)
        if action == "recommend_roles":
            return service.recommend_roles(session_id)
        if action == "explain_score":
            return service.explain_score(session_id)
        if action == "show_gaps":
            return service.show_gaps(session_id)
        if action == "show_pathway":
            return service.show_pathway(session_id)
        if action == "generate_action_plan":
            return service.generate_action_plan(session_id)
        if action == "resume_confirm_skills":
            return service.confirm_resume_skills(session_id)
        if action == "resume_back_review":
            return service.back_to_resume_review(session_id)
        if action == "resume_back_targets":
            return service.back_to_resume_targets(session_id)
        if action == "resume_confirm_back_start":
            return service.confirm_back_to_start(session_id)
        if action == "resume_review_page":
            return service.review_resume_skills(session_id, int(value or "0"))
        if action == "resume_edit_skill":
            return service.edit_resume_skill(session_id, value)
        if action == "resume_set_level":
            return service.set_resume_skill_level(session_id, value)
        if action == "resume_remove_skill":
            return service.remove_resume_skill(session_id, value)
        if action == "resume_add_skill":
            return service.prompt_add_resume_skill(session_id)
        if action == "resume_add_select":
            return service.select_resume_add_skill(session_id, value)
        if action == "resume_add_level":
            return service.add_resume_skill_level(session_id, value)
        if action == "resume_explain_skills":
            return service.explain_resume_skills(session_id)
        if action == "resume_explore":
            return service.start_resume_explore(session_id)
        if action == "resume_advance":
            return service.start_resume_advance(session_id)
        if action == "resume_choose_role":
            return service.choose_resume_target_role(session_id, value)
        if action == "resume_specific_role":
            return service.choose_resume_specific_role(session_id, value)
        if action == "resume_start_from_role":
            return service.start_profile_from_role(session_id, value)
        if action == "resume_jd_text":
            return service.start_resume_jd_text(session_id)
        if action == "resume_cancel_jd":
            return service.cancel_resume_jd_text(session_id)
        if action == "resume_report":
            return service.generate_resume_report(session_id, debug=False)
        if action == "resume_debug_report":
            if not service.debug_mode:
                return BotResponse("Debug report is hidden in normal mode. Restart the bot with --debug-mode to expose it.", service._resume_result_buttons())
            return service.generate_resume_report(session_id, debug=True)
        return BotResponse("Unknown action. Start a fresh assessment to continue.", RECOVERY_BUTTONS)

    progress_message = "Generating detailed report..." if action in {"resume_report", "resume_debug_report", "generate_action_plan"} else None
    await run_service_call(update, context, action, dispatch, progress_message=progress_message)


def build_application(token: str, project_root: Path = PROJECT_ROOT, event_log_path: Path | None = None, debug_mode: bool = False) -> Application:
    service = TelegramCareerBotService(project_root, debug_mode=debug_mode)
    application = Application.builder().token(token).build()
    application.bot_data["career_bot_service"] = service
    application.bot_data["event_log_path"] = event_log_path
    application.bot_data["rate_limiter"] = InMemoryRateLimiter()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("first_time_user", first_time_user))
    application.add_handler(CommandHandler("start_assessment", start_assessment))
    application.add_handler(CommandHandler("start_resume", start_resume))
    application.add_handler(CommandHandler("search_roles", search_roles))
    application.add_handler(CommandHandler("recommend_roles", recommend_roles))
    application.add_handler(CommandHandler("explain_score", explain_score))
    application.add_handler(CommandHandler("show_gaps", show_gaps))
    application.add_handler(CommandHandler("show_pathway", show_pathway))
    application.add_handler(CommandHandler("generate_action_plan", generate_action_plan))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    return application


def smoke_test_adapter(project_root: Path = PROJECT_ROOT) -> dict[str, object]:
    """Validate adapter conversion without a bot token or Telegram network call."""
    service = TelegramCareerBotService(project_root)
    limiter = InMemoryRateLimiter()
    decision = limiter.check_window("adapter-smoke", GENERAL_RATE_LIMIT, GENERAL_RULE)
    if not decision.allowed:
        raise AssertionError("Fresh rate limiter should allow the first general action")
    start_response = service.start("adapter-smoke")
    start_markup = build_reply_markup(start_response)
    if start_markup is None or "Upload resume" not in start_response.text:
        raise AssertionError("Start must produce v2 entry buttons")

    first_button = start_response.buttons[0]
    encoded = callback_data(first_button.action, first_button.value)
    decoded = parse_callback_data(encoded)
    if decoded != (first_button.action, first_button.value):
        raise AssertionError("Callback payload must round-trip action and value")

    resume_response = service.start_resume_flow("adapter-smoke")
    if "Upload your resume" not in resume_response.text:
        raise AssertionError("Resume shortcut must ask for upload")

    return {
        "question_text": "v2 start",
        "button_count": len(start_response.buttons),
        "first_callback": encoded,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the live Telegram career pathway bot.")
    parser.add_argument("--smoke-test", action="store_true", help="Validate adapter conversion without reading a token or polling.")
    parser.add_argument("--check-token", action="store_true", help="Verify the configured Telegram token and exit without polling.")
    parser.add_argument("--drop-pending-updates", action="store_true", help="Discard queued Telegram updates when polling starts.")
    parser.add_argument("--event-log", type=Path, default=None, help="Optional privacy-safe JSONL event log for manual live testing.")
    parser.add_argument("--debug-mode", action="store_true", help="Expose debug report buttons in Telegram responses.")
    args = parser.parse_args()

    if args.smoke_test:
        result = smoke_test_adapter(PROJECT_ROOT)
        print("Telegram adapter smoke test passed")
        print(f"question={result['question_text']}")
        print(f"buttons={result['button_count']}")
        return 0

    if args.check_token:
        bot_name = asyncio.run(check_bot_token(PROJECT_ROOT))
        print("Telegram token check passed")
        print(f"bot={bot_name}")
        return 0

    token = load_bot_token(PROJECT_ROOT)
    configure_logging(token)
    application = build_application(token, PROJECT_ROOT, args.event_log, debug_mode=args.debug_mode)
    print("Telegram bot polling started. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=args.drop_pending_updates)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

