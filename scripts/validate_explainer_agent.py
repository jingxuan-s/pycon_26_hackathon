"""Validate optional explainer-agent routing and rule fallback behavior."""

from __future__ import annotations

import os
import sys
from pathlib import Path



PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from jobs_skills.explainer_agent import CASEY_EXPLAINER_SYSTEM_PROMPT, ExplainerAgent, load_explainer_agent_from_env
from jobs_skills.questionnaire import answer_question, answers_to_user_vector, recommend_pathways, select_baseline_questions
from jobs_skills.scoring import ScoringPaths, get_role_requirements, load_role_skill_requirements, score_role_fit, select_role_id
SESSION_ENV_KEYS = [
    "EXPLAINER_AGENT_API_TOKEN",
    "explainer_agent_api_token",
    "AGENT_API_TOKEN",
    "agent_api_token",
    "OPENAI_API_KEY",
    "openai_api_key",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    for key in SESSION_ENV_KEYS:
        os.environ.pop(key, None)
    os.environ["EXPLAINER_AGENT_DISABLED"] = "1"

    loaded = load_explainer_agent_from_env(PROJECT_ROOT)
    require(not loaded.enabled, "Explainer must fall back when disabled or tokenless")
    require(loaded.model == "gpt-5-nano", "Default explainer model must be gpt-5-nano")
    require("Casey the Career Auntie" in CASEY_EXPLAINER_SYSTEM_PROMPT, "Explainer prompt must include Casey persona")
    require("do not change scores" in CASEY_EXPLAINER_SYSTEM_PROMPT, "Explainer prompt must keep deterministic score boundary")
    require("invent skills" in CASEY_EXPLAINER_SYSTEM_PROMPT, "Explainer prompt must forbid invented skills")

    paths = ScoringPaths.from_project_root(PROJECT_ROOT)
    requirements = load_role_skill_requirements(paths.processed_dir)
    current_role_id = select_role_id(
        requirements,
        job_role="Data Analyst",
        sector="Financial Services",
        track="Digital and Data Analytics",
    )
    target_role_id = select_role_id(
        requirements,
        job_role="Data Scientist",
        sector="Financial Services",
        track="Digital and Data Analytics",
    )

    questions = select_baseline_questions(requirements, current_role_id, count=10)
    answers = [answer_question(question, question.target_level, confidence="validation") for question in questions]
    user_vector = answers_to_user_vector(answers)
    recommendations = recommend_pathways(requirements, user_vector, current_role_id, count=3)
    target_requirements = get_role_requirements(requirements, target_role_id)
    summary, gap_table = score_role_fit(user_vector, target_requirements)

    explainer = ExplainerAgent(api_token=None)
    recommendation = explainer.explain_recommendations(recommendations, current_role=requirements.iloc[0])
    score = explainer.explain_score(summary, gap_table)

    require(not recommendation.used_agent, "Recommendation explanation must use fallback without token")
    require("Casey recommendation insight (rule-based fallback)" in recommendation.text, "Fallback recommendation text must be labelled")
    require("Casey checked" in recommendation.text, "Fallback recommendation must use Casey framing")
    require("deterministic skill suitability" in recommendation.text, "Fallback recommendation must explain ranking logic")
    require("All MVP skill weights are 1.0" in recommendation.text, "Fallback recommendation must expose weighting assumption")
    require(not score.used_agent, "Score explanation must use fallback without token")
    require("Casey score insight (rule-based fallback)" in score.text, "Fallback score text must be labelled")
    require("Casey checked the deterministic score" in score.text, "Fallback score must use Casey framing")
    require("does not rescore" in score.text, "Fallback score text must state agent boundary")

    agent_prefix_check = ExplainerAgent(api_token="test-token")
    agent_prefix_check._call_openai = lambda task, facts, instruction: "Computed-fact explanation only."
    agent_prefix = agent_prefix_check.explain_score(summary, gap_table)
    require(agent_prefix.used_agent, "Mocked live explainer path must report agent usage")
    require(agent_prefix.text.startswith("Casey insight (gpt-5-nano)"), "Live explainer text must use Casey insight label")


    os.environ.pop("EXPLAINER_AGENT_DISABLED", None)
    print("Explainer agent validation passed")
    print(f"model={loaded.model}")
    print(f"recommendation_source={recommendation.source}")
    print(f"score_source={score.source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
