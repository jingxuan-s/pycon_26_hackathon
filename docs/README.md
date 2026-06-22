# Documentation Index

Use this page as the entry point for project documentation.

## Product And Demo

- [README](../README.md): product overview, setup, validation commands, and judging criteria mapping.
- [Telegram live testing](telegram_live_testing.md): BotFather commands, local polling commands, and manual demo flow.
- [Demo validation](demo_validation.md): recommended validation order and evidence checklist.
- [Casey persona](casey_persona.md): user-facing voice and safety boundaries.

## Methodology

- [Scoring methodology](scoring_methodology.md): sparse skill vectors, weighted L1 Explore discovery, suitability scoring, goal-mode diagrams, pathway graph assumptions, and agent boundaries.
- [Project brief](project_brief.md): broader methodology notes, dataset findings, product decisions, and judging rationale.
- [Workflow diagram](workflow_diagram.md): technical flow showing parser, scoring, related-skill, explainer, and report layers.
- [Simplified workflow diagram](workflow_diagram_simplified.md): non-technical workflow overview.
- [Minimal workflow diagram](workflow_diagram_minimal.md): compact high-level flow.

## Delivery And Evidence

- [Roadmap](roadmap.md): milestone prompts, implementation history, and current completion notes.
- [Judging package](judging_package.md): evidence mapping to judging criteria.
- [Future work completion audit](future_work_completion_audit.md): status of parser agents, policy hooks, live Telegram adapter, and remaining evidence notes.
- [Local workflow review](local_workflow_review.md): local CLI tools for reviewing workflow behavior outside Telegram.
- [Daily discussion summaries](daily_discussion/): compact process evidence.
- [Raw daily discussion archives](daily_discussion/raw/): raw process archives for judging.

## Current Product Truth

- Core demo surface: Telegram bot with Casey the Career Auntie persona.
- Main entry paths: upload resume or search/select a current role.
- Mandatory review: users review, edit, remove, or add skills before scoring.
- Goal modes: Explore pathways, Advance roles, Search target role, Paste JD.
- Scoring: deterministic target-aware suitability; agents extract or explain only.
- Explore discovery: weighted L1 nearest-neighbour shortlist with shared-skill overlap guard, then suitability/gap re-ranking.
- Reports: normal Telegram reports/action plans are transient attachments; debug reports preserve audit details when explicitly enabled.
