"""Run the M5 explainability and action-plan report demo."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from jobs_skills.explainability import (
    build_action_plan,
    load_skill_ka_items,
    recommendation_reasons,
    score_explanation_text,
)
from jobs_skills.pathway_graph import PathwayPolicy, derive_pathway_graph, dijkstra_path, path_edges, pathway_fit_percentage
from jobs_skills.questionnaire import (
    answer_effects,
    answer_question,
    answers_to_user_vector,
    apply_answers_to_vector,
    recommend_pathways,
    select_baseline_questions,
    select_target_gap_questions,
)
from jobs_skills.scoring import ScoringPaths, get_role_requirements, load_role_skill_requirements, score_role_fit, select_role_id


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def frame_to_markdown(frame: pd.DataFrame, columns: list[str], limit: int | None = None) -> str:
    subset = frame.loc[:, columns].copy()
    if limit is not None:
        subset = subset.head(limit)
    if subset.empty:
        return ""
    for col in subset.columns:
        if subset[col].dtype.kind in "fc":
            subset[col] = subset[col].round(2)

    def cell(value: object) -> str:
        text = "" if value is None else str(value)
        return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")

    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, row in subset.iterrows():
        lines.append("| " + " | ".join(cell(row[col]) for col in columns) + " |")
    return "\n".join(lines)


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

    target_requirements = get_role_requirements(requirements, target_role_id)
    before_summary, _ = score_role_fit(baseline_vector, target_requirements)
    followup_questions, _ = select_target_gap_questions(requirements, baseline_vector, target_role_id, count=5)
    followup_answers = []
    for question in followup_questions:
        current_level = baseline_vector.get(question.skill_id, 0.0)
        selected_level = max(1.0, question.target_level - 1.0) if current_level <= 0 else min(question.target_level, current_level + 1.0)
        followup_answers.append(answer_question(question, selected_level, confidence="scripted-followup"))
    refined_vector = apply_answers_to_vector(baseline_vector, followup_answers)
    after_summary, after_gap_table = score_role_fit(refined_vector, target_requirements)
    effects = answer_effects(baseline_vector, refined_vector, target_requirements)
    action_plan = build_action_plan(after_gap_table, ka_items, max_actions=5)

    graph = derive_pathway_graph(requirements, current_role_id, target_role_id, PathwayPolicy(), max_edges_per_source=6)
    path, total_cost = dijkstra_path(graph, current_role_id, target_role_id)
    selected_path_edges = path_edges(graph, path)
    pathway_fit = pathway_fit_percentage(total_cost, len(selected_path_edges))

    matched_skills = after_gap_table.loc[after_gap_table["covered_level"] > 0].sort_values(
        ["covered_level", "target_level", "unique_skill_title"], ascending=[False, False, True]
    )
    priority_gaps = after_gap_table.loc[after_gap_table["gap"] > 0]

    report = [
        "# Career Pathway Explanation And Action Plan",
        "",
        "## User-Facing Summary",
        "",
        "- Current assessed role: Financial Services / Digital and Data Analytics / Data Analyst",
        "- Selected target pathway: Financial Services / Digital and Data Analytics / Data Scientist",
        f"- Skill suitability after follow-up: {after_summary.suitability_percentage:.2f}%",
        f"- Pathway fit: {pathway_fit:.2f}%",
        f"- Remaining gap cost: {after_summary.gap_cost:.2f}",
        "- Pathway label: inferred from SkillsFuture role-skill data and configurable pathway policy",
        "",
        "## How You Were Judged",
        "",
        score_explanation_text(),
        "",
        "Visible inputs used:",
        "",
        "- 10 baseline current-role answers",
        "- 5 selected-pathway follow-up answers",
        "- M1 normalized role-skill requirements",
        "- M1 K&A items for action planning",
        "- M4 inferred pathway edge policy",
        "",
        "## Why These Pathways Were Recommended",
        "",
        frame_to_markdown(
            reasons,
            ["job_role", "sector", "track", "suitability_percentage", "gap_cost", "matched_skill_count", "why_recommended", "selected"],
        ),
        "",
        "## Selected Pathway Explanation",
        "",
        f"Dijkstra path: {' -> '.join(path)}",
        "",
        frame_to_markdown(
            selected_path_edges,
            [
                "source_job_role",
                "target_job_role",
                "skill_suitability_percentage",
                "edge_fit_percentage",
                "edge_weight",
                "priority_gap_titles",
                "edge_assumptions",
            ],
        ),
        "",
        "## Which Answers Changed The Score",
        "",
        frame_to_markdown(
            effects,
            ["unique_skill_title", "before_level", "after_level", "level_change", "required_level", "remaining_gap", "tsc_ccs_code"],
        ),
        "",
        "## Skills That Currently Support The Target",
        "",
        frame_to_markdown(
            matched_skills,
            ["unique_skill_title", "current_level", "target_level", "covered_level", "gap", "tsc_ccs_code", "source_row_number"],
            limit=8,
        ),
        "",
        "## Priority Gaps Causing The Remaining Score Gap",
        "",
        frame_to_markdown(
            priority_gaps,
            ["unique_skill_title", "current_level", "target_level", "gap", "tsc_ccs_code", "source_row_number"],
            limit=8,
        ),
        "",
        "## Next 5 Actions",
        "",
        frame_to_markdown(
            action_plan,
            [
                "skill",
                "current_level",
                "target_level",
                "gap",
                "next_action",
                "ka_classification",
                "ka_level",
                "ka_source_row_number",
                "role_skill_source_row_number",
            ],
        ),
        "",
        "## Data Traceability",
        "",
        "- Role requirements trace to `data/processed/role_skill_requirements.csv` by `role_skill_source_row_number`.",
        "- Actions trace to `data/processed/skill_ka_items.csv` by `ka_source_row_number`.",
        "- All score weights are `1.0` for the MVP.",
        "- Derived pathways are inferred and should be shown as assumptions, not official SkillsFuture transitions.",
        "",
    ]

    output_path = paths.processed_dir / "m5_explainability_action_plan.md"
    output_path.write_text("\n".join(report), encoding="utf-8")

    print(f"after_suitability_percentage={after_summary.suitability_percentage:.2f}")
    print(f"pathway_fit_percentage={pathway_fit:.2f}")
    print(f"actions={len(action_plan)}")
    print(f"output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
