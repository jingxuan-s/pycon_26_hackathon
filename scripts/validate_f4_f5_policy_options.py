"""Validate optional F4/F5 weighting and sector-constraint methodology hooks."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from jobs_skills.pathway_graph import (
    SECTOR_MODE_OPEN_MOBILITY,
    SECTOR_MODE_PREFER_SAME_SECTOR,
    SECTOR_MODE_RESTRICT_SAME_SECTOR,
    build_transition_edge,
    pathway_policy_for_sector_mode,
    policy_as_rows,
)
from jobs_skills.scoring import (
    SkillWeightPolicy,
    apply_skill_weight_policy,
    build_user_vector_from_role,
    get_role_requirements,
    load_role_skill_requirements,
    score_role_fit,
    select_role_id,
    skill_weight_policy_rows,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "data" / "processed" / "f4_f5_policy_options_demo.md"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    processed_dir = PROJECT_ROOT / "data" / "processed"
    requirements = load_role_skill_requirements(processed_dir)

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

    target_requirements = get_role_requirements(requirements, target_role_id)
    user_vector = build_user_vector_from_role(requirements, current_role_id)
    baseline_summary, baseline_gaps = score_role_fit(user_vector, target_requirements)
    require(baseline_gaps["skill_weight"].eq(1.0).all(), "MVP role requirements must keep default skill weights at 1.0")

    tagged = {"Programming and Coding": "core", "Data Governance": "important"}
    default_weighted = apply_skill_weight_policy(target_requirements, tagged, SkillWeightPolicy())
    require(default_weighted["skill_weight"].eq(1.0).all(), "Default policy must keep all tagged skill weights at 1.0")

    future_policy = SkillWeightPolicy(core=1.5, important=1.2, supporting=1.0)
    future_weighted = apply_skill_weight_policy(target_requirements, tagged, future_policy)
    require(float(future_weighted.loc[future_weighted["unique_skill_title"].eq("Programming and Coding"), "skill_weight"].iloc[0]) == 1.5, "Core skill multiplier must be visible when explicitly enabled")
    require(float(future_weighted.loc[future_weighted["unique_skill_title"].eq("Data Governance"), "skill_weight"].iloc[0]) == 1.2, "Important skill multiplier must be visible when explicitly enabled")
    future_summary, future_gaps = score_role_fit(user_vector, future_weighted)
    require("skill_weight" in future_gaps.columns, "Weighted gap table must expose skill weights")
    require(future_summary.weighted_target_level > baseline_summary.weighted_target_level, "Future non-default weighting should alter weighted target level only when enabled")

    open_policy = pathway_policy_for_sector_mode(SECTOR_MODE_OPEN_MOBILITY)
    prefer_policy = pathway_policy_for_sector_mode(SECTOR_MODE_PREFER_SAME_SECTOR)
    restrict_policy = pathway_policy_for_sector_mode(SECTOR_MODE_RESTRICT_SAME_SECTOR)
    same_open = build_transition_edge(requirements, current_role_id, target_role_id, open_policy)
    same_prefer = build_transition_edge(requirements, current_role_id, target_role_id, prefer_policy)
    require(same_prefer["edge_weight"] < same_open["edge_weight"], "Prefer-same-sector mode should reward same-sector pathways")

    ranked_cross = requirements.loc[requirements["sector"].ne("Financial Services"), ["role_id"]].drop_duplicates()
    require(not ranked_cross.empty, "Need at least one cross-sector role to validate restrict mode")
    cross_role_id = str(ranked_cross.iloc[0]["role_id"])
    cross_open = build_transition_edge(requirements, current_role_id, cross_role_id, open_policy)
    cross_restrict = build_transition_edge(requirements, current_role_id, cross_role_id, restrict_policy)
    require(cross_open["edge_weight"] < float("inf"), "Open mobility should allow cross-sector edges")
    require(cross_restrict["edge_weight"] == float("inf"), "Restrict-same-sector mode should block cross-sector edges")

    REPORT_PATH.write_text(
        _render_report(
            baseline_summary,
            future_summary,
            tagged,
            skill_weight_policy_rows(future_policy),
            policy_as_rows(open_policy),
            policy_as_rows(prefer_policy),
            policy_as_rows(restrict_policy),
            same_open,
            same_prefer,
            cross_open,
            cross_restrict,
        ),
        encoding="utf-8",
    )
    report_text = REPORT_PATH.read_text(encoding="utf-8")
    for phrase in ["Skill Weighting", "Sector Constraint Modes", "open_mobility", "prefer_same_sector", "restrict_same_sector"]:
        require(phrase in report_text, f"Report missing phrase: {phrase}")

    print("F4-F5 policy validation passed")
    print(f"baseline_suitability={baseline_summary.suitability_percentage:.2f}")
    print(f"future_weighted_suitability={future_summary.suitability_percentage:.2f}")
    print(f"same_sector_open_weight={same_open['edge_weight']:.4f}")
    print(f"same_sector_prefer_weight={same_prefer['edge_weight']:.4f}")
    print(f"cross_sector_restrict_weight={cross_restrict['edge_weight']}")
    print(f"output={REPORT_PATH}")
    return 0


def _render_report(
    baseline_summary,
    future_summary,
    tagged: dict[str, str],
    weight_policy_rows: pd.DataFrame,
    open_policy_rows: pd.DataFrame,
    prefer_policy_rows: pd.DataFrame,
    restrict_policy_rows: pd.DataFrame,
    same_open: dict[str, object],
    same_prefer: dict[str, object],
    cross_open: dict[str, object],
    cross_restrict: dict[str, object],
) -> str:
    tagged_rows = pd.DataFrame([{"skill": skill, "tier": tier, "mvp_multiplier": 1.0} for skill, tier in tagged.items()])
    edge_rows = pd.DataFrame(
        [
            {"mode": "open_mobility", "edge": "same sector", "edge_weight": same_open["edge_weight"], "allowed": same_open["edge_weight"] < float("inf")},
            {"mode": "prefer_same_sector", "edge": "same sector", "edge_weight": same_prefer["edge_weight"], "allowed": same_prefer["edge_weight"] < float("inf")},
            {"mode": "open_mobility", "edge": "cross sector", "edge_weight": cross_open["edge_weight"], "allowed": cross_open["edge_weight"] < float("inf")},
            {"mode": "restrict_same_sector", "edge": "cross sector", "edge_weight": cross_restrict["edge_weight"], "allowed": cross_restrict["edge_weight"] < float("inf")},
        ]
    )
    lines = [
        "# F4-F5 Policy Options Demo",
        "",
        "## Skill Weighting",
        "",
        "MVP weighting remains 1.0 for every skill. The helper below only makes future core / important / supporting tags explicit and auditable when a non-default methodology is approved.",
        "",
        _markdown_table(tagged_rows),
        "",
        "Future non-default example policy, not active in MVP scoring:",
        "",
        _markdown_table(weight_policy_rows),
        "",
        f"Baseline suitability with MVP weights: {baseline_summary.suitability_percentage:.2f}%",
        f"Future weighted example suitability: {future_summary.suitability_percentage:.2f}%",
        "",
        "## Sector Constraint Modes",
        "",
        "Sector is treated as pathway metadata and graph policy, not as a skill-vector dimension.",
        "",
        "### open_mobility",
        _markdown_table(open_policy_rows),
        "",
        "### prefer_same_sector",
        _markdown_table(prefer_policy_rows),
        "",
        "### restrict_same_sector",
        _markdown_table(restrict_policy_rows),
        "",
        "## Edge Examples",
        "",
        _markdown_table(edge_rows),
        "",
    ]
    return "\n".join(lines)


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "No rows."
    columns = list(frame.columns)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in frame.itertuples(index=False):
        values = [str(value).replace("\n", " ").replace("|", "/")[:180] for value in row]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
