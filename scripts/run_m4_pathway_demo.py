"""Run the M4 pathway graph demo."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from jobs_skills.pathway_graph import (
    PathwayPolicy,
    derive_pathway_graph,
    derive_transition_edges,
    dijkstra_path,
    path_edges,
    pathway_fit_percentage,
    policy_as_rows,
)
from jobs_skills.scoring import ScoringPaths, load_role_skill_requirements, select_role_id


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


def main() -> int:
    paths = ScoringPaths.from_project_root(PROJECT_ROOT)
    requirements = load_role_skill_requirements(paths.processed_dir)
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

    source_edges = derive_transition_edges(
        requirements, current_role_id, policy, max_edges=8, include_role_ids={target_role_id}
    )
    graph = derive_pathway_graph(requirements, current_role_id, target_role_id, policy, max_edges_per_source=6)
    path, total_cost = dijkstra_path(graph, current_role_id, target_role_id)
    selected_path_edges = path_edges(graph, path)
    fit = pathway_fit_percentage(total_cost, len(selected_path_edges))

    report = [
        "# M4 Pathway Graph Demo - Data Analyst to Data Scientist",
        "",
        "## Scope",
        "",
        "- Pathways are inferred from role-skill requirements, not explicitly provided by the dataset.",
        "- Skill suitability remains the deterministic M2 score.",
        "- Pathway fit is a separate graph metric using configurable sector/track context multipliers.",
        "",
        "## Pathway Policy",
        "",
        frame_to_markdown(policy_as_rows(policy), ["setting", "value"]),
        "",
        "## Source Role Candidate Edges",
        "",
        frame_to_markdown(
            source_edges,
            [
                "target_job_role",
                "target_sector",
                "target_track",
                "skill_suitability_percentage",
                "skill_gap_cost",
                "skill_overlap_ratio",
                "edge_weight",
                "edge_fit_percentage",
                "edge_assumptions",
            ],
            limit=10,
        ),
        "",
        "## Dijkstra Selected Path",
        "",
        f"- Role-id path: {' -> '.join(path)}",
        f"- Total graph cost: {total_cost:.4f}",
        f"- Pathway fit: {fit:.2f}%",
        "",
        frame_to_markdown(
            selected_path_edges,
            [
                "source_job_role",
                "target_job_role",
                "skill_suitability_percentage",
                "skill_gap_cost",
                "edge_weight",
                "edge_fit_percentage",
                "priority_gap_titles",
                "edge_assumptions",
            ],
        ),
        "",
        "## Derived Local Graph Size",
        "",
        f"- Nodes touched: {len(set(graph['source_role_id']).union(set(graph['target_role_id'])))}",
        f"- Directed edges: {len(graph)}",
        "",
    ]

    output_path = paths.processed_dir / "m4_pathway_graph_demo.md"
    output_path.write_text("\n".join(report), encoding="utf-8")

    print(f"current_role_id={current_role_id}")
    print(f"target_role_id={target_role_id}")
    print(f"graph_edges={len(graph)}")
    print(f"path={' -> '.join(path)}")
    print(f"pathway_fit_percentage={fit:.2f}")
    print(f"output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
