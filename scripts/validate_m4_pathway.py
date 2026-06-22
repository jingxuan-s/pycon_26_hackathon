"""Validate M4 inferred pathway graph acceptance checks."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from jobs_skills.pathway_graph import (
    PathwayPolicy,
    build_transition_edge,
    derive_pathway_graph,
    derive_transition_edges,
    dijkstra_path,
    path_edges,
    pathway_fit_percentage,
)
from jobs_skills.scoring import build_user_vector_from_role, load_role_skill_requirements, score_all_roles, select_role_id


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    paths = PROJECT_ROOT / "data" / "processed"
    requirements = load_role_skill_requirements(paths)
    policy = PathwayPolicy()

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

    source_edges = derive_transition_edges(requirements, current_role_id, policy, max_edges=8, include_role_ids={target_role_id})
    require(len(source_edges) >= 3, "Source role must have multiple inferred candidate edges")
    require("edge_assumptions" in source_edges.columns, "Edges must expose assumptions")
    require(source_edges["edge_assumptions"].str.contains("inferred pathway edge", regex=False).all(), "Edges must be labelled inferred")
    require(source_edges["edge_assumptions"].str.contains("MVP skill weights all 1.0", regex=False).all(), "Edges must expose MVP weighting assumption")

    top_two = set(source_edges.head(2)["target_job_role"])
    require({"Data Engineer", "Data Scientist"}.issubset(top_two), "Same-track data pathways should rank first for Data Analyst")
    require(source_edges.head(2)["target_sector"].eq("Financial Services").all(), "Top pathways should remain in the same sector")
    require(source_edges.head(2)["target_track"].eq("Digital and Data Analytics").all(), "Top pathways should remain in the same track")

    data_scientist_edge = build_transition_edge(requirements, current_role_id, target_role_id, policy)
    user_vector = build_user_vector_from_role(requirements, current_role_id)
    ranked = score_all_roles(requirements, user_vector, exclude_role_ids={current_role_id})
    cross_sector = ranked.loc[ranked["sector"].ne("Financial Services")].head(20)
    require(not cross_sector.empty, "Need cross-sector candidates for sanity check")
    cross_edges = pd.DataFrame(
        [build_transition_edge(requirements, current_role_id, str(row.role_id), policy) for row in cross_sector.itertuples()]
    ).sort_values("edge_weight")
    best_cross_sector = cross_edges.iloc[0]
    require(
        data_scientist_edge["edge_weight"] < float(best_cross_sector["edge_weight"]),
        "Same-sector Data Scientist pathway should rank ahead of unrelated cross-sector low-requirement roles",
    )

    graph = derive_pathway_graph(requirements, current_role_id, target_role_id, policy, max_edges_per_source=6)
    require(len(graph) > 0, "Derived local graph must contain edges")
    path, total_cost = dijkstra_path(graph, current_role_id, target_role_id)
    selected_edges = path_edges(graph, path)
    fit = pathway_fit_percentage(total_cost, len(selected_edges))
    require(path[0] == current_role_id and path[-1] == target_role_id, "Dijkstra path must connect source to selected target")
    require(0 < fit <= 100, "Pathway fit percentage must be separate and bounded")
    require("skill_suitability_percentage" in selected_edges.columns, "Path edge must retain raw skill suitability")
    require("edge_fit_percentage" in selected_edges.columns, "Path edge must expose separate edge fit")
    require(
        not selected_edges["skill_suitability_percentage"].equals(selected_edges["edge_fit_percentage"]),
        "Pathway fit must be separate from skill suitability",
    )
    require(selected_edges["priority_gap_titles"].astype(str).str.len().gt(0).all(), "Path steps must identify priority skill gaps")

    report_path = paths / "m4_pathway_graph_demo.md"
    require(report_path.exists(), "M4 pathway graph demo report must exist")
    report_text = report_path.read_text(encoding="utf-8")
    for phrase in [
        "Pathway Policy",
        "Source Role Candidate Edges",
        "Dijkstra Selected Path",
        "Pathway fit",
        "edge_assumptions",
    ]:
        require(phrase in report_text, f"M4 report missing section: {phrase}")

    print("M4 validation passed")
    print(f"source_edges={len(source_edges)}")
    print(f"graph_edges={len(graph)}")
    print(f"path={' -> '.join(path)}")
    print(f"pathway_fit_percentage={fit:.2f}")
    print(f"best_cross_sector_role={best_cross_sector['target_job_role']}")
    print(f"data_scientist_edge_weight={data_scientist_edge['edge_weight']:.4f}")
    print(f"best_cross_sector_edge_weight={float(best_cross_sector['edge_weight']):.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
