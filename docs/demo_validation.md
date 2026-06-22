# Demo Validation Guide

## Demo Scenario

Use one polished path for judging:

- Interface: Telegram bot with Casey the Career Auntie persona
- Starting point: upload a resume or choose a current role from the SkillsFuture role list
- User control: review, edit, remove, or add skills before scoring
- Goal mode: Explore pathways, Advance roles, Search target role, or Paste JD
- Final artifact: transient Telegram action-plan/report attachment, or explicit debug/local validation artifact

A good default demo is:

```text
/start -> Upload resume -> Review skills -> Explore pathways -> choose Data Analyst/Data Engineer/Risk Analytics style target -> Why this score? -> Show gaps -> Generate action plan
```

## Run Order

Use the repo-local virtual environment:

```powershell
.\.venv\Scripts\python.exe scripts\validate_m1_data.py
.\.venv\Scripts\python.exe scripts\validate_m2_scoring.py
.\.venv\Scripts\python.exe scripts\validate_resume_recommender.py
.\.venv\Scripts\python.exe scripts\validate_m6_telegram.py
.\.venv\Scripts\python.exe scripts\validate_m7_demo.py
```

Optional checks:

```powershell
.\.venv\Scripts\python.exe scripts\validate_explainer_agent.py
.\.venv\Scripts\python.exe scripts\validate_future_work.py
.\.venv\Scripts\python.exe scripts\run_telegram_bot.py --smoke-test
```

## Evidence Artifacts

Core evidence:

- `data/processed/data_quality_report.md`
- `data/processed/m2_scoring_example.md`
- `data/processed/m4_pathway_graph_demo.md`
- `data/processed/m5_explainability_action_plan.md`
- `data/processed/m7_demo_validation_report.md`
- `docs/scoring_methodology.md`
- `docs/workflow_diagram.md`
- `docs/daily_discussion/2026-06-19.md`
- `docs/daily_discussion/2026-06-21.md`

Current resume/Telegram evidence:

- Transient normal Telegram report attachment (`career_pathway_report.md`, not saved locally in normal mode)
- `data/processed/resume_first_result_*_debug.md`
- Transient Telegram action-plan attachment (`career_action_plan.md`, not saved locally in normal mode)

Historical/questionnaire evidence:

- `data/processed/m3_questionnaire_demo.md`
- `data/processed/local_questionnaire_result_*.md`
- `data/processed/local_workflow_preview.md`

## Acceptance Checklist

- M1 data quality report shows counts, join coverage, proficiency normalization, and traceability.
- M2 deterministic scoring produces the same score from the same inputs.
- Resume/role-first workflow parses or seeds skills, requires user review, and avoids persisting normal live user reports; debug/local validation artifacts contain only derived evidence.
- Explore pathways use weighted L1 nearest-neighbour discovery with a shared-skill overlap guard, then suitability/gap re-ranking.
- Specific role and JD comparisons use direct target-aware suitability scoring.
- Telegram `/start` shows the v2 resume/role-first menu, not the old questionnaire.
- Telegram Explore/Advance lists show compact target options without gap counts until a target is selected.
- Why this score, Show gaps, Generate action plan, and Generate report work from the active resume/JD/role result.
- Normal Telegram attachments hide parser confidence, raw evidence snippets, mapping internals, source rows, parser status, formulas, and debug prompts.
- Debug reports include parser/scoring audit details when explicitly enabled.
- Optional agents fall back cleanly and never calculate final scores or rankings.
- Live Telegram evidence can be validated with `scripts/validate_telegram_live_events.py` after running the manual flow with `--event-log`.
