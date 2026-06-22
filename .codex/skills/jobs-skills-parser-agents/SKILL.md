---
name: jobs-skills-parser-agents
description: Design, implement, or review stretch parser agents for resume and job-description analysis in the jobs-skills project. Use when Codex needs to extract skill evidence, infer proficiency levels with confidence, map resume/JD text to SkillsFuture unique skills, or keep parser outputs auditable for deterministic scoring.
---

# Jobs Skills Parser Agents

## Status

This is a stretch feature after the questionnaire MVP works.

## Core Principle

Parser agents extract evidence. They do not decide final suitability scores.

## Resume Parser Output

Each extracted skill should include:

- `skill_id` or candidate unique skill title
- inferred level
- confidence
- evidence quote or resume section reference
- reason for inference
- uncertainty flag when user confirmation is needed

Example:

```text
Skill: Programming and Coding
Inferred level: 3
Confidence: 0.74
Evidence: Built Python scripts to automate monthly reports.
Reason: Shows applied coding in work context, but not advanced production ownership.
```

## JD Parser Output

Each target requirement should include:

- mapped unique skill
- inferred target level if available
- confidence
- evidence from JD text
- whether mapping is exact dataset match or inferred semantic match

## Guardrails

- Ask user to confirm uncertain inferred skills.
- Do not store full resume text by default.
- Label non-dataset mappings as inferred.
- Pass parser output into the deterministic scoring engine; do not ask an agent to generate the final score directly.