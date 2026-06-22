---
name: jobs-skills-explainability-planner
description: Build, update, or review explanation and action-plan generation for the jobs-skills career pathway MVP. Use when Codex needs to explain scores, show matched and missing skills, trace recommendations to dataset rows, or convert skill/proficiency gaps into learning actions using K&A items.
---

# Jobs Skills Explainability Planner

## Product Promise

Users should understand why a role was recommended, which skills caused the recommendation, and what actions can move them closer.

## Required Explanation Blocks

For each recommended role or selected pathway, show:

- skill suitability percentage
- pathway fit, if graph context is used
- matched skills
- priority gaps
- current level, target level, and gap
- source logic from role-skill requirements and K&A items
- next 3 to 5 actions

## Action Plan Logic

For each priority gap:

1. Identify the skill and target role requirement.
2. Pull proficiency descriptions and K&A items for the target level.
3. Compare current level to target level.
4. Generate concise next actions tied to evidence the user can produce.

Good pattern:

```text
Gap: Data Governance
Current level: 3
Target level: 4
Why it matters: Required by the selected Data Scientist role.
Next action: Practise the level-4 ability items and build evidence through a project or workplace task.
Source: Skills Framework K&A items for Data Governance level 4.
```

## Guardrails

- Do not show long full skill lists in Telegram.
- Do not generate unsupported claims; explanations must trace to user answers or dataset rows.
- Do not hide scoring assumptions. Show if all weights are `1.0` in MVP.
- Label derived pathways as inferred.