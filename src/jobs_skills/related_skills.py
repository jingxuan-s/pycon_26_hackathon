"""Explanation-only related-skill matching for target gaps.

The deterministic scoring engine remains exact skill-id matching. This module
only finds nearby confirmed skills so reports can explain likely foundations
without changing suitability percentages.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from typing import Iterable, Mapping

import pandas as pd


TITLE_OVERLAP_THRESHOLD = 0.50
TITLE_SIMILARITY_THRESHOLD = 0.70
DESCRIPTION_OVERLAP_THRESHOLD = 0.25

STOPWORDS = {
    "and",
    "or",
    "of",
    "the",
    "to",
    "for",
    "in",
    "on",
    "with",
    "using",
    "use",
    "skill",
    "skills",
}

CURATED_RELATED_TITLE_PAIRS = {
    frozenset(("data analytics and computational modelling", "computational modelling")),
    frozenset(("analytics and computational modelling", "computational modelling")),
}


@dataclass(frozen=True)
class RelatedSkillMatch:
    target_skill_id: str
    target_skill_title: str
    related_skill_id: str
    related_skill_title: str
    related_level: float
    score: float
    source_rule: str


def build_related_skill_notes(
    gap_table: pd.DataFrame,
    profile: object | None,
    skills: pd.DataFrame,
    *,
    max_notes: int | None = None,
) -> dict[str, RelatedSkillMatch]:
    """Return one strongest related confirmed skill per exact-missing gap."""
    if profile is None or gap_table.empty:
        return {}
    profile_items = list(getattr(profile, "items", []) or [])
    if not profile_items:
        return {}

    skill_lookup = _skill_lookup(skills)
    notes: dict[str, RelatedSkillMatch] = {}
    missing_gaps = gap_table.loc[(gap_table["gap"] > 0) & (gap_table["current_level"] <= 0)].copy()
    for gap in missing_gaps.itertuples(index=False):
        match = find_related_skill_for_gap(gap, profile_items, skill_lookup)
        if match is not None:
            notes[str(gap.skill_id)] = match
            if max_notes is not None and len(notes) >= max_notes:
                break
    return notes


def find_related_skill_for_gap(
    gap: object,
    profile_items: Iterable[object],
    skill_lookup: Mapping[str, Mapping[str, str]],
) -> RelatedSkillMatch | None:
    target_skill_id = str(getattr(gap, "skill_id", ""))
    target_title = str(getattr(gap, "unique_skill_title", "") or "")
    target_desc = str(getattr(gap, "unique_skill_description", "") or "")
    if not target_desc:
        target_desc = str(getattr(gap, "proficiency_description", "") or "")

    best: RelatedSkillMatch | None = None
    for item in profile_items:
        related_skill_id = str(getattr(item, "skill_id", ""))
        if not related_skill_id or related_skill_id == target_skill_id:
            continue
        related_title = str(getattr(item, "unique_skill_title", "") or "")
        related_desc = str(skill_lookup.get(related_skill_id, {}).get("unique_skill_description", ""))
        candidate = _related_candidate(
            target_skill_id=target_skill_id,
            target_title=target_title,
            target_desc=target_desc,
            related_skill_id=related_skill_id,
            related_title=related_title,
            related_desc=related_desc,
            related_level=float(getattr(item, "level", 0.0) or 0.0),
        )
        if candidate is None:
            continue
        if best is None or candidate.score > best.score:
            best = candidate
    return best


def related_skill_normal_note(match: RelatedSkillMatch) -> str:
    return (
        f"Related evidence found: you have {match.related_skill_title} at level {match.related_level:g}. "
        f"SkillsFuture defines this separately from {match.target_skill_title}, so MVP scoring only gives credit "
        "for exact skill matches. This still suggests a useful foundation."
    )


def related_skill_debug_note(match: RelatedSkillMatch) -> str:
    return f"Related-skill rule: {match.source_rule}; similarity score {match.score:.2f}."


def _related_candidate(
    *,
    target_skill_id: str,
    target_title: str,
    target_desc: str,
    related_skill_id: str,
    related_title: str,
    related_desc: str,
    related_level: float,
) -> RelatedSkillMatch | None:
    title_pair = frozenset((_normalize_title(target_title), _normalize_title(related_title)))
    if title_pair in CURATED_RELATED_TITLE_PAIRS:
        return RelatedSkillMatch(
            target_skill_id=target_skill_id,
            target_skill_title=target_title,
            related_skill_id=related_skill_id,
            related_skill_title=related_title,
            related_level=related_level,
            score=1.0,
            source_rule="curated_override",
        )

    title_overlap = _token_overlap(_tokens(target_title), _tokens(related_title))
    title_similarity = SequenceMatcher(None, _normalize_title(target_title), _normalize_title(related_title)).ratio()
    description_overlap = _token_overlap(_tokens(target_desc), _tokens(related_desc))

    if title_overlap >= TITLE_OVERLAP_THRESHOLD:
        score = max(title_overlap, title_similarity)
        return RelatedSkillMatch(
            target_skill_id=target_skill_id,
            target_skill_title=target_title,
            related_skill_id=related_skill_id,
            related_skill_title=related_title,
            related_level=related_level,
            score=float(score),
            source_rule="title_token_overlap",
        )
    if title_similarity >= TITLE_SIMILARITY_THRESHOLD and description_overlap >= DESCRIPTION_OVERLAP_THRESHOLD:
        score = (0.7 * title_similarity) + (0.3 * description_overlap)
        return RelatedSkillMatch(
            target_skill_id=target_skill_id,
            target_skill_title=target_title,
            related_skill_id=related_skill_id,
            related_skill_title=related_title,
            related_level=related_level,
            score=float(score),
            source_rule="title_similarity_description_overlap",
        )
    return None


def _skill_lookup(skills: pd.DataFrame) -> dict[str, dict[str, str]]:
    if skills.empty or "skill_id" not in skills.columns:
        return {}
    columns = [column for column in ("skill_id", "unique_skill_title", "unique_skill_description") if column in skills.columns]
    deduped = skills[columns].drop_duplicates("skill_id")
    return {
        str(row.skill_id): {
            "unique_skill_title": str(getattr(row, "unique_skill_title", "") or ""),
            "unique_skill_description": str(getattr(row, "unique_skill_description", "") or ""),
        }
        for row in deduped.itertuples(index=False)
    }


def _normalize_title(value: str) -> str:
    return " ".join(_tokens(value))


def _tokens(value: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", str(value).casefold()) if token not in STOPWORDS]


def _token_overlap(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)
