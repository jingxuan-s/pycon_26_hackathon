---
name: jobs-skills-questionnaire-flow
description: Design, implement, or review the hybrid questionnaire assessment flow for the career pathway MVP. Use when Codex needs to choose baseline questions, map answers to proficiency levels, recommend 3 pathways, ask target-gap follow-up questions, or keep Telegram assessment concise.
---

# Jobs Skills Questionnaire Flow

## MVP Flow

Use the hybrid questionnaire flow from `docs/project_brief.md`.

Step 1: Assess current-role baseline.

- Ask current role, sector, and target intent.
- Select 8 to 12 high-signal skills from the likely current role family.
- Ask evidence-based questions mapped to proficiency descriptions and K&A items.
- Build the baseline user skill vector.

Step 2: Recommend 3 pathways.

- Compare the baseline vector to role profiles.
- Show 3 distinct choices such as growth, lateral transfer, and exploratory switch.
- Provide a short explanation for each.

Step 3: Refine selected pathway.

- After the user chooses a pathway, ask 3 to 5 extra questions for uncertain or high-impact target gaps.
- Recalculate scores and show what changed.

## Question Design

Prefer evidence-based options over vague self-rating.

Good pattern:

```text
For Data Governance, which best describes your experience?
A. I have not worked with this.
B. I follow existing data handling rules.
C. I apply governance checks in my own analysis.
D. I help define or improve governance practices for a team.
```

Map each option to an explicit level and store the mapping for explanation.

## Output Contract

Each answer should produce:

- `skill_id`
- selected answer
- inferred level
- confidence or certainty flag
- explanation text shown to the user when requested

## Guardrails

- Do not ask the user to rate all skills.
- Do not ask target-role gap questions before the user sees pathway options.
- Keep Telegram responses short; put detailed explanation into generated reports.