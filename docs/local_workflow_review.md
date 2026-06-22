# Local Workflow Review Runbook

Use this local review loop to refine parser behavior, recommendation wording, scoring outputs, and user experience before restarting Telegram.

## Why This Exists

Telegram is the demo surface, not the best place to debug every workflow detail. Local tools make it easier to inspect parsed skills, target modes, reports, and validator failures without waiting for chat interactions.

Local review separates:

- compact Telegram prompt text
- full dataset detail for auditability
- parsed skill evidence and uncertainty flags
- skill review/edit/remove/add behavior
- recommendation presentation
- score and action-plan presentation
- normal vs debug report boundaries

## Resume-First Local Flow

Use this when you want to test the current product workflow locally:

```powershell
.\.venv\Scripts\python.exe scripts\run_resume_recommender.py
```

The flow supports:

- PDF/DOCX resume ingestion
- role-start baseline selection
- parsed skill review
- edit/remove/add skill operations
- Explore pathways
- Advance roles
- specific role search
- pasted JD scoring
- transient normal attachments and explicit debug/local reports

Validate the scripted version:

```powershell
.\.venv\Scripts\python.exe scripts\validate_resume_recommender.py
```

## Telegram Service Validation

Use this to validate the Telegram service without polling the live bot:

```powershell
.\.venv\Scripts\python.exe scripts\validate_m6_telegram.py
```

This checks the resume/role-first `/start` flow, review pagination, edit/remove/add, target modes, compact outputs, normal/debug report behavior, action-plan attachments, and rate-limit-safe service interactions.

## Legacy Questionnaire Flow

The questionnaire flow remains available for methodology comparison and historical validation, but it is no longer the default Telegram product flow.

Interactive terminal run:

```powershell
.\.venv\Scripts\python.exe scripts\run_local_questionnaire.py
```

Validator:

```powershell
.\.venv\Scripts\python.exe scripts\validate_local_questionnaire.py
```

## Optional Explainer Agent

The local flows route recommendation and score explanations through the optional explainer layer when configured. Deterministic scoring remains the source of truth.

To use the agent, `.env` should include a token and should not disable the explainer:

```text
EXPLAINER_AGENT_API_TOKEN=<your token>
EXPLAINER_AGENT_MODEL=gpt-5-nano
```

This forces rule-based fallback even if a token exists:

```text
EXPLAINER_AGENT_DISABLED=1
```

Remove that line or set it to `0` when you want the agent call to run. Output/report metadata shows whether the explanation came from the agent or fallback.

## Preview Artifact

The older local preview is still useful for reviewing questionnaire wording and report structure:

```powershell
.\.venv\Scripts\python.exe scripts\run_local_workflow_preview.py
```

Default output:

```text
data/processed/local_workflow_preview.md
```

Validate it with:

```powershell
.\.venv\Scripts\python.exe scripts\validate_local_workflow_preview.py
```

## Product Rule

Use local tooling to refine logic and wording first. Telegram should receive compact, polished prompts and short explanations. Put full dataset language, parser diagnostics, formula details, and source rows in debug reports or local audit artifacts. Normal Telegram attachments should stay compact and transient.
