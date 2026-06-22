---
name: jobs-skills-data-pipeline
description: Build, update, or review the Python data pipeline for the SkillsFuture jobs-skills datasets. Use when Codex needs to ingest Excel files, normalize proficiency levels, join role-skill rows to unique skills and K&A items, create feature-store tables, or perform data quality checks for the career pathway MVP.
---

# Jobs Skills Data Pipeline

## Core Workflow

Use `docs/project_brief.md` as the product reference. Keep the pipeline Python-first and deterministic.

Primary source sheets:

- `Job Role_Description`
- `Job Role_TCS_CCS`
- `TSC_CCS_Key`
- `TSC_CCS_K&A`
- `jobsandskills-skillsfuture-tsc-to-unique-skills-mapping.xlsx` sheet `data`
- `jobsandskills-skillsfuture-unique-skills-list.xlsx` sheet `Unique Skills List`

## Required Tables

Create or maintain these normalized tables:

- `roles`: `role_id`, sector, track, job_role, description, performance_expectation
- `skills`: `skill_id`, unique_skill_title, description, type, emerging, casl
- `role_skill_requirements`: `role_id`, `skill_id`, required_level, skill_weight, tsc_ccs_code, tsc_ccs_title
- `skill_ka_items`: `skill_id`, tsc_ccs_code, level, item, classification, proficiency_description

## Rules

- Join role skills to unique skills by `TSC_CCS Code` plus `Proficiency Level`, not by title.
- Normalize proficiency values with `Basic = 1`, `Intermediate = 3`, `Advanced = 5` for MVP, and keep this assumption visible.
- Collapse duplicate role + unique skill rows using max required proficiency.
- Keep audit columns so recommendations can trace back to source rows.
- Set `skill_weight = 1.0` for every role-skill row in MVP.
- Do not discard original TSC/CCS codes; they are needed for explainability.

## Validation

Before considering the pipeline done, report:

- role count
- skill count
- role-skill row count
- join coverage from role skills to unique skills
- join coverage from role skills to K&A items
- count of normalized non-numeric proficiency values
- sample Data Analyst and Data Scientist role profiles if available