"""Run the M2 deterministic scoring example."""

from __future__ import annotations

from pathlib import Path

from jobs_skills.scoring import (
    ScoringPaths,
    build_user_vector_from_role,
    get_role_requirements,
    load_role_skill_requirements,
    score_all_roles,
    score_role_fit,
    select_role_id,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def frame_to_markdown(rows: list[dict[str, object]], columns: list[str]) -> str:
    if not rows:
        return ""

    def cell(value: object) -> str:
        text = "" if value is None else str(value)
        return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")

    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(cell(row.get(col)) for col in columns) + " |")
    return "\n".join(lines)


def rounded_records(frame, columns: list[str], limit: int) -> list[dict[str, object]]:
    subset = frame.loc[:, columns].head(limit).copy()
    for col in subset.columns:
        if subset[col].dtype.kind in "fc":
            subset[col] = subset[col].round(2)
    return subset.to_dict(orient="records")


def main() -> int:
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

    user_vector = build_user_vector_from_role(requirements, current_role_id)
    target_requirements = get_role_requirements(requirements, target_role_id)
    summary, gap_table = score_role_fit(user_vector, target_requirements)
    rankings = score_all_roles(requirements, user_vector, exclude_role_ids={current_role_id}).head(10)

    top_gaps = gap_table.loc[gap_table["gap"] > 0]
    top_matches = gap_table.loc[gap_table["covered_level"] > 0].sort_values(
        ["covered_level", "target_level", "unique_skill_title"], ascending=[False, False, True]
    )

    report = [
        "# M2 Scoring Example - Data Analyst to Data Scientist",
        "",
        "## Scenario",
        "",
        "- Current profile: Financial Services / Digital and Data Analytics / Data Analyst",
        "- Target role: Financial Services / Digital and Data Analytics / Data Scientist",
        "- User vector source: current-role requirements from M1 normalized data",
        "- MVP skill weights: `1.0` for every skill",
        "",
        "## Suitability Formula",
        "",
        "```text",
        "covered_level = min(current_level, target_level)",
        "suitability = sum(skill_weight * covered_level) / sum(skill_weight * target_level)",
        "gap = max(target_level - current_level, 0)",
        "gap_cost = sum(skill_weight * gap)",
        "```",
        "",
        "## Result",
        "",
        f"- Suitability: {summary.suitability_percentage:.2f}%",
        f"- Weighted covered level: {summary.weighted_covered_level:.2f}",
        f"- Weighted target level: {summary.weighted_target_level:.2f}",
        f"- Gap cost: {summary.gap_cost:.2f}",
        f"- Matched target skills: {summary.matched_skill_count} / {summary.target_skill_count}",
        f"- Skills with gaps: {summary.gap_skill_count}",
        "",
        "## Top Priority Gaps",
        "",
        frame_to_markdown(
            rounded_records(
                top_gaps,
                ["unique_skill_title", "current_level", "target_level", "gap", "tsc_ccs_code", "source_row_number"],
                10,
            ),
            ["unique_skill_title", "current_level", "target_level", "gap", "tsc_ccs_code", "source_row_number"],
        ),
        "",
        "## Top Matched Skills",
        "",
        frame_to_markdown(
            rounded_records(
                top_matches,
                ["unique_skill_title", "current_level", "target_level", "gap", "tsc_ccs_code", "source_row_number"],
                10,
            ),
            ["unique_skill_title", "current_level", "target_level", "gap", "tsc_ccs_code", "source_row_number"],
        ),
        "",
        "## Top 10 Role Ranking From Current Vector",
        "",
        frame_to_markdown(
            rounded_records(
                rankings,
                [
                    "job_role",
                    "sector",
                    "track",
                    "suitability_percentage",
                    "gap_cost",
                    "matched_skill_count",
                    "target_skill_count",
                ],
                10,
            ),
            [
                "job_role",
                "sector",
                "track",
                "suitability_percentage",
                "gap_cost",
                "matched_skill_count",
                "target_skill_count",
            ],
        ),
        "",
    ]

    output_path = paths.processed_dir / "m2_scoring_example.md"
    output_path.write_text("\n".join(report), encoding="utf-8")

    print(f"current_role_id={current_role_id}")
    print(f"target_role_id={target_role_id}")
    print(f"suitability_percentage={summary.suitability_percentage:.2f}")
    print(f"gap_cost={summary.gap_cost:.2f}")
    print(f"output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
