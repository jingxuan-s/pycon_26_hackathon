# M1 Data Quality Report

## Summary Counts

- Roles: 2,030
- Skills: 2,316
- Role-skill source rows: 44,527
- Role-skill normalized requirement rows: 43,799
- K&A source rows: 150,264
- K&A normalized rows: 150,264

## Join Coverage

- Role-skill rows matched to roles: 44,527 / 44,527 (100.00%)
- Role-skill rows matched to unique skills: 44,495 / 44,527 (99.93%)
- Role-skill rows with matching K&A items: 44,527 / 44,527 (100.00%)
- K&A rows matched to unique skills: 149,691 / 150,264 (99.62%)
- TSC mapping rows missing unique skill ids: 42

## Proficiency Normalization

- Numeric proficiency levels are kept as numeric values.
- Text proficiency levels are mapped with `Basic = 1`, `Intermediate = 3`, `Advanced = 5`.
- Role-skill rows with text proficiency levels normalized: 579

## Source Traceability

- `role_skill_requirements` preserves source file, sheet, row number, TSC/CCS code, source title, raw proficiency, and proficiency description.
- `skill_ka_items` preserves source file, sheet, row number, TSC/CCS code, K&A classification, item text, and proficiency description.
- MVP `skill_weight` is set to `1.0` for every role-skill requirement.

## Sample Data Analyst Profile Rows

| sector | track | job_role | unique_skill_title | required_level | tsc_ccs_code | tsc_ccs_title |
| --- | --- | --- | --- | --- | --- | --- |
| Energy and Power | Energy Retail | Demand Management Data Analyst | Autonomous Systems Technology Application | 2.0 | EPW-TEM-2022-1.1 | Autonomous Systems Technology Application |
| Energy and Power | Energy Retail | Demand Management Data Analyst | Business Intelligence and Data Analytics | 3.0 | EPW-DAT-3011-1.1 | Business Intelligence and Data Analytics |
| Energy and Power | Energy Retail | Demand Management Data Analyst | Continuous Improvement Management | 3.0 | EPW-BIN-3034-1.1 | Continuous Improvement Management |
| Energy and Power | Energy Retail | Demand Management Data Analyst | Internet of Things Management | 3.0 | EPW-TEM-3004-1.1 | Internet of Things Management |
| Energy and Power | Energy Retail | Demand Management Data Analyst | Demand Management Operations | 4.0 | EPW-ACE-4008-1.1 | Demand Management Operations |
| Energy and Power | Energy Retail | Demand Management Data Analyst | Demand Management Plan Development | 4.0 | EPW-ACE-4009-1.1 | Demand Management Plan Development |
| Energy and Power | Energy Retail | Demand Management Data Analyst | Energy Management and Audit | 4.0 | EPW-AUD-4012-1.1 | Energy Management and Audit |
| Energy and Power | Energy Retail | Demand Management Data Analyst | Hazards and Risk Identification and Management | 4.0 | EPW-WSH-4021-1.1 | Hazards and Risk Identification and Management |
| Energy and Power | Energy Retail | Demand Management Data Analyst | Project Management | 4.0 | EPW-PMT-4021-1.1 | Project Management |
| Energy and Power | Energy Retail | Demand Management Data Analyst | Regulatory Compliance | 4.0 | EPW-CGP-4012-1.1 | Regulatory Compliance |
| Energy and Power | Energy Retail | Demand Management Data Analyst | Safe System of Work Development and Implementation | 4.0 | EPW-WSH-4019-1.1 | Safe System of Work Development and Implementation |
| Energy and Power | Energy Retail | Demand Management Data Analyst | Technical Report Writing | 4.0 | EPW-BIN-4043-1.1 | Technical Report Writing |
| Energy and Power | Energy Retail | Demand Management Data Analyst | Workplace Safety and Health Framework Development and Implementation | 4.0 | EPW-WSH-4020-1.1 | Workplace Safety and Health Framework Development and Implementation |
| Financial Services | Digital and Data Analytics | Data Analyst | Data Analytics and Computational Modelling | 3.0 | FSE-DAT-3019-1.1 | Data Analytics and Computational Modelling |
| Financial Services | Digital and Data Analytics | Data Analyst | Data Collection and Analysis | 3.0 | FSE-IAD-3003-1.1-1 | Data Collection and Analysis |
| Financial Services | Digital and Data Analytics | Data Analyst | Data Governance | 3.0 | FSE-SNA-3008-1.1-1 | Data Governance |
| Financial Services | Digital and Data Analytics | Data Analyst | Data Storytelling and Visualisation | 3.0 | FSE-DAT-3020-1.1 | Data Storytelling and Visualisation |
| Financial Services | Digital and Data Analytics | Data Analyst | Data-mining and Modelling | 3.0 | FSE-DAT-3003-1.1-1 | Data Mining and Modelling |
| Financial Services | Digital and Data Analytics | Data Analyst | Emerging Technology Synthesis | 3.0 | FSE-SNA-3011-1.1-1 | Emerging Technology Synthesis |
| Financial Services | Digital and Data Analytics | Data Analyst | Ethical Culture | 3.0 | FSE-PVE-3004-1.1-1 | Ethical Culture |
| Financial Services | Digital and Data Analytics | Data Analyst | Impact Indicators, Measurement and Reporting | 3.0 | FSE-SUS-3002-1.2 | Impact Indicators, Measurement and Reporting |
| Financial Services | Digital and Data Analytics | Data Analyst | Programming and Coding | 3.0 | FSE-DIT-3018-1.1 | Programming and Coding |
| Financial Services | Digital and Data Analytics | Data Analyst | Project Management | 3.0 | FSE-BIN-3021-1.1 | Project Management |
| Financial Services | Digital and Data Analytics | Data Analyst | Stakeholder Management | 3.0 | FSE-BIN-3074-1.1 | Stakeholder Management |
| Financial Services | Digital and Data Analytics | Data Analyst | Sustainability Risk Management | 3.0 | FSE-SUS-3004-1.2 | Sustainability Risk Management |
| Financial Services | Digital and Data Analytics | Data Analyst | Sustainability Reporting | 4.0 | FSE-SUS-4003-1.2 | Sustainability Reporting |
| Infocomm Technology | Data and Artificial Intelligence | Data Analyst / Associate Data Engineer | Business Needs Analysis | 2.0 | ICT-PMT-2001-1.1 | Business Needs Analysis |
| Infocomm Technology | Data and Artificial Intelligence | Data Analyst / Associate Data Engineer | Data Engineering | 2.0 | ICT-DIT-2005-1.1 | Data Engineering |
| Infocomm Technology | Data and Artificial Intelligence | Data Analyst / Associate Data Engineer | Database Administration | 2.0 | ICT-OUS-2006-1.1 | Database Administration |
| Infocomm Technology | Data and Artificial Intelligence | Data Analyst / Associate Data Engineer | Stakeholder Management | 2.0 | ICT-SCM-2004-1.1 | Stakeholder Management |

## Sample Data Scientist Profile Rows

| sector | track | job_role | unique_skill_title | required_level | tsc_ccs_code | tsc_ccs_title |
| --- | --- | --- | --- | --- | --- | --- |
| Financial Services | Digital and Data Analytics | Data Scientist | Impact Indicators, Measurement and Reporting | 3.0 | FSE-SUS-3002-1.2 | Impact Indicators, Measurement and Reporting |
| Financial Services | Digital and Data Analytics | Data Scientist | Sustainability Risk Management | 3.0 | FSE-SUS-3004-1.2 | Sustainability Risk Management |
| Financial Services | Digital and Data Analytics | Data Scientist | Data Analytics and Computational Modelling | 4.0 | FSE-DAT-4019-1.1 | Data Analytics and Computational Modelling |
| Financial Services | Digital and Data Analytics | Data Scientist | Data Collection and Analysis | 4.0 | FSE-IAD-4003-1.1-1 | Data Collection and Analysis |
| Financial Services | Digital and Data Analytics | Data Scientist | Data Governance | 4.0 | FSE-SNA-4008-1.1-1 | Data Governance |
| Financial Services | Digital and Data Analytics | Data Scientist | Data Storytelling and Visualisation | 4.0 | FSE-DAT-4020-1.1 | Data Storytelling and Visualisation |
| Financial Services | Digital and Data Analytics | Data Scientist | Data-mining and Modelling | 4.0 | FSE-DAT-4003-1.1 | Data Mining and Modelling |
| Financial Services | Digital and Data Analytics | Data Scientist | Emerging Technology Synthesis | 4.0 | FSE-SNA-4011-1.1-1 | Emerging Technology Synthesis |
| Financial Services | Digital and Data Analytics | Data Scientist | Ethical Culture | 4.0 | FSE-PVE-4004-1.1-1 | Ethical Culture |
| Financial Services | Digital and Data Analytics | Data Scientist | People Performance Management | 4.0 | FSE-PDV-4051-1.1 | People Performance Management |
| Financial Services | Digital and Data Analytics | Data Scientist | Programming and Coding | 4.0 | FSE-DIT-4018-1.1 | Programming and Coding |
| Financial Services | Digital and Data Analytics | Data Scientist | Project Management | 4.0 | FSE-BIN-4021-1.1 | Project Management |
| Financial Services | Digital and Data Analytics | Data Scientist | Software Configuration | 4.0 | FSE-DIT-4014-1.1-1 | Software Configuration |
| Financial Services | Digital and Data Analytics | Data Scientist | Stakeholder Management | 4.0 | FSE-BIN-4074-1.1-1 | Stakeholder Management |
| Financial Services | Digital and Data Analytics | Data Scientist | Sustainability Reporting | 4.0 | FSE-SUS-4003-1.2 | Sustainability Reporting |
| Infocomm Technology | Data and Artificial Intelligence | Data Scientist / Artificial Intelligence Scientist | Computer Vision Technology | 4.0 | ICT-DIT-4022-1.1 | Computer Vision Technology |
| Infocomm Technology | Data and Artificial Intelligence | Data Scientist / Artificial Intelligence Scientist | Emerging Technology Synthesis | 4.0 | ICT-SNA-4011-1.1 | Emerging Technology Synthesis |
| Infocomm Technology | Data and Artificial Intelligence | Data Scientist / Artificial Intelligence Scientist | Self-Learning Systems | 4.0 | ICT-DIT-4028-1.1 | Self-Learning Systems |
| Infocomm Technology | Data and Artificial Intelligence | Data Scientist / Artificial Intelligence Scientist | Stakeholder Management | 4.0 | ICT-SCM-4004-1.1 | Stakeholder Management |
| Infocomm Technology | Data and Artificial Intelligence | Data Scientist / Artificial Intelligence Scientist | Business Innovation | 5.0 | ICT-SNA-5003-1.1 | Business Innovation |
| Infocomm Technology | Data and Artificial Intelligence | Data Scientist / Artificial Intelligence Scientist | Business Needs Analysis | 5.0 | ICT-PMT-5001-1.1 | Business Needs Analysis |
| Infocomm Technology | Data and Artificial Intelligence | Data Scientist / Artificial Intelligence Scientist | Computational Modelling | 5.0 | ICT-DIT-5001-1.1 | Computational Modelling |
| Infocomm Technology | Data and Artificial Intelligence | Data Scientist / Artificial Intelligence Scientist | Data Design | 5.0 | ICT-DES-5001-1.1 | Data Design |
| Infocomm Technology | Data and Artificial Intelligence | Data Scientist / Artificial Intelligence Scientist | Data Ethics | 5.0 | ICT-LGL-5004-1.1 | Data Ethics |
| Infocomm Technology | Data and Artificial Intelligence | Data Scientist / Artificial Intelligence Scientist | Data Governance | 5.0 | ICT-SNA-5008-1.1 | Data Governance |
| Infocomm Technology | Data and Artificial Intelligence | Data Scientist / Artificial Intelligence Scientist | Data Strategy | 5.0 | ICT-SNA-5009-1.1 | Data Strategy |
| Infocomm Technology | Data and Artificial Intelligence | Data Scientist / Artificial Intelligence Scientist | Design Thinking Practice | 5.0 | ICT-ACE-5014-1.1 | Design Thinking Practice |
| Infocomm Technology | Data and Artificial Intelligence | Data Scientist / Artificial Intelligence Scientist | IT Test Planning | 5.0 | ICT-DIT-5017-1.1 | Test Planning |
| Infocomm Technology | Data and Artificial Intelligence | Data Scientist / Artificial Intelligence Scientist | Intelligent Reasoning | 5.0 | ICT-ACE-5030-1.1 | Intelligent Reasoning |
| Infocomm Technology | Data and Artificial Intelligence | Data Scientist / Artificial Intelligence Scientist | Pattern Recognition Systems | 5.0 | ICT-DIT-5026-1.1 | Pattern Recognition Systems |
