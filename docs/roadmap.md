# MVP Roadmap

## Current MVP Goal

Build a Telegram-first career pathway tool using the SkillsFuture jobs-skills datasets. The current demo surface is Casey the Career Auntie, a guided Telegram workflow that starts from either a resume upload or a selected dataset role.

Current core flow:

```text
resume upload or role search
-> parsed or role-derived skill profile
-> user reviews, edits, removes, or adds skills
-> choose goal mode: Explore, Advance, Search target role, or Paste JD
-> deterministic suitability and gap scoring
-> Casey explanation, skill gaps, transient normal attachments, and optional debug reports
```

Historical note: the original M0-M7 roadmap was questionnaire-first, with resume/JD parsing scoped as stretch. Product testing later showed the resume/role-first workflow was more practical, so the current MVP uses that flow while retaining the questionnaire implementation as legacy/internal validation evidence.

## Backbone Principle: Data Processing First

Data processing is the backbone of the product. M1 Data Pipeline may take extra time because all downstream scoring, pathway planning, and explainability depend on clean normalized data.

Do not build recommendation logic on unclear joins, unvalidated role-skill tables, or untraceable skill mappings. Every downstream score must be traceable to normalized data rows and source dataset logic.

## MVP Complete Definition

The current MVP is complete when:

- A user can start in Telegram with `/start`.
- A user can upload a resume or choose a current role from the dataset.
- The system builds a draft skill-proficiency vector.
- The user can review, edit, remove, and add skills before scoring.
- The user can choose Explore pathways, Advance roles, Search target role, or Paste JD.
- The system calculates deterministic suitability and skill gaps.
- Explore recommendations show relevant overlap-filtered role options before detailed comparison.
- The system generates Casey explanations, skill gaps, K&A-backed actions, transient normal attachments, and optional debug reports.

## Milestone Index

- M0: Project setup and documentation hygiene
- M1: Data pipeline and normalized feature tables
- M2: Deterministic scoring engine
- M3: Hybrid questionnaire engine
- M4: Pathway graph and pathway fit
- M5: Explainability and action-plan report
- M6: Telegram bot integration
- M7: End-to-end demo validation and judging package
- Stretch: Resume/JD parser agents

## Current Build Status

Status as of 2026-06-22: M0 through M7 are complete, and the product has been extended with resume/role-first Telegram flow, Casey persona, parser/JD support, related-skill explanations, hybrid Explore scoring, transient normal attachments, and optional debug reports.

| Milestone | Status | Primary Evidence |
| --- | --- | --- |
| M0: Project setup and documentation hygiene | Complete | `docs/project_brief.md`, `docs/roadmap.md`, `.codex/skills/`, `docs/daily_discussion/2026-06-19.md` |
| M1: Data pipeline and normalized feature tables | Complete | `src/jobs_skills/data_pipeline.py`, `scripts/validate_m1_data.py`, `data/processed/data_quality_report.md` |
| M2: Deterministic scoring engine | Complete | `src/jobs_skills/scoring.py`, `scripts/validate_m2_scoring.py`, `data/processed/m2_scoring_example.md` |
| M3: Hybrid questionnaire engine | Complete | `src/jobs_skills/questionnaire.py`, `scripts/validate_m3_questionnaire.py`, `data/processed/m3_questionnaire_demo.md` |
| M4: Pathway graph and pathway fit | Complete | `src/jobs_skills/pathway_graph.py`, `scripts/validate_m4_pathway.py`, `data/processed/m4_pathway_graph_demo.md` |
| M5: Explainability and action-plan report | Complete | `src/jobs_skills/explainability.py`, `scripts/validate_m5_report.py`, `data/processed/m5_explainability_action_plan.md` |
| M6: Telegram bot integration | Complete | `src/jobs_skills/telegram_bot.py`, `scripts/validate_m6_telegram.py`, `data/processed/m6_telegram_flow_demo.md` |
| M7: End-to-end demo validation and judging package | Complete | `scripts/validate_m7_demo.py`, `data/processed/m7_demo_validation_report.md`, `docs/demo_validation.md`, `docs/judging_package.md` |

Latest full validation command:

```powershell
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe scripts\validate_m7_demo.py
```

Latest validation result:

```text
M7 validation passed
validators=6
artifacts=10
```

## What Was Built

The completed MVP supports this validated flow:

```text
Data Analyst baseline questionnaire
-> 10 current-role skill questions
-> 3 recommended pathways
-> selected Data Scientist pathway
-> 5 target-gap follow-up questions
-> recalculated skill suitability
-> inferred pathway fit
-> top skill gaps
-> generated K&A-backed action plan
```

Core implementation artifacts:

- Python data pipeline that normalizes SkillsFuture role, skill, role-skill, and K&A data.
- Deterministic scoring engine using `covered_level = min(current_level, target_level)` and MVP `skill_weight = 1.0`.
- Hybrid questionnaire engine that avoids asking all skills upfront.
- Inferred pathway graph with configurable sector/track policy and Dijkstra search.
- Explainability/action-plan generator that traces recommendations to role-skill rows and K&A rows.
- Telegram-style command/button service layer that validates the MVP interaction without requiring a live bot token.
- Judging package with process evidence, validation report, and criteria mapping.

## Recommended Next Steps

### N1: Live Telegram Bot Testing

**Status**

Complete enough for MVP progression. Live adapter, token check, polling runbook, privacy-safe event logging, and manual user feedback confirm the Telegram MVP flow works. Remaining refinements are tracked under N2.

**Goal Prompt**

Wire `src/jobs_skills/telegram_bot.py` to an actual Telegram bot runtime so the validated M6 command/button flow can be tested in Telegram. Keep business logic in the existing `TelegramCareerBotService`; the live bot layer should only adapt Telegram commands and callback buttons to the service methods.

**Why This Matters**

M6 validates a Telegram-style flow locally, but judging/demo testing needs a real bot that can be opened in Telegram, started with `/start_assessment`, advanced through inline buttons, and used to generate an action plan. This milestone turns the MVP from a backend simulation into a live interactive demo surface.

**Inputs**

- `src/jobs_skills/telegram_bot.py`
- `scripts/validate_m6_telegram.py`
- `data/processed/` generated tables and reports
- `.env` containing `telegram_api_token=...`
- BotFather commands configured for the bot

**Outputs**

- `scripts/run_telegram_bot.py` live bot entrypoint
- `python-telegram-bot` and `python-dotenv` added to `requirements.txt`
- Telegram adapter that converts internal `InlineButton` objects into Telegram `InlineKeyboardButton`s
- Callback query handler for hidden button actions
- Local run instructions in docs, README, or a short Telegram runbook
- Smoke test or validation script that checks adapter behavior without exposing the token

Current implementation evidence:

- `scripts/run_telegram_bot.py` live polling adapter
- `scripts/validate_telegram_adapter.py` no-token adapter validation
- `scripts/run_telegram_bot.py --check-token` live token connectivity check
- `docs/telegram_live_testing.md` local runbook

**Implementation Notes**

- Use polling for local testing first. Webhooks are unnecessary for MVP demo testing.
- Load the token from `.env`; never print or commit the token.
- Keep `.env` ignored by git.
- Use chat id as the session id for the MVP.
- Keep user-visible slash commands small. Use inline buttons for selections.
- Convert service responses using this mapping:
  - `BotResponse.text` -> Telegram message text
  - `BotResponse.buttons` -> Telegram inline keyboard rows
  - `BotResponse.attachment_path` -> send as document if feasible, otherwise show the generated path
- Use callback data format such as `action|value`.
- Hidden callback actions should include:
  - `answer_question|<level>`
  - `choose_pathway|<role_id>`
  - `answer_gap_question|<level>`
  - `recommend_roles|top3`
  - `explain_score|`
  - `show_gaps|`
  - `show_pathway|`
  - `generate_action_plan|`

**BotFather Command Setup**

Register only the user-facing slash commands:

```text
start_assessment - Start the career pathway assessment
recommend_roles - Show 3 recommended pathways
explain_score - Explain why this score was given
show_gaps - Show priority skill gaps
show_pathway - Show inferred pathway and pathway fit
generate_action_plan - Generate the learning action plan
```

Do not register these hidden actions as typed slash commands:

```text
answer_question
choose_pathway
answer_gap_question
```

They should be Telegram inline button callback actions only.

**Local Test Commands**

Install new dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install python-telegram-bot python-dotenv
```

After updating `requirements.txt`, run the live bot locally:

```powershell
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe scripts\run_telegram_bot.py
```

Then open Telegram and test:

```text
/start_assessment
```

Expected manual flow:

```text
/start_assessment
-> Question 1/10 appears
-> tap answer buttons through all 10 baseline questions
-> tap Recommend roles
-> tap Data Scientist
-> answer 5 target-gap questions
-> final score appears
-> tap Why this score?
-> tap Show skill gaps
-> tap Show pathway
-> tap Generate action plan
```

**Acceptance Checks**

- `/start_assessment` sends Question 1/10 in Telegram.
- Baseline answer buttons advance through all 10 baseline questions.
- `Recommend roles` shows exactly 3 pathway options.
- Choosing `Data Scientist` triggers 5 follow-up target-gap questions.
- Follow-up answer buttons advance through all 5 gap questions.
- Final response shows skill suitability.
- Buttons expose score explanation, skill gaps, pathway, and action plan.
- `Generate action plan` sends a Markdown attachment; normal mode keeps it transient, while debug/local validation can persist audit artifacts.
- Existing local validation still passes:

```powershell
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe scripts\validate_m6_telegram.py
.\.venv\Scripts\python.exe scripts\validate_m7_demo.py
```

- No bot token or private Telegram identifiers are committed.

**Do Not Stray Into**

- dashboard frontend
- parser agents
- changing scoring formulas
- new weighting scheme
- storing private user data by default
- webhook deployment before local polling works

### N2: Improve Demo Robustness And Judge Experience

**Status**

In progress. Initial feedback found the questionnaire too technical, answer labels too formal, and Telegram explanations too cluttered. First UX polish pass is implemented with a current-role steering step, friendlier answer labels, shorter prompts, clearer pathway reasons, and plain-language score explanations. The next refinement loop is local-first: generate workflow previews, review wording and presentation, then push polished compact text back into Telegram.

**Goal Prompt**
Make the existing MVP easier to demo and judge without changing core formulas.

**Why This Matters**
The backend is validated, but judges need a smooth story, predictable commands, and clear artifacts.

**Inputs**
- `docs/demo_validation.md`
- `docs/judging_package.md`
- `data/processed/m5_explainability_action_plan.md`
- `data/processed/m6_telegram_flow_demo.md`

**Outputs**
- concise demo script
- local workflow preview artifact
- questionnaire UX review runbook
- one-page judge walkthrough
- expected output screenshots or transcript snippets
- README quickstart update

**Acceptance Checks**
- A judge can understand the product in under 2 minutes.
- Demo path can be repeated from clean setup.
- Local workflow preview shows compact prompts, full dataset detail, answer mappings, recommendations, and UX flags.
- Explainability and data traceability are visible without reading code.

**Do Not Stray Into**
- new product features
- model-based resume parsing
- manual weighting redesign

### N7: Optional Explain Agent Routing

**Status**

Implemented as an optional post-scoring explanation layer. The agent uses `gpt-5-nano` when an explainer token is configured and falls back to deterministic rule-based explanations when no token exists, the SDK is unavailable, or the call fails.

**Goal Prompt**

Route recommendation and score explanations through an optional explain agent while preserving deterministic scoring as the source of truth.

**Why This Matters**

Judges and users need more insight than a percentage. The agent can make computed facts easier to understand, but the product remains explainable only if scores, rankings, and pathways are still generated by deterministic dataset logic.

**Inputs**

- recommendation table from the questionnaire/scoring engine
- selected-role `FitSummary`
- selected-role gap table
- `.env` optional explainer token

**Outputs**

- `src/jobs_skills/explainer_agent.py`
- optional `gpt-5-nano` explanation when configured
- rule-based fallback explanation when no token is configured
- Telegram recommendation and `Why this score?` messages with explicit agent boundary

**Implementation Notes**

- Parser agents sit before scoring as evidence extractors.
- The explain agent sits after deterministic scoring and before Telegram/report rendering.
- The explain agent receives structured computed facts only.
- It must not change scores, rankings, pathway fit, or gap tables.
- Supported token keys include `EXPLAINER_AGENT_API_TOKEN`, `AGENT_API_TOKEN`, and `OPENAI_API_KEY`.
- Default model is `gpt-5-nano`.

**Acceptance Checks**

- `scripts/validate_explainer_agent.py` passes with no token.
- `scripts/validate_m6_telegram.py` shows recommendation and score explanation fallback text in deterministic test mode.
- Telegram still shows the deterministic suitability percentage.
- Agent failures do not break the user flow.

**Do Not Stray Into**

- agent-generated final scores
- agent-generated ranking changes
- parser-agent upload flows
- storing private user text

### N3: Add A Second Role Family Or Scenario

**Goal Prompt**
Add one more validated demo scenario using the same engine, preferably a lateral role transfer, without changing the MVP scoring assumptions.

**Why This Matters**
A second scenario shows the method is not hard-coded to Data Analyst to Data Scientist.

**Inputs**
- normalized role-skill tables
- scoring/questionnaire/pathway modules
- M2-M6 validators as templates

**Outputs**
- second scripted demo report
- second validation path
- short comparison of growth versus lateral transfer

**Acceptance Checks**
- Second scenario produces 3 recommendations.
- Follow-up questions remain within 3 to 5.
- Generated action plan has K&A-backed actions.
- Scenario does not introduce new weights or hidden assumptions.

**Do Not Stray Into**
- broad role-family tagging
- manual skill weighting categories
- dashboard work

### N4: Decide Whether To Keep Large Generated CSVs In Git

**Goal Prompt**
Review repository packaging and decide whether generated processed data should stay committed or be regenerated during setup.

**Why This Matters**
`data/processed/skill_ka_items.csv` is useful for judge visibility but is above GitHub's recommended 50 MB file size.

**Inputs**
- `data/processed/`
- `scripts/run_data_pipeline.py`
- `scripts/validate_m1_data.py`

**Outputs**
- packaging decision
- README setup note
- optional `.gitignore` update if generated outputs should not be tracked later

**Acceptance Checks**
- Fresh clone instructions are clear.
- Judges can still inspect evidence artifacts.
- No file exceeds GitHub's hard file size limit.

**Do Not Stray Into**
- changing data schema
- deleting evidence without replacement

### N5: Stretch Only - Resume/JD Parser Agents

**Status**

Partially implemented as an offline stretch demo. `src/jobs_skills/parser_agents.py` extracts resume and JD skill evidence, inferred levels, confidence, mapping type, and uncertainty flags. `scripts/validate_f1_f3_parser_agents.py` confirms uncertain parser output can be user-confirmed, converts parser output into vectors, reuses deterministic scoring, and writes `data/processed/f3_resume_jd_suitability_demo.md`. Live Telegram upload/chat integration is not implemented yet.

**Goal Prompt**
Add parser agents only after the live Telegram/demo package is stable. Parser agents extract evidence, but deterministic scoring remains the final scoring authority.

**Why This Matters**
Resume/JD parsing is valuable but introduces uncertainty. It should not weaken the explainable questionnaire MVP.

**Inputs**
- `.codex/skills/jobs-skills-parser-agents/SKILL.md`
- normalized skills table
- deterministic scoring engine

**Outputs**
- resume skill evidence extraction
- JD requirement extraction
- confidence/evidence fields
- user confirmation for uncertain mappings
- offline resume-to-JD suitability demo report

**Acceptance Checks**
- Parser output includes evidence and confidence.
- User can confirm uncertain inferred skills.
- Final suitability score is still calculated by deterministic scoring.
- Full resume text is not stored by default.
- `scripts/validate_f1_f3_parser_agents.py` passes and produces `data/processed/f3_resume_jd_suitability_demo.md`.

**Do Not Stray Into**
- replacing the questionnaire MVP
- agent-generated final scores
- storing private resume data by default

### N6: Optional Policy Hooks - Weights And Sector Constraints

**Status**

Implemented as explicit opt-in methodology hooks. `SkillWeightPolicy` and `apply_skill_weight_policy` allow future core / important / supporting tags while defaulting every multiplier to `1.0`. `pathway_policy_for_sector_mode` exposes `open_mobility`, `prefer_same_sector`, and `restrict_same_sector` modes while keeping sector as pathway metadata rather than a skill-vector dimension. `scripts/validate_f4_f5_policy_options.py` writes `data/processed/f4_f5_policy_options_demo.md`.

**Goal Prompt**
Add future-facing policy options without changing MVP defaults. Keep all active MVP skill weights at `1.0`, and keep sector outside the skill vector.

**Why This Matters**
This answers the weighting and sector methodology questions without introducing hidden assumptions into the demo score.

**Inputs**
- deterministic scoring engine
- inferred pathway graph policy
- role sector and track metadata

**Outputs**
- visible optional weighting policy table
- explicit sector constraint modes
- validation report showing default and future-policy behavior

**Acceptance Checks**
- Default skill weights remain `1.0`.
- Non-default weighting only applies when explicitly supplied.
- Sector toggle supports open mobility, prefer same sector, and restrict same sector.
- `scripts/validate_f4_f5_policy_options.py` passes.

**Do Not Stray Into**
- activating differentiated weights by default
- treating sector as a skill dimension
- hiding sector penalties inside suitability percentage

## Milestones

### M0: Project setup and documentation hygiene

**Goal Prompt**

You are setting up project structure and process evidence only. Focus on docs, project skills, and discussion archives. Do not implement product features.

**Why This Matters**

The judging criteria include process evidence. The repo needs clear planning artifacts before implementation starts.

**Inputs**

- `docs/project_brief.md`
- project-level `.codex/skills`
- existing daily discussion archive workflow

**Outputs**

- `docs/roadmap.md`
- validated project-level skills
- daily discussion summary/raw archive process

**Implementation Notes**

- Keep roadmap and process docs concise but decision-complete.
- Use daily discussion summaries to preserve human-AI collaboration evidence.
- Add `AGENTS.md` later only if implementation conventions need to be made durable.

**Acceptance Checks**

- `docs/project_brief.md` exists.
- `docs/roadmap.md` exists.
- Project-level skills under `.codex/skills` validate.
- Daily discussion archive workflow is documented.

**Do Not Stray Into**

- Dataset processing
- Scoring
- Questionnaire logic
- Telegram bot implementation

### M1: Data pipeline and normalized feature tables

**Goal Prompt**

You are building the data backbone. Focus only on ingesting, cleaning, joining, validating, and exporting normalized SkillsFuture data tables. Do not build recommendations, Telegram flows, graph search, or parser agents yet.

**Why This Matters**

All scoring, pathways, and explanations depend on clean role-skill-proficiency data. Weak data processing weakens the whole product.

**Inputs**

- `dataset/jobsandskills-skillsfuture-skills-framework-dataset.xlsx`
- `dataset/jobsandskills-skillsfuture-tsc-to-unique-skills-mapping.xlsx`
- `dataset/jobsandskills-skillsfuture-unique-skills-list.xlsx`
- `docs/project_brief.md`
- `.codex/skills/jobs-skills-data-pipeline`

**Outputs**

- normalized `roles`
- normalized `skills`
- normalized `role_skill_requirements`
- normalized `skill_ka_items`
- data quality report
- sample Data Analyst and Data Scientist role profiles

**Implementation Notes**

- Use Python as the core language.
- Read datasets from the repo-local `dataset/` directory; do not depend on files in `Downloads`.
- Join role skills to unique skills by `TSC_CCS Code` plus `Proficiency Level`, not title.
- Normalize proficiency values with `Basic = 1`, `Intermediate = 3`, `Advanced = 5`.
- Collapse duplicate role + unique skill rows using max required proficiency.
- Set every MVP `skill_weight = 1.0`.
- Preserve source codes, source titles, source proficiency levels, and source row references for auditability.
- Prefer reproducible scripts over notebook-only work.

**Acceptance Checks**

- Role count is reported.
- Skill count is reported.
- Role-skill requirement row count is reported.
- K&A item count is reported.
- Join coverage from role skills to unique skills is reported.
- Join coverage from role skills to K&A items is reported.
- Non-numeric proficiency normalization count is reported.
- Sample Data Analyst and Data Scientist profiles can be printed from normalized tables.
- Every role-skill requirement can trace back to source skill code/title/proficiency.

**Do Not Stray Into**

- Recommendation ranking
- Telegram bot
- Graph pathway planning
- Resume/JD parsing

### M2: Deterministic scoring engine

**Goal Prompt**

You are building deterministic suitability and gap scoring from normalized tables. Focus on reproducible formulas and explainable outputs. Do not build Telegram, graph multipliers, or parser agents.

**Why This Matters**

Users need to understand how they are being judged. Deterministic scoring makes recommendations reproducible and auditable.

**Inputs**

- normalized tables from M1
- `.codex/skills/jobs-skills-scoring-engine`
- sample user skill vector

**Outputs**

- role vectors
- user vectors
- skill suitability percentage
- gap table
- top matched skills
- top priority gaps

**Implementation Notes**

- Use all skill weights as `1.0`.
- Keep the weighted formula in code, but MVP results behave as unweighted.
- Treat missing user skill as level `0` unless explicitly marked unknown.
- Keep skill suitability separate from pathway fit.
- Return source identifiers needed for explanation.

**Acceptance Checks**

- Same inputs always produce the same score.
- Data Analyst to Data Scientist example produces a reproducible score and gap table.
- Output includes current level, target level, gap, and source skill title.
- Top gaps can be sorted by gap size and target level.
- Score can be recomputed manually from visible values.

**Do Not Stray Into**

- Sector/track graph multipliers
- Telegram UI
- Resume/JD parsing
- Manual core/important/supporting weighting

### M3: Hybrid questionnaire engine

**Goal Prompt**

You are building the assessment flow. Focus on turning user answers into a user skill vector through a short baseline questionnaire and selected-pathway follow-up. Do not build parser agents or polish Telegram UI.

**Why This Matters**

The questionnaire is the core MVP input. It keeps the product controlled, explainable, and independent of uncertain resume parsing.

**Inputs**

- normalized tables from M1
- scoring engine from M2
- `.codex/skills/jobs-skills-questionnaire-flow`

**Outputs**

- baseline question selection
- answer-to-level mapping
- user skill vector updates
- 3 pathway recommendation handoff
- 3 to 5 selected-pathway follow-up questions

**Implementation Notes**

- Baseline assessment asks 8 to 12 current-role skills.
- Follow-up asks only target-gap questions after the user chooses a pathway.
- Questions should be evidence-based, not vague self-ratings.
- Store answer, inferred level, confidence or unknown flag, and explanation.
- Show why the score changed after follow-up answers.

**Acceptance Checks**

- Scripted user can complete baseline assessment.
- System recommends 3 pathways after baseline.
- User can choose one pathway.
- Selected pathway triggers only 3 to 5 target-gap questions.
- Updated score reflects the extra answers.
- Explanation can show which answers affected the score.

**Do Not Stray Into**

- Full Telegram polish
- Resume/JD parsing
- Manual differentiated skill weights
- Dashboard frontend

### M4: Pathway graph and pathway fit

**Goal Prompt**

You are building inferred role-to-role pathways. Focus on graph edges, pathway policy, and pathway fit. Do not change skill suitability formulas.

**Why This Matters**

Skill fit alone does not explain whether a transition is realistic. Pathway fit adds explainable sector, track, and transition context.

**Inputs**

- normalized role and role-skill tables from M1
- scoring outputs from M2
- selected pathway from M3
- `.codex/skills/jobs-skills-pathway-graph`

**Outputs**

- derived role graph
- configurable pathway policy
- pathway fit score
- Dijkstra path for selected target
- explanation of inferred path

**Implementation Notes**

- Sector and track are metadata, not skill-vector dimensions.
- Use context multipliers for sector/track friction.
- Keep all skill weights at `1.0`.
- Label pathways as inferred.
- Use graph search only after target pathway selection.
- Keep skill suitability separate from pathway fit.

**Acceptance Checks**

- Same-sector realistic pathways rank ahead of unrelated low-requirement roles.
- Pathway fit is shown separately from skill suitability.
- Edge assumptions can be displayed to the user.
- Dijkstra path can be produced for a selected target role.
- Pathway step explanation identifies skills and transition context.

**Do Not Stray Into**

- Changing data joins
- Changing scoring formulas
- Telegram UI
- Resume/JD parsing

### M5: Explainability and action-plan report

**Goal Prompt**

You are building user-facing explanation and action planning. Focus on making every score and pathway understandable. Do not alter scoring formulas or pathway ranking.

**Why This Matters**

The product value depends on users understanding how they are judged, why a path is recommended, and what actions they can take next.

**Inputs**

- scoring outputs from M2
- selected pathway and pathway fit from M4
- K&A items from M1
- `.codex/skills/jobs-skills-explainability-planner`

**Outputs**

- concise recommendation explanation
- top gap explanation
- learning action plan
- Markdown or HTML report

**Implementation Notes**

- Use K&A items for concrete actions.
- Show matched skills, missing skills, current level, target level, and gap.
- Explain all scores from visible inputs.
- Keep Telegram text short and put detail in the generated report.
- State that all skill weights are `1.0` for MVP.
- Label derived pathways as inferred.

**Acceptance Checks**

- User can see how they were judged.
- User can see why each pathway was recommended.
- User can see which skills caused the recommendation.
- Report includes 3 to 5 concrete next actions.
- Every recommendation links back to role-skill requirements and K&A logic.

**Do Not Stray Into**

- Changing ranking logic
- Parser agents
- Broad UI dashboard work
- New weighting scheme

### M6: Telegram bot integration

**Goal Prompt**

You are wiring the existing engine into Telegram. Focus on the constrained MVP interaction. Do not move business logic into bot handlers.

**Why This Matters**

Telegram reduces frontend complexity and lets the MVP focus on data quality, scoring, pathway logic, and explainability.

**Inputs**

- questionnaire engine from M3
- scoring engine from M2
- pathway graph from M4
- report generator from M5
- `.codex/skills/telegram-career-bot`

**Outputs**

- Telegram command handlers
- inline buttons
- session state
- connection to scoring/questionnaire/report modules

**Implementation Notes**

- Current v2 BotFather commands:
  - `/start`
  - `/first_time_user`
  - `/start_resume`
  - `/search_roles`
  - `/explain_score`
  - `/show_gaps`
  - `/generate_action_plan`
- Legacy questionnaire actions remain internal/validation-only unless explicitly revived.
- Keep messages concise.
- Send transient report/action-plan attachments for detailed normal-mode explanations; persist debug reports only when explicitly enabled.
- Do not store private identifiers by default.
- Keep business logic in Python modules or service layer, not bot handlers.

**Acceptance Checks**

- User can complete full MVP through Telegram.
- Buttons expose score explanation, gaps, pathway, and action plan.
- Telegram flow uses deterministic backend outputs.
- Report generation is accessible from Telegram.
- Session state supports baseline questions, pathway selection, and gap follow-up.

**Do Not Stray Into**

- Dashboard frontend
- Resume/JD parser agents
- Changing scoring logic
- Adding private-data collection

### M7: End-to-end demo validation and judging package

**Goal Prompt**

You are validating and packaging the demo. Focus on reliability, judging evidence, and process documentation. Do not add new product features unless required to fix a demo blocker.

**Why This Matters**

The judging criteria include both product and process. The final package must prove technical execution, transparent data use, user value, and human-AI collaboration.

**Inputs**

- complete MVP flow from M1 to M6
- `docs/project_brief.md`
- `docs/roadmap.md`
- daily discussion summaries and raw archives

**Outputs**

- scripted demo scenario
- validation checklist
- generated sample report
- judging notes mapped to criteria
- process evidence package

**Implementation Notes**

- Use one polished demo path, such as Data Analyst to Data Scientist.
- Capture inputs, scores, explanations, pathway, and generated report.
- Preserve daily discussion summaries and raw archives.
- Map final evidence to data integrity, user focus, technical execution, and process.

**Acceptance Checks**

- One complete end-to-end demo path works.
- Data integrity checks are visible.
- Explainability checks pass.
- Generated report is readable and concise.
- Process artifacts are ready for submission.

**Do Not Stray Into**

- New parser features
- Broad refactors
- Additional UI channels
- New scoring assumptions

### Stretch: Resume/JD parser agents

**Goal Prompt**

You are adding stretch parsing only after the questionnaire MVP works. Focus on evidence extraction with confidence. Do not let agents decide final suitability.

**Why This Matters**

Resume/JD parsing can improve job-fit analysis, but it introduces uncertainty. It should not weaken the deterministic and explainable MVP.

**Inputs**

- questionnaire MVP outputs
- normalized skills and K&A tables
- `.codex/skills/jobs-skills-parser-agents`

**Outputs**

- resume skill evidence extraction
- JD skill requirement extraction
- confidence and evidence fields
- user confirmation flow for uncertain skills

**Implementation Notes**

- Parser agents extract evidence only.
- Deterministic scoring engine calculates final suitability.
- Label non-dataset mappings as inferred.
- Do not store full resume text by default.

**Acceptance Checks**

- Parser output includes evidence, inferred level, and confidence.
- Uncertain skills can be confirmed by the user.
- Parser output feeds deterministic scoring.
- Agent does not generate final score directly.

**Do Not Stray Into**

- Replacing the questionnaire MVP
- Agent-generated final scores
- Storing full resume text by default

## Test Plan

- M1: Validate counts, join coverage, proficiency normalization, and sample role profiles.
- M2: Test deterministic scoring with fixed user and role vectors.
- M3: Run a scripted questionnaire session through baseline and selected-pathway follow-up.
- M4: Test pathway ranking against the known gap-only failure mode.
- M5: Review explanation completeness against score inputs and source dataset logic.
- M6: Run Telegram end-to-end flow.
- M7: Rehearse the demo and verify judging artifacts.
- Stretch F1-F3: Run `scripts/validate_f1_f3_parser_agents.py` to verify parser evidence extraction, confirmation, deterministic suitability, and action-plan output.
- Optional F4-F5: Run `scripts/validate_f4_f5_policy_options.py` to verify default 1.0 weights, opt-in weighting, and sector constraint modes.
- Optional explain agent: Run `scripts/validate_explainer_agent.py` to verify no-token fallback, default `gpt-5-nano`, and agent boundary checks.
- Local UX preview: Run `scripts/validate_local_workflow_preview.py` to verify compact prompts, full dataset detail, and local workflow artifact generation.

## Assumptions

These assumptions were the original roadmap guardrails. The current product truth is noted at the top of this file.

- Data processing is allowed to take extra time because it is the product backbone.
- Original M0-M7 scope was questionnaire-first; current demo is resume/role-first with questionnaire retained as legacy/internal validation.
- Resume/JD parsing started as stretch and is now implemented for the current Telegram workflow.
- Telegram plus transient report/action-plan attachments is the MVP demo surface.
- All skill weights are `1.0` for MVP.
- Private personal data is not stored by default.
