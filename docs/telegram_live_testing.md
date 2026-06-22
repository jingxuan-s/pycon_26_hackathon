# Telegram Live Testing Runbook

This runbook covers the live Telegram demo. The live adapter is `scripts/run_telegram_bot.py`; the deterministic product logic remains in `src/jobs_skills/telegram_bot.py` and downstream service modules.

## BotFather Commands

Register only these user-facing slash commands:

```text
start - Start career pathway workflow
first_time_user - Explain how the recommender works
start_resume - Start with resume upload
search_roles - Start by searching a role
explain_score - Explain current suitability score
show_gaps - Show current skill gaps
generate_action_plan - Generate action plan report
```

Do not expose callback actions as typed commands. These are inline button actions only:

```text
resume_explore
resume_advance
resume_choose_role
resume_review_page
resume_edit_skill
resume_remove_skill
resume_add_skill
resume_jd_text
resume_report
resume_debug_report
```

## Local Environment

Keep tokens outside git in `.env`:

```text
telegram_api_token=<your BotFather token>
PARSER_AGENT_API_TOKEN=<optional parser token>
EXPLAINER_AGENT_API_TOKEN=<optional explainer token>
EXPLAINER_AGENT_MODEL=gpt-5-nano
```

Agent tokens are optional. If no token is configured, or if an agent call fails, the product falls back to deterministic/rule-based behavior. `.env` is ignored by git.

Install dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Smoke Tests Before Polling

Run the Telegram service validator:

```powershell
.\.venv\Scripts\python.exe scripts\validate_m6_telegram.py
```

Run the adapter smoke test:

```powershell
.\.venv\Scripts\python.exe scripts\run_telegram_bot.py --smoke-test
```

Check the token without starting polling:

```powershell
.\.venv\Scripts\python.exe scripts\run_telegram_bot.py --check-token
```

The command prints bot identity details but never prints the token.

## Start Live Polling

```powershell
.\.venv\Scripts\python.exe scripts\run_telegram_bot.py --drop-pending-updates --event-log C:\tmp\pycon_telegram_bot.events.jsonl
```

Use debug mode only when you intentionally want debug report buttons visible:

```powershell
.\.venv\Scripts\python.exe scripts\run_telegram_bot.py --drop-pending-updates --debug-mode --event-log C:\tmp\pycon_telegram_bot.events.jsonl
```

The optional event log stores action names, button counts, and attachment presence only. It does not store chat ids, answers, token, resume text, JD text, or message text.

## Expected Manual Flow

Open Telegram and send:

```text
/start
```

Recommended resume-first demo path:

```text
/start
-> tap Upload resume
-> upload PDF or DOCX resume
-> tap Why these skills? if you want a compact parser explanation
-> tap Review skills
-> edit/remove/add skills if needed
-> tap Continue
-> tap Explore pathways, Advance roles, Search target role, or Paste JD
-> choose a target role or paste a JD
-> tap Why this score?
-> tap Show skill gaps
-> tap Generate action plan
-> tap Generate report if a full normal report attachment is needed; normal mode sends it without saving locally
```

Role-first demo path:

```text
/start
-> tap Search role
-> search for a role such as data analyst
-> select a dataset role baseline
-> review/edit/remove/add skills
-> choose a goal mode
-> inspect score, gaps, action plan, and report
```

## Validate Live Event Evidence

After completing the manual Telegram flow through `Generate action plan`, run:

```powershell
.\.venv\Scripts\python.exe scripts\validate_telegram_live_events.py C:\tmp\pycon_telegram_bot.events.jsonl
```

If a future audit requires live evidence as mandatory, run:

```powershell
.\.venv\Scripts\python.exe scripts\validate_future_work.py --require-live-event-log
```

## Privacy Notes

- The adapter hashes the Telegram chat id into a temporary session key before calling the service.
- The token is loaded from `.env` or environment variables and is never printed.
- Runtime logs are kept at warning level and redact the token if an exception message includes it.
- The optional event log stores only action names, button counts, and attachment presence.
- Raw resume and JD text are read at runtime only and should not be persisted.
- The bot keeps only in-memory session state for the local demo.
- Debug/local validation reports should be reviewed before committing.
- Do not commit `.env`, raw resumes, Telegram private identifiers, or debug/local reports from real users.
