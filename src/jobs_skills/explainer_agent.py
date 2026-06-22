"""Optional explanation agent wrapper for deterministic career recommendations."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from jobs_skills.scoring import FitSummary


DEFAULT_EXPLAINER_MODEL = "gpt-5-nano"
CASEY_EXPLAINER_SYSTEM_PROMPT = (
    "You are Casey the Career Auntie, a warm but precise Singapore-style career guide. "
    "Explain deterministic career scoring results in plain, practical language. "
    "Be friendly and reassuring, but do not overclaim. "
    "You may use light local phrasing sparingly, such as 'come, we check this properly'. "
    "Do not use heavy Singlish, jokes, stereotypes, or scolding. "
    "You explain computed facts only. "
    "You do not change scores, rerank roles, invent skills, invent evidence, or recommend unsupported actions."
)
TOKEN_ENV_NAMES = (
    "EXPLAINER_AGENT_API_TOKEN",
    "explainer_agent_api_token",
    "AGENT_API_TOKEN",
    "agent_api_token",
    "OPENAI_API_KEY",
    "openai_api_key",
)
MODEL_ENV_NAMES = ("EXPLAINER_AGENT_MODEL", "explainer_agent_model")
DISABLE_ENV_NAMES = ("EXPLAINER_AGENT_DISABLED", "explainer_agent_disabled")
PROXY_ENV_NAMES = ("EXPLAINER_AGENT_TRUST_ENV_PROXY", "explainer_agent_trust_env_proxy")


@dataclass(frozen=True)
class ExplanationResult:
    text: str
    source: str
    model: str
    used_agent: bool


class ExplainerAgent:
    """Explain deterministic outputs with an optional LLM and rule fallback."""

    def __init__(self, api_token: str | None = None, model: str = DEFAULT_EXPLAINER_MODEL, timeout_seconds: float = 8.0) -> None:
        self.api_token = api_token.strip() if api_token else ""
        self.model = model.strip() or DEFAULT_EXPLAINER_MODEL
        self.timeout_seconds = timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self.api_token)

    def explain_recommendations(
        self,
        recommendations: pd.DataFrame,
        current_role: Mapping[str, Any] | pd.Series | None = None,
    ) -> ExplanationResult:
        facts = recommendation_facts(recommendations, current_role)
        fallback = rule_based_recommendation_explanation(facts, self.model)
        return self._agent_or_fallback(
            task="recommendations",
            facts=facts,
            fallback=fallback,
            instruction=(
                "Explain why these career pathways were recommended in Casey's voice. Use only the provided facts. "
                "Mention the deterministic ranking logic, the top matched/gap signals, and that all MVP skill weights are 1.0. "
                "Do not invent skills, scores, new ranking reasons, or unsupported advice. Keep it under 90 words."
            ),
        )

    def explain_score(self, summary: FitSummary, gap_table: pd.DataFrame) -> ExplanationResult:
        facts = score_facts(summary, gap_table)
        fallback = rule_based_score_explanation(facts, self.model)
        return self._agent_or_fallback(
            task="score",
            facts=facts,
            fallback=fallback,
            instruction=(
                "Explain why the selected role suitability score was given in Casey's voice. Use only the provided facts. "
                "Mention matched skills, priority gaps, the suitability formula in plain language, and that all MVP skill weights are 1.0. "
                "Do not recalculate, change the score, invent evidence, or recommend unsupported actions. Keep it under 110 words."
            ),
        )

    def _agent_or_fallback(
        self,
        task: str,
        facts: dict[str, Any],
        fallback: str,
        instruction: str,
    ) -> ExplanationResult:
        if not self.enabled:
            return ExplanationResult(text=fallback, source="rule-based fallback: no explainer token configured", model=self.model, used_agent=False)

        try:
            text = self._call_openai(task=task, facts=facts, instruction=instruction)
        except Exception as exc:
            source = f"rule-based fallback: explainer call failed ({_exception_summary(exc)})"
            return ExplanationResult(text=fallback, source=source, model=self.model, used_agent=False)

        if not text:
            return ExplanationResult(text=fallback, source="rule-based fallback: empty explainer response", model=self.model, used_agent=False)
        return ExplanationResult(text=f"Casey insight ({self.model})\n{text}", source="agent", model=self.model, used_agent=True)

    def _call_openai(self, task: str, facts: dict[str, Any], instruction: str) -> str:
        import httpx
        from openai import OpenAI  # type: ignore[import-not-found]

        http_client = httpx.Client(timeout=self.timeout_seconds, trust_env=_trust_env_proxy())
        client = OpenAI(api_key=self.api_token, http_client=http_client)
        response = client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": CASEY_EXPLAINER_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": json.dumps({"task": task, "instruction": instruction, "facts": facts}, ensure_ascii=True),
                },
            ],
            max_output_tokens=900,
            reasoning={"effort": "minimal"},
        )
        output_text = getattr(response, "output_text", "")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()
        return ""


def load_explainer_agent_from_env(project_root: Path | None = None) -> ExplainerAgent:
    """Load optional explainer config from environment without exposing secrets."""
    if project_root is not None:
        try:
            from dotenv import load_dotenv

            load_dotenv(project_root / ".env")
        except ImportError:
            pass

    disabled = next((os.getenv(name, "") for name in DISABLE_ENV_NAMES if os.getenv(name)), "")
    if disabled.strip().casefold() in {"1", "true", "yes", "on"}:
        return ExplainerAgent(api_token=None, model=_env_value(MODEL_ENV_NAMES) or DEFAULT_EXPLAINER_MODEL)

    return ExplainerAgent(
        api_token=_env_value(TOKEN_ENV_NAMES),
        model=_env_value(MODEL_ENV_NAMES) or DEFAULT_EXPLAINER_MODEL,
    )


def recommendation_facts(recommendations: pd.DataFrame, current_role: Mapping[str, Any] | pd.Series | None = None) -> dict[str, Any]:
    current = _series_to_dict(current_role)
    roles: list[dict[str, Any]] = []
    for index, row in recommendations.reset_index(drop=True).iterrows():
        role_facts = {
            "rank": index + 1,
            "role_id": str(row.role_id),
            "job_role": str(row.job_role),
            "sector": str(row.sector),
            "track": str(row.track),
            "suitability_percentage": round(float(row.suitability_percentage), 2),
            "matched_skill_count": int(row.matched_skill_count),
            "target_skill_count": int(row.target_skill_count),
            "gap_skill_count": int(row.gap_skill_count),
            "gap_cost": round(float(row.gap_cost), 2),
        }
        if "vector_distance" in recommendations.columns:
            role_facts["vector_distance"] = round(float(row.vector_distance), 2)
            role_facts["shared_skill_count"] = int(row.shared_skill_count)
            role_facts["compared_skill_count"] = int(row.compared_skill_count)
        roles.append(role_facts)
    has_vector_discovery = "vector_distance" in recommendations.columns
    ranking_logic = (
        "Explore pathways first finds nearby roles in skill-vector space using weighted L1 nearest-neighbour distance, "
        "then re-ranks those roles using suitability and gap cost."
        if has_vector_discovery
        else "Roles are ranked by deterministic skill suitability, then lower gap cost, then matched skill count."
    )
    return {
        "current_role": {
            "job_role": current.get("job_role", ""),
            "sector": current.get("sector", ""),
            "track": current.get("track", ""),
        },
        "ranking_logic": ranking_logic,
        "skill_weight_policy": "All MVP skill weights are 1.0.",
        "agent_boundary": "The explainer may describe results but cannot change scores or rankings.",
        "recommendations": roles,
    }


def score_facts(summary: FitSummary, gap_table: pd.DataFrame) -> dict[str, Any]:
    gaps = gap_table.loc[gap_table["gap"] > 0].head(3)
    priority_gaps = [
        {
            "skill": str(row.unique_skill_title),
            "current_level": float(row.current_level),
            "target_level": float(row.target_level),
            "gap": float(row.gap),
        }
        for row in gaps.itertuples(index=False)
    ]
    return {
        "target_role": summary.job_role,
        "sector": summary.sector,
        "track": summary.track,
        "suitability_percentage": round(summary.suitability_percentage, 2),
        "matched_skill_count": summary.matched_skill_count,
        "target_skill_count": summary.target_skill_count,
        "gap_skill_count": summary.gap_skill_count,
        "gap_cost": round(summary.gap_cost, 2),
        "formula": "suitability = sum(skill_weight * min(current_level, target_level)) / sum(skill_weight * target_level)",
        "skill_weight_policy": "All MVP skill weights are 1.0.",
        "agent_boundary": "The explainer may describe results but cannot change scores or rankings.",
        "priority_gaps": priority_gaps,
    }


def rule_based_recommendation_explanation(facts: dict[str, Any], model: str = DEFAULT_EXPLAINER_MODEL) -> str:
    roles = facts.get("recommendations", [])
    top = roles[0] if roles else {}
    current = facts.get("current_role", {})
    lines = [
        "Casey recommendation insight (rule-based fallback)",
        f"Current baseline: {_role_label(current)}",
        "Come, Casey checked this against the deterministic recommender.",
        str(facts.get("ranking_logic", "Roles are ranked by deterministic skill suitability from your answered skill vector.")),
    ]
    if top:
        lines.append(
            "Top path: "
            f"{top['job_role']} at {top['suitability_percentage']:.2f}% fit, "
            f"matching {top['matched_skill_count']}/{top['target_skill_count']} target skills with {top['gap_skill_count']} gaps."
        )
    lines.append(f"All MVP skill weights are 1.0. Explainer model setting: {model}; Casey explains only and no score is changed by this layer.")
    return "\n".join(lines)


def rule_based_score_explanation(facts: dict[str, Any], model: str = DEFAULT_EXPLAINER_MODEL) -> str:
    lines = [
        "Casey score insight (rule-based fallback)",
        f"Casey checked the deterministic score for {facts['target_role']}.",
        f"Suitability is {facts['suitability_percentage']:.2f}%.",
        f"You cover {facts['matched_skill_count']}/{facts['target_skill_count']} target skills; {facts['gap_skill_count']} skills remain below target.",
    ]
    priority_gaps = facts.get("priority_gaps", [])
    if priority_gaps:
        top = priority_gaps[0]
        lines.append(f"Priority gap: {top['skill']} is level {top['current_level']:g}; target is level {top['target_level']:g}.")
    lines.append("The score is covered required levels divided by total target required levels. All MVP skill weights are 1.0.")
    lines.append(f"Explainer model setting: {model}; Casey explains only and does not rescore.")
    return "\n".join(lines)


def _trust_env_proxy() -> bool:
    value = _env_value(PROXY_ENV_NAMES)
    return bool(value and value.strip().casefold() in {"1", "true", "yes", "on"})


def _exception_summary(exc: Exception) -> str:
    parts = [type(exc).__name__]
    message = str(exc).strip()
    if message:
        parts.append(message[:180])
    cause = getattr(exc, "__cause__", None)
    if cause is not None:
        cause_text = str(cause).strip()
        if cause_text:
            parts.append(f"cause: {type(cause).__name__}: {cause_text[:180]}")
    return "; ".join(parts)


def _env_value(names: tuple[str, ...]) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def _series_to_dict(value: Mapping[str, Any] | pd.Series | None) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, pd.Series):
        return value.to_dict()
    return dict(value)


def _role_label(role: Mapping[str, Any]) -> str:
    job_role = str(role.get("job_role") or "selected role")
    sector = str(role.get("sector") or "").strip()
    track = str(role.get("track") or "").strip()
    if sector and track:
        return f"{job_role} ({sector} / {track})"
    return job_role
