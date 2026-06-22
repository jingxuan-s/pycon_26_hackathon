"""Validate M3 hybrid questionnaire acceptance checks."""

from __future__ import annotations

from pathlib import Path

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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


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
    require(8 <= len(baseline_questions) <= 12, "Baseline must ask 8 to 12 questions")
    require(all(question.phase == "baseline" for question in baseline_questions), "Baseline questions must be labelled baseline")
    require(all(question.options for question in baseline_questions), "Each baseline question must have answer options")
    first_labels = {option.label for option in baseline_questions[0].options}
    require("Not familiar" in first_labels and "Used at work" in first_labels, "Questionnaire must use user-friendly answer labels")
    require("Evidence reference" not in baseline_questions[0].prompt, "Telegram prompt must not expose raw technical proficiency text")
    require("What it means:" in baseline_questions[0].prompt, "Question prompt must describe the dataset skill")
    require(baseline_questions[0].skill_description, "Question must retain the dataset skill description")

    baseline_answers = [answer_question(question, question.target_level, confidence="scripted-current-role") for question in baseline_questions]
    baseline_vector = answers_to_user_vector(baseline_answers)
    require(len(baseline_vector) == len(baseline_questions), "Baseline answers must create one vector entry per question")

    recommendations = recommend_pathways(requirements, baseline_vector, current_role_id, count=3)
    require(len(recommendations) == 3, "System must recommend exactly 3 pathways after baseline")
    require(current_role_id not in set(recommendations["role_id"]), "Recommendations must exclude current role")

    data_scientist = recommendations.loc[recommendations["job_role"].str.casefold().eq("data scientist")]
    require(not data_scientist.empty, "Scripted user must be able to choose Data Scientist from recommendations")
    selected_role_id = str(data_scientist.iloc[0]["role_id"])

    target_requirements = get_role_requirements(requirements, selected_role_id)
    before_summary, _ = score_role_fit(baseline_vector, target_requirements)
    followup_questions, _ = select_target_gap_questions(requirements, baseline_vector, selected_role_id, count=5)
    require(3 <= len(followup_questions) <= 5, "Selected pathway must trigger only 3 to 5 follow-up questions")
    require(all(question.phase == "followup" for question in followup_questions), "Follow-up questions must be labelled followup")
    baseline_skill_ids = {question.skill_id for question in baseline_questions}
    followup_skill_ids = {question.skill_id for question in followup_questions}
    require(followup_skill_ids, "Follow-up questions must target actual gaps")

    followup_answers = []
    for question in followup_questions:
        current_level = baseline_vector.get(question.skill_id, 0.0)
        selected_level = max(1.0, question.target_level - 1.0) if current_level <= 0 else min(question.target_level, current_level + 1.0)
        followup_answers.append(answer_question(question, selected_level, confidence="scripted-followup"))

    refined_vector = apply_answers_to_vector(baseline_vector, followup_answers)
    after_summary, _ = score_role_fit(refined_vector, target_requirements)
    require(after_summary.suitability > before_summary.suitability, "Updated score must improve after positive follow-up answers")
    require(after_summary.gap_cost < before_summary.gap_cost, "Updated gap cost must decrease after positive follow-up answers")

    effects = answer_effects(baseline_vector, refined_vector, target_requirements)
    require(not effects.empty, "Explanation must show which answers affected the score")
    require(set(effects["skill_id"]).issubset(followup_skill_ids | baseline_skill_ids), "Score effects must trace to answered skills")

    report_path = paths.processed_dir / "m3_questionnaire_demo.md"
    require(report_path.exists(), "M3 questionnaire demo report must exist")
    report_text = report_path.read_text(encoding="utf-8")
    for phrase in [
        "Baseline Questions",
        "Three Pathway Recommendations After Baseline",
        "Selected-Pathway Follow-up Questions",
        "Score Change",
        "Answers That Affected The Score",
    ]:
        require(phrase in report_text, f"M3 report missing section: {phrase}")

    print("M3 validation passed")
    print(f"baseline_questions={len(baseline_questions)}")
    print(f"recommendations={len(recommendations)}")
    print(f"selected_role_id={selected_role_id}")
    print(f"followup_questions={len(followup_questions)}")
    print(f"before_suitability_percentage={before_summary.suitability_percentage:.2f}")
    print(f"after_suitability_percentage={after_summary.suitability_percentage:.2f}")
    print(f"score_effect_rows={len(effects)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
