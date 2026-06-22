# Judging Package Notes

## Product Summary

The MVP is a Telegram-based career pathway assistant using SkillsFuture jobs-skills data. Casey the Career Auntie guides users through a resume-first or role-first flow: start from a resume upload or a selected dataset role, review the inferred skill profile, choose a goal, then receive an explainable suitability score, skill gaps, and a K&A-backed action plan.

The current default flow is resume/role-first. The earlier questionnaire flow remains useful as historical methodology and local validation evidence, but it is not the default Telegram experience.

## Process Evidence

Human-AI collaboration is captured in:

- `docs/daily_discussion/2026-06-19.md`
- `docs/daily_discussion/2026-06-21.md`
- `docs/daily_discussion/raw/2026-06-19.md`
- `docs/daily_discussion/raw/2026-06-21.md`
- `docs/project_brief.md`
- `docs/roadmap.md`

The roadmap uses goal-prompt milestone sections to keep implementation focused and prevent scope drift. Daily discussion archives capture methodology decisions, product pivots, validation evidence, and milestone outcomes.

## Data Integrity / Data Quality

Evidence:

- `data/processed/data_quality_report.md`
- `scripts/validate_m1_data.py`
- normalized tables under `data/processed/`

Key points:

- Role-skill rows matched to roles: 100.00%.
- Role-skill rows matched to unique skills: 99.93% at raw audit level.
- Final normalized role-skill requirements have resolved skill ids and titles.
- Role-skill rows with matching K&A items: 100.00%.
- Text proficiency levels are normalized with `Basic = 1`, `Intermediate = 3`, `Advanced = 5`.
- The product uses normalized unique skills as vector dimensions.

## User Focus / Project Value

Evidence:

- `README.md`
- `docs/scoring_methodology.md`
- `docs/workflow_diagram_simplified.md`
- Transient normal Telegram report attachment (`career_pathway_report.md`, not saved locally in normal mode)
- Transient Telegram action-plan attachment (`career_action_plan.md`, not saved locally in normal mode)

Key points:

- Users are not scored directly from hidden parser output; they review, edit, remove, and add skills first.
- Telegram offers four clear goal modes: Explore pathways, Advance roles, Search target role, and Paste JD.
- Explore recommendations show up to six options and hide detailed gaps until the user selects a target.
- Results explain matched skills, priority gaps, and concrete next actions without overwhelming the user.
- Normal Telegram attachments hide confidence, raw evidence snippets, mapping type, source rows, parser status, and formulas; debug reports preserve audit details when explicitly enabled.

## Technical Execution

Evidence:

- `src/jobs_skills/data_pipeline.py`
- `src/jobs_skills/scoring.py`
- `src/jobs_skills/resume_recommender.py`
- `src/jobs_skills/parser_agents.py`
- `src/jobs_skills/related_skills.py`
- `src/jobs_skills/pathway_graph.py`
- `src/jobs_skills/explainability.py`
- `src/jobs_skills/explainer_agent.py`
- `src/jobs_skills/telegram_bot.py`
- `scripts/run_telegram_bot.py`
- `scripts/validate_resume_recommender.py`
- `scripts/validate_m6_telegram.py`
- `scripts/validate_m7_demo.py`

Key points:

- Python is the core implementation language.
- Scoring is deterministic and reproducible.
- Explore pathways use weighted L1 nearest-neighbour discovery with a shared-skill overlap guard, then suitability/gap re-ranking.
- Specific target-role and JD scoring use direct target-aware suitability scoring.
- Pathway fit is separate from raw skill suitability.
- Telegram integration is a thin service layer over backend modules, with a live polling adapter for local Telegram testing.
- Optional parser/explainer agents use `gpt-5-nano` when configured and fall back to deterministic/rule-based behavior when unavailable.

## Explainability

Evidence:

- `docs/scoring_methodology.md`
- Transient normal Telegram report attachment (`career_pathway_report.md`, not saved locally in normal mode)
- `data/processed/resume_first_result_*_debug.md`

The product makes visible:

- confirmed user skills and levels
- target role or JD-derived required skills
- matched skills
- priority gaps
- current level vs target level
- related-skill notes where SkillsFuture defines overlapping skills separately
- K&A/proficiency rows used for action planning
- parser and explainer boundaries

Agents are advisory. Parser agents extract structured evidence; explainer agents narrate computed results. Neither layer calculates final scores or rankings.

## Known Tradeoffs

- Related skills are explanation-only and do not change suitability percentages.
- Current skill weights are all `1.0`; the methodology explains how future role-specific weighting could be added only with defensible tagging.
- Telegram rate limiting is process-local for the hackathon demo; hosted multi-instance deployment should use shared storage such as Redis.
- The dataset supports K&A-backed learning actions, not official course recommendations.
- Generated demo/report artifacts should be reviewed before committing because real resume/JD runs may contain sensitive derived evidence.
