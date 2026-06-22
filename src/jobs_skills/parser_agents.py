"""Evidence-first parser agents for resume and job-description stretch flows.

The parser layer extracts auditable skill evidence. It does not decide final
recommendations or suitability scores; deterministic scoring consumes its output.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import re
from typing import Iterable, Mapping, Sequence

import pandas as pd


@dataclass(frozen=True)
class ParsedSkillEvidence:
    skill_id: str
    unique_skill_title: str
    inferred_level: float
    confidence: float
    evidence: str
    reason: str
    uncertainty_flag: bool
    mapping_type: str
    matched_phrase: str


@dataclass(frozen=True)
class ParserResult:
    source_type: str
    extracted_skills: tuple[ParsedSkillEvidence, ...]
    parser_notes: tuple[str, ...] = field(default_factory=tuple)

    def to_user_vector(self) -> dict[str, float]:
        vector: dict[str, float] = {}
        for item in self.extracted_skills:
            vector[item.skill_id] = max(vector.get(item.skill_id, 0.0), float(item.inferred_level))
        return vector


TITLE_ALIASES: Mapping[str, tuple[str, ...]] = {
    "Programming and Coding": (
        "programming",
        "coding",
        "python",
        "sql",
        "r scripts",
        "automation scripts",
        "code",
    ),
    "Data Analytics and Computational Modelling": (
        "data analytics",
        "computational modelling",
        "computational modeling",
        "predictive model",
        "machine learning",
        "statistical model",
        "analytics model",
    ),
    "Data Collection and Analysis": (
        "data collection",
        "data analysis",
        "collect data",
        "analyse data",
        "analyze data",
        "analysed customer data",
        "analyzed customer data",
    ),
    "Data Storytelling and Visualisation": (
        "data storytelling",
        "visualisation",
        "visualization",
        "dashboard",
        "dashboards",
        "power bi",
        "tableau",
        "charts",
    ),
    "Data-mining and Modelling": (
        "data mining",
        "data-mining",
        "modelling",
        "modeling",
        "forecasting",
        "clustering",
        "segmentation",
    ),
    "Data Governance": (
        "data governance",
        "data quality",
        "data handling",
        "data policy",
        "privacy checks",
        "governance checks",
    ),
    "Project Management": (
        "project management",
        "project plan",
        "delivery timeline",
        "managed project",
    ),
    "Stakeholder Management": (
        "stakeholder management",
        "stakeholders",
        "business users",
        "cross-functional",
    ),
    "Business Needs Analysis": (
        "business needs",
        "requirements gathering",
        "business requirements",
        "user requirements",
    ),
    "Data Engineering": (
        "data engineering",
        "etl",
        "data pipeline",
        "data pipelines",
        "extract transform load",
    ),
    "Data Ethics": (
        "data ethics",
        "ethical data",
        "responsible ai",
    ),
    "Software Configuration": (
        "software configuration",
        "version control",
        "git",
        "deployment configuration",
    ),
    "Text Analytics and Processing": (
        "text analytics",
        "natural language processing",
        "nlp",
        "text processing",
    ),
    "Computational Modelling": (
        "computational modelling",
        "computational modeling",
        "simulation model",
        "mathematical model",
    ),
    "Business Intelligence and Data Analytics": (
        "business intelligence",
        "bi dashboard",
        "data analytics",
        "power bi",
        "tableau",
    ),
}

RESUME_LEVEL_CUES: tuple[tuple[float, tuple[str, ...], str], ...] = (
    (5.0, ("set direction", "owned strategy", "led organisation", "mentored", "coach others"), "leadership or coaching evidence"),
    (4.0, ("led", "owned", "designed", "architected", "optimised", "optimized", "advanced"), "ownership of complex or non-routine work"),
    (3.0, ("built", "developed", "implemented", "automated", "analysed", "analyzed", "delivered", "created"), "independent applied work evidence"),
    (2.0, ("used", "supported", "assisted", "prepared", "maintained", "followed"), "guided or routine-use evidence"),
    (1.0, ("familiar", "learning", "course", "trained", "studied"), "basic familiarity evidence"),
)

JD_LEVEL_CUES: tuple[tuple[float, tuple[str, ...], str], ...] = (
    (6.0, ("set enterprise", "organisation-wide", "organization-wide", "head of", "principal"), "organisation-level requirement"),
    (5.0, ("lead", "own", "define strategy", "mentor", "drive adoption", "senior"), "leadership or strategic requirement"),
    (4.0, ("design", "advanced", "optimise", "optimize", "complex", "production", "end-to-end"), "advanced independent requirement"),
    (3.0, ("build", "develop", "implement", "analyse", "analyze", "deliver", "create"), "applied practitioner requirement"),
    (2.0, ("support", "assist", "use", "prepare", "maintain"), "routine-use requirement"),
    (1.0, ("basic", "familiar", "awareness", "exposure"), "basic awareness requirement"),
)


def load_skills(processed_dir) -> pd.DataFrame:
    path = processed_dir / "skills.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing skills file: {path}")
    return pd.read_csv(path)


def parse_resume_text(text: str, skills: pd.DataFrame, max_skills: int = 20) -> ParserResult:
    return _parse_text(
        text=text,
        skills=skills,
        source_type="resume",
        level_cues=RESUME_LEVEL_CUES,
        default_level=2.0,
        max_skills=max_skills,
    )


def parse_jd_text(text: str, skills: pd.DataFrame, max_skills: int = 20) -> ParserResult:
    return _parse_text(
        text=text,
        skills=skills,
        source_type="job_description",
        level_cues=JD_LEVEL_CUES,
        default_level=3.0,
        max_skills=max_skills,
    )



def apply_confirmed_levels(result: ParserResult, confirmed_levels: Mapping[str, float]) -> ParserResult:
    """Return parser output with user-confirmed levels applied by skill_id.

    This is the confirmation hook for uncertain parser mappings. It preserves
    evidence text while marking confirmed skills as high-confidence user input.
    """
    updated: list[ParsedSkillEvidence] = []
    for item in result.extracted_skills:
        if item.skill_id not in confirmed_levels:
            updated.append(item)
            continue
        level = float(confirmed_levels[item.skill_id])
        updated.append(
            replace(
                item,
                inferred_level=level,
                confidence=0.99,
                uncertainty_flag=False,
                reason=f"User confirmed level {level:g}. Original parser reason: {item.reason}",
            )
        )
    notes = tuple(result.parser_notes) + ("One or more parser mappings were confirmed by the user.",)
    return ParserResult(source_type=result.source_type, extracted_skills=tuple(updated), parser_notes=notes)

def parser_result_to_frame(result: ParserResult) -> pd.DataFrame:
    return pd.DataFrame([item.__dict__ for item in result.extracted_skills])


def build_target_requirements_from_jd(result: ParserResult, skills: pd.DataFrame, role_label: str = "Parsed Job Description") -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    skill_lookup = skills.set_index("skill_id")
    for index, item in enumerate(result.extracted_skills, start=1):
        description = ""
        if item.skill_id in skill_lookup.index:
            description = str(skill_lookup.loc[item.skill_id].get("unique_skill_description", ""))
        rows.append(
            {
                "role_skill_requirement_id": f"parsed_jd_req_{index:03d}",
                "role_id": "parsed_jd_role",
                "skill_id": item.skill_id,
                "required_level": float(item.inferred_level),
                "skill_weight": 1.0,
                "sector": "Parsed JD",
                "track": "Parsed JD",
                "job_role": role_label,
                "unique_skill_title": item.unique_skill_title,
                "tsc_ccs_code": "parsed_jd",
                "tsc_ccs_title": item.unique_skill_title,
                "tsc_ccs_type": "parsed",
                "proficiency_level_raw": str(item.inferred_level),
                "proficiency_description": description,
                "source_file": "parser_agent",
                "source_sheet": result.source_type,
                "source_row_number": index,
                "parser_mapping_type": item.mapping_type,
                "parser_confidence": float(item.confidence),
                "parser_evidence": item.evidence,
                "parser_reason": item.reason,
                "parser_uncertainty_flag": bool(item.uncertainty_flag),
                "parser_matched_phrase": item.matched_phrase,
            }
        )
    return pd.DataFrame(rows)


def _parse_text(
    text: str,
    skills: pd.DataFrame,
    source_type: str,
    level_cues: Sequence[tuple[float, Sequence[str], str]],
    default_level: float,
    max_skills: int,
) -> ParserResult:
    if not text.strip():
        return ParserResult(source_type=source_type, extracted_skills=(), parser_notes=("No text was provided.",))

    sentences = _split_sentences(text)
    normalized_text = _normalize(text)
    candidates: list[ParsedSkillEvidence] = []

    for row in skills[["skill_id", "unique_skill_title"]].dropna().itertuples(index=False):
        title = str(row.unique_skill_title)
        aliases = _aliases_for_title(title)
        best: ParsedSkillEvidence | None = None
        for phrase, mapping_type in aliases:
            if not _contains_phrase(normalized_text, phrase):
                continue
            evidence = _best_evidence_sentence(sentences, phrase)
            level, level_reason = _infer_level(evidence, level_cues, default_level)
            confidence = _confidence_for_match(mapping_type, evidence, phrase)
            uncertainty = confidence < 0.75 or level <= 2.0
            item = ParsedSkillEvidence(
                skill_id=str(row.skill_id),
                unique_skill_title=title,
                inferred_level=level,
                confidence=confidence,
                evidence=evidence,
                reason=f"Matched '{phrase}' with {level_reason}.",
                uncertainty_flag=uncertainty,
                mapping_type=mapping_type,
                matched_phrase=phrase,
            )
            if best is None or (item.confidence, item.inferred_level) > (best.confidence, best.inferred_level):
                best = item
        if best is not None:
            candidates.append(best)

    deduped = _suppress_nested_matches(_dedupe_by_skill(candidates))
    ranked = sorted(deduped, key=lambda item: (item.confidence, item.inferred_level, len(item.evidence)), reverse=True)
    notes = (
        "Parser extracts evidence only; deterministic scoring must calculate suitability.",
        "Uncertain low-confidence mappings should be confirmed by the user before production use.",
    )
    return ParserResult(source_type=source_type, extracted_skills=tuple(ranked[:max_skills]), parser_notes=notes)


def _aliases_for_title(title: str) -> tuple[tuple[str, str], ...]:
    phrases: list[tuple[str, str]] = [(_normalize(title), "exact_dataset_title")]
    for alias in TITLE_ALIASES.get(title, ()): 
        phrases.append((_normalize(alias), "inferred_alias"))
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for phrase, mapping_type in phrases:
        if phrase and phrase not in seen:
            seen.add(phrase)
            unique.append((phrase, mapping_type))
    return tuple(unique)


def _dedupe_by_skill(items: Iterable[ParsedSkillEvidence]) -> tuple[ParsedSkillEvidence, ...]:
    best_by_skill: dict[str, ParsedSkillEvidence] = {}
    for item in items:
        current = best_by_skill.get(item.skill_id)
        if current is None or (item.confidence, item.inferred_level) > (current.confidence, current.inferred_level):
            best_by_skill[item.skill_id] = item
    return tuple(best_by_skill.values())



def _suppress_nested_matches(items: Sequence[ParsedSkillEvidence]) -> tuple[ParsedSkillEvidence, ...]:
    kept: list[ParsedSkillEvidence] = []
    for item in items:
        phrase = _normalize(item.matched_phrase)
        is_nested = False
        for other in items:
            if other.skill_id == item.skill_id:
                continue
            other_phrase = _normalize(other.matched_phrase)
            if not phrase or not other_phrase or phrase == other_phrase:
                continue
            same_evidence = _normalize(item.evidence) == _normalize(other.evidence)
            more_specific = len(other_phrase.split()) > len(phrase.split()) and phrase in other_phrase
            if same_evidence and more_specific and other.confidence >= item.confidence - 0.05:
                is_nested = True
                break
        if not is_nested:
            kept.append(item)
    return tuple(kept)

def _split_sentences(text: str) -> list[str]:
    normalized_lines = re.sub(r"[\r\n]+", " ", text)
    parts = re.split(r"(?<=[.!?])\s+|;+", normalized_lines)
    return [part.strip(" -\t") for part in parts if part.strip()]


def _normalize(text: str) -> str:
    lowered = text.casefold().replace("&", " and ")
    return re.sub(r"[^a-z0-9+#.]+", " ", lowered).strip()


def _contains_phrase(normalized_text: str, phrase: str) -> bool:
    if not phrase:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", normalized_text) is not None


def _best_evidence_sentence(sentences: Sequence[str], phrase: str) -> str:
    for sentence in sentences:
        if _contains_phrase(_normalize(sentence), phrase):
            return sentence[:280]
    return phrase


def _infer_level(evidence: str, cues: Sequence[tuple[float, Sequence[str], str]], default_level: float) -> tuple[float, str]:
    normalized = _normalize(evidence)
    year_bonus = 0.0
    year_match = re.search(r"(\d+)\+?\s+years?", normalized)
    if year_match and int(year_match.group(1)) >= 3:
        year_bonus = 1.0

    for level, phrases, reason in cues:
        for phrase in phrases:
            if _contains_phrase(normalized, _normalize(phrase)):
                return min(6.0, level + year_bonus), reason
    return default_level, "default level because evidence names the skill but gives limited proficiency detail"


def _confidence_for_match(mapping_type: str, evidence: str, phrase: str) -> float:
    base = 0.90 if mapping_type == "exact_dataset_title" else 0.72
    normalized_evidence = _normalize(evidence)
    if len(phrase.split()) >= 2:
        base += 0.05
    if any(term in normalized_evidence for term in ("built", "developed", "required", "must", "led", "designed")):
        base += 0.05
    return min(base, 0.95)
