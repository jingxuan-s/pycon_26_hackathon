"""Resume-first local workflow for career pathway recommendations.

This module turns runtime resume/JD text into reviewed skill profiles, then feeds
only confirmed skill levels into the deterministic scoring engine.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from difflib import SequenceMatcher
from datetime import datetime
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from jobs_skills.document_ingestion import ExtractedDocument, document_text_from_pasted_input, extract_text_from_file
from jobs_skills.explainability import build_action_plan, load_skill_ka_items, score_explanation_text
from jobs_skills.explainer_agent import (
    DEFAULT_EXPLAINER_MODEL,
    MODEL_ENV_NAMES,
    TOKEN_ENV_NAMES,
    ExplanationResult,
    load_explainer_agent_from_env,
)
from jobs_skills.related_skills import (
    RelatedSkillMatch,
    build_related_skill_notes,
    related_skill_debug_note,
    related_skill_normal_note,
)
from jobs_skills.parser_agents import (
    ParserResult,
    ParsedSkillEvidence,
    TITLE_ALIASES,
    build_target_requirements_from_jd,
    parse_jd_text,
    parse_resume_text,
)
from jobs_skills.pathway_graph import PathwayPolicy, build_transition_edge, role_catalog
from jobs_skills.scoring import (
    FitSummary,
    ScoringPaths,
    get_role_requirements,
    load_role_skill_requirements,
    nearest_role_neighbors_l1,
    score_all_roles,
    score_role_fit,
)


@dataclass(frozen=True)
class SkillProfileItem:
    skill_id: str
    unique_skill_title: str
    level: float
    confidence: float
    evidence: str
    reason: str
    source_section: str
    source_type: str
    mapping_type: str
    uncertainty_flag: bool


@dataclass(frozen=True)
class ReviewedSkillProfile:
    items: tuple[SkillProfileItem, ...]
    parser_source: str
    parser_notes: tuple[str, ...]

    def to_user_vector(self) -> dict[str, float]:
        vector: dict[str, float] = {}
        for item in self.items:
            vector[item.skill_id] = max(vector.get(item.skill_id, 0.0), float(item.level))
        return vector


@dataclass(frozen=True)
class ResumeWorkflowContext:
    project_root: Path
    paths: ScoringPaths
    requirements: pd.DataFrame
    skills: pd.DataFrame
    ka_items: pd.DataFrame


@dataclass(frozen=True)
class TargetModeResult:
    target_mode: str
    target_label: str
    recommendations: pd.DataFrame
    selected_summary: FitSummary
    selected_gap_table: pd.DataFrame
    action_plan: pd.DataFrame
    score_explanation: ExplanationResult
    pathway_edge: dict[str, object] | None
    parser_source: str
    parsed_target_requirements: pd.DataFrame | None = None
    report_path: Path | None = None


@dataclass(frozen=True)
class AgentParserConfig:
    enabled: bool
    source: str
    model: str

SKILLSFUTURE_INTERACTIVE_FRAMEWORKS_URL = "https://jobsandskills.skillsfuture.gov.sg/frameworks/interactive-skills-frameworks"


MANUAL_SKILL_SEARCH_ALIASES: Mapping[str, tuple[str, ...]] = {
    "Programming and Coding": (
        "software programming",
        "software development",
        "python programming",
        "sql queries",
        "javascript",
        "typescript",
        "java",
        "c sharp",
        "c#",
        "c++",
        "cpp",
    ),
    "Business Intelligence and Data Analytics": (
        "excel",
        "spreadsheet",
        "spreadsheets",
        "pivot table",
        "power query",
        "business intelligence",
    ),
    "Data Storytelling and Visualisation": (
        "power bi",
        "tableau",
        "looker",
        "charts",
        "dashboard",
        "dashboards",
    ),
    "Data Engineering": (
        "airflow",
        "dbt",
        "spark",
        "data warehouse",
        "data pipelines",
    ),
    "Cloud Computing Application": (
        "aws",
        "azure",
        "gcp",
        "cloud platform",
    ),
    "Cloud Computing Implementation": (
        "aws",
        "azure",
        "gcp",
        "cloud infrastructure",
    ),
    "Software Configuration": (
        "git",
        "github",
        "version control",
    ),
    "Agile Software Development": (
        "scrum",
        "jira",
        "kanban",
    ),
    "Data Protection Management": (
        "pdpa",
        "gdpr",
        "data privacy",
    ),
    "Infocomm Security and Data Privacy": (
        "pdpa",
        "gdpr",
        "data privacy",
        "privacy",
    ),
    "User Interface and User Experience (UI/UX) Optimisation": (
        "figma",
        "ui",
        "ux",
        "user interface",
        "user experience",
    ),
    "Database Administration": (
        "mysql",
        "postgres",
        "postgresql",
        "oracle database",
        "database",
    ),
    "Cybersecurity": (
        "cyber security",
        "security",
    ),
    "Artificial Intelligence Application": (
        "ai",
        "llm",
        "chatgpt",
    ),
}


def load_resume_workflow_context(project_root: Path) -> ResumeWorkflowContext:
    root = project_root.resolve()
    try:
        from dotenv import load_dotenv

        load_dotenv(root / ".env")
    except ImportError:
        pass
    paths = ScoringPaths.from_project_root(root)
    requirements = _with_skill_descriptions(load_role_skill_requirements(paths.processed_dir), paths.processed_dir)
    skills = pd.read_csv(paths.processed_dir / "skills.csv")
    ka_items = load_skill_ka_items(paths.processed_dir)
    return ResumeWorkflowContext(project_root=root, paths=paths, requirements=requirements, skills=skills, ka_items=ka_items)


def parse_resume_document(
    document: ExtractedDocument,
    context: ResumeWorkflowContext,
    max_skills: int = 20,
    use_agent: bool = True,
) -> ReviewedSkillProfile:
    parser_result, parser_source = _parse_with_optional_agent(
        text=document.text,
        skills=context.skills,
        document_kind="resume",
        max_skills=max_skills,
        use_agent=use_agent,
    )
    profile = parser_result_to_profile(parser_result, source_type=document.source_type, parser_source=parser_source, ka_items=context.ka_items)
    notes = tuple(parser_result.parser_notes) + tuple(document.extraction_notes)
    return replace(profile, parser_notes=notes)


def parse_resume_file(path: str | Path, context: ResumeWorkflowContext, max_skills: int = 20, use_agent: bool = True) -> ReviewedSkillProfile:
    return parse_resume_document(extract_text_from_file(path), context, max_skills=max_skills, use_agent=use_agent)


def parse_jd_document(
    document: ExtractedDocument,
    context: ResumeWorkflowContext,
    max_skills: int = 20,
    use_agent: bool = True,
) -> tuple[ParserResult, str]:
    parser_result, parser_source = _parse_with_optional_agent(
        text=document.text,
        skills=context.skills,
        document_kind="job_description",
        max_skills=max_skills,
        use_agent=use_agent,
    )
    parser_result = ParserResult(
        source_type=parser_result.source_type,
        extracted_skills=parser_result.extracted_skills,
        parser_notes=tuple(parser_result.parser_notes) + tuple(document.extraction_notes),
    )
    return parser_result, parser_source


def parser_result_to_profile(
    result: ParserResult,
    source_type: str,
    parser_source: str = "rule-based parser",
    ka_items: pd.DataFrame | None = None,
) -> ReviewedSkillProfile:
    items: list[SkillProfileItem] = []
    notes = list(result.parser_notes)
    for item in result.extracted_skills:
        evidence = _clean_evidence_text(item.evidence)
        weak_evidence = _is_weak_evidence(evidence, item.unique_skill_title)
        level, level_note = cap_level_to_skill_guidance(ka_items, item.skill_id, float(item.inferred_level), allow_zero=False)
        below_dataset_range = level_note is not None and level == float(item.inferred_level)
        if weak_evidence:
            notes.append(f"Weak evidence flagged for {item.unique_skill_title}; user review required before scoring.")
        if level_note:
            notes.append(f"{item.unique_skill_title} {level_note}")
        cleaned_reason = _clean_parser_reason(item.reason, item.unique_skill_title, evidence, weak_evidence)
        if level_note and level != float(item.inferred_level):
            cleaned_reason = f"{cleaned_reason} {level_note}"[:240]
        items.append(
            SkillProfileItem(
                skill_id=item.skill_id,
                unique_skill_title=item.unique_skill_title,
                level=float(level),
                confidence=min(float(item.confidence), 0.60) if weak_evidence else float(item.confidence),
                evidence=_snippet(evidence),
                reason=cleaned_reason,
                source_section=_infer_source_section(evidence, source_type),
                source_type=source_type,
                mapping_type=item.mapping_type,
                uncertainty_flag=bool(item.uncertainty_flag or weak_evidence or below_dataset_range),
            )
        )
    return ReviewedSkillProfile(items=tuple(items), parser_source=parser_source, parser_notes=tuple(notes))


def build_profile_from_role(context: ResumeWorkflowContext, role_id: str) -> ReviewedSkillProfile:
    role_requirements = get_role_requirements(context.requirements, role_id)
    role = role_requirements.iloc[0]
    items = tuple(
        SkillProfileItem(
            skill_id=str(row.skill_id),
            unique_skill_title=str(row.unique_skill_title),
            level=float(row.required_level),
            confidence=1.0,
            evidence=f"Dataset baseline for {role.job_role}: required level {float(row.required_level):g}.",
            reason="User chose this dataset role as the starting baseline.",
            source_section="dataset role baseline",
            source_type="selected_role",
            mapping_type="dataset_requirement",
            uncertainty_flag=False,
        )
        for row in role_requirements.itertuples(index=False)
    )
    notes = ("Profile was seeded from a selected dataset role; user review is still required before scoring.",)
    return ReviewedSkillProfile(items=items, parser_source="dataset role baseline", parser_notes=notes)


def edit_profile_level(
    profile: ReviewedSkillProfile,
    index: int,
    level: float,
    ka_items: pd.DataFrame | None = None,
) -> ReviewedSkillProfile:
    _validate_level(level)
    items = list(profile.items)
    if index < 0 or index >= len(items):
        raise IndexError(f"Profile item index out of range: {index}")
    item = items[index]
    selected_level, level_note = cap_level_to_skill_guidance(ka_items, item.skill_id, float(level), allow_zero=True)
    reason = f"User reviewed and set level {float(selected_level):g}. Original reason: {item.reason}"
    if level_note and selected_level != float(level):
        reason = f"{reason} {level_note}"[:240]
    items[index] = replace(
        item,
        level=float(selected_level),
        confidence=0.99,
        uncertainty_flag=False,
        reason=reason,
    )
    note = f"User edited {item.unique_skill_title} to level {float(selected_level):g}."
    if level_note:
        note = f"{note} {level_note}"
    notes = tuple(profile.parser_notes) + (note,)
    return ReviewedSkillProfile(items=tuple(items), parser_source=profile.parser_source, parser_notes=notes)


def remove_profile_item(profile: ReviewedSkillProfile, index: int) -> ReviewedSkillProfile:
    items = list(profile.items)
    if index < 0 or index >= len(items):
        raise IndexError(f"Profile item index out of range: {index}")
    removed = items.pop(index)
    notes = tuple(profile.parser_notes) + (f"User removed {removed.unique_skill_title} from the confirmed profile.",)
    return ReviewedSkillProfile(items=tuple(items), parser_source=profile.parser_source, parser_notes=notes)


def add_profile_skill(
    profile: ReviewedSkillProfile,
    skills: pd.DataFrame,
    skill_id: str,
    level: float,
    evidence: str = "User added this skill during review.",
    ka_items: pd.DataFrame | None = None,
) -> ReviewedSkillProfile:
    _validate_level(level)
    matches = skills.loc[skills["skill_id"].astype(str).eq(str(skill_id))]
    if matches.empty:
        raise ValueError(f"Unknown skill_id={skill_id!r}")
    row = matches.iloc[0]
    selected_level, level_note = cap_level_to_skill_guidance(ka_items, skill_id, float(level), allow_zero=True)
    reason = f"User added skill at level {float(selected_level):g} during mandatory review."
    if level_note and selected_level != float(level):
        reason = f"{reason} {level_note}"[:240]
    item = SkillProfileItem(
        skill_id=str(row.skill_id),
        unique_skill_title=str(row.unique_skill_title),
        level=float(selected_level),
        confidence=0.99,
        evidence=_snippet(evidence),
        reason=reason,
        source_section="manual review",
        source_type="user_added_skill",
        mapping_type="manual_dataset_skill",
        uncertainty_flag=False,
    )
    kept = [existing for existing in profile.items if existing.skill_id != item.skill_id]
    note = f"User added {item.unique_skill_title} at level {float(selected_level):g}."
    if level_note:
        note = f"{note} {level_note}"
    notes = tuple(profile.parser_notes) + (note,)
    return ReviewedSkillProfile(items=tuple(kept + [item]), parser_source=profile.parser_source, parser_notes=notes)


def search_skills(skills: pd.DataFrame, query: str, limit: int = 8) -> pd.DataFrame:
    query = query.strip()
    if not query:
        return skills.head(0)
    frame = skills.copy()
    normalized_query = _normalize_search_text(query)
    tokens = [token for token in normalized_query.split() if token]
    if not tokens:
        return skills.head(0)

    description = frame["unique_skill_description"].astype(str) if "unique_skill_description" in frame.columns else ""
    frame["normalized_title"] = frame["unique_skill_title"].astype(str).map(_normalize_search_text)
    frame["normalized_description"] = description.map(_normalize_search_text) if hasattr(description, "map") else ""
    frame["parser_alias_text"] = frame["unique_skill_title"].astype(str).map(_skill_search_parser_alias_text)
    frame["manual_alias_text"] = frame["unique_skill_title"].astype(str).map(_skill_search_manual_alias_text)
    frame["alias_text"] = (frame["parser_alias_text"].astype(str) + " " + frame["manual_alias_text"].astype(str)).str.strip()
    frame["search_text"] = (
        frame["normalized_title"].astype(str) + " "
        + frame["normalized_description"].astype(str) + " "
        + frame["alias_text"].astype(str)
    )

    frame = frame.loc[frame["search_text"].map(lambda text: all(_search_text_contains_phrase(str(text), token) for token in tokens))]
    if frame.empty:
        return frame.drop(columns=["search_text", "normalized_title", "normalized_description", "parser_alias_text", "manual_alias_text", "alias_text"], errors="ignore")

    frame["rank"] = frame.apply(lambda row: _skill_search_rank(row, normalized_query, tokens), axis=1)
    return frame.sort_values(["rank", "unique_skill_title"]).head(limit).drop(
        columns=["search_text", "normalized_title", "normalized_description", "parser_alias_text", "manual_alias_text", "alias_text", "rank"],
        errors="ignore",
    )

def _skill_search_parser_alias_text(title: str) -> str:
    return " ".join(dict.fromkeys(_normalize_search_text(alias) for alias in TITLE_ALIASES.get(title, ()) if alias))


def _skill_search_manual_alias_text(title: str) -> str:
    return " ".join(dict.fromkeys(_normalize_search_text(alias) for alias in MANUAL_SKILL_SEARCH_ALIASES.get(title, ()) if alias))


def _search_text_contains_phrase(text: str, phrase: str) -> bool:
    if not phrase:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text) is not None


def _skill_search_rank(row: Any, normalized_query: str, tokens: Sequence[str]) -> tuple[int, int]:
    title = str(row.normalized_title)
    description = str(row.normalized_description)
    parser_aliases = str(row.parser_alias_text)
    manual_aliases = str(row.manual_alias_text)
    aliases = str(row.alias_text)
    if title == normalized_query:
        return (0, 0)
    if _search_text_contains_phrase(manual_aliases, normalized_query):
        return (1, 0)
    if _search_text_contains_phrase(parser_aliases, normalized_query):
        return (2, 0)
    if _search_text_contains_phrase(title, normalized_query):
        return (3, 0)
    manual_token_matches = sum(1 for token in tokens if _search_text_contains_phrase(manual_aliases, token))
    if manual_token_matches:
        return (4, -manual_token_matches)
    alias_token_matches = sum(1 for token in tokens if _search_text_contains_phrase(aliases, token))
    if alias_token_matches:
        return (5, -alias_token_matches)
    if _search_text_contains_phrase(description, normalized_query):
        return (6, 0)
    return (7, 0)

def _normalize_search_text(text: str) -> str:
    normalized = _normalize_for_match(str(text))
    spelling_variants = {
        "modeling": "modelling",
        "visualization": "visualisation",
        "visualizations": "visualisations",
        "analyze": "analyse",
        "analyzing": "analysing",
        "optimization": "optimisation",
        "behavior": "behaviour",
    }
    for source, target in spelling_variants.items():
        normalized = re.sub(rf"\b{source}\b", target, normalized)
    return normalized


def search_roles(requirements: pd.DataFrame, query: str, limit: int = 8) -> pd.DataFrame:
    query = query.strip()
    if not query:
        return role_catalog(requirements).head(0)
    catalog = role_catalog(requirements).copy()
    tokens = [token for token in query.casefold().split() if token]
    catalog["search_text"] = (
        catalog["job_role"].astype(str) + " " + catalog["sector"].astype(str) + " " + catalog["track"].astype(str)
    ).str.casefold()
    for token in tokens:
        catalog = catalog.loc[catalog["search_text"].str.contains(token, regex=False, na=False)]
    if catalog.empty:
        return catalog.drop(columns=["search_text"], errors="ignore")
    query_text = query.casefold()
    catalog["rank"] = catalog.apply(
        lambda row: (
            0 if str(row.job_role).casefold() == query_text else
            1 if query_text in str(row.job_role).casefold() else
            2 if query_text in str(row.track).casefold() else
            3
        ),
        axis=1,
    )
    return catalog.sort_values(["rank", "job_role", "sector", "track"]).head(limit).drop(columns=["search_text", "rank"])


def recommend_explore_targets(
    context: ResumeWorkflowContext,
    profile: ReviewedSkillProfile,
    current_role_id: str | None = None,
    count: int = 3,
    diversify: bool = True,
    shortlist_size: int = 20,
    min_shared_skill_count: int = 2,
) -> pd.DataFrame:
    excluded = {current_role_id} if current_role_id else set()
    user_vector = profile.to_user_vector()
    neighbors = nearest_role_neighbors_l1(
        context.requirements,
        user_vector,
        exclude_role_ids=excluded,
        limit=shortlist_size,
        min_shared_skill_count=min_shared_skill_count,
    )
    if len(neighbors) < min(count, shortlist_size) and min_shared_skill_count > 1:
        relaxed_neighbors = nearest_role_neighbors_l1(
            context.requirements,
            user_vector,
            exclude_role_ids=excluded,
            limit=shortlist_size,
            min_shared_skill_count=1,
        )
        if len(relaxed_neighbors) > len(neighbors):
            neighbors = relaxed_neighbors
    if neighbors.empty:
        neighbors = nearest_role_neighbors_l1(
            context.requirements,
            user_vector,
            exclude_role_ids=excluded,
            limit=shortlist_size,
            min_shared_skill_count=0,
        )
    if neighbors.empty:
        return neighbors
    shortlist_ids = set(neighbors["role_id"].astype(str))
    shortlist_requirements = context.requirements.loc[context.requirements["role_id"].astype(str).isin(shortlist_ids)].copy()
    ranked = score_all_roles(shortlist_requirements, user_vector)
    ranked = ranked.merge(neighbors, on="role_id", how="left")
    ranked = ranked.sort_values(
        ["suitability", "gap_cost", "matched_skill_count", "vector_distance", "job_role"],
        ascending=[False, True, False, True, True],
    ).reset_index(drop=True)
    if diversify:
        ranked = diversify_role_families(ranked, count=count)
    return ranked.head(count).reset_index(drop=True)


def recommend_advance_targets(
    context: ResumeWorkflowContext,
    profile: ReviewedSkillProfile,
    current_role_id: str | None = None,
    count: int = 3,
    diversify: bool = True,
) -> pd.DataFrame:
    ranked = score_all_roles(context.requirements, profile.to_user_vector(), exclude_role_ids={current_role_id} if current_role_id else set())
    if current_role_id:
        catalog = role_catalog(context.requirements)
        current = catalog.loc[catalog["role_id"].eq(current_role_id)]
        if not current.empty:
            current_row = current.iloc[0]
            same_context = ranked.loc[
                ranked["sector"].eq(current_row.sector) | ranked["track"].eq(current_row.track)
            ].copy()
            if not same_context.empty:
                ranked = same_context
    advanced = ranked.loc[ranked["gap_cost"].gt(0)].copy()
    if advanced.empty:
        advanced = ranked.copy()
    advanced = advanced.sort_values(
        ["suitability", "gap_cost", "matched_skill_count", "job_role"],
        ascending=[False, True, False, True],
    )
    if diversify:
        advanced = diversify_role_families(advanced, count=count)
    return advanced.head(count).reset_index(drop=True)


def diversify_role_families(ranked: pd.DataFrame, count: int) -> pd.DataFrame:
    """Prefer one role per near-duplicate role family before showing variants."""
    if ranked.empty or "job_role" not in ranked.columns:
        return ranked
    ranked = ranked.copy().reset_index(drop=True)
    ranked["_family_key"] = ranked["job_role"].astype(str).map(_role_family_key)
    first_per_family = ranked.drop_duplicates(subset=["_family_key"], keep="first")
    if len(first_per_family) >= count:
        return first_per_family.drop(columns=["_family_key"]).reset_index(drop=True)
    selected_role_ids = set(first_per_family["role_id"].astype(str))
    remainder = ranked.loc[~ranked["role_id"].astype(str).isin(selected_role_ids)]
    combined = pd.concat([first_per_family, remainder], ignore_index=True)
    return combined.drop(columns=["_family_key"]).reset_index(drop=True)


def _role_family_key(job_role: str) -> str:
    normalized = job_role.casefold()
    normalized = re.sub(r"\([^)]*\)", "", normalized)
    normalized = normalized.replace("/", " ")
    normalized = re.sub(r"\b(senior|junior|associate|assistant|executive|manager|lead|principal)\b", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def build_target_result_for_role(
    context: ResumeWorkflowContext,
    profile: ReviewedSkillProfile,
    role_id: str,
    target_mode: str,
    recommendations: pd.DataFrame | None = None,
    current_role_id: str | None = None,
) -> TargetModeResult:
    target_requirements = get_role_requirements(context.requirements, role_id)
    summary, gap_table = score_role_fit(profile.to_user_vector(), target_requirements)
    action_plan = build_action_plan(gap_table, context.ka_items, max_actions=5)
    explainer = load_explainer_agent_from_env(context.project_root)
    score_explanation = explainer.explain_score(summary, gap_table)
    pathway_edge = None
    if current_role_id and current_role_id != role_id:
        try:
            pathway_edge = build_transition_edge(context.requirements, current_role_id, role_id, PathwayPolicy())
        except Exception as exc:
            pathway_edge = {"edge_error": f"Unable to build dataset pathway edge: {type(exc).__name__}: {str(exc)[:160]}"}
    if recommendations is None or recommendations.empty:
        recommendations = pd.DataFrame([
            {
                "role_id": summary.role_id,
                "sector": summary.sector,
                "track": summary.track,
                "job_role": summary.job_role,
                "suitability": summary.suitability,
                "suitability_percentage": summary.suitability_percentage,
                "gap_cost": summary.gap_cost,
                "matched_skill_count": summary.matched_skill_count,
                "gap_skill_count": summary.gap_skill_count,
                "target_skill_count": summary.target_skill_count,
            }
        ])
    return TargetModeResult(
        target_mode=target_mode,
        target_label=summary.job_role,
        recommendations=recommendations,
        selected_summary=summary,
        selected_gap_table=gap_table,
        action_plan=action_plan,
        score_explanation=score_explanation,
        pathway_edge=pathway_edge,
        parser_source=profile.parser_source,
        parsed_target_requirements=None,
    )


def build_target_result_for_jd(
    context: ResumeWorkflowContext,
    profile: ReviewedSkillProfile,
    jd_document: ExtractedDocument,
    role_label: str = "Parsed Job Description",
    use_agent: bool = True,
) -> TargetModeResult:
    jd_result, jd_parser_source = parse_jd_document(jd_document, context, use_agent=use_agent)
    jd_requirements = build_target_requirements_from_jd(jd_result, context.skills, role_label=role_label)
    jd_requirements = _apply_requirement_level_guidance(jd_requirements, context.ka_items)
    if jd_requirements.empty:
        raise ValueError("No dataset skills could be extracted from the JD text. Try adding clearer role requirements or tools.")
    jd_requirements = _with_skill_descriptions(jd_requirements, context.paths.processed_dir)
    jd_requirements = _prepare_parsed_jd_requirements(jd_requirements)
    scored_jd_requirements = jd_requirements.loc[~jd_requirements["parser_optional_requirement"].fillna(False)].copy()
    if scored_jd_requirements.empty:
        raise ValueError("Only optional JD skills were extracted. Add clearer must-have requirements before scoring.")
    summary, gap_table = score_role_fit(profile.to_user_vector(), scored_jd_requirements)
    action_plan = build_action_plan(gap_table, context.ka_items, max_actions=5)
    explainer = load_explainer_agent_from_env(context.project_root)
    score_explanation = explainer.explain_score(summary, gap_table)
    recommendations = pd.DataFrame([
        {
            "role_id": summary.role_id,
            "sector": summary.sector,
            "track": summary.track,
            "job_role": summary.job_role,
            "suitability": summary.suitability,
            "suitability_percentage": summary.suitability_percentage,
            "gap_cost": summary.gap_cost,
            "matched_skill_count": summary.matched_skill_count,
            "gap_skill_count": summary.gap_skill_count,
            "target_skill_count": summary.target_skill_count,
        }
    ])
    return TargetModeResult(
        target_mode="jd_scoring",
        target_label=role_label,
        recommendations=recommendations,
        selected_summary=summary,
        selected_gap_table=gap_table,
        action_plan=action_plan,
        score_explanation=score_explanation,
        pathway_edge=None,
        parser_source=f"profile={profile.parser_source}; jd={jd_parser_source}",
        parsed_target_requirements=jd_requirements,
    )


def render_result_report_markdown(
    context: ResumeWorkflowContext,
    profile: ReviewedSkillProfile,
    result: TargetModeResult,
    target_mode_detail: str,
    report_mode: str = "debug",
) -> str:
    """Render a resume workflow report without deciding whether to persist it."""
    summary = result.selected_summary
    if report_mode != "debug":
        lines = _normal_result_report_lines(context, profile, result, target_mode_detail)
        return "\n".join(lines) + "\n"
    related_notes = build_related_skill_notes(result.selected_gap_table, profile, context.skills)
    lines = [
        "# Resume-First Local Workflow Result",
        "",
        "## Privacy Boundary",
        "",
        "- Raw resume/JD text is read at runtime only and is not written to this report.",
        "- Persisted fields are reviewed skills, short evidence snippets, confidence, score outputs, and source notes.",
        "",
        "## Confirmed Skill Profile",
        "",
    ]
    if not profile.items:
        lines.append("- No skills were confirmed.")
    for item in profile.items:
        lines.append(f"- {item.unique_skill_title}: level {item.level:g}, confidence {item.confidence:.2f}")
        lines.append(f"  Evidence snippet: {_snippet(item.evidence, limit=180)}")
        lines.append(f"  Source: {item.source_section}; mapping: {item.mapping_type}")
    lines.extend(["", "## Parser Diagnostics", ""])
    lines.extend(_profile_parser_diagnostic_lines(profile))
    if result.parsed_target_requirements is not None and not result.parsed_target_requirements.empty:
        lines.extend(["", "## Parsed JD Requirements", ""])
        lines.extend(_parsed_jd_requirement_lines(result.parsed_target_requirements))
    lines.extend([
        "",
        "## Target Mode",
        "",
        f"- Mode: {result.target_mode}",
        f"- Detail: {target_mode_detail}",
        f"- Target label: {result.target_label}",
        "",
        "## Suitability Score",
        "",
        f"- Suitability: {summary.suitability_percentage:.2f}%",
        f"- Matched skills: {summary.matched_skill_count}/{summary.target_skill_count}",
        f"- Skills below target: {summary.gap_skill_count}",
        f"- Gap cost: {summary.gap_cost:.2f}",
        "- All MVP skill weights are 1.0.",
        f"- Formula: {score_explanation_text()}",
    ])
    if result.pathway_edge:
        lines.extend(["", "## Pathway Fit", ""])
        if "edge_fit_percentage" in result.pathway_edge:
            lines.append(f"- Dataset role-to-role pathway fit: {float(result.pathway_edge['edge_fit_percentage']):.2f}%")
            lines.append(f"- Edge assumptions: {result.pathway_edge.get('edge_assumptions', '')}")
        else:
            lines.append(f"- {result.pathway_edge.get('edge_error', 'No pathway edge available.')}")
    lines.extend([
        "",
        "## Recommendations",
        "",
    ])
    for index, row in enumerate(result.recommendations.itertuples(index=False), start=1):
        lines.append(
            f"{index}. {row.job_role} ({row.sector} / {row.track}) - "
            f"{float(row.suitability_percentage):.2f}% fit, gaps {int(row.gap_skill_count)}"
        )
    lines.extend([
        "",
        "## Why This Score",
        "",
        result.score_explanation.text,
        "",
        f"Explanation source: {result.score_explanation.source}",
        "",
        "## Top Gaps",
        "",
    ])
    gaps = result.selected_gap_table.loc[result.selected_gap_table["gap"] > 0].head(10)
    if gaps.empty:
        lines.append("- No remaining target gaps.")
    for row in gaps.itertuples(index=False):
        lines.append(f"- {row.unique_skill_title}: current {row.current_level:g}, target {row.target_level:g}, gap {row.gap:g}")
        related = related_notes.get(str(row.skill_id))
        if related is not None:
            lines.append(f"  {related_skill_normal_note(related)}")
            lines.append(f"  {related_skill_debug_note(related)}")
        if hasattr(row, "source_row_number"):
            lines.append(f"  Source row: role-skill row {row.source_row_number}")
    related_lines = _related_score_report_lines(result.selected_gap_table, related_notes, debug=True)
    if related_lines:
        lines.extend(["", "## Related Skill Notes", ""])
        lines.extend(related_lines)
    lines.extend(["", "## Action Plan", ""])
    lines.extend(_report_action_plan_lines(result.action_plan, related_notes, debug=True))
    lines.extend(["", "## Parser And Explainer Status", ""])
    lines.append(f"- Parser source: {result.parser_source}")
    for note in profile.parser_notes:
        lines.append(f"- Parser note: {note}")
    lines.append(f"- Explainer source: {result.score_explanation.source}")
    lines.append(f"- Explainer model setting: {result.score_explanation.model}")
    _append_skillsfuture_explore_link(lines)
    return "\n".join(lines) + "\n"


def write_result_report(
    context: ResumeWorkflowContext,
    profile: ReviewedSkillProfile,
    result: TargetModeResult,
    target_mode_detail: str,
    report_mode: str = "debug",
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "debug" if report_mode == "debug" else "normal"
    output_path = context.paths.processed_dir / f"resume_first_result_{timestamp}_{suffix}.md"
    output_path.write_text(
        render_result_report_markdown(context, profile, result, target_mode_detail, report_mode=report_mode),
        encoding="utf-8",
    )
    return output_path


def _normal_result_report_lines(
    context: ResumeWorkflowContext,
    profile: ReviewedSkillProfile,
    result: TargetModeResult,
    target_mode_detail: str,
) -> list[str]:
    summary = result.selected_summary
    related_notes = build_related_skill_notes(result.selected_gap_table, profile, context.skills)
    lines = [
        "# Career Pathway Result",
        "",
        "## Privacy Boundary",
        "",
        "- Raw resume/JD text is read at runtime only and is not written to this report.",
        "- This report shows confirmed skills, score outputs, gaps, and recommended actions.",
        "",
        "## Confirmed Skill Profile",
        "",
    ]
    if not profile.items:
        lines.append("- No skills were confirmed.")
    for item in profile.items:
        lines.append(f"- {item.unique_skill_title}: level {item.level:g}")
        lines.append(f"  Reason: {_user_facing_skill_reason(item)}")
    lines.extend([
        "",
        "## Target",
        "",
        f"- Mode: {result.target_mode}",
        f"- Detail: {target_mode_detail}",
        f"- Target: {result.target_label}",
        "",
        "## Suitability",
        "",
        f"- Suitability: {summary.suitability_percentage:.2f}%",
        f"- Matched skills: {summary.matched_skill_count}/{summary.target_skill_count}",
        f"- Skills below target: {summary.gap_skill_count}",
        "",
        "## Why This Score",
        "",
    ])
    lines.extend(_plain_score_explanation_lines(summary, result.selected_gap_table))
    lines.extend(["", "## Top Gaps", ""])
    gaps = result.selected_gap_table.loc[result.selected_gap_table["gap"] > 0].head(10)
    if gaps.empty:
        lines.append("- No remaining target gaps.")
    for row in gaps.itertuples(index=False):
        lines.append(f"- {row.unique_skill_title}: current {row.current_level:g}, target {row.target_level:g}, gap {row.gap:g}")
        related = related_notes.get(str(row.skill_id))
        if related is not None:
            lines.append(f"  {related_skill_normal_note(related)}")
    related_lines = _related_score_report_lines(result.selected_gap_table, related_notes, debug=False)
    if related_lines:
        lines.extend(["", "## Related Skill Notes", ""])
        lines.extend(related_lines)
    lines.extend(["", "## Action Plan", ""])
    lines.extend(_report_action_plan_lines(result.action_plan, related_notes, debug=False))
    _append_skillsfuture_explore_link(lines)
    return lines


def _append_skillsfuture_explore_link(lines: list[str]) -> None:
    lines.extend([
        "",
        "## Explore More Skills",
        "",
        f"Visit the SkillsFuture interactive skills frameworks to explore more skills: {SKILLSFUTURE_INTERACTIVE_FRAMEWORKS_URL}",
    ])


def _related_score_report_lines(
    gap_table: pd.DataFrame,
    related_notes: dict[str, RelatedSkillMatch],
    *,
    debug: bool,
) -> list[str]:
    lines: list[str] = []
    gaps = gap_table.loc[gap_table["gap"] > 0]
    for gap in gaps.itertuples(index=False):
        related = related_notes.get(str(gap.skill_id))
        if related is None:
            continue
        lines.append(f"- {gap.unique_skill_title}: {related_skill_normal_note(related)}")
        if debug:
            lines.append(f"  {related_skill_debug_note(related)}")
    return lines


def _report_action_plan_lines(
    action_plan: pd.DataFrame,
    related_notes: dict[str, RelatedSkillMatch],
    *,
    debug: bool,
) -> list[str]:
    lines: list[str] = []
    if action_plan.empty:
        return ["- No action items were generated because no target gaps were found."]
    for index, row in enumerate(action_plan.itertuples(index=False), start=1):
        code = str(getattr(row, "tsc_ccs_code", "")).strip()
        suffix = f" ({code})" if code else ""
        lines.extend([
            f"### {index}. {row.skill}{suffix}",
            "",
            f"Current level: {row.current_level:g}  ",
            f"Target level: {row.target_level:g}",
            "",
        ])
        related = related_notes.get(str(getattr(row, "skill_id", "")))
        if related is not None:
            lines.extend([
                "Related evidence:",
                f"{related.related_skill_title}, level {related.related_level:g}.",
                "",
                "Why it is still a gap:",
                f"SkillsFuture defines this separately from {related.target_skill_title}, so MVP scoring only gives credit for exact skill matches.",
                "",
            ])
            if debug:
                lines.extend([related_skill_debug_note(related), ""])
        description = str(getattr(row, "proficiency_description", "")).strip()
        if description:
            lines.extend(["Target proficiency:", _snippet(description, limit=320), ""])
        ka_item = str(getattr(row, "ka_item", "")).strip()
        if ka_item:
            lines.extend(["K&A focus:", _snippet(ka_item, limit=320), ""])
        lines.extend([
            "Action:",
            str(getattr(row, "practical_action", getattr(row, "next_action", ""))).strip(),
            "",
            "Evidence to build:",
            str(getattr(row, "evidence_to_build", "")).strip(),
            "",
        ])
        if debug:
            lines.extend([
                f"Source: K&A row {getattr(row, 'ka_source_row_number', '')}; role-skill row {getattr(row, 'role_skill_source_row_number', '')}.",
                "",
            ])
    return lines


def _plain_score_explanation_lines(summary: FitSummary, gap_table: pd.DataFrame) -> list[str]:
    matched = gap_table.loc[gap_table["current_level"] > 0, "unique_skill_title"].head(6).astype(str).tolist()
    gaps = gap_table.loc[gap_table["gap"] > 0].head(3)
    lines = [f"You match {summary.matched_skill_count} of {summary.target_skill_count} target skills."]
    if matched:
        suffix = "." if len(matched) < 6 else ", and more."
        lines.append("Matched skills: " + ", ".join(matched) + suffix)
    if not gaps.empty:
        gap_bits = [f"{row.unique_skill_title} (you {row.current_level:g}, target {row.target_level:g})" for row in gaps.itertuples(index=False)]
        lines.append("The score is pulled down mainly by: " + "; ".join(gap_bits) + ".")
    lines.append(f"Overall suitability is {summary.suitability_percentage:.2f}% because the covered target levels are compared with the total target levels.")
    return lines


def _apply_requirement_level_guidance(requirements: pd.DataFrame, ka_items: pd.DataFrame | None) -> pd.DataFrame:
    if requirements.empty or "skill_id" not in requirements.columns or "required_level" not in requirements.columns:
        return requirements
    prepared = requirements.copy()
    notes: list[str] = []
    adjusted_levels: list[float] = []
    for row in prepared.itertuples(index=False):
        requested = float(getattr(row, "required_level"))
        adjusted, note = cap_level_to_skill_guidance(ka_items, str(getattr(row, "skill_id")), requested, allow_zero=False)
        adjusted_levels.append(float(adjusted))
        notes.append(note or "")
    prepared["required_level"] = adjusted_levels
    prepared["proficiency_level_raw"] = [f"{level:g}" for level in adjusted_levels]
    if "parser_reason" in prepared.columns:
        prepared["parser_reason"] = [
            f"{reason} {note}".strip() if note else str(reason)
            for reason, note in zip(prepared["parser_reason"].astype(str), notes)
        ]
    if "parser_uncertainty_flag" in prepared.columns:
        prepared["parser_uncertainty_flag"] = [bool(flag) or bool(note) for flag, note in zip(prepared["parser_uncertainty_flag"], notes)]
    return prepared


def _prepare_parsed_jd_requirements(requirements: pd.DataFrame) -> pd.DataFrame:
    prepared = requirements.copy().reset_index(drop=True)
    if prepared.empty:
        return prepared
    prepared["parser_optional_requirement"] = prepared.apply(_is_optional_jd_requirement, axis=1)
    prepared["parser_scoring_status"] = prepared["parser_optional_requirement"].map(
        lambda value: "excluded_optional" if bool(value) else "scored"
    )
    prepared["_family_key"] = prepared["unique_skill_title"].astype(str).map(_jd_skill_family_key)
    prepared["_mapping_rank"] = prepared.get("parser_mapping_type", "").astype(str).map(_mapping_priority)
    prepared["_confidence"] = pd.to_numeric(prepared.get("parser_confidence", 0.0), errors="coerce").fillna(0.0)
    prepared["_required_level"] = pd.to_numeric(prepared["required_level"], errors="coerce").fillna(0.0)
    prepared = prepared.sort_values(
        ["parser_optional_requirement", "_mapping_rank", "_required_level", "_confidence", "unique_skill_title"],
        ascending=[True, True, False, False, True],
    ).reset_index(drop=True)

    seen_scored_families: set[str] = set()
    statuses: list[str] = []
    optional_flags: list[bool] = []
    for _, row in prepared.iterrows():
        family = str(row.get("_family_key", ""))
        already_seen = family in seen_scored_families
        is_optional = bool(row.get("parser_optional_requirement", False))
        if already_seen:
            statuses.append("excluded_duplicate")
            optional_flags.append(True)
            continue
        if is_optional:
            statuses.append("excluded_optional")
            optional_flags.append(True)
            continue
        statuses.append("scored")
        optional_flags.append(False)
        if family:
            seen_scored_families.add(family)

    prepared["parser_scoring_status"] = statuses
    prepared["parser_optional_requirement"] = optional_flags
    return prepared.drop(columns=["_family_key", "_mapping_rank", "_confidence", "_required_level"], errors="ignore").reset_index(drop=True)


def _is_optional_jd_requirement(row: pd.Series) -> bool:
    text = " ".join(
        str(row.get(column, ""))
        for column in ("parser_evidence", "parser_reason", "proficiency_description")
    ).casefold()
    return bool(re.search(r"\b(additional exposure|nice to have|good to have|plus|preferred|advantage|exposure)\b", text))


def _mapping_priority(mapping_type: str) -> int:
    normalized = str(mapping_type).casefold()
    if normalized == "exact_dataset_title":
        return 0
    if normalized == "agent_shortlist_match":
        return 1
    if normalized == "agent_suggested_fuzzy_high":
        return 2
    if normalized == "inferred_alias":
        return 3
    if normalized == "agent_suggested_fuzzy_needs_review":
        return 4
    return 5


def _jd_skill_family_key(title: str) -> str:
    normalized = _normalize_for_match(title)
    tokens = set(normalized.split())
    if "analytics" in tokens and ({"data", "computational", "modelling", "modeling", "intelligence"} & tokens):
        return "analytics_modelling"
    if {"application", "applications", "development"} & tokens and ("development" in tokens or "applications" in tokens):
        return "applications_development"
    if "communication" in tokens or "collaboration" in tokens:
        return "communication_collaboration"
    if "artificial" in tokens and "intelligence" in tokens:
        return "artificial_intelligence"
    return normalized

def _profile_parser_diagnostic_lines(profile: ReviewedSkillProfile) -> list[str]:
    if not profile.items:
        return ["- No parser diagnostics because no skills were confirmed."]
    counts: dict[str, int] = {}
    review_count = 0
    for item in profile.items:
        counts[item.mapping_type] = counts.get(item.mapping_type, 0) + 1
        if item.uncertainty_flag:
            review_count += 1
    lines = [
        f"- Total confirmed profile skills: {len(profile.items)}",
        f"- Skills still marked for review: {review_count}",
    ]
    for mapping_type, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])):
        lines.append(f"- Mapping type `{mapping_type}`: {count}")
    lines.append("- Parser-agent verification note: agent shortlist matches can support or upgrade fallback evidence, but fallback-only skills are not auto-removed unless the user removes them during review.")
    return lines


def _parsed_jd_requirement_lines(requirements: pd.DataFrame, limit: int = 20) -> list[str]:
    lines: list[str] = []
    if "parser_mapping_type" in requirements.columns:
        counts = requirements["parser_mapping_type"].fillna("unknown").astype(str).value_counts().to_dict()
        lines.append(f"- Parsed JD skills: {len(requirements)}")
        for mapping_type, count in counts.items():
            lines.append(f"- JD mapping type `{mapping_type}`: {count}")
        lines.append("")
    if "parser_scoring_status" in requirements.columns:
        status_counts = requirements["parser_scoring_status"].fillna("unknown").astype(str).value_counts().to_dict()
        for status, count in status_counts.items():
            lines.append(f"- JD scoring status `{status}`: {count}")
        lines.append("")
    for row in requirements.head(limit).itertuples(index=False):
        confidence = getattr(row, "parser_confidence", "")
        confidence_text = f", confidence {float(confidence):.2f}" if confidence != "" and pd.notna(confidence) else ""
        mapping = getattr(row, "parser_mapping_type", "unknown")
        status = getattr(row, "parser_scoring_status", "scored")
        evidence = _snippet(str(getattr(row, "parser_evidence", "")), limit=170)
        reason = _snippet(str(getattr(row, "parser_reason", "")), limit=170)
        uncertainty = getattr(row, "parser_uncertainty_flag", "")
        review_text = " needs review" if str(uncertainty).casefold() == "true" else ""
        lines.append(f"- {row.unique_skill_title}: target level {float(row.required_level):g}{confidence_text}; mapping {mapping}; status {status}{review_text}")
        if evidence:
            lines.append(f"  Evidence: {evidence}")
        if reason:
            lines.append(f"  Reason: {reason}")
    if len(requirements) > limit:
        lines.append(f"- {len(requirements) - limit} additional parsed JD requirement(s) omitted from this report section.")
    return lines or ["- No parsed JD requirements available."]

def _parse_with_optional_agent(
    text: str,
    skills: pd.DataFrame,
    document_kind: str,
    max_skills: int,
    use_agent: bool,
) -> tuple[ParserResult, str]:
    fallback = parse_resume_text(text, skills, max_skills=max_skills) if document_kind == "resume" else parse_jd_text(text, skills, max_skills=max_skills)
    if not use_agent:
        return fallback, "rule-based fallback: agent disabled for this run"

    config = _agent_parser_config()
    if not config.enabled:
        return fallback, config.source

    try:
        candidate_skills = _candidate_skills_for_agent(fallback, skills, limit=_parser_candidate_limit())
        agent_payload = _call_agent_parser(
            text=text,
            candidate_skills=candidate_skills,
            document_kind=document_kind,
            model=config.model,
            max_skills=max_skills,
        )
        merged = _merge_agent_and_rule_results(agent_payload, fallback, skills, document_kind, max_skills=max_skills)
        if not merged.extracted_skills:
            return fallback, "rule-based fallback: agent returned no mapped dataset skills"
        return merged, f"agent-assisted parser ({config.model}) with candidate shortlist and fuzzy suggestion mapping"
    except Exception as exc:
        note = f"rule-based fallback: parser agent failed ({type(exc).__name__}: {str(exc)[:160]})"
        return fallback, note


def _agent_parser_config() -> AgentParserConfig:
    disabled = os.getenv("PARSER_AGENT_DISABLED", "").strip().casefold()
    if disabled in {"1", "true", "yes", "on"}:
        return AgentParserConfig(enabled=False, source="rule-based fallback: parser agent disabled", model=_env_value(MODEL_ENV_NAMES) or DEFAULT_EXPLAINER_MODEL)
    token = _env_value(("PARSER_AGENT_API_TOKEN", "parser_agent_api_token") + TOKEN_ENV_NAMES)
    model = _env_value(("PARSER_AGENT_MODEL", "parser_agent_model") + MODEL_ENV_NAMES) or DEFAULT_EXPLAINER_MODEL
    if not token:
        return AgentParserConfig(enabled=False, source="rule-based fallback: no parser agent token configured", model=model)
    return AgentParserConfig(enabled=True, source="agent", model=model)


def _call_agent_parser(
    text: str,
    candidate_skills: pd.DataFrame,
    document_kind: str,
    model: str,
    max_skills: int,
) -> dict[str, Any]:
    import httpx
    from openai import OpenAI  # type: ignore[import-not-found]

    token = _env_value(("PARSER_AGENT_API_TOKEN", "parser_agent_api_token") + TOKEN_ENV_NAMES)
    if not token:
        return {"shortlist_matches": [], "additional_suggestions": []}

    candidates = _agent_candidate_payload(candidate_skills)
    client = OpenAI(api_key=token, http_client=httpx.Client(timeout=_parser_timeout_seconds(), trust_env=False))
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You extract auditable SkillsFuture skill evidence from resumes or job descriptions. "
                    "Return JSON only. You do not score suitability, rank roles, or recommend roles. "
                    "For shortlist_matches, use only provided candidate skill_id values. "
                    "For additional_suggestions, suggest evidence-backed skills that appear missing from the candidate shortlist."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "document_kind": document_kind,
                        "candidate_skills": candidates,
                        "schema": {
                            "shortlist_matches": [
                                {
                                    "skill_id": "exact candidate skill_id",
                                    "skill_title": "exact candidate skill_title",
                                    "inferred_level": "number from 1 to 6",
                                    "confidence": "number from 0 to 1",
                                    "evidence": "short evidence snippet",
                                    "reason": "brief reason",
                                    "source_section": "work experience, internship, project, coursework, tools, or JD requirement",
                                }
                            ],
                            "additional_suggestions": [
                                {
                                    "suggested_skill": "skill phrase not present in candidate shortlist",
                                    "inferred_level": "number from 1 to 6",
                                    "confidence": "number from 0 to 1",
                                    "evidence": "short evidence snippet",
                                    "reason": "brief reason",
                                    "source_section": "work experience, internship, project, coursework, tools, or JD requirement",
                                }
                            ],
                        },
                        "rules": [
                            "Keep evidence short and do not include personal contact details.",
                            "Only include skills with concrete evidence from the document.",
                            "Use additional_suggestions sparingly for skills missing from candidate_skills.",
                        ],
                        "text": text[:_parser_text_limit()],
                        "max_items": max_skills,
                    },
                    ensure_ascii=True,
                ),
            },
        ],
        max_output_tokens=1200,
        reasoning={"effort": "minimal"},
    )
    output_text = getattr(response, "output_text", "") or ""
    payload = _extract_json_payload(output_text)
    if isinstance(payload, list):
        return {"shortlist_matches": payload, "additional_suggestions": []}
    if not isinstance(payload, dict):
        return {"shortlist_matches": [], "additional_suggestions": []}
    return {
        "shortlist_matches": _list_of_dicts(payload.get("shortlist_matches", payload.get("skills", payload.get("items", [])))),
        "additional_suggestions": _list_of_dicts(payload.get("additional_suggestions", [])),
    }


def _merge_agent_and_rule_results(
    agent_payload: Mapping[str, Any] | Sequence[dict[str, Any]],
    fallback: ParserResult,
    skills: pd.DataFrame,
    document_kind: str,
    max_skills: int,
) -> ParserResult:
    if isinstance(agent_payload, Mapping):
        shortlist_matches = _list_of_dicts(agent_payload.get("shortlist_matches", []))
        additional_suggestions = _list_of_dicts(agent_payload.get("additional_suggestions", []))
    else:
        shortlist_matches = _list_of_dicts(agent_payload)
        additional_suggestions = []

    skill_id_lookup = {str(row.skill_id): row for row in skills.itertuples(index=False)}
    title_lookup = {str(row.unique_skill_title).casefold(): row for row in skills.itertuples(index=False)}
    extracted: list[ParsedSkillEvidence] = []

    for item in shortlist_matches[:max_skills]:
        row = skill_id_lookup.get(str(item.get("skill_id", "")).strip())
        if row is None:
            title = str(item.get("skill_title", "")).strip()
            row = title_lookup.get(title.casefold())
        if row is None:
            continue
        extracted.append(_agent_item_to_evidence(item, row, mapping_type="agent_shortlist_match", document_kind=document_kind))

    for item in additional_suggestions[:max_skills]:
        suggestion = str(item.get("suggested_skill", item.get("skill_title", ""))).strip()
        if not suggestion:
            continue
        match = _fuzzy_match_skill(suggestion, skills)
        if match is None:
            continue
        row, score = match
        mapping_type = "agent_suggested_fuzzy_high" if score >= 0.90 else "agent_suggested_fuzzy_needs_review"
        evidence = _agent_item_to_evidence(item, row, mapping_type=mapping_type, matched_phrase=suggestion, document_kind=document_kind)
        extracted.append(
            ParsedSkillEvidence(
                skill_id=evidence.skill_id,
                unique_skill_title=evidence.unique_skill_title,
                inferred_level=evidence.inferred_level,
                confidence=min(evidence.confidence, score),
                evidence=evidence.evidence,
                reason=f"{evidence.reason} Fuzzy mapped agent suggestion '{suggestion}' at score {score:.2f}.",
                uncertainty_flag=True,
                mapping_type=mapping_type,
                matched_phrase=suggestion,
            )
        )

    by_skill = {item.skill_id: item for item in fallback.extracted_skills}
    for item in extracted:
        current = by_skill.get(item.skill_id)
        if current is None or (item.confidence, item.inferred_level) > (current.confidence, current.inferred_level):
            by_skill[item.skill_id] = item
    ranked = sorted(by_skill.values(), key=lambda item: (item.confidence, item.inferred_level), reverse=True)[:max_skills]
    notes = tuple(fallback.parser_notes) + (
        "Agent parser reviewed a local candidate shortlist instead of the full SkillsFuture skill list.",
        "Agent additional suggestions were fuzzy-mapped back to dataset skills and require user review before scoring.",
    )
    source_type = "resume" if document_kind == "resume" else "job_description"
    return ParserResult(source_type=source_type, extracted_skills=tuple(ranked), parser_notes=notes)


def _agent_item_to_evidence(
    item: Mapping[str, Any],
    row: Any,
    mapping_type: str,
    matched_phrase: str | None = None,
    document_kind: str = "resume",
) -> ParsedSkillEvidence:
    title = str(row.unique_skill_title)
    level = _clamp_level(item.get("inferred_level", 2.0))
    confidence = _clamp_confidence(item.get("confidence", 0.65))
    evidence = _snippet(_clean_evidence_text(str(item.get("evidence", "")) or title))
    reason = _clean_parser_reason(
        str(item.get("reason", "Agent mapped this evidence to a dataset skill."))[:240],
        title,
        evidence,
        _is_weak_evidence(evidence, title),
    )
    if document_kind == "resume":
        capped_level, cap_reason = _cap_resume_agent_level(level, evidence, reason)
        if capped_level < level:
            level = capped_level
            reason = f"{reason} {cap_reason}"[:240]
            confidence = min(confidence, 0.80)
    return ParsedSkillEvidence(
        skill_id=str(row.skill_id),
        unique_skill_title=title,
        inferred_level=level,
        confidence=confidence,
        evidence=evidence,
        reason=reason,
        uncertainty_flag=confidence < 0.80 or mapping_type != "agent_shortlist_match",
        mapping_type=mapping_type,
        matched_phrase=matched_phrase or str(item.get("skill_title", title)),
    )


def _cap_resume_agent_level(level: float, evidence: str, reason: str) -> tuple[float, str]:
    if level < 5.0:
        return level, ""
    text = f"{evidence} {reason}".casefold()
    strategic_cues = (
        "strategy", "strategic", "organisation-wide", "organization-wide", "enterprise",
        "mentored", "coached", "coach others", "set direction", "owned strategy",
    )
    advanced_cues = (
        "led", "lead ", "owned", "designed", "architected", "production", "complex",
        "optimised", "optimized", "managed", "supervised",
    )
    if any(cue in text for cue in strategic_cues):
        return level, ""
    if any(cue in text for cue in advanced_cues):
        return 4.0, "Agent level capped from 5 to 4 because resume evidence shows advanced ownership but not strategic/mentoring evidence."
    return 3.0, "Agent level capped from 5 to 3 because resume evidence shows applied use but not strategic/mentoring evidence."

def _candidate_skills_for_agent(fallback: ParserResult, skills: pd.DataFrame, limit: int = 80) -> pd.DataFrame:
    selected_ids = [item.skill_id for item in fallback.extracted_skills]
    selected = skills.loc[skills["skill_id"].astype(str).isin(selected_ids)].copy()
    if len(selected) >= limit:
        return selected.head(limit).reset_index(drop=True)

    priority_terms = (
        "data", "analytics", "analysis", "programming", "coding", "visualisation", "visualization",
        "engineering", "governance", "modelling", "modeling", "stakeholder", "business", "project",
        "text", "machine learning", "intelligence",
    )
    pool = skills.copy()
    search_text = (pool["unique_skill_title"].astype(str) + " " + pool.get("unique_skill_description", "").astype(str)).str.casefold()
    priority_mask = search_text.apply(lambda value: any(term in value for term in priority_terms))
    priority = pool.loc[priority_mask]
    combined = pd.concat([selected, priority, pool], ignore_index=True)
    combined = combined.drop_duplicates(subset=["skill_id"], keep="first")
    return combined.head(limit).reset_index(drop=True)


def _agent_candidate_payload(candidate_skills: pd.DataFrame) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in candidate_skills.itertuples(index=False):
        rows.append(
            {
                "skill_id": str(row.skill_id),
                "skill_title": str(row.unique_skill_title),
                "skill_description": _snippet(str(getattr(row, "unique_skill_description", "")), limit=180),
            }
        )
    return rows


def _fuzzy_match_skill(suggestion: str, skills: pd.DataFrame, minimum_score: float = 0.75) -> tuple[Any, float] | None:
    normalized_suggestion = _normalize_for_match(suggestion)
    if not normalized_suggestion:
        return None
    best_row = None
    best_score = 0.0
    suggestion_tokens = set(normalized_suggestion.split())
    for row in skills.itertuples(index=False):
        title = str(row.unique_skill_title)
        description = str(getattr(row, "unique_skill_description", ""))
        normalized_title = _normalize_for_match(title)
        normalized_description = _normalize_for_match(description)
        title_score = SequenceMatcher(None, normalized_suggestion, normalized_title).ratio()
        description_score = SequenceMatcher(None, normalized_suggestion, normalized_description[:240]).ratio() if normalized_description else 0.0
        title_tokens = set(normalized_title.split())
        token_score = len(suggestion_tokens & title_tokens) / len(suggestion_tokens | title_tokens) if suggestion_tokens and title_tokens else 0.0
        score = max(title_score, description_score * 0.85, token_score)
        if score > best_score:
            best_score = score
            best_row = row
    if best_row is None or best_score < minimum_score:
        return None
    return best_row, float(best_score)


def _normalize_for_match(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _parser_timeout_seconds() -> float:
    value = os.getenv("PARSER_AGENT_TIMEOUT_SECONDS", "45")
    try:
        return max(5.0, float(value))
    except ValueError:
        return 45.0


def _parser_candidate_limit() -> int:
    value = os.getenv("PARSER_AGENT_CANDIDATE_LIMIT", "80")
    try:
        return max(20, min(200, int(value)))
    except ValueError:
        return 80


def _parser_text_limit() -> int:
    value = os.getenv("PARSER_AGENT_TEXT_LIMIT", "9000")
    try:
        return max(2000, min(20000, int(value)))
    except ValueError:
        return 9000

def _extract_json_payload(text: str) -> Any:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.casefold().startswith("json"):
            stripped = stripped[4:].strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start_candidates = [index for index in (stripped.find("["), stripped.find("{")) if index >= 0]
        if not start_candidates:
            raise
        start = min(start_candidates)
        end = max(stripped.rfind("]"), stripped.rfind("}"))
        if end <= start:
            raise
        return json.loads(stripped[start : end + 1])


def _with_skill_descriptions(requirements: pd.DataFrame, processed_dir: Path) -> pd.DataFrame:
    if "unique_skill_description" in requirements.columns:
        return requirements
    skills_path = processed_dir / "skills.csv"
    if not skills_path.exists():
        return requirements
    skills = pd.read_csv(skills_path, usecols=["skill_id", "unique_skill_description"])
    return requirements.merge(skills, on="skill_id", how="left")


def _infer_source_section(evidence: str, source_type: str) -> str:
    text = evidence.casefold()
    if any(term in text for term in ("intern", "internship")):
        return "internship"
    if any(term in text for term in ("project", "capstone", "coursework", "course")):
        return "project/coursework"
    if any(term in text for term in ("education", "master", "degree", "training", "certification", "deep skilling")):
        return "education/training"
    if any(term in text for term in ("experience", "managed", "led", "lead ", "built", "developed", "implemented", "provided", "investigation", "incident report")):
        return "work experience"
    if any(term in text for term in ("tool", "python", "sql", "tableau", "power bi")):
        return "tools"
    return source_type


def _clean_evidence_text(text: str) -> str:
    cleaned = str(text)
    cleaned = re.sub(r"\b[\w.+-]+@[\w.-]+\.\w+\b", "[email redacted]", cleaned)
    cleaned = re.sub(r"\b(?:\+?\d[\d\s().-]{7,}\d)\b", "[phone redacted]", cleaned)
    cleaned = re.sub(r"\b(?:https?://)?(?:www\.)?(?:linkedin\.com|github\.com)/\S+", "[profile redacted]", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:singaporean|nationality|address|linkedin)\b[:\s\w@.+/-]{0,80}", " ", cleaned, flags=re.IGNORECASE)
    return _snippet(cleaned, limit=240)


def _is_weak_evidence(evidence: str, skill_title: str) -> bool:
    text = _normalize_for_match(evidence)
    if not text:
        return True
    weak_terms = {"email", "phone", "linkedin", "singaporean", "nationality", "address", "education", "master", "bachelor"}
    tokens = set(text.split())
    action_terms = ("built", "created", "developed", "led", "used", "analysed", "analyzed", "dashboard", "project", "intern", "implemented", "automated", "prepared")
    if len(tokens) <= 4:
        return True
    if len(tokens & weak_terms) >= 2 and not any(term in text for term in action_terms):
        return True
    title_tokens = set(_normalize_for_match(skill_title).split())
    if title_tokens and not (title_tokens & tokens) and not any(term in text for term in ("python", "sql", "tableau", "dashboard", "pipeline", "model", "stakeholder", "business", "data")):
        return True
    return False


def _clean_parser_reason(reason: str, skill_title: str, evidence: str, weak_evidence: bool = False) -> str:
    if weak_evidence:
        return f"Parser found a possible {skill_title} signal, but the supporting evidence is weak and needs user confirmation."
    return _snippet(str(reason), limit=240)


def _user_facing_skill_reason(item: SkillProfileItem) -> str:
    return _user_reason_from_text(item.unique_skill_title, item.evidence, item.reason)


def _user_reason_from_text(skill_title: str, evidence: str, reason: str) -> str:
    text = f"{evidence} {reason}".casefold()
    if any(term in text for term in ("dashboard", "visual", "tableau", "power bi", "chart")):
        return "Shows evidence of turning data into dashboards or visuals for communication."
    if any(term in text for term in ("python", "sql", "script", "code", "program")):
        return "Shows hands-on use of programming or query tools to complete analytics work."
    if any(term in text for term in ("pipeline", "etl", "data engineering")):
        return "Shows evidence of preparing or moving data for analytics use."
    if any(term in text for term in ("collaboration", "cross-functional", "stakeholder", "business users")):
        return "Shows experience working with other teams or stakeholders to complete work."
    if any(term in text for term in ("model", "machine learning", "forecast", "nlp")):
        return "Shows exposure to modelling or machine-learning related work."
    return _snippet(reason, limit=160)


def _snippet(text: str, limit: int = 240) -> str:
    compact = " ".join(str(text).split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 3)].rstrip() + "..."


def valid_levels_for_skill(ka_items: pd.DataFrame | None, skill_id: str, include_zero: bool = True) -> tuple[float, ...]:
    """Return dataset-backed levels for a skill, with level 0 as user-facing no-evidence shorthand."""
    fallback = tuple(float(level) for level in (range(0, 7) if include_zero else range(1, 7)))
    if ka_items is None or ka_items.empty or "skill_id" not in ka_items.columns:
        return fallback
    rows = ka_items.loc[ka_items["skill_id"].astype(str).eq(str(skill_id))].copy()
    if rows.empty or "proficiency_level" not in rows.columns:
        return fallback
    levels = sorted(
        {float(level) for level in pd.to_numeric(rows["proficiency_level"], errors="coerce").dropna().tolist()}
    )
    if not levels:
        return fallback
    if include_zero and 0.0 not in levels:
        levels = [0.0] + levels
    return tuple(levels)


def cap_level_to_skill_guidance(
    ka_items: pd.DataFrame | None,
    skill_id: str,
    requested_level: float,
    allow_zero: bool = True,
) -> tuple[float, str | None]:
    """Conservatively align a level to available SkillsFuture guidance where possible."""
    _validate_level(requested_level)
    requested = float(requested_level)
    if allow_zero and requested == 0.0:
        return 0.0, None
    dataset_levels = tuple(level for level in valid_levels_for_skill(ka_items, skill_id, include_zero=False) if level > 0)
    if not dataset_levels or dataset_levels == tuple(float(level) for level in range(1, 7)):
        return requested, None

    minimum = min(dataset_levels)
    maximum = max(dataset_levels)
    if requested > maximum:
        capped = maximum
        return capped, (
            f"capped from level {requested:g} to {capped:g} because SkillsFuture has no level {requested:g} "
            "K&A row for this skill."
        )
    if requested < minimum:
        return requested, (
            f"kept at level {requested:g} and marked for review because SkillsFuture guidance for this skill starts at "
            f"level {minimum:g}."
        )
    if requested not in dataset_levels:
        lower_or_equal = [level for level in dataset_levels if level <= requested]
        capped = max(lower_or_equal) if lower_or_equal else minimum
        return capped, (
            f"capped from level {requested:g} to {capped:g} because SkillsFuture has no level {requested:g} "
            "K&A row for this skill."
        )
    return requested, None


def _validate_level(level: float) -> None:
    if float(level) < 0 or float(level) > 6:
        raise ValueError("Skill level must be between 0 and 6.")


def _clamp_level(value: Any) -> float:
    try:
        level = float(value)
    except (TypeError, ValueError):
        level = 2.0
    return max(1.0, min(6.0, level))


def _clamp_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.65
    return max(0.0, min(1.0, confidence))


def _env_value(names: Iterable[str]) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def pasted_jd_document(text: str) -> ExtractedDocument:
    return document_text_from_pasted_input(text, source_type="pasted_jd")





