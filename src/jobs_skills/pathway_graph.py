"""Inferred career pathway graph and pathway fit logic."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from heapq import heappop, heappush
from typing import Iterable, Mapping

import pandas as pd

from jobs_skills.scoring import build_user_vector_from_role, get_role_requirements, score_all_roles, score_role_fit


@dataclass(frozen=True)
class PathwayPolicy:
    allow_cross_sector: bool = True
    min_skill_overlap: float = 0.25
    max_gap_cost: float | None = None
    same_sector_multiplier: float = 1.00
    related_sector_multiplier: float = 1.15
    unrelated_sector_multiplier: float = 1.35
    same_track_multiplier: float = 0.85
    related_track_multiplier: float = 0.95
    unrelated_track_multiplier: float = 1.20
    low_overlap_penalty: float = 5.0
    missing_critical_skill_penalty: float = 0.0



SECTOR_MODE_OPEN_MOBILITY = "open_mobility"
SECTOR_MODE_PREFER_SAME_SECTOR = "prefer_same_sector"
SECTOR_MODE_RESTRICT_SAME_SECTOR = "restrict_same_sector"
SECTOR_CONSTRAINT_MODES = (
    SECTOR_MODE_OPEN_MOBILITY,
    SECTOR_MODE_PREFER_SAME_SECTOR,
    SECTOR_MODE_RESTRICT_SAME_SECTOR,
)


def pathway_policy_for_sector_mode(mode: str) -> PathwayPolicy:
    """Build an explicit pathway policy for the owner-selected sector toggle."""
    normalized = mode.strip().casefold().replace("-", "_").replace(" ", "_")
    if normalized == SECTOR_MODE_OPEN_MOBILITY:
        return PathwayPolicy(allow_cross_sector=True)
    if normalized == SECTOR_MODE_PREFER_SAME_SECTOR:
        return PathwayPolicy(
            allow_cross_sector=True,
            same_sector_multiplier=0.90,
            related_sector_multiplier=1.10,
            unrelated_sector_multiplier=1.60,
        )
    if normalized == SECTOR_MODE_RESTRICT_SAME_SECTOR:
        return PathwayPolicy(allow_cross_sector=False)
    allowed = ", ".join(SECTOR_CONSTRAINT_MODES)
    raise ValueError(f"Unknown sector constraint mode {mode!r}; expected one of: {allowed}")

def role_catalog(requirements: pd.DataFrame) -> pd.DataFrame:
    return requirements[["role_id", "sector", "track", "job_role"]].drop_duplicates().reset_index(drop=True)


def _role_row(catalog: pd.DataFrame, role_id: str) -> pd.Series:
    matches = catalog.loc[catalog["role_id"].eq(role_id)]
    if matches.empty:
        raise ValueError(f"No role found for role_id={role_id!r}")
    return matches.iloc[0]


def _sector_multiplier(source: pd.Series, target: pd.Series, policy: PathwayPolicy) -> tuple[float, str]:
    if source.sector == target.sector:
        return policy.same_sector_multiplier, "same sector"
    if not policy.allow_cross_sector:
        return float("inf"), "cross-sector blocked by policy"
    return policy.unrelated_sector_multiplier, "cross-sector friction"


def _track_multiplier(source: pd.Series, target: pd.Series, policy: PathwayPolicy) -> tuple[float, str]:
    if source.track == target.track:
        return policy.same_track_multiplier, "same track"
    if source.sector == target.sector:
        return policy.related_track_multiplier, "different track in same sector"
    return policy.unrelated_track_multiplier, "different track and sector"


def _edge_assumptions(
    source: pd.Series,
    target: pd.Series,
    sector_note: str,
    track_note: str,
    low_overlap_additive: float,
    policy: PathwayPolicy,
) -> str:
    assumptions = [
        "inferred pathway edge",
        "skill suitability from deterministic M2 scoring",
        f"sector context: {sector_note}",
        f"track context: {track_note}",
        "MVP skill weights all 1.0",
    ]
    if low_overlap_additive > 0:
        assumptions.append(f"low-overlap additive penalty {low_overlap_additive:.2f}")
    if policy.missing_critical_skill_penalty == 0:
        assumptions.append("critical-skill penalty inactive for MVP")
    return "; ".join(assumptions)


def build_transition_edge(
    requirements: pd.DataFrame,
    source_role_id: str,
    target_role_id: str,
    policy: PathwayPolicy,
) -> dict[str, object]:
    catalog = role_catalog(requirements)
    source = _role_row(catalog, source_role_id)
    target = _role_row(catalog, target_role_id)
    user_vector = build_user_vector_from_role(requirements, source_role_id)
    target_requirements = get_role_requirements(requirements, target_role_id)
    summary, gap_table = score_role_fit(user_vector, target_requirements)

    overlap_ratio = summary.matched_skill_count / summary.target_skill_count if summary.target_skill_count else 0.0
    base_skill_gap_cost = 1.0 - summary.suitability
    low_overlap_additive = max(policy.min_skill_overlap - overlap_ratio, 0.0) * policy.low_overlap_penalty
    sector_multiplier, sector_note = _sector_multiplier(source, target, policy)
    track_multiplier, track_note = _track_multiplier(source, target, policy)
    context_multiplier = sector_multiplier * track_multiplier
    edge_weight = (base_skill_gap_cost + low_overlap_additive + policy.missing_critical_skill_penalty) * context_multiplier

    if policy.max_gap_cost is not None and summary.gap_cost > policy.max_gap_cost:
        edge_weight = float("inf")

    priority_gaps = gap_table.loc[gap_table["gap"] > 0].head(5)
    priority_gap_titles = ", ".join(priority_gaps["unique_skill_title"].astype(str).tolist())

    return {
        "source_role_id": source_role_id,
        "source_job_role": source.job_role,
        "source_sector": source.sector,
        "source_track": source.track,
        "target_role_id": target_role_id,
        "target_job_role": target.job_role,
        "target_sector": target.sector,
        "target_track": target.track,
        "skill_suitability": summary.suitability,
        "skill_suitability_percentage": summary.suitability_percentage,
        "skill_gap_cost": summary.gap_cost,
        "skill_overlap_ratio": overlap_ratio,
        "matched_skill_count": summary.matched_skill_count,
        "target_skill_count": summary.target_skill_count,
        "base_skill_gap_cost": base_skill_gap_cost,
        "low_overlap_additive": low_overlap_additive,
        "sector_multiplier": sector_multiplier,
        "track_multiplier": track_multiplier,
        "context_multiplier": context_multiplier,
        "edge_weight": edge_weight,
        "edge_fit_percentage": 100.0 / (1.0 + edge_weight) if edge_weight != float("inf") else 0.0,
        "priority_gap_titles": priority_gap_titles,
        "edge_assumptions": _edge_assumptions(source, target, sector_note, track_note, low_overlap_additive, policy),
    }


def derive_transition_edges(
    requirements: pd.DataFrame,
    source_role_id: str,
    policy: PathwayPolicy,
    max_edges: int = 6,
    include_role_ids: Iterable[str] = (),
) -> pd.DataFrame:
    user_vector = build_user_vector_from_role(requirements, source_role_id)
    ranked = score_all_roles(requirements, user_vector, exclude_role_ids={source_role_id})
    if policy.max_gap_cost is not None:
        ranked = ranked.loc[ranked["gap_cost"] <= policy.max_gap_cost]
    ranked = ranked.loc[(ranked["matched_skill_count"] / ranked["target_skill_count"]) >= policy.min_skill_overlap]
    candidate_ids = ranked.head(max_edges)["role_id"].astype(str).tolist()
    for role_id in include_role_ids:
        if role_id != source_role_id and role_id not in candidate_ids:
            candidate_ids.append(str(role_id))

    edges = [build_transition_edge(requirements, source_role_id, target_role_id, policy) for target_role_id in candidate_ids]
    frame = pd.DataFrame(edges)
    if frame.empty:
        return frame
    return frame.loc[frame["edge_weight"] < float("inf")].sort_values(
        ["edge_weight", "skill_gap_cost", "target_job_role"], ascending=[True, True, True]
    ).reset_index(drop=True)


def derive_pathway_graph(
    requirements: pd.DataFrame,
    current_role_id: str,
    selected_target_role_id: str,
    policy: PathwayPolicy | None = None,
    max_edges_per_source: int = 6,
) -> pd.DataFrame:
    policy = policy or PathwayPolicy()
    first_edges = derive_transition_edges(
        requirements,
        current_role_id,
        policy,
        max_edges=max_edges_per_source,
        include_role_ids={selected_target_role_id},
    )
    source_ids = [role_id for role_id in first_edges["target_role_id"].astype(str).tolist() if role_id != selected_target_role_id]
    all_edges = [first_edges]
    for role_id in source_ids[:max_edges_per_source]:
        all_edges.append(
            derive_transition_edges(
                requirements,
                role_id,
                policy,
                max_edges=max_edges_per_source,
                include_role_ids={selected_target_role_id},
            )
        )
    graph = pd.concat(all_edges, ignore_index=True).drop_duplicates(subset=["source_role_id", "target_role_id"])
    return graph.sort_values(["source_role_id", "edge_weight", "target_job_role"]).reset_index(drop=True)


def dijkstra_path(edges: pd.DataFrame, source_role_id: str, target_role_id: str) -> tuple[list[str], float]:
    adjacency: dict[str, list[tuple[str, float]]] = {}
    for row in edges.itertuples(index=False):
        adjacency.setdefault(str(row.source_role_id), []).append((str(row.target_role_id), float(row.edge_weight)))

    heap: list[tuple[float, str, list[str]]] = [(0.0, source_role_id, [source_role_id])]
    visited: dict[str, float] = {}
    while heap:
        cost, role_id, path = heappop(heap)
        if role_id in visited and visited[role_id] <= cost:
            continue
        visited[role_id] = cost
        if role_id == target_role_id:
            return path, cost
        for next_role_id, edge_cost in adjacency.get(role_id, []):
            if next_role_id not in visited or cost + edge_cost < visited[next_role_id]:
                heappush(heap, (cost + edge_cost, next_role_id, path + [next_role_id]))
    raise ValueError(f"No pathway found from {source_role_id!r} to {target_role_id!r}")


def path_edges(edges: pd.DataFrame, path: list[str]) -> pd.DataFrame:
    pairs = list(zip(path, path[1:]))
    rows = []
    for source_role_id, target_role_id in pairs:
        match = edges.loc[edges["source_role_id"].eq(source_role_id) & edges["target_role_id"].eq(target_role_id)]
        if match.empty:
            raise ValueError(f"Missing edge for path step {source_role_id!r} -> {target_role_id!r}")
        rows.append(match.iloc[0])
    if not rows:
        return pd.DataFrame(columns=edges.columns)
    return pd.DataFrame(rows).reset_index(drop=True)


def pathway_fit_percentage(total_cost: float, step_count: int) -> float:
    if step_count <= 0:
        return 100.0
    average_cost = total_cost / step_count
    return 100.0 / (1.0 + average_cost)


def policy_as_rows(policy: PathwayPolicy) -> pd.DataFrame:
    return pd.DataFrame([{"setting": key, "value": value} for key, value in asdict(policy).items()])
