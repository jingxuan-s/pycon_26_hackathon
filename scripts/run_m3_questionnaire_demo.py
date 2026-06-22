"""Run the M3 hybrid questionnaire demo."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from jobs_skills.questionnaire import (
    answer_effects,
    answer_question,
    answers_to_user_vector,
    apply_answers_to_vector,
    recommend_pathways,
    select_baseline_questions,
    select_target_gap_questions,
)
from jobs_skills.scoring import (
    ScoringPaths,
    get_role_requirements,
    load_role_skill_requirements,
    score_role_fit,
    select_role_id,
)


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


def answers_frame(answers) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "phase": answer.phase,
                "skill": answer.unique_skill_title,
                "selected_level": answer.selected_level,
                "selected_label": answer.selected_label,
                "confidence": answer.confidence,
            }
            for answer in answers
        ]
    )


def questions_frame(questions) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "phase": question.phase,
                "skill": question.unique_skill_title,
                "target_level": question.target_level,
                "tsc_ccs_code": question.tsc_ccs_code,
                "source_row_number": question.source_row_number,
            }
            for question in questions
        ]
    )


def choose_data_scientist(recommendations: pd.DataFrame) -> str:
    matches = recommendations.loc[recommendations["job_role"].str.casefold().eq("data scientist")]
    if matches.empty:
        raise AssertionError("Scripted M3 demo expected Data Scientist to appear in the 3 recommendations")
    return str(matches.iloc[0]["role_id"])


def main() -> int:
    paths = ScoringPaths.from_project_root(PROJECT_ROOT)
    requirements = load_role_skill_requirements(paths.processed_dir)

    current_role_id = select_role_id(
        requirements,
        job_role="Data Analyst",
        sector="Financial Services",
        track="Digital and Data Analytics",
    )

    baseline_questions = select_baseline_questions(requirements, current_role_id, count=10)
    baseline_answers = [answer_question(question, question.target_level, confidence="scripted-current-role") for question in baseline_questions]
    baseline_vector = answers_to_user_vector(baseline_answers)

    recommendations = recommend_pathways(requirements, baseline_vector, current_role_id, count=3)
    selected_role_id = choose_data_scientist(recommendations)
    target_requirements = get_role_requirements(requirements, selected_role_id)
    before_summary, _ = score_role_fit(baseline_vector, target_requirements)

    followup_questions, followup_gap_table = select_target_gap_questions(
        requirements, baseline_vector, selected_role_id, count=5
    )
    followup_answers = []
    for question in followup_questions:
        current_level = baseline_vector.get(question.skill_id, 0.0)
        if current_level <= 0:
            selected_level = max(1.0, question.target_level - 1.0)
        else:
            selected_level = min(question.target_level, current_level + 1.0)
        followup_answers.append(answer_question(question, selected_level, confidence="scripted-followup"))

    refined_vector = apply_answers_to_vector(baseline_vector, followup_answers)
    after_summary, after_gap_table = score_role_fit(refined_vector, target_requirements)
    effects = answer_effects(baseline_vector, refined_vector, target_requirements)

    report = [
        "# M3 Hybrid Questionnaire Demo",
        "",
        "## Scenario",
        "",
        "- Current role: Financial Services / Digital and Data Analytics / Data Analyst",
        "- Baseline question count: 10",
        "- Recommendation count: 3",
        "- Selected pathway: Financial Services / Digital and Data Analytics / Data Scientist",
        "- Follow-up question count: 5",
        "",
        "## Baseline Questions",
        "",
        frame_to_markdown(
            questions_frame(baseline_questions),
            ["phase", "skill", "target_level", "tsc_ccs_code", "source_row_number"],
        ),
        "",
        "## Baseline Answers",
        "",
        frame_to_markdown(
            answers_frame(baseline_answers),
            ["phase", "skill", "selected_level", "selected_label", "confidence"],
        ),
        "",
        "## Three Pathway Recommendations After Baseline",
        "",
        frame_to_markdown(
            recommendations,
            ["job_role", "sector", "track", "suitability_percentage", "gap_cost", "matched_skill_count", "target_skill_count"],
        ),
        "",
        "## Selected-Pathway Follow-up Questions",
        "",
        frame_to_markdown(
            questions_frame(followup_questions),
            ["phase", "skill", "target_level", "tsc_ccs_code", "source_row_number"],
        ),
        "",
        "## Follow-up Answers",
        "",
        frame_to_markdown(
            answers_frame(followup_answers),
            ["phase", "skill", "selected_level", "selected_label", "confidence"],
        ),
        "",
        "## Score Change",
        "",
        f"- Before follow-up suitability: {before_summary.suitability_percentage:.2f}%",
        f"- After follow-up suitability: {after_summary.suitability_percentage:.2f}%",
        f"- Before gap cost: {before_summary.gap_cost:.2f}",
        f"- After gap cost: {after_summary.gap_cost:.2f}",
        "",
        "## Answers That Affected The Score",
        "",
        frame_to_markdown(
            effects,
            ["unique_skill_title", "before_level", "after_level", "level_change", "required_level", "remaining_gap", "tsc_ccs_code"],
        ),
        "",
        "## Remaining Top Gaps After Follow-up",
        "",
        frame_to_markdown(
            after_gap_table.loc[after_gap_table["gap"] > 0],
            ["unique_skill_title", "current_level", "target_level", "gap", "tsc_ccs_code", "source_row_number"],
            limit=10,
        ),
        "",
    ]

    output_path = paths.processed_dir / "m3_questionnaire_demo.md"
    output_path.write_text("\n".join(report), encoding="utf-8")

    print(f"baseline_questions={len(baseline_questions)}")
    print(f"recommendations={len(recommendations)}")
    print(f"selected_role_id={selected_role_id}")
    print(f"followup_questions={len(followup_questions)}")
    print(f"before_suitability_percentage={before_summary.suitability_percentage:.2f}")
    print(f"after_suitability_percentage={after_summary.suitability_percentage:.2f}")
    print(f"output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
