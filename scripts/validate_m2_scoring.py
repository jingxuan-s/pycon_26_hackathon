"""Validate M2 deterministic scoring acceptance checks."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jobs_skills.scoring import (
    ScoringPaths,
    build_user_vector_from_role,
    get_role_requirements,
    load_role_skill_requirements,
    nearest_role_neighbors_l1,
    score_all_roles,
    score_role_fit,
    select_role_id,
)


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
    target_role_id = select_role_id(
        requirements,
        job_role="Data Scientist",
        sector="Financial Services",
        track="Digital and Data Analytics",
    )

    user_vector = build_user_vector_from_role(requirements, current_role_id)
    target_requirements = get_role_requirements(requirements, target_role_id)

    summary_a, gap_table_a = score_role_fit(user_vector, target_requirements)
    summary_b, gap_table_b = score_role_fit(user_vector, target_requirements)

    require(summary_a == summary_b, "Same inputs must produce the same summary")
    require(gap_table_a.equals(gap_table_b), "Same inputs must produce the same gap table")
    require(summary_a.suitability > 0, "Data Analyst to Data Scientist score should be non-zero")
    require(summary_a.suitability < 1, "Data Analyst to Data Scientist score should expose remaining gaps")
    require(summary_a.gap_skill_count > 0, "Data Analyst to Data Scientist example should produce gaps")

    manual_covered = float((gap_table_a["skill_weight"] * gap_table_a["covered_level"]).sum())
    manual_target = float((gap_table_a["skill_weight"] * gap_table_a["target_level"]).sum())
    manual_score = manual_covered / manual_target
    require(abs(manual_score - summary_a.suitability) < 1e-12, "Score must recompute from visible values")

    required_gap_cols = [
        "unique_skill_title",
        "current_level",
        "target_level",
        "gap",
        "tsc_ccs_code",
        "source_row_number",
    ]
    for col in required_gap_cols:
        require(col in gap_table_a.columns, f"Gap table missing explainability column: {col}")

    top_gaps = gap_table_a.loc[gap_table_a["gap"] > 0].head(10)
    require(not top_gaps.empty, "Top gaps must be available")
    require(top_gaps["gap"].is_monotonic_decreasing, "Top gaps must be sorted by gap size")

    rankings = score_all_roles(requirements, user_vector, exclude_role_ids={current_role_id})
    require(len(rankings) > 0, "Role ranking must return candidate roles")
    require(current_role_id not in set(rankings["role_id"]), "Current role must be excluded from ranking")
    require(rankings["suitability"].is_monotonic_decreasing, "Role ranking must sort by suitability first")

    synthetic_requirements = pd.DataFrame([
        {"role_id": "same", "sector": "Synthetic", "track": "Synthetic", "job_role": "Same", "skill_id": "s1", "unique_skill_title": "Skill One", "required_level": 2.0, "skill_weight": 1.0},
        {"role_id": "missing", "sector": "Synthetic", "track": "Synthetic", "job_role": "Missing", "skill_id": "s2", "unique_skill_title": "Skill Two", "required_level": 2.0, "skill_weight": 1.0},
        {"role_id": "over", "sector": "Synthetic", "track": "Synthetic", "job_role": "Over", "skill_id": "s1", "unique_skill_title": "Skill One", "required_level": 4.0, "skill_weight": 1.0},
        {"role_id": "tie_a", "sector": "Synthetic", "track": "Synthetic", "job_role": "Tie A", "skill_id": "s1", "unique_skill_title": "Skill One", "required_level": 3.0, "skill_weight": 1.0},
        {"role_id": "tie_b", "sector": "Synthetic", "track": "Synthetic", "job_role": "Tie B", "skill_id": "s2", "unique_skill_title": "Skill Two", "required_level": 1.0, "skill_weight": 1.0},
    ])
    nearest = nearest_role_neighbors_l1(synthetic_requirements, {"s1": 2.0}, limit=5)
    same = nearest.loc[nearest["role_id"].eq("same")].iloc[0]
    missing = nearest.loc[nearest["role_id"].eq("missing")].iloc[0]
    over = nearest.loc[nearest["role_id"].eq("over")].iloc[0]
    require(float(same.vector_distance) == 0.0, "Identical vectors must have zero weighted L1 distance")
    require(float(missing.vector_distance) == 4.0, "Missing user and role skills must be compared as zero-valued dimensions")
    require(float(over.vector_distance) == 2.0, "Overqualification must contribute to discovery distance")
    over_summary, _ = score_role_fit({"s1": 4.0}, synthetic_requirements.loc[synthetic_requirements["role_id"].eq("same")])
    require(over_summary.suitability == 1.0, "Overqualification must not reduce target-aware suitability")
    require(list(nearest["vector_distance"]) == sorted(nearest["vector_distance"]), "Nearest-neighbour rows must sort by vector distance")
    shared_only = nearest_role_neighbors_l1(synthetic_requirements, {"s1": 2.0}, limit=5, min_shared_skill_count=1)
    require("missing" not in set(shared_only["role_id"]), "Shared-skill filter must remove zero-overlap roles")
    require(set(shared_only["shared_skill_count"]).issubset({1}), "Shared-skill filter should keep only roles with shared skills in fixture")
    limited = nearest_role_neighbors_l1(synthetic_requirements, {"s1": 2.0}, limit=2)
    require(len(limited) == 2, "Nearest-neighbour helper must respect the shortlist limit")

    report_path = paths.processed_dir / "m2_scoring_example.md"
    require(report_path.exists(), "M2 scoring example report must exist")
    report_text = report_path.read_text(encoding="utf-8")
    for phrase in [
        "Suitability Formula",
        "Top Priority Gaps",
        "Top Matched Skills",
        "Top 10 Role Ranking",
    ]:
        require(phrase in report_text, f"M2 report missing section: {phrase}")

    print("M2 validation passed")
    print(f"current_role_id={current_role_id}")
    print(f"target_role_id={target_role_id}")
    print(f"suitability_percentage={summary_a.suitability_percentage:.2f}")
    print(f"gap_cost={summary_a.gap_cost:.2f}")
    print(f"gap_rows={len(gap_table_a)}")
    print(f"ranked_roles={len(rankings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
