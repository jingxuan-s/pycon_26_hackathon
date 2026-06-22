"""Validate M5 explainability and action-plan acceptance checks."""

from __future__ import annotations

from pathlib import Path

from jobs_skills.explainability import build_action_plan, load_skill_ka_items, recommendation_reasons, score_explanation_text
from jobs_skills.pathway_graph import PathwayPolicy, derive_pathway_graph, dijkstra_path, path_edges
from jobs_skills.questionnaire import (
    answer_question,
    answers_to_user_vector,
    apply_answers_to_vector,
    recommend_pathways,
    select_baseline_questions,
    select_target_gap_questions,
)
from jobs_skills.scoring import ScoringPaths, get_role_requirements, load_role_skill_requirements, score_role_fit, select_role_id


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    paths = ScoringPaths.from_project_root(PROJECT_ROOT)
    requirements = load_role_skill_requirements(paths.processed_dir)
    ka_items = load_skill_ka_items(paths.processed_dir)

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

    baseline_questions = select_baseline_questions(requirements, current_role_id, count=10)
    baseline_answers = [answer_question(question, question.target_level, confidence="scripted-current-role") for question in baseline_questions]
    baseline_vector = answers_to_user_vector(baseline_answers)
    recommendations = recommend_pathways(requirements, baseline_vector, current_role_id, count=3)
    reasons = recommendation_reasons(recommendations, target_role_id)
    require(len(reasons) == 3, "Explanation must cover all 3 recommended pathways")
    require(reasons["why_recommended"].str.contains("skill suitability", regex=False).all(), "Recommendation reasons must explain score basis")
    require(reasons["selected"].any(), "Selected pathway must be marked in recommendation explanation")

    target_requirements = get_role_requirements(requirements, target_role_id)
    followup_questions, _ = select_target_gap_questions(requirements, baseline_vector, target_role_id, count=5)
    followup_answers = []
    for question in followup_questions:
        current_level = baseline_vector.get(question.skill_id, 0.0)
        selected_level = max(1.0, question.target_level - 1.0) if current_level <= 0 else min(question.target_level, current_level + 1.0)
        followup_answers.append(answer_question(question, selected_level, confidence="scripted-followup"))
    refined_vector = apply_answers_to_vector(baseline_vector, followup_answers)
    summary, gap_table = score_role_fit(refined_vector, target_requirements)
    action_plan = build_action_plan(gap_table, ka_items, max_actions=5)

    require(3 <= len(action_plan) <= 5, "Report must include 3 to 5 concrete next actions")
    require(action_plan["next_action"].str.contains("Practise and document evidence", regex=False).all(), "Actions must be concrete evidence-building tasks")
    require(action_plan["ka_source_row_number"].astype(str).str.len().gt(0).all(), "Actions must trace to K&A source rows")
    require(action_plan["role_skill_source_row_number"].astype(str).str.len().gt(0).all(), "Actions must trace to role-skill source rows")

    graph = derive_pathway_graph(requirements, current_role_id, target_role_id, PathwayPolicy(), max_edges_per_source=6)
    path, _ = dijkstra_path(graph, current_role_id, target_role_id)
    selected_path_edges = path_edges(graph, path)
    require(selected_path_edges["edge_assumptions"].str.contains("inferred pathway edge", regex=False).all(), "Pathway explanation must label inferred edges")
    require("covered_level" in gap_table.columns and "gap" in gap_table.columns, "Skill explanation must include covered level and gap")
    require("skill_weight" in gap_table.columns, "Skill explanation must expose MVP skill weights")
    require("skill_weight" in score_explanation_text(), "Score explanation must show scoring assumptions")
    require(summary.suitability_percentage > 0, "Report scenario must produce a positive suitability score")

    report_path = paths.processed_dir / "m5_explainability_action_plan.md"
    require(report_path.exists(), "M5 explainability report must exist")
    report_text = report_path.read_text(encoding="utf-8")
    for phrase in [
        "How You Were Judged",
        "Why These Pathways Were Recommended",
        "Selected Pathway Explanation",
        "Skills That Currently Support The Target",
        "Priority Gaps Causing The Remaining Score Gap",
        "Next 5 Actions",
        "Data Traceability",
        "All score weights are `1.0`",
    ]:
        require(phrase in report_text, f"M5 report missing section or assumption: {phrase}")

    print("M5 validation passed")
    print(f"suitability_percentage={summary.suitability_percentage:.2f}")
    print(f"actions={len(action_plan)}")
    print(f"recommendations_explained={len(reasons)}")
    print(f"path_steps={len(selected_path_edges)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
