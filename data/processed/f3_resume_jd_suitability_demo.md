# F1-F3 Resume/JD Parser Suitability Demo

## Parser Boundary

Parser agents extract structured evidence only: skill mapping, inferred level, confidence, evidence, reason, and uncertainty. Final suitability is calculated by the deterministic scoring engine, not by the parser.

## Deterministic Suitability

Target: Parsed Data Scientist JD
Suitability: 40.74%
Matched skills: 4 of 6
Gap skills: 6
Formula inputs: covered=11.00, target=27.00, gap_cost=16.00
All parser stretch skill weights remain 1.0.

## Extracted Resume Evidence

| unique_skill_title | inferred_level | confidence | mapping_type | evidence |
| --- | --- | --- | --- | --- |
| Data Governance | 2.0 | 0.99 | exact_dataset_title | Supported data governance checks by documenting data quality issues and privacy handling rules. |
| Business Intelligence and Data Analytics | 3.0 | 0.8200000000000001 | inferred_alias | Built Python and SQL automation scripts for monthly reporting and developed Power BI dashboards for finance stakeholders. |
| Data Storytelling and Visualisation | 3.0 | 0.8200000000000001 | inferred_alias | Built Python and SQL automation scripts for monthly reporting and developed Power BI dashboards for finance stakeholders. |
| Programming and Coding | 3.0 | 0.8200000000000001 | inferred_alias | Built Python and SQL automation scripts for monthly reporting and developed Power BI dashboards for finance stakeholders. |
| Stakeholder Management | 3.0 | 0.77 | inferred_alias | Built Python and SQL automation scripts for monthly reporting and developed Power BI dashboards for finance stakeholders. |
| Data Collection and Analysis | 3.0 | 0.77 | inferred_alias | Analysed customer data to identify churn patterns and created segmentation models. |
| Data-mining and Modelling | 3.0 | 0.72 | inferred_alias | Analysed customer data to identify churn patterns and created segmentation models. |

## Extracted JD Requirements

| unique_skill_title | inferred_level | confidence | mapping_type | evidence |
| --- | --- | --- | --- | --- |
| Data Governance | 5.0 | 0.95 | exact_dataset_title | The candidate should lead data governance practices, support project management, and work with stakeholders to turn analysis into decisions. |
| Project Management | 5.0 | 0.95 | exact_dataset_title | The candidate should lead data governance practices, support project management, and work with stakeholders to turn analysis into decisions. |
| Data Analytics and Computational Modelling | 4.0 | 0.95 | exact_dataset_title | The role must build predictive models, use Python and SQL for programming and coding, design data analytics and computational modelling approaches, and create dashboards that expla |
| Programming and Coding | 4.0 | 0.95 | exact_dataset_title | The role must build predictive models, use Python and SQL for programming and coding, design data analytics and computational modelling approaches, and create dashboards that expla |
| Data Storytelling and Visualisation | 4.0 | 0.77 | inferred_alias | The role must build predictive models, use Python and SQL for programming and coding, design data analytics and computational modelling approaches, and create dashboards that expla |
| Stakeholder Management | 5.0 | 0.72 | inferred_alias | The candidate should lead data governance practices, support project management, and work with stakeholders to turn analysis into decisions. |

## Priority Gaps

| unique_skill_title | current_level | target_level | gap | skill_weight |
| --- | --- | --- | --- | --- |
| Project Management | 0.0 | 5.0 | 5.0 | 1.0 |
| Data Analytics and Computational Modelling | 0.0 | 4.0 | 4.0 | 1.0 |
| Data Governance | 2.0 | 5.0 | 3.0 | 1.0 |
| Stakeholder Management | 3.0 | 5.0 | 2.0 | 1.0 |
| Data Storytelling and Visualisation | 3.0 | 4.0 | 1.0 | 1.0 |
| Programming and Coding | 3.0 | 4.0 | 1.0 | 1.0 |

## Action Plan

| skill | current_level | target_level | next_action | ka_classification | ka_source_row_number |
| --- | --- | --- | --- | --- | --- |
| Project Management | 0.0 | 5.0 | Practise and document evidence for: Determine appropriate methodologies and tools to ensure that they are fit-for-purpose | ability | 2466 |
| Data Analytics and Computational Modelling | 0.0 | 4.0 | Practise and document evidence for: Apply complex and advanced statistical analysis and modelling techniques to uncover relationships between variables | ability | 54848 |
| Data Governance | 2.0 | 5.0 | Practise and document evidence for: Anticipate legal implications of data handling processes | ability | 843 |
| Stakeholder Management | 3.0 | 5.0 | Practise and document evidence for: Address escalated issues and lead negotiations to influence key stakeholder decisions | ability | 2754 |
| Data Storytelling and Visualisation | 3.0 | 4.0 | Practise and document evidence for: Amend storyboard and data presentation materials to match audience needs | ability | 888 |
