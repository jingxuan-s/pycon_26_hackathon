"""Deterministic skill suitability and gap scoring for the jobs-skills MVP."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd


@dataclass(frozen=True)
class ScoringPaths:
    project_root: Path
    processed_dir: Path

    @classmethod
    def from_project_root(cls, project_root: Path, processed_dir: Path = Path("data/processed")) -> "ScoringPaths":
        root = project_root.resolve()
        return cls(
            project_root=root,
            processed_dir=(root / processed_dir).resolve() if not processed_dir.is_absolute() else processed_dir.resolve(),
        )


@dataclass(frozen=True)
class SkillWeightPolicy:
    """Optional future weighting policy.

    MVP scoring leaves all values at 1.0. Non-default values should only be used
    when role owners have a documented core / important / supporting method.
    """

    core: float = 1.0
    important: float = 1.0
    supporting: float = 1.0

    def multiplier_for_tier(self, tier: str) -> float:
        normalized = tier.strip().casefold()
        if normalized == "core":
            return float(self.core)
        if normalized == "important":
            return float(self.important)
        if normalized == "supporting":
            return float(self.supporting)
        raise ValueError(f"Unknown skill weight tier: {tier!r}")

@dataclass(frozen=True)
class FitSummary:
    role_id: str
    sector: str
    track: str
    job_role: str
    target_skill_count: int
    matched_skill_count: int
    gap_skill_count: int
    weighted_covered_level: float
    weighted_target_level: float
    gap_cost: float
    suitability: float

    @property
    def suitability_percentage(self) -> float:
        return self.suitability * 100.0


def load_role_skill_requirements(processed_dir: Path) -> pd.DataFrame:
    path = processed_dir / "role_skill_requirements.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing role-skill requirements file: {path}")
    frame = pd.read_csv(path, low_memory=False)
    numeric_cols = ["required_level", "skill_weight"]
    for col in numeric_cols:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame


def select_role_id(
    requirements: pd.DataFrame,
    job_role: str,
    sector: str | None = None,
    track: str | None = None,
) -> str:
    mask = requirements["job_role"].str.casefold().eq(job_role.casefold())
    if sector is not None:
        mask &= requirements["sector"].str.casefold().eq(sector.casefold())
    if track is not None:
        mask &= requirements["track"].str.casefold().eq(track.casefold())

    matches = requirements.loc[mask, ["role_id", "sector", "track", "job_role"]].drop_duplicates()
    if matches.empty:
        raise ValueError(f"No role found for job_role={job_role!r}, sector={sector!r}, track={track!r}")
    if len(matches) > 1:
        details = matches.sort_values(["sector", "track", "job_role"]).to_dict(orient="records")
        raise ValueError(f"Role selection is ambiguous: {details}")
    return str(matches.iloc[0]["role_id"])


def get_role_requirements(requirements: pd.DataFrame, role_id: str) -> pd.DataFrame:
    role_rows = requirements.loc[requirements["role_id"].eq(role_id)].copy()
    if role_rows.empty:
        raise ValueError(f"No requirements found for role_id={role_id!r}")
    return role_rows.sort_values(["required_level", "unique_skill_title", "skill_id"]).reset_index(drop=True)


def build_user_vector_from_role(requirements: pd.DataFrame, role_id: str) -> dict[str, float]:
    role_rows = get_role_requirements(requirements, role_id)
    return dict(zip(role_rows["skill_id"], role_rows["required_level"].astype(float)))


def score_role_fit(user_vector: Mapping[str, float], target_requirements: pd.DataFrame) -> tuple[FitSummary, pd.DataFrame]:
    target = target_requirements.copy().reset_index(drop=True)
    target["target_level"] = pd.to_numeric(target["required_level"], errors="coerce").fillna(0.0)
    target["current_level"] = target["skill_id"].map(user_vector).fillna(0.0).astype(float)
    target["skill_weight"] = pd.to_numeric(target["skill_weight"], errors="coerce").fillna(1.0)
    target["covered_level"] = target[["current_level", "target_level"]].min(axis=1)
    target["gap"] = (target["target_level"] - target["current_level"]).clip(lower=0.0)
    target["weighted_covered_level"] = target["skill_weight"] * target["covered_level"]
    target["weighted_target_level"] = target["skill_weight"] * target["target_level"]
    target["weighted_gap"] = target["skill_weight"] * target["gap"]
    target["is_matched"] = target["covered_level"] > 0
    target["has_gap"] = target["gap"] > 0

    weighted_target = float(target["weighted_target_level"].sum())
    weighted_covered = float(target["weighted_covered_level"].sum())
    suitability = weighted_covered / weighted_target if weighted_target else 0.0

    first = target.iloc[0]
    summary = FitSummary(
        role_id=str(first["role_id"]),
        sector=str(first["sector"]),
        track=str(first["track"]),
        job_role=str(first["job_role"]),
        target_skill_count=int(len(target)),
        matched_skill_count=int(target["is_matched"].sum()),
        gap_skill_count=int(target["has_gap"].sum()),
        weighted_covered_level=weighted_covered,
        weighted_target_level=weighted_target,
        gap_cost=float(target["weighted_gap"].sum()),
        suitability=suitability,
    )

    columns = [
        "role_skill_requirement_id",
        "skill_id",
        "unique_skill_title",
        "unique_skill_description",
        "current_level",
        "target_level",
        "gap",
        "skill_weight",
        "weighted_gap",
        "covered_level",
        "tsc_ccs_code",
        "tsc_ccs_title",
        "proficiency_description",
        "source_file",
        "source_sheet",
        "source_row_number",
        "parser_mapping_type",
        "parser_confidence",
        "parser_evidence",
        "parser_reason",
        "parser_uncertainty_flag",
        "parser_matched_phrase",
    ]
    columns = [column for column in columns if column in target.columns]
    gap_table = target[columns].sort_values(
        ["gap", "target_level", "unique_skill_title"], ascending=[False, False, True]
    ).reset_index(drop=True)
    return summary, gap_table



def apply_skill_weight_policy(
    requirements: pd.DataFrame,
    skill_tiers: Mapping[str, str],
    policy: SkillWeightPolicy | None = None,
) -> pd.DataFrame:
    """Return requirements with visible optional skill weights applied.

    `skill_tiers` may be keyed by `skill_id` or `unique_skill_title`. The MVP
    default policy keeps every tier at 1.0, so tagging can be introduced before
    differentiated multipliers are activated.
    """
    selected_policy = policy or SkillWeightPolicy()
    weighted = requirements.copy()
    weighted["skill_weight"] = pd.to_numeric(weighted["skill_weight"], errors="coerce").fillna(1.0)
    if not skill_tiers:
        return weighted

    def row_weight(row: pd.Series) -> float:
        tier = skill_tiers.get(str(row.skill_id)) or skill_tiers.get(str(row.unique_skill_title))
        if tier is None:
            return float(row.skill_weight)
        return selected_policy.multiplier_for_tier(tier)

    weighted["skill_weight"] = weighted.apply(row_weight, axis=1)
    return weighted


def skill_weight_policy_rows(policy: SkillWeightPolicy | None = None) -> pd.DataFrame:
    selected_policy = policy or SkillWeightPolicy()
    return pd.DataFrame([{"tier": tier, "multiplier": value} for tier, value in asdict(selected_policy).items()])


def nearest_role_neighbors_l1(
    requirements: pd.DataFrame,
    user_vector: Mapping[str, float],
    exclude_role_ids: Iterable[str] = (),
    limit: int = 20,
    min_shared_skill_count: int = 0,
) -> pd.DataFrame:
    """Return nearest role vectors using weighted L1 distance over sparse skills.

    This is a discovery metric for Explore pathways only. It does not replace
    target-aware suitability scoring.
    """
    excluded = {str(role_id) for role_id in exclude_role_ids if role_id}
    target = requirements.loc[~requirements["role_id"].astype(str).isin(excluded)].copy()
    if target.empty:
        return pd.DataFrame(columns=["role_id", "vector_distance", "shared_skill_count", "compared_skill_count"])

    user_levels = {str(skill_id): float(level) for skill_id, level in user_vector.items() if float(level) != 0.0}
    user_skill_count = len(user_levels)
    user_level_total = float(sum(abs(level) for level in user_levels.values()))

    target["target_level"] = pd.to_numeric(target["required_level"], errors="coerce").fillna(0.0)
    target["skill_weight"] = pd.to_numeric(target["skill_weight"], errors="coerce").fillna(1.0)
    target["skill_id"] = target["skill_id"].astype(str)
    target["current_level"] = target["skill_id"].map(user_levels).fillna(0.0).astype(float)
    target["weighted_abs_diff"] = target["skill_weight"] * (target["current_level"] - target["target_level"]).abs()
    target["shared_user_level"] = target.apply(
        lambda row: abs(float(row.current_level)) if str(row.skill_id) in user_levels else 0.0,
        axis=1,
    )
    target["is_shared_skill"] = target["skill_id"].isin(user_levels.keys())

    grouped = target.groupby("role_id", sort=False).agg(
        role_vector_distance=("weighted_abs_diff", "sum"),
        shared_user_level=("shared_user_level", "sum"),
        shared_skill_count=("is_shared_skill", "sum"),
        target_skill_count=("skill_id", "size"),
    ).reset_index()
    grouped["vector_distance"] = grouped["role_vector_distance"] + (user_level_total - grouped["shared_user_level"])
    grouped["compared_skill_count"] = grouped["target_skill_count"] + user_skill_count - grouped["shared_skill_count"]
    if min_shared_skill_count > 0:
        grouped = grouped.loc[grouped["shared_skill_count"].ge(int(min_shared_skill_count))].copy()
    if grouped.empty:
        return pd.DataFrame(columns=["role_id", "vector_distance", "shared_skill_count", "compared_skill_count"])

    return grouped[
        ["role_id", "vector_distance", "shared_skill_count", "compared_skill_count"]
    ].sort_values(
        ["vector_distance", "shared_skill_count", "role_id"],
        ascending=[True, False, True],
    ).head(limit).reset_index(drop=True)


def score_all_roles(
    requirements: pd.DataFrame,
    user_vector: Mapping[str, float],
    exclude_role_ids: Iterable[str] = (),
) -> pd.DataFrame:
    """Score all dataset roles with vectorized deterministic M2 logic."""
    excluded = {str(role_id) for role_id in exclude_role_ids if role_id}
    target = requirements.loc[~requirements["role_id"].astype(str).isin(excluded)].copy()
    if target.empty:
        return pd.DataFrame(
            columns=[
                "role_id",
                "sector",
                "track",
                "job_role",
                "suitability",
                "suitability_percentage",
                "gap_cost",
                "matched_skill_count",
                "gap_skill_count",
                "target_skill_count",
            ]
        )

    target["target_level"] = pd.to_numeric(target["required_level"], errors="coerce").fillna(0.0)
    target["current_level"] = target["skill_id"].map(user_vector).fillna(0.0).astype(float)
    target["skill_weight"] = pd.to_numeric(target["skill_weight"], errors="coerce").fillna(1.0)
    target["covered_level"] = target[["current_level", "target_level"]].min(axis=1)
    target["gap"] = (target["target_level"] - target["current_level"]).clip(lower=0.0)
    target["weighted_covered_level"] = target["skill_weight"] * target["covered_level"]
    target["weighted_target_level"] = target["skill_weight"] * target["target_level"]
    target["weighted_gap"] = target["skill_weight"] * target["gap"]
    target["is_matched"] = target["covered_level"].gt(0)
    target["has_gap"] = target["gap"].gt(0)

    grouped = target.groupby("role_id", sort=False).agg(
        weighted_covered_level=("weighted_covered_level", "sum"),
        weighted_target_level=("weighted_target_level", "sum"),
        gap_cost=("weighted_gap", "sum"),
        matched_skill_count=("is_matched", "sum"),
        gap_skill_count=("has_gap", "sum"),
        target_skill_count=("skill_id", "size"),
    ).reset_index()
    grouped["suitability"] = grouped.apply(
        lambda row: float(row.weighted_covered_level) / float(row.weighted_target_level)
        if float(row.weighted_target_level) else 0.0,
        axis=1,
    )
    grouped["suitability_percentage"] = grouped["suitability"] * 100.0

    catalog = requirements[["role_id", "sector", "track", "job_role"]].drop_duplicates(subset=["role_id"])
    rows = grouped.merge(catalog, on="role_id", how="left")
    return rows[
        [
            "role_id",
            "sector",
            "track",
            "job_role",
            "suitability",
            "suitability_percentage",
            "gap_cost",
            "matched_skill_count",
            "gap_skill_count",
            "target_skill_count",
        ]
    ].sort_values(
        ["suitability", "gap_cost", "matched_skill_count", "job_role"],
        ascending=[False, True, False, True],
    ).reset_index(drop=True)


