# Project Brief

## Current Status Note

This brief records the methodology exploration and product decisions made during the hackathon. Some earlier sections discuss a questionnaire-first MVP because that was the initial direction. The current implemented demo is resume/role-first in Telegram: users upload a resume or choose a dataset role, review their skill profile, choose a goal mode, then receive deterministic suitability scoring, gaps, explanations, and an action plan.

The questionnaire implementation remains useful as historical evidence and local validation, but it is not the default `/start` flow.

## Workflow Design Choice

The implemented workflow uses two starting points because users arrive with different levels of prepared evidence:

- Resume upload: suitable for users with work, internship, project, or coursework evidence that can be parsed into draft skills.
- Current-role selection: suitable for users who want a quick baseline from a known SkillsFuture dataset role without preparing a resume.

After the starting point, the system requires skill review before scoring. This is an explicit product choice: users should be able to correct the skill profile that the scoring engine will judge, instead of being scored from hidden parser assumptions.

The four goal modes map to common career questions:

- Explore pathways: "What adjacent roles fit what I already have?"
- Advance roles: "How can I progress in a similar track or sector?"
- Search target role: "How far am I from this specific role?"
- Paste JD: "Am I suitable for this actual job posting, and what gaps should I close?"

This keeps the product flexible without exposing users to the full raw dataset at once.

## Dataset Findings

Source files inspected:

- `jobsandskills-skillsfuture-skills-framework-dataset.xlsx`
- `jobsandskills-skillsfuture-tsc-to-unique-skills-mapping.xlsx`
- `jobsandskills-skillsfuture-unique-skills-list.xlsx`

Key usable tables:

| File | Sheet | Useful fields |
| --- | --- | --- |
| Skills framework dataset | `Job Role_Description` | Sector, track, job role, role description, performance expectation |
| Skills framework dataset | `Job Role_TCS_CCS` | Sector, track, job role, skill title, skill type, proficiency level, skill code |
| Skills framework dataset | `TSC_CCS_K&A` | Skill code, proficiency level, proficiency description, knowledge/ability items |
| TSC to unique skills mapping | `data` | Skills Framework skill code/proficiency to updated unique skill |
| Unique skills list | `Unique Skills List` | Unique skill title, description, skill type, emerging/CASL flags |

Observed scale:

- 2,000 distinct role profiles across 39 sectors and 247 sector-track combinations.
- 44,527 role-skill-proficiency rows.
- 2,086 distinct TSC/CCS skill titles in role profiles.
- 2,316 unique skills in the unique skills list.
- 2,047 unique skill dimensions are represented by role profiles after mapping.
- Median role profile has 20 skills; average is about 22 skills.
- The role x unique-skill matrix has about 43,821 non-zero entries, around 0.95% density if represented as 2,000 x 2,316.
- Every `Job Role_TCS_CCS` row matched the TSC key, the knowledge/ability table, and the TSC-to-unique-skill mapping on code plus proficiency level.

Important schema notes:

- Most proficiency levels are numeric 1 to 6, but a small number of CCS rows use `Basic`, `Intermediate`, and `Advanced`. Normalize these before vector scoring.
- Some roles have the same skill title at more than one proficiency level. Collapse to max required proficiency per role and unique skill.
- Joining the unique-skill mapping by title can create duplicates. Join by `TSC_CCS Code` plus `Proficiency Level`.

## Feasibility Assessment

The proposed method is feasible, but it should be implemented as a hybrid system:

1. Sparse vector search for matching users to role profiles.
2. A typed knowledge graph for explanation and pathway planning.
3. Rule-based constraints to keep career paths realistic.
4. Retrieval or language-model extraction only for questionnaire/resume/JD parsing, not for final recommendation justification.

The strongest part of the dataset is the explicit role-to-skill-to-proficiency structure. This directly supports explainable recommendations:

```text
Role -> requires -> Unique Skill -> at proficiency level N
Skill -> has -> proficiency description
Skill/proficiency -> includes -> knowledge and ability items
```

This means recommendations can show exactly which dataset rows caused the score, the gap, and the learning plan.

## Vector Space Design

Use unique skills as dimensions and proficiency level as value:

```text
role_vector[unique_skill] = required proficiency level
user_vector[unique_skill] = assessed proficiency level
```

Recommended representation:

- Use sparse vectors because the matrix is less than 1% dense.
- Keep the original role-skill rows for explanations.
- Keep both `TSC_CCS Code` and `Unique skill_updated_skill_title`; use unique skills for product clarity and TSC codes for auditability.

Normalize proficiency:

| Raw value | Suggested numeric value |
| --- | ---: |
| `1` to `6` | 1 to 6 |
| `Basic` | 1 or 2 |
| `Intermediate` | 3 or 4 |
| `Advanced` | 5 or 6 |

For hackathon simplicity, use `Basic = 1`, `Intermediate = 3`, `Advanced = 5`, then expose the mapping as an assumption.

Useful scoring formulas:

```text
covered_skill_value = min(user_level, target_role_level)
target_skill_value = target_role_level
suitability = sum(covered_skill_value) / sum(target_skill_value)

gap_for_skill = max(target_role_level - user_level, 0)
gap_cost = sum(weight(skill) * gap_for_skill)
```

Do not rely only on cosine similarity. Cosine finds similar skill shape, but it hides whether the user is below the required level. The current Explore pathway method uses weighted L1 nearest-neighbour discovery over sparse skill vectors to shortlist nearby roles, then uses target-aware suitability and gap cost to rank actionability.

### Weighted Suitability Percentage

The gap analysis can be expressed as a percentage, for example:

```text
Your current Data Analyst profile is 80% aligned to the target Data Scientist role.
```

Use proficiency levels directly:

```text
weighted_suitability =
  sum(skill_weight * min(user_level, target_role_level))
  /
  sum(skill_weight * target_role_level)
```

Unweighted MVP version:

```text
suitability =
  sum(min(user_level, target_role_level))
  /
  sum(target_role_level)
```

Interpretation:

- `100%` means the user meets or exceeds every required skill level for the target role.
- `80%` means the user already covers 80% of the weighted proficiency requirement.
- Gaps are still shown separately, because a user may score high overall but miss one critical skill.

Example:

```text
Target role: Data Scientist

Skill                         User level   Target level   Covered
Programming and Coding        3            4              3 / 4
Data Mining and Modelling     3            4              3 / 4
Data Governance               3            4              3 / 4
Software Configuration        0            4              0 / 4

Suitability = covered proficiency / target proficiency
```

The percentage should always be paired with:

- top matched skills
- top gaps
- critical missing skills
- next learning actions

Otherwise, the percentage becomes a black-box score.

### Skill Weights

For the MVP, create the weight field but set every skill weight to `1.0`.

This keeps the first scoring version simple and reproducible:

```text
skill_weight = 1.0 for every required skill
```

The suitability formula still accepts weights:

```text
weighted_suitability =
  sum(skill_weight * min(user_level, target_role_level))
  /
  sum(skill_weight * target_role_level)
```

But with all weights set to `1.0`, the MVP behaves like the unweighted score. This is useful because:

- users can reproduce the percentage easily
- the team can validate the scoring engine before tuning importance assumptions
- the data model is ready for future `core`, `important`, and `supporting` skill labels

Future version:

```text
Core skill: 1.5
Important skill: 1.0
Supporting skill: 0.7
```

Do not activate differentiated weights until there is enough time to define and explain the assignment method. When differentiated weights are introduced, explain them directly in the result:

```text
Programming and Coding has a higher weight because it was tagged as a core skill for the selected Data Scientist role family.
```

For a small dataset of 2,000 roles, exact nearest-neighbor search is enough for MVP. HNSW is reasonable later if you add many more job postings, resumes, or generated role variants.

## Knowledge Graph Design

Recommended node types:

- `Person`
- `Resume`
- `JobDescription`
- `Sector`
- `Track`
- `JobRole`
- `UniqueSkill`
- `TscCcsSkill`
- `ProficiencyLevel`
- `KnowledgeAbilityItem`
- `LearningAction`

Recommended edge types:

- `(:JobRole)-[:IN_SECTOR]->(:Sector)`
- `(:JobRole)-[:IN_TRACK]->(:Track)`
- `(:JobRole)-[:REQUIRES {level, source_code}]->(:UniqueSkill)`
- `(:UniqueSkill)-[:MAPPED_FROM]->(:TscCcsSkill)`
- `(:TscCcsSkill)-[:HAS_KA_ITEM {level, classification}]->(:KnowledgeAbilityItem)`
- `(:Person)-[:HAS_SKILL {level, evidence, confidence}]->(:UniqueSkill)`
- `(:JobRole)-[:ADJACENT_TO {similarity, gap_cost, direction}]->(:JobRole)`
- `(:LearningAction)-[:BUILDS]->(:UniqueSkill)`

Role-to-role edges are not explicitly provided by the dataset. They should be derived.

Suggested derived role-edge rules:

```text
edge allowed if:
  same sector or same track, unless user asks for cross-sector moves
  skill overlap above threshold
  target role is not materially lower than current role
  gap cost is below threshold
```

Potential edge weight:

```text
edge_weight =
  proficiency_gap_cost
  + missing_critical_skill_penalty
  + cross_sector_penalty
  + low_overlap_penalty
  - same_track_bonus
```

Then Dijkstra can find the lowest-cost pathway from current role to target role.
### Edge Weight Calibration

Use a hybrid edge-weight formula for career pathways:

```text
edge_weight =
  base_skill_gap_cost
+ additive_blocker_penalties

edge_weight =
  edge_weight
  * sector_multiplier
  * track_multiplier
  * intent_multiplier
```

Or equivalently:

```text
edge_weight =
  (base_skill_gap_cost + additive_blocker_penalties)
  * context_multipliers
```

Use multipliers for friction:

- same sector vs cross-sector transition
- same track vs related or unrelated track
- lateral move vs promotion vs career switch
- domain distance

Use additive penalties for hard blockers:

- missing critical skill
- very low skill overlap
- target role is much more senior
- required certification or licence is missing

This is partly heuristic for the MVP, but the numbers can be made more defensible through a calibration methodology.

Recommended calibration steps:

1. Start with transparent defaults.
2. Back-test against obvious pathway examples in the dataset.
3. Run sensitivity analysis to check whether rankings are stable.
4. Calibrate against expert-labelled pathway difficulty if available.
5. Learn or tune weights from user feedback later.

Transparent MVP defaults:

```text
same sector multiplier: 1.00
related sector multiplier: 1.15
unrelated sector multiplier: 1.35
same track multiplier: 0.85
related track multiplier: 0.95
unrelated track multiplier: 1.20
missing critical skill penalty: +5 to +10
low overlap penalty: +5
```

Make the methodology explicit in the product:

```text
This pathway score combines skill gaps from the SkillsFuture dataset with configurable pathway assumptions, such as whether cross-sector moves should be treated as harder. These assumptions are shown separately from the raw skill suitability score.
```

Do not hide the assumptions inside one score. Show at least two scores:

```text
Skill Suitability: 82%
Pathway Fit: 74%
```

This makes the recommendation explainable:

```text
Your skill suitability is high, but pathway fit is lower because this is a cross-sector transition and two critical skills are missing.
```

A more rigorous later version can estimate multipliers from labelled examples:

```text
expert_label: easy / moderate / hard transition
features: skill_gap, overlap, same_sector, same_track, critical_missing_count
model: logistic regression, ordinal regression, or calibrated gradient boosting
```

For the hackathon, the key is not to claim the multipliers are objectively true. Claim they are configurable pathway policy assumptions, grounded in skill-gap logic and made visible to the user.

Important correction: pure least-cost path can produce bad recommendations. In a quick prototype, a gap-only score from Financial Services Data Analyst returned unrelated lower-requirement roles before Data Scientist. The graph must use constraints and penalties, not just raw gap distance.

## Example: Data Analyst to Data Scientist

The dataset contains several role variants:

- Financial Services / Digital and Data Analytics / Data Analyst
- Financial Services / Digital and Data Analytics / Data Scientist
- Infocomm Technology / Data and Artificial Intelligence / Data Analyst / Associate Data Engineer
- Infocomm Technology / Data and Artificial Intelligence / Data Scientist / Artificial Intelligence Scientist

For Financial Services Data Analyst to Financial Services Data Scientist:

- Source role has 13 unique skills.
- Target role has 15 unique skills.
- 13 skills overlap.
- Weighted suitability, if the user exactly matches the Data Analyst profile, is about 69%.
- Key gaps include:
  - People Performance Management: missing level 4
  - Software Configuration: missing level 4
  - Several data skills moving from level 3 to level 4, including Data Governance, Data Storytelling and Visualisation, Data Collection and Analysis, Data Mining and Modelling, Programming and Coding, Project Management, and Stakeholder Management.

This is a good pathway example because the explanation is compact: mostly level upgrades plus two new skill areas.

For Infocomm Data Analyst / Associate Data Engineer to Infocomm Data Scientist / AI Scientist:

- Source role has 13 unique skills.
- Target role has 20 unique skills.
- Only 6 skills overlap.
- Weighted suitability, if the user exactly matches the source profile, is about 17.5%.
- Gaps include Text Analytics and Processing, Computational Modelling, Data Design, Data Governance, Data Strategy, Intelligent Reasoning, Pattern Recognition Systems, Software Design, Solution Architecture, Computer Vision Technology, and Self-Learning Systems.

This is not a simple lateral pathway. It needs a staged plan, probably through adjacent data engineering, AI engineering, or analytics roles.

## Product Flow Recommendations

The prompt says there are 2 user stories, but lists 3. Treat them as 3 flows:

1. Questionnaire to assess proficiency, then ask whether the user wants lateral transfer or broader recommendations.
2. Resume upload to infer proficiency, then ask whether the user wants role-change recommendations or pathway planning.
3. Resume plus target job description upload to compute suitability percentage and skill-gap plan.

Recommended MVP flow:

### Flow A: Hybrid Questionnaire

Use a hybrid questionnaire so the user is not forced to answer target-role questions before seeing possible pathways.

Step 1: Assess current-role baseline.

1. Ask for current role, sector, and target intent.
2. Select 8 to 12 high-signal skills from the likely current role family.
3. For each skill, ask evidence-based questions mapped to proficiency descriptions and K&A items.
4. Build the baseline `user_vector`.

Step 2: Recommend 3 possible pathways.

1. Compare the baseline `user_vector` against role profiles.
2. Show 3 realistic pathways with skill suitability, pathway fit, and a short explanation.
3. Keep the choices distinct enough to be meaningful, for example growth path, lateral transfer, and exploratory switch.

Step 3: Ask target-gap questions after the user chooses one pathway.

1. Identify the top uncertain or high-impact target gaps for the selected pathway.
2. Ask 3 to 5 extra questions only for those gaps.
3. Update the `user_vector`, suitability percentage, and action plan.
4. Show why the score changed after the extra answers.

This keeps the assessment short while still improving accuracy for the chosen target pathway.

### Flow B: Resume to Recommendation

1. Parse resume into skill evidence.
2. Map evidence to unique skills using title, description, K&A items, and proficiency descriptions.
3. Store confidence per skill.
4. Ask user to confirm uncertain inferred skills.
5. Run recommendation search.
6. Show an explanation grounded in dataset rows and resume evidence.

### Flow C: Resume plus Job Description

1. Parse resume into `user_vector`.
2. Parse JD into `target_vector`.
3. If JD skills match SkillsFuture unique skills, use them directly.
4. If JD has non-dataset skills, map them to nearest unique skill and label as inferred.
5. Score suitability.
6. Produce a prioritized gap plan:
   - critical missing skills
   - near-miss skills, where the user is 1 proficiency level short
   - skills already covered
   - concrete K&A items to learn next

## Agent Design

Use agents for interpretation and explanation, but keep scoring deterministic.

Recommended agents:

| Agent | Input | Output |
| --- | --- | --- |
| Resume Parser Agent | Resume text | Skill evidence, inferred skill levels, confidence |
| JD Parser Agent | Job description text | Target skills, inferred levels, confidence |
| Career Planner Agent | User vector, target role vector, gaps, K&A items | Action plan and explanation |

The parser agents should not directly decide final suitability. They should produce auditable intermediate evidence:

```text
Skill: Programming and Coding
Inferred level: 3
Confidence: 0.74
Evidence: "Built Python scripts to automate monthly reports"
Reason: Evidence shows applied coding in work context, but not advanced production ownership.
```

The deterministic scoring engine then compares:

```text
Target role: Data Scientist
Required skill: Programming and Coding
Required level: 4
User level: 3
Gap: 1
Weight: Core
```

This keeps explainability strong:

```text
The AI extracts evidence.
The dataset defines required role skills.
The scoring engine calculates the score.
The planner explains the gap and next actions.
```

### Career Planner Agent

The Career Planner Agent should turn a level gap into concrete actions using Skills Framework data.

For each priority gap:

```text
current user level -> target role level
```

Pull:

- proficiency description at the user's level
- proficiency description at the target level
- knowledge items for the target level
- ability items for the target level

Then generate:

```text
You are assessed at level 3 for Data Collection and Analysis.
The target Data Scientist role requires level 4.

To move from level 3 to level 4:
1. Practise the level-4 ability items from the Skills Framework.
2. Build evidence through a project or workplace task.
3. Reassess this skill after producing evidence.
```

The planner should only show 3 to 5 priority skills at a time. This satisfies the product goal of actionable pathways instead of overwhelming skill sets.

## Explainability Requirements

The product must make it clear how the user is being judged. Every recommendation, score, and pathway should be traceable to the underlying dataset logic.

For every recommended role, show:

- matched skills
- missing skills
- skills where the user is below the required proficiency level
- skill weights or priority labels
- whether sector/track assumptions affected the pathway fit
- source dataset references, such as role, skill title, required level, and K&A items

Recommended user-facing explanation structure:

```text
Why this role was recommended

1. Skill match
   You match 13 of 15 required skill areas for this role.

2. Proficiency gap
   You are one level below the target requirement in 6 skills.

3. Critical skill impact
   Programming and Coding, Data Mining and Modelling, and Data Governance are core skills for this pathway, so they have higher priority.

4. Pathway logic
   This is a same-sector transition, so pathway friction is low.

5. Recommended next actions
   Start with the 3 highest-impact gaps instead of trying to close every gap at once.
```

The tool should separate three concepts:

| Concept | Meaning | User-facing label |
| --- | --- | --- |
| Skill coverage | How much of the target role's proficiency requirement the user already covers | Skill Suitability |
| Gap priority | Which gaps matter most based on level difference and role-specific weight | Priority Gaps |
| Pathway friction | Whether the transition is same sector, same track, related, or exploratory | Pathway Fit |

Avoid a single unexplained score. A good result card should show:

```text
Target role: Data Scientist
Skill Suitability: 82%
Pathway Fit: 74%

Why these scores?
- 13 of 15 target skill areas overlap with your profile.
- 6 skills are one proficiency level below the target.
- 2 core skills are missing or weak.
- The pathway is same sector but higher proficiency, so it is a growth pathway rather than a career switch.
```

For every pathway step, show why the step exists:

```text
Data Analyst -> Data Scientist
Recommended because:
- high overlap in data collection, data governance, visualisation, and programming skills
- target role mainly requires level 3 to level 4 progression
- same sector and same track reduce transition friction
```

For every learning action, show the source logic:

```text
Gap: Data Governance
Current level: 3
Target level: 4
Reason this matters: Required by the target Data Scientist role.
Action source: Skills Framework proficiency description and K&A items for level 4.
```

This directly supports the product promise:

```text
Users should not just see what role is recommended.
They should understand why the role was recommended, which skills caused the recommendation, and what concrete actions can move them closer.
```
## Explainability Pattern

Every recommendation should show:

```text
Recommended role: Data Scientist
Why shown:
  - 13 of 15 target skills overlap with your current profile.
  - Your strongest matches are Data Collection and Analysis, Data Governance, and Sustainability Reporting.
  - The smallest actionable gaps are mostly level 3 to level 4 upgrades.
  - Two new level-4 areas are People Performance Management and Software Configuration.

Next actions:
  1. Close near-miss level gaps first.
  2. Add missing critical skills.
  3. Reassess suitability after completion.
```

This directly addresses the product requirement:

- Recommendations are shown using dataset logic.
- Users see a small action plan instead of a long skill dump.

## Implementation Suggestions

Build these tables first:

1. `roles`
   - `role_id`, sector, track, job_role, description, performance_expectation
2. `skills`
   - `skill_id`, unique_skill_title, description, type, emerging, casl
3. `role_skill_requirements`
   - `role_id`, `skill_id`, required_level, tsc_ccs_code, tsc_ccs_title
4. `skill_ka_items`
   - `skill_id`, tsc_ccs_code, level, item, classification
5. `role_edges`
   - `source_role_id`, `target_role_id`, similarity, gap_cost, edge_weight, explanation
6. `user_skill_assessments`
   - `user_id`, `skill_id`, level, source, evidence, confidence

Ranking strategy:

1. Use hard filters first: sector, track, target mode, excluded sectors, desired role family.
2. Use vector similarity to shortlist roles.
3. Use gap-cost ranking for the shortlist.
4. Use graph search only after a target role or target family is known.
5. Generate the final explanation from relational rows, not from vector index internals.

Pathway strategy:

- For a direct role target, run Dijkstra from current/inferred role to target over constrained role edges.
- For recommendations, do not run Dijkstra to every role blindly. First identify realistic target roles, then compute pathways.
- Represent each path step as 3 to 5 priority skills, not all gaps.

## Risks And Fixes

| Risk | Fix |
| --- | --- |
| Resume parsing overclaims proficiency | Store evidence and confidence; ask user to confirm uncertain skills |
| Users get overwhelmed by 20 to 80 skills | Show only top gaps, near-misses, and critical missing skills |
| Similarity recommends current role or near-duplicates | Filter current role and collapse equivalent role variants |
| Gap-only cost recommends unrelated low-requirement roles | Add sector/track constraints, overlap thresholds, and cross-sector penalties |
| Dataset has no explicit career progression | Derive role edges and label them as inferred pathways |
| HNSW feels impressive but unnecessary for 2,000 roles | Use exact search for MVP; keep HNSW for scale-up |
| Proficiency scale mixing numeric and Basic/Intermediate/Advanced | Normalize and disclose assumptions |

## Recommended MVP

The core MVP is the hybrid questionnaire pathway flow:

1. Assess the user's current-role baseline.
2. Recommend 3 possible pathways.
3. Let the user choose one pathway.
4. Ask 3 to 5 extra target-gap questions for the chosen pathway.
5. Recalculate skill suitability and pathway fit.
6. Show the top 3 to 5 gaps and concrete learning actions using K&A items.

Historical note: this section reflects the earlier planning stage, when resume/JD parsing was scoped as stretch. The current demo has since promoted resume/role-first onboarding into the main Telegram flow.

The resume/JD flow was originally framed as a stretch feature after the questionnaire MVP:

1. Upload or paste resume.
2. Upload or paste target JD.
3. Parse both into skill vectors.
4. Output suitability percentage.
5. Show top 5 skill gaps.
6. For each gap, show K&A items from the dataset as concrete learning actions.
7. If the target role maps to a SkillsFuture role, show a pathway from current closest role to target role.

This sequence keeps the first demo focused on explainable career pathway guidance while preserving the resume/JD idea for later job-fit analysis.

## MVP Interface: Telegram Bot

Use Telegram as the MVP interaction layer instead of building a full dashboard first.

Rationale:

- Reduces frontend complexity for a solo project.
- Originally fit the questionnaire-first flow; the current demo now uses a resume/role-first flow because hands-on testing showed it is more practical and flexible.
- Keeps users inside a constrained set of API functions.
- Makes the product feel conversational without needing a complex UI.
- Lets development focus on data integrity, scoring, graph logic, and explainability.

Recommended interaction model:

```text
Telegram bot
-> start from resume upload or current-role search
-> parser/role baseline creates draft skill profile
-> user reviews, edits, removes, or adds skills
-> user chooses Explore, Advance, Search target role, or Paste JD
-> scoring engine returns suitability, matched skills, and gaps
-> Casey explains the result and sends transient report/action-plan attachments
```

Suggested Telegram buttons:

```text
[Why this score?]
[Show skill gaps]
[Generate action plan]
[Generate report]
[Back]
```

Keep chat responses short:

```text
Suitability: 82%
Target: Data Scientist
Matched: 13/15 skills
Gaps: 6

Why:
- You already cover most analytics and programming requirements.
- The largest gaps are Data Governance and Computational Modelling.
- Related evidence is shown separately when SkillsFuture defines similar skills as separate skill IDs.

Next actions:
1. Work on the top SkillsFuture K&A-backed gap.
2. Build portfolio evidence for the required proficiency level.
3. Recheck the target role or paste a JD for direct job-fit scoring.
```

Use transient Markdown attachments and debug/local audit artifacts for detailed explainability. Telegram should not try to display full matrices, long skill lists, or all K&A items inline.

Recommended API boundary:

```text
/start
/first_time_user
/start_resume
/search_roles
/explain_score
/show_gaps
/generate_action_plan
```

Backend structure:

```text
Telegram Bot -> FastAPI service -> Python scoring/pathway engine -> dataset tables
```

For the hackathon demo, this is enough:

1. Telegram baseline questionnaire flow.
2. Deterministic recommendation of 3 pathways.
3. User-selected pathway refinement with 3 to 5 target-gap questions.
4. Suitability percentage and pathway fit.
5. Top 3 to 5 gaps.
6. Button-driven explanations.
7. Generated action plan report.

This keeps the MVP scoped while still addressing the judging criteria for technical execution, explainable data use, and user-focused guidance.

## MVP Privacy And Data Retention

For the current resume/role-first MVP, do not store private information by default.

Recommended assumptions:

- Store only temporary session state needed to complete the Telegram assessment.
- Do not require name, NRIC, phone number, employer, salary, or persistent raw resume/JD text.
- Normal Telegram report/action-plan attachments are generated transiently. Debug/local validation reports may include derived skills, evidence summaries, and inferred proficiency levels, but should not include unnecessary personal identifiers.
- Human-AI judging logs should document product decisions and implementation process, not real user private data.
- If resume/JD parsing is expanded for public deployment, add explicit consent, stronger redaction, and clear retention controls around debug artifacts.

This keeps the MVP aligned with the current product assumption: the system explains skill assessment and pathway logic without storing sensitive personal data.

## Python-First Implementation

Use Python as the core programming language. The whole MVP can be built with a Python data and graph pipeline:

| Layer | Python choice |
| --- | --- |
| Excel ingestion | `pandas.read_excel` |
| Data cleaning | `pandas`, `numpy` |
| Sparse role vectors | `scipy.sparse` |
| Exact nearest-neighbor search | `numpy` or `scikit-learn` |
| Optional HNSW search | `hnswlib` or FAISS later |
| Career graph | `networkx` |
| Dijkstra shortest path | `networkx.shortest_path(..., weight="edge_weight")` |
| API/backend | `FastAPI` |
| Resume/JD parsing | Python text extraction plus LLM or rules |
| Prototype UI | Streamlit, Gradio, or a small FastAPI frontend |

Recommended MVP modules:

```text
src/
  data_loader.py          # read Excel files and normalize schemas
  feature_store.py        # build role, skill, role_skill tables
  vector_model.py         # build sparse skill-proficiency vectors
  recommender.py          # rank roles by similarity, suitability, gap cost
  graph_builder.py        # derive role-to-role edges
  pathway.py              # Dijkstra pathway planning
  explanation.py          # convert scores and gaps into dataset-grounded text
  app.py                  # Streamlit/FastAPI demo entrypoint
```

For the dataset size here, do not start with HNSW. Exact search over 2,000 role vectors is fast, easier to debug, and easier to explain. Add HNSW only if the product later indexes many job descriptions, resumes, or generated role variants.
