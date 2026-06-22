"""Validate stretch parser-agent flow without replacing deterministic scoring."""

from __future__ import annotations

from pathlib import Path

from jobs_skills.explainability import build_action_plan, load_skill_ka_items
from jobs_skills.parser_agents import (
    apply_confirmed_levels,
    build_target_requirements_from_jd,
    load_skills,
    parse_jd_text,
    parse_resume_text,
    parser_result_to_frame,
)
from jobs_skills.scoring import ScoringPaths, score_role_fit


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "data" / "processed" / "f3_resume_jd_suitability_demo.md"

SAMPLE_RESUME = """
Data analyst with 4 years of experience. Built Python and SQL automation scripts
for monthly reporting and developed Power BI dashboards for finance stakeholders.
Analysed customer data to identify churn patterns and created segmentation models.
Supported data governance checks by documenting data quality issues and privacy
handling rules. Managed delivery timelines with business users and presented
insights to cross-functional stakeholders.
"""

SAMPLE_JD = """
We are hiring a Data Scientist. The role must build predictive models, use Python
and SQL for programming and coding, design data analytics and computational
modelling approaches, and create dashboards that explain model results. The
candidate should lead data governance practices, support project management, and
work with stakeholders to turn analysis into decisions.
"""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    paths = ScoringPaths.from_project_root(PROJECT_ROOT)
    skills = load_skills(paths.processed_dir)
    ka_items = load_skill_ka_items(paths.processed_dir)

    resume_result = parse_resume_text(SAMPLE_RESUME, skills, max_skills=12)
    jd_result = parse_jd_text(SAMPLE_JD, skills, max_skills=12)

    require(resume_result.source_type == "resume", "Resume parser must label source type")
    require(jd_result.source_type == "job_description", "JD parser must label source type")
    require(len(resume_result.extracted_skills) >= 5, "Resume parser should extract several auditable skills")
    require(len(jd_result.extracted_skills) >= 5, "JD parser should extract several target requirements")
    require(all(item.evidence for item in resume_result.extracted_skills), "Resume evidence snippets must not be empty")
    require(all(item.confidence > 0 for item in jd_result.extracted_skills), "JD confidence values must be positive")
    require(any(item.mapping_type == "inferred_alias" for item in resume_result.extracted_skills), "Resume parser should label inferred mappings")
    uncertain_item = next((item for item in resume_result.extracted_skills if item.uncertainty_flag), None)
    require(uncertain_item is not None, "Parser should flag uncertain mappings for confirmation")
    confirmed_resume_result = apply_confirmed_levels(resume_result, {uncertain_item.skill_id: uncertain_item.inferred_level})
    confirmed_item = next(item for item in confirmed_resume_result.extracted_skills if item.skill_id == uncertain_item.skill_id)
    require(not confirmed_item.uncertainty_flag, "User-confirmed parser skills should clear uncertainty")
    require(confirmed_item.confidence == 0.99, "User-confirmed parser skills should become high-confidence inputs")

    resume_vector = confirmed_resume_result.to_user_vector()
    target_requirements = build_target_requirements_from_jd(jd_result, skills, role_label="Parsed Data Scientist JD")
    summary, gap_table = score_role_fit(resume_vector, target_requirements)
    action_plan = build_action_plan(gap_table, ka_items, max_actions=5)

    require(summary.suitability_percentage > 0, "Deterministic suitability should be non-zero")
    require(summary.suitability_percentage < 100, "Sample should retain visible gaps")
    require("skill_weight" in gap_table.columns, "Gap table must expose scoring weights")
    require(gap_table["skill_weight"].eq(1.0).all(), "Parser stretch flow must keep MVP weights at 1.0")
    require(not action_plan.empty, "Parser suitability flow should produce gap actions")

    resume_frame = parser_result_to_frame(confirmed_resume_result)
    jd_frame = parser_result_to_frame(jd_result)
    REPORT_PATH.write_text(_render_report(resume_frame, jd_frame, summary, gap_table, action_plan), encoding="utf-8")

    report_text = REPORT_PATH.read_text(encoding="utf-8")
    for phrase in [
        "Parser Boundary",
        "Deterministic Suitability",
        "Extracted Resume Evidence",
        "Extracted JD Requirements",
        "Priority Gaps",
        "Action Plan",
    ]:
        require(phrase in report_text, f"Report missing section: {phrase}")

    print("F1-F3 parser validation passed")
    print(f"resume_skills={len(resume_result.extracted_skills)}")
    print(f"jd_skills={len(jd_result.extracted_skills)}")
    print(f"suitability_percentage={summary.suitability_percentage:.2f}")
    print(f"gap_count={summary.gap_skill_count}")
    print(f"output={REPORT_PATH}")
    return 0


def _render_report(resume_frame, jd_frame, summary, gap_table, action_plan) -> str:
    top_resume = resume_frame[["unique_skill_title", "inferred_level", "confidence", "mapping_type", "evidence"]].head(8)
    top_jd = jd_frame[["unique_skill_title", "inferred_level", "confidence", "mapping_type", "evidence"]].head(8)
    top_gaps = gap_table.loc[gap_table["gap"] > 0, ["unique_skill_title", "current_level", "target_level", "gap", "skill_weight"]].head(8)
    actions = action_plan[["skill", "current_level", "target_level", "next_action", "ka_classification", "ka_source_row_number"]].head(5)

    lines = [
        "# F1-F3 Resume/JD Parser Suitability Demo",
        "",
        "## Parser Boundary",
        "",
        "Parser agents extract structured evidence only: skill mapping, inferred level, confidence, evidence, reason, and uncertainty. Final suitability is calculated by the deterministic scoring engine, not by the parser.",
        "",
        "## Deterministic Suitability",
        "",
        f"Target: {summary.job_role}",
        f"Suitability: {summary.suitability_percentage:.2f}%",
        f"Matched skills: {summary.matched_skill_count} of {summary.target_skill_count}",
        f"Gap skills: {summary.gap_skill_count}",
        f"Formula inputs: covered={summary.weighted_covered_level:.2f}, target={summary.weighted_target_level:.2f}, gap_cost={summary.gap_cost:.2f}",
        "All parser stretch skill weights remain 1.0.",
        "",
        "## Extracted Resume Evidence",
        "",
        _markdown_table(top_resume),
        "",
        "## Extracted JD Requirements",
        "",
        _markdown_table(top_jd),
        "",
        "## Priority Gaps",
        "",
        _markdown_table(top_gaps),
        "",
        "## Action Plan",
        "",
        _markdown_table(actions),
        "",
    ]
    return "\n".join(lines)




def _markdown_table(frame) -> str:
    if frame.empty:
        return "No rows."
    columns = list(frame.columns)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in frame.itertuples(index=False):
        values = []
        for value in row:
            cell = str(value).replace("\n", " ").replace("|", "/")
            values.append(cell[:180])
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)
if __name__ == "__main__":
    raise SystemExit(main())
