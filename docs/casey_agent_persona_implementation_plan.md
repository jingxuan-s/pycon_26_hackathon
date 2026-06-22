# Casey Agent Persona Implementation Plan

## Current Decision

Implement only the explainer-agent persona update for now.

Do not implement parser-agent persona changes yet. Do not integrate the action-plan summariser agent yet.

This decision comes from the prototype result: the action-plan summariser made the output easier to scan, but it mostly paraphrased deterministic K&A rows and did not add enough practical value to justify more agent surface area. The parser agent should also remain neutral for now because parser output feeds the skill-review workflow.

## Summary

Apply Casey the Career Auntie to the explainer layer only, while keeping deterministic scoring and parser extraction unchanged.

Casey's role in this phase:

- Explain computed recommendation and score facts in warmer, clearer language.
- Keep explanations practical and user-facing.
- Preserve all deterministic boundaries: no rescoring, reranking, invented skills, invented evidence, or unsupported advice.

## Goals

- Make `Why this score?` and recommendation explanations sound consistent with Casey's Telegram persona.
- Keep the explainer advisory only.
- Preserve deterministic suitability scoring and role ranking.
- Keep parser extraction neutral and auditable.
- Avoid heavy Singlish, jokes, caricature, scolding, or unsupported confidence.

## Non-Goals

- Do not change scoring formulas.
- Do not let agents rerank roles or alter suitability percentages.
- Do not change parser prompts or parser schema.
- Do not add `display_reason` to parser output yet.
- Do not integrate the action-plan summariser agent.
- Do not rewrite action-plan generation in this milestone.
- Do not rewrite all normal/debug reports unless directly affected by explainer output.

## M1: Explainer Agent Persona

### Goal Prompt

Update the explainer agent so user-facing explanations are written in Casey the Career Auntie voice: warm, practical, local, and precise. The explainer must still explain computed facts only and must not change scores, rankings, gaps, recommendations, skill levels, or action plans.

### Why This Matters

The explainer is shown when users ask why a score or recommendation was produced. Casey's tone can make this feel less clinical while still keeping the reasoning transparent and dataset-backed.

This is the safest agent-persona layer because the explainer already receives computed facts from deterministic scoring.

### Inputs

- `src/jobs_skills/explainer_agent.py`
- `docs/casey_persona.md`
- Existing `recommendation_facts()` payload
- Existing `score_facts()` payload
- Existing rule-based fallback explanation functions
- `scripts/validate_explainer_agent.py`

### Outputs

- Updated explainer system instruction.
- Optional helper constant, e.g. `CASEY_EXPLAINER_SYSTEM_PROMPT`.
- Rule-based fallback copy lightly aligned to Casey.
- Validator coverage proving agent boundaries remain intact.

### Implementation Notes

Suggested explainer system prompt:

```text
You are Casey the Career Auntie, a warm but precise Singapore-style career guide.

Explain deterministic career scoring results in plain, practical language.
Be friendly and reassuring, but do not overclaim.

You may use light local phrasing sparingly, such as "come, we check this properly".
Do not use heavy Singlish, jokes, stereotypes, or scolding.

You explain computed facts only.
You do not change scores, rerank roles, invent skills, invent evidence, or recommend unsupported actions.
```

Keep the existing deterministic boundary sentence. The prompt should make Casey's voice a presentation layer, not a reasoning authority.

Recommended fallback style:

```text
Casey checked the deterministic score.
You match 5 of 9 target skills. The biggest gaps are Data Governance and Computational Modelling.
The score is based on covered target levels divided by total target levels.
```

Keep formulas and model metadata out of normal Telegram messages unless debug/report mode explicitly asks for them.

### Acceptance Checks

- Explainer system prompt includes Casey persona and deterministic-boundary language.
- Rule-based fallback still states score/ranking logic clearly.
- Recommendation explanation still mentions ranking logic and top role signals.
- Score explanation still mentions matched skills, priority gaps, and score basis.
- No scoring, parser, or action-plan code changes are required.
- `scripts/validate_explainer_agent.py` passes.
- `scripts/validate_m6_telegram.py` passes.

### Do Not Stray Into

- Parser prompt changes.
- Parser schema changes.
- Action-plan summariser integration.
- Telegram UI redesign.
- Scoring methodology changes.
- Report-format overhaul.

## Deferred: Parser Agent Display-Reason Persona

### Status

Deferred.

### Reason

Parser output feeds the skill-review workflow. The parser must remain evidence-first, neutral, and auditable. Adding Casey's voice directly to parser reasons may blur the line between extraction evidence and user-facing explanation.

### Future Option

If revisited later, prefer a separate field:

```json
{
  "reason": "neutral audit reason tied to evidence",
  "display_reason": "short user-facing reason in Casey's voice"
}
```

Until then, keep using deterministic/user-facing formatting helpers such as `_user_facing_skill_reason()` for Telegram copy.

### Future Guardrails

- Parser agent must still extract evidence only.
- Parser result must remain auditable with evidence, confidence, mapping type, and uncertainty flag.
- No raw resume/JD text should be persisted.
- Debug reports must remain neutral and audit-friendly.
- Parser must not decide suitability.

## Deferred: Action-Plan Summariser Agent

### Status

Deferred after prototype.

### Prototype Evidence

Prototype script:

```text
scripts/prototype_action_plan_summariser.py
```

Generated comparison artifacts under `data/processed/action_plan_summariser_prototype_*.md`.

### Finding

The agent rewrite improved formatting but did not add enough practical guidance. The first run also overstepped by adding an extra follow-up offer and referencing all gaps instead of only the provided action rows. A stricter prompt improved compliance, but the output still mostly paraphrased deterministic K&A rows.

### Decision

Do not integrate this into Telegram or reports yet.

### Better Next Step

Improve deterministic action templates in `src/jobs_skills/explainability.py` first, especially:

- starter tasks
- practice tasks
- concrete portfolio artifacts
- level-aware evidence suggestions
- skill-type-aware templates

After deterministic action content is stronger, an optional Casey polish layer can be reconsidered.

## Documentation Update

### Goal Prompt

Document Casey's agent boundary clearly: Casey is a presentation/persona layer for explanation, not a scoring authority.

### Inputs

- `docs/casey_persona.md`
- `docs/scoring_methodology.md`
- `docs/project_brief.md`

### Outputs

- Short note in `docs/casey_persona.md` explaining:
  - Telegram copy uses Casey directly.
  - Explainer agent may use Casey voice.
  - Parser remains neutral for now.
  - Action plans remain deterministic for now.

### Acceptance Checks

- Docs make clear that Casey does not change scores.
- Docs distinguish parser extraction from explainer narration.
- README remains concise.

## Test Plan

Run with explicit timeouts:

```powershell
.\.venv\Scripts\python.exe -m py_compile src\jobs_skills\explainer_agent.py src\jobs_skills\telegram_bot.py scripts\validate_explainer_agent.py scripts\validate_m6_telegram.py
.\.venv\Scripts\python.exe scripts\validate_explainer_agent.py
.\.venv\Scripts\python.exe scripts\validate_m6_telegram.py
.\.venv\Scripts\python.exe scripts\validate_telegram_adapter.py
.\.venv\Scripts\python.exe scripts\run_telegram_bot.py --smoke-test
```

Optional live-agent check, only when a token is configured and network access is available:

```powershell
.\.venv\Scripts\python.exe scripts\validate_explainer_agent.py --use-agent
```

If no live-agent validator exists yet, add a small safe check that invokes the explainer with synthetic facts and verifies the output is non-empty, does not change numbers, and does not invent extra roles or skills.

## Recommended Execution Order

1. Update explainer system prompt with Casey persona and deterministic boundary.
2. Lightly update rule-based fallback wording.
3. Update `docs/casey_persona.md` with the agent-boundary note.
4. Update or add explainer validation checks.
5. Run the test plan.
6. Manually compare a `Why this score?` output before deciding whether further copy tuning is needed.

## Risk Controls

- Keep deterministic scoring as the source of truth.
- Keep parser raw evidence neutral.
- Keep normal Telegram output compact.
- Keep debug reports audit-friendly.
- Treat Casey as a presentation layer, not a model authority.
- Fall back to rule-based explanations if the agent is missing, times out, or produces empty output.
