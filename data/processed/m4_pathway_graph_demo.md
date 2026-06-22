# M4 Pathway Graph Demo - Data Analyst to Data Scientist

## Scope

- Pathways are inferred from role-skill requirements, not explicitly provided by the dataset.
- Skill suitability remains the deterministic M2 score.
- Pathway fit is a separate graph metric using configurable sector/track context multipliers.

## Pathway Policy

| setting | value |
| --- | --- |
| allow_cross_sector | True |
| min_skill_overlap | 0.25 |
| max_gap_cost | nan |
| same_sector_multiplier | 1.0 |
| related_sector_multiplier | 1.15 |
| unrelated_sector_multiplier | 1.35 |
| same_track_multiplier | 0.85 |
| related_track_multiplier | 0.95 |
| unrelated_track_multiplier | 1.2 |
| low_overlap_penalty | 5.0 |
| missing_critical_skill_penalty | 0.0 |

## Source Role Candidate Edges

| target_job_role | target_sector | target_track | skill_suitability_percentage | skill_gap_cost | skill_overlap_ratio | edge_weight | edge_fit_percentage | edge_assumptions |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Data Engineer | Financial Services | Digital and Data Analytics | 72.0 | 7.0 | 0.75 | 0.24 | 80.78 | inferred pathway edge; skill suitability from deterministic M2 scoring; sector context: same sector; track context: same track; MVP skill weights all 1.0; critical-skill penalty inactive for MVP |
| Data Scientist | Financial Services | Digital and Data Analytics | 68.97 | 18.0 | 0.87 | 0.26 | 79.13 | inferred pathway edge; skill suitability from deterministic M2 scoring; sector context: same sector; track context: same track; MVP skill weights all 1.0; critical-skill penalty inactive for MVP |
| Risk Analytics Analyst / Compliance Analytics Analyst | Financial Services | Risk, Compliance and Legal | 58.33 | 15.0 | 0.58 | 0.4 | 71.64 | inferred pathway edge; skill suitability from deterministic M2 scoring; sector context: same sector; track context: different track in same sector; MVP skill weights all 1.0; critical-skill penalty inactive for MVP |
| Risk Analytics Analyst / Compliance Analytics Analyst (Asset Management) | Financial Services | Risk, Compliance and Legal | 58.33 | 15.0 | 0.58 | 0.4 | 71.64 | inferred pathway edge; skill suitability from deterministic M2 scoring; sector context: same sector; track context: different track in same sector; MVP skill weights all 1.0; critical-skill penalty inactive for MVP |
| Risk Analytics Analyst / Compliance Analytics Analyst (Corporate Banking) | Financial Services | Risk, Compliance and Legal | 58.33 | 15.0 | 0.58 | 0.4 | 71.64 | inferred pathway edge; skill suitability from deterministic M2 scoring; sector context: same sector; track context: different track in same sector; MVP skill weights all 1.0; critical-skill penalty inactive for MVP |
| Risk Analytics Analyst / Compliance Analytics Analyst (Retail Banking) | Financial Services | Risk, Compliance and Legal | 58.33 | 15.0 | 0.58 | 0.4 | 71.64 | inferred pathway edge; skill suitability from deterministic M2 scoring; sector context: same sector; track context: different track in same sector; MVP skill weights all 1.0; critical-skill penalty inactive for MVP |
| Risk Analytics Analyst / Compliance Analytics Analyst (investment Banking) | Financial Services | Risk, Compliance and Legal | 58.33 | 15.0 | 0.58 | 0.4 | 71.64 | inferred pathway edge; skill suitability from deterministic M2 scoring; sector context: same sector; track context: different track in same sector; MVP skill weights all 1.0; critical-skill penalty inactive for MVP |
| Head of Data Analytics | Financial Services | Digital and Data Analytics | 52.31 | 31.0 | 0.79 | 0.41 | 71.15 | inferred pathway edge; skill suitability from deterministic M2 scoring; sector context: same sector; track context: same track; MVP skill weights all 1.0; critical-skill penalty inactive for MVP |

## Dijkstra Selected Path

- Role-id path: role_535b6c2a545b -> role_7e5ba6ce4199
- Total graph cost: 0.2638
- Pathway fit: 79.13%

| source_job_role | target_job_role | skill_suitability_percentage | skill_gap_cost | edge_weight | edge_fit_percentage | priority_gap_titles | edge_assumptions |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Data Analyst | Data Scientist | 68.97 | 18.0 | 0.26 | 79.13 | People Performance Management, Software Configuration, Data Analytics and Computational Modelling, Data Collection and Analysis, Data Governance | inferred pathway edge; skill suitability from deterministic M2 scoring; sector context: same sector; track context: same track; MVP skill weights all 1.0; critical-skill penalty inactive for MVP |

## Derived Local Graph Size

- Nodes touched: 10
- Directed edges: 40
