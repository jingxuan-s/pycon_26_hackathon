---
name: telegram-career-bot
description: Build, update, or review the Telegram MVP interface for the jobs-skills career pathway project. Use when Codex needs to implement bot commands, inline buttons, session state, questionnaire interactions, pathway selection, score explanations, or generated report links for the Telegram-first MVP.
---

# Telegram Career Bot

## MVP Role

Telegram is the constrained interaction layer. Keep business logic in Python services/modules, not inside bot handlers.

Recommended backend shape:

```text
Telegram Bot -> FastAPI/service layer -> scoring/pathway engine -> dataset tables
```

## Required Flow

1. `/start_assessment`
2. Ask baseline questionnaire.
3. Build user vector.
4. Recommend 3 pathways.
5. User selects one pathway.
6. Ask 3 to 5 target-gap questions.
7. Recalculate scores.
8. Offer explanation/action-plan buttons.

## Commands / Actions

- `/start_assessment`
- `/answer_question`
- `/recommend_roles`
- `/choose_pathway`
- `/answer_gap_question`
- `/explain_score`
- `/show_gaps`
- `/show_pathway`
- `/generate_action_plan`

## Response Style

Keep chat responses short:

```text
Recommended pathway: Data Analyst -> Data Scientist
Skill Suitability: 82%
Pathway Fit: 74%

Why:
- 13 of 15 target skill areas overlap.
- 6 skills are one level below target.
- 2 gaps need attention first.
```

Use buttons for drill-down:

```text
[Why this score?]
[Show skill gaps]
[Show pathway]
[Change target]
[Generate action plan]
```

## Privacy

For the questionnaire MVP, do not request or persist private identifiers. Store only temporary session state needed to complete the assessment.