"""Explainability and action-plan helpers for the jobs-skills MVP."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_skill_ka_items(processed_dir: Path) -> pd.DataFrame:
    path = processed_dir / "skill_ka_items.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing skill K&A items file: {path}")
    frame = pd.read_csv(path, low_memory=False)
    frame["proficiency_level"] = pd.to_numeric(frame["proficiency_level"], errors="coerce")
    return frame


def select_ka_evidence(
    ka_items: pd.DataFrame,
    skill_id: str,
    current_level: float,
    target_level: float,
    limit: int = 3,
) -> pd.DataFrame:
    skill_rows = ka_items.loc[ka_items["skill_id"].eq(skill_id)].copy()
    if skill_rows.empty:
        return skill_rows

    target_rows = skill_rows.loc[skill_rows["proficiency_level"].eq(float(target_level))]
    if target_rows.empty:
        target_rows = skill_rows.loc[
            skill_rows["proficiency_level"].gt(float(current_level))
            & skill_rows["proficiency_level"].le(float(target_level))
        ]
    if target_rows.empty:
        target_rows = skill_rows.sort_values("proficiency_level", ascending=False)

    return target_rows.sort_values(["proficiency_level", "ka_classification", "source_row_number"]).head(limit)


def build_action_plan(gap_table: pd.DataFrame, ka_items: pd.DataFrame, max_actions: int = 5) -> pd.DataFrame:
    gaps = gap_table.loc[gap_table["gap"] > 0].head(max_actions).copy()
    rows: list[dict[str, object]] = []
    for gap in gaps.itertuples(index=False):
        evidence = select_ka_evidence(
            ka_items,
            skill_id=str(gap.skill_id),
            current_level=float(gap.current_level),
            target_level=float(gap.target_level),
            limit=1,
        )
        if evidence.empty:
            action = f"Build evidence for {gap.unique_skill_title} from level {gap.current_level:g} to {gap.target_level:g}."
            ka_classification = "fallback"
            ka_source_row = ""
            ka_level = gap.target_level
            ka_item = ""
            proficiency_description = getattr(gap, "proficiency_description", "")
        else:
            item = evidence.iloc[0]
            action = f"Practise and document evidence for: {item.ka_item}"
            ka_classification = item.ka_classification
            ka_source_row = int(item.source_row_number)
            ka_level = float(item.proficiency_level)
            ka_item = str(item.ka_item)
            proficiency_description = str(getattr(item, "proficiency_description", ""))

        rows.append(
            {
                "skill_id": gap.skill_id,
                "skill": gap.unique_skill_title,
                "current_level": float(gap.current_level),
                "target_level": float(gap.target_level),
                "gap": float(gap.gap),
                "why_it_matters": "Required by the selected target role.",
                "next_action": action,
                "practical_action": _practical_action(str(gap.unique_skill_title), float(gap.current_level), float(gap.target_level), ka_item),
                "evidence_to_build": _evidence_to_build(str(gap.unique_skill_title), float(gap.target_level)),
                "ka_item": ka_item,
                "ka_classification": ka_classification,
                "ka_level": ka_level,
                "ka_source_row_number": ka_source_row,
                "role_skill_source_row_number": int(gap.source_row_number),
                "tsc_ccs_code": gap.tsc_ccs_code,
                "proficiency_description": proficiency_description,
            }
        )
    return pd.DataFrame(rows)


def _practical_action(skill: str, current_level: float, target_level: float, ka_item: str) -> str:
    if ka_item:
        return (
            f"Create a small work or portfolio task that demonstrates this ability: {ka_item}. "
            f"Aim to move from level {current_level:g} evidence to level {target_level:g} evidence."
        )
    return f"Create a project or workplace example that demonstrates {skill} at level {target_level:g}."


def _evidence_to_build(skill: str, target_level: float) -> str:
    return (
        f"Keep a short artifact for {skill}: problem statement, approach, output, and reflection showing level {target_level:g} ownership."
    )


def recommendation_reasons(recommendations: pd.DataFrame, selected_role_id: str) -> pd.DataFrame:
    reasons = recommendations.copy()
    reasons["why_recommended"] = reasons.apply(
        lambda row: (
            f"{row.job_role} was ranked from the baseline user vector with "
            f"{row.suitability_percentage:.2f}% skill suitability, "
            f"{row.matched_skill_count} matched skills, and gap cost {row.gap_cost:.2f}."
        ),
        axis=1,
    )
    reasons["selected"] = reasons["role_id"].eq(selected_role_id)
    return reasons


def score_explanation_text() -> str:
    return (
        "The score uses deterministic M2 logic: for every target-role skill, "
        "covered_level = min(current_level, target_level), gap = max(target_level - current_level, 0), "
        "and suitability = sum(skill_weight * covered_level) / sum(skill_weight * target_level). "
        "All MVP skill weights are 1.0. Missing user skills are treated as level 0 unless answered later."
    )
