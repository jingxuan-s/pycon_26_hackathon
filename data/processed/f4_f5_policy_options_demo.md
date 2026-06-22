# F4-F5 Policy Options Demo

## Skill Weighting

MVP weighting remains 1.0 for every skill. The helper below only makes future core / important / supporting tags explicit and auditable when a non-default methodology is approved.

| skill | tier | mvp_multiplier |
| --- | --- | --- |
| Programming and Coding | core | 1.0 |
| Data Governance | important | 1.0 |

Future non-default example policy, not active in MVP scoring:

| tier | multiplier |
| --- | --- |
| core | 1.5 |
| important | 1.2 |
| supporting | 1.0 |

Baseline suitability with MVP weights: 68.97%
Future weighted example suitability: 69.24%

## Sector Constraint Modes

Sector is treated as pathway metadata and graph policy, not as a skill-vector dimension.

### open_mobility
| setting | value |
| --- | --- |
| allow_cross_sector | True |
| min_skill_overlap | 0.25 |
| max_gap_cost | None |
| same_sector_multiplier | 1.0 |
| related_sector_multiplier | 1.15 |
| unrelated_sector_multiplier | 1.35 |
| same_track_multiplier | 0.85 |
| related_track_multiplier | 0.95 |
| unrelated_track_multiplier | 1.2 |
| low_overlap_penalty | 5.0 |
| missing_critical_skill_penalty | 0.0 |

### prefer_same_sector
| setting | value |
| --- | --- |
| allow_cross_sector | True |
| min_skill_overlap | 0.25 |
| max_gap_cost | None |
| same_sector_multiplier | 0.9 |
| related_sector_multiplier | 1.1 |
| unrelated_sector_multiplier | 1.6 |
| same_track_multiplier | 0.85 |
| related_track_multiplier | 0.95 |
| unrelated_track_multiplier | 1.2 |
| low_overlap_penalty | 5.0 |
| missing_critical_skill_penalty | 0.0 |

### restrict_same_sector
| setting | value |
| --- | --- |
| allow_cross_sector | False |
| min_skill_overlap | 0.25 |
| max_gap_cost | None |
| same_sector_multiplier | 1.0 |
| related_sector_multiplier | 1.15 |
| unrelated_sector_multiplier | 1.35 |
| same_track_multiplier | 0.85 |
| related_track_multiplier | 0.95 |
| unrelated_track_multiplier | 1.2 |
| low_overlap_penalty | 5.0 |
| missing_critical_skill_penalty | 0.0 |

## Edge Examples

| mode | edge | edge_weight | allowed |
| --- | --- | --- | --- |
| open_mobility | same sector | 0.26379310344827583 | True |
| prefer_same_sector | same sector | 0.23741379310344823 | True |
| open_mobility | cross sector | 2.233636363636364 | True |
| restrict_same_sector | cross sector | inf | False |
