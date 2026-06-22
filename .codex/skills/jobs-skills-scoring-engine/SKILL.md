---
name: jobs-skills-scoring-engine
description: Build, update, or review deterministic scoring and recommendation logic for the jobs-skills career pathway MVP. Use when Codex needs to create skill vectors, calculate suitability percentages, compute gap costs, rank roles, or explain user-role fit from proficiency levels.
---

# Jobs Skills Scoring Engine

## Core Principle

Scoring must be deterministic and reproducible. Agents may interpret or explain, but they must not directly decide the final score.

## Inputs

- `user_vector[skill_id] = assessed proficiency level`
- `role_vector[skill_id] = required proficiency level`
- `skill_weight = 1.0` for MVP
- optional filters: current role, sector, track, target intent, excluded sectors

## MVP Formulas

```text
covered = min(user_level, target_level)
suitability = sum(covered) / sum(target_level)
gap = max(target_level - user_level, 0)
gap_cost = sum(skill_weight * gap)
```

The weighted formula should exist in code, but all weights remain `1.0` until a defensible weighting method is added.

## Ranking Flow

1. Exclude the user's current role and near-duplicate roles when needed.
2. Apply hard filters from user intent.
3. Shortlist roles by skill overlap or exact vector similarity.
4. Rank shortlisted roles by suitability, gap cost, and pathway policy.
5. Return the top 3 pathways for the hybrid questionnaire MVP.

## Output Contract

Every recommendation should include:

- `role_id`
- skill suitability percentage
- pathway fit if graph context is available
- matched skills
- gaps sorted by impact
- current level, target level, and gap per priority skill
- source row identifiers needed for explanation

## Guardrails

- Do not use HNSW for the MVP dataset unless the indexed role/job set grows substantially.
- Do not hide context penalties inside one unexplained score; keep raw skill suitability separate from pathway fit.
- Treat missing user skill as level `0`, unless the questionnaire explicitly records `unknown` and asks follow-up questions.