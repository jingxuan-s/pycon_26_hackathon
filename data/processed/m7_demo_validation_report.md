# M7 Demo Validation Report

## End-to-End Scenario

Current role: Financial Services / Digital and Data Analytics / Data Analyst
Target pathway: Financial Services / Digital and Data Analytics / Data Scientist
Interface surface: Telegram-style command/button flow plus generated Markdown report

## Validation Results

| Validator | Status | Duration Seconds | Key Output |
| --- | --- | --- | --- |
| `scripts/validate_m1_data.py` | PASS | 1.09 | M1 validation passed |
| `scripts/validate_m2_scoring.py` | PASS | 0.86 | M2 validation passed |
| `scripts/validate_m3_questionnaire.py` | PASS | 0.67 | M3 validation passed |
| `scripts/validate_m4_pathway.py` | PASS | 2.38 | M4 validation passed |
| `scripts/validate_m5_report.py` | PASS | 2.46 | M5 validation passed |
| `scripts/validate_m6_telegram.py` | PASS | 6.02 | M6 Telegram v2 validation passed |
| `scripts/validate_explainer_agent.py` | PASS | 0.70 | Explainer agent validation passed |

## Required Artifacts

- `data/processed/data_quality_report.md`
- `data/processed/m2_scoring_example.md`
- `data/processed/m3_questionnaire_demo.md`
- `data/processed/m4_pathway_graph_demo.md`
- `data/processed/m5_explainability_action_plan.md`
- `data/processed/m6_telegram_flow_demo.md`
- `docs/daily_discussion/2026-06-19.md`
- `docs/daily_discussion/raw/2026-06-19.md`
- `docs/project_brief.md`
- `docs/roadmap.md`

## Acceptance Summary

- One complete end-to-end demo path works from questionnaire baseline to generated action plan.
- Data integrity checks are visible through M1 data quality report and validation script.
- Explainability checks pass through M5 report validation.
- Telegram MVP flow is validated without requiring a live token.
- Process artifacts are ready under `docs/daily_discussion/`.
