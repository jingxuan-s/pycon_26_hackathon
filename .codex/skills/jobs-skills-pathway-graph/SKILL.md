---
name: jobs-skills-pathway-graph
description: Build, update, or review the career pathway graph for the jobs-skills MVP. Use when Codex needs to derive role-to-role edges, configure sector/track constraints, calculate pathway fit, tune edge weights, or run Dijkstra/path search with explainable policy assumptions.
---

# Jobs Skills Pathway Graph

## Core Principle

Role-to-role pathways are inferred, not explicitly provided by the dataset. Label them as inferred pathways and explain the edge logic.

## Graph Nodes

- `JobRole`
- `Sector`
- `Track`
- `UniqueSkill`
- `TscCcsSkill`
- `KnowledgeAbilityItem`
- optional user/session nodes for runtime state

## Edge Policy

Use a configurable `PathwayPolicy` rather than hard-coded constants:

```python
@dataclass
class PathwayPolicy:
    allow_cross_sector: bool = True
    min_skill_overlap: float = 0.25
    max_gap_cost: float | None = None
    same_sector_multiplier: float = 1.00
    related_sector_multiplier: float = 1.15
    unrelated_sector_multiplier: float = 1.35
    same_track_multiplier: float = 0.85
    related_track_multiplier: float = 0.95
    unrelated_track_multiplier: float = 1.20
    low_overlap_penalty: float = 5.0
    missing_critical_skill_penalty: float = 0.0  # MVP weights all skills equally
```

For MVP, keep critical skill penalties inactive unless critical skills are explicitly tagged.

## Edge Weight

```text
edge_weight = (base_skill_gap_cost + additive_penalties) * context_multipliers
```

Keep skill suitability separate from pathway fit.

## Search Flow

- For recommendations, first shortlist realistic target roles with the scoring engine.
- Only run pathway search after a target role or target family is known.
- Use Dijkstra for chosen pathway planning.
- Show 3 to 5 priority skills per path step, not all gaps.

## Validation

Check that gap-only paths do not recommend unrelated low-requirement roles ahead of realistic transitions. Use Data Analyst -> Data Scientist examples as sanity checks.