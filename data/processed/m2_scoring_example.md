# M2 Scoring Example - Data Analyst to Data Scientist

## Scenario

- Current profile: Financial Services / Digital and Data Analytics / Data Analyst
- Target role: Financial Services / Digital and Data Analytics / Data Scientist
- User vector source: current-role requirements from M1 normalized data
- MVP skill weights: `1.0` for every skill

## Suitability Formula

```text
covered_level = min(current_level, target_level)
suitability = sum(skill_weight * covered_level) / sum(skill_weight * target_level)
gap = max(target_level - current_level, 0)
gap_cost = sum(skill_weight * gap)
```

## Result

- Suitability: 68.97%
- Weighted covered level: 40.00
- Weighted target level: 58.00
- Gap cost: 18.00
- Matched target skills: 13 / 15
- Skills with gaps: 12

## Top Priority Gaps

| unique_skill_title | current_level | target_level | gap | tsc_ccs_code | source_row_number |
| --- | --- | --- | --- | --- | --- |
| People Performance Management | 0.0 | 4.0 | 4.0 | FSE-PDV-4051-1.1 | 16882 |
| Software Configuration | 0.0 | 4.0 | 4.0 | FSE-DIT-4014-1.1-1 | 16883 |
| Data Analytics and Computational Modelling | 3.0 | 4.0 | 1.0 | FSE-DAT-4019-1.1 | 16887 |
| Data Collection and Analysis | 3.0 | 4.0 | 1.0 | FSE-IAD-4003-1.1-1 | 16888 |
| Data Governance | 3.0 | 4.0 | 1.0 | FSE-SNA-4008-1.1-1 | 16884 |
| Data Storytelling and Visualisation | 3.0 | 4.0 | 1.0 | FSE-DAT-4020-1.1 | 16880 |
| Data-mining and Modelling | 3.0 | 4.0 | 1.0 | FSE-DAT-4003-1.1 | 16886 |
| Emerging Technology Synthesis | 3.0 | 4.0 | 1.0 | FSE-SNA-4011-1.1-1 | 16890 |
| Ethical Culture | 3.0 | 4.0 | 1.0 | FSE-PVE-4004-1.1-1 | 16885 |
| Programming and Coding | 3.0 | 4.0 | 1.0 | FSE-DIT-4018-1.1 | 16891 |

## Top Matched Skills

| unique_skill_title | current_level | target_level | gap | tsc_ccs_code | source_row_number |
| --- | --- | --- | --- | --- | --- |
| Sustainability Reporting | 4.0 | 4.0 | 0.0 | FSE-SUS-4003-1.2 | 16889 |
| Data Analytics and Computational Modelling | 3.0 | 4.0 | 1.0 | FSE-DAT-4019-1.1 | 16887 |
| Data Collection and Analysis | 3.0 | 4.0 | 1.0 | FSE-IAD-4003-1.1-1 | 16888 |
| Data Governance | 3.0 | 4.0 | 1.0 | FSE-SNA-4008-1.1-1 | 16884 |
| Data Storytelling and Visualisation | 3.0 | 4.0 | 1.0 | FSE-DAT-4020-1.1 | 16880 |
| Data-mining and Modelling | 3.0 | 4.0 | 1.0 | FSE-DAT-4003-1.1 | 16886 |
| Emerging Technology Synthesis | 3.0 | 4.0 | 1.0 | FSE-SNA-4011-1.1-1 | 16890 |
| Ethical Culture | 3.0 | 4.0 | 1.0 | FSE-PVE-4004-1.1-1 | 16885 |
| Programming and Coding | 3.0 | 4.0 | 1.0 | FSE-DIT-4018-1.1 | 16891 |
| Project Management | 3.0 | 4.0 | 1.0 | FSE-BIN-4021-1.1 | 16881 |

## Top 10 Role Ranking From Current Vector

| job_role | sector | track | suitability_percentage | gap_cost | matched_skill_count | target_skill_count |
| --- | --- | --- | --- | --- | --- | --- |
| Data Engineer | Financial Services | Digital and Data Analytics | 72.0 | 7.0 | 6 | 8 |
| Data Scientist | Financial Services | Digital and Data Analytics | 68.97 | 18.0 | 13 | 15 |
| Risk Analytics Analyst / Compliance Analytics Analyst | Financial Services | Risk, Compliance and Legal | 58.33 | 15.0 | 7 | 12 |
| Risk Analytics Analyst / Compliance Analytics Analyst (Asset Management) | Financial Services | Risk, Compliance and Legal | 58.33 | 15.0 | 7 | 12 |
| Risk Analytics Analyst / Compliance Analytics Analyst (Corporate Banking) | Financial Services | Risk, Compliance and Legal | 58.33 | 15.0 | 7 | 12 |
| Risk Analytics Analyst / Compliance Analytics Analyst (Retail Banking) | Financial Services | Risk, Compliance and Legal | 58.33 | 15.0 | 7 | 12 |
| Risk Analytics Analyst / Compliance Analytics Analyst (investment Banking) | Financial Services | Risk, Compliance and Legal | 58.33 | 15.0 | 7 | 12 |
| Head of Data Analytics | Financial Services | Digital and Data Analytics | 52.31 | 31.0 | 11 | 14 |
| Pricing Actuarial Executive | Financial Services | Product Solutioning and Management | 51.43 | 17.0 | 6 | 11 |
| Reserving Actuarial Executive | Financial Services | Product Solutioning and Management | 51.43 | 17.0 | 6 | 11 |
