"""Hybrid questionnaire flow for the jobs-skills MVP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import pandas as pd

from jobs_skills.scoring import get_role_requirements, score_all_roles, score_role_fit


@dataclass(frozen=True)
class QuestionOption:
    level: float
    label: str
    explanation: str


@dataclass(frozen=True)
class SkillQuestion:
    question_id: str
    phase: str
    skill_id: str
    unique_skill_title: str
    prompt: str
    skill_description: str
    target_level: float
    tsc_ccs_code: str
    source_row_number: int
    options: tuple[QuestionOption, ...]


@dataclass(frozen=True)
class SkillAnswer:
    question_id: str
    phase: str
    skill_id: str
    unique_skill_title: str
    selected_level: float
    selected_label: str
    confidence: str
    explanation: str


LEVEL_LABELS = {
    0: "Not familiar",
    1: "Just started",
    2: "Used with help",
    3: "Used at work",
    4: "Used often",
    5: "Guide others",
    6: "Set direction",
}

LEVEL_EXPLANATIONS = {
    0: "Maps to level 0: no current evidence for this skill.",
    1: "Maps to level 1: basic familiarity or early learning.",
    2: "Maps to level 2: can use the skill with guidance or examples.",
    3: "Maps to level 3: can use the skill independently in normal work.",
    4: "Maps to level 4: uses the skill often and handles non-routine issues.",
    5: "Maps to level 5: guides others or owns complex work in this skill.",
    6: "Maps to level 6: sets direction or owns organisation-level practice.",
}


def build_options(max_level: float) -> tuple[QuestionOption, ...]:
    upper = max(1, int(max_level))
    options: list[QuestionOption] = []
    for level in range(0, upper + 1):
        label = LEVEL_LABELS.get(level, f"Level {level}")
        explanation = LEVEL_EXPLANATIONS.get(level, f"Maps to proficiency level {level}.")
        options.append(QuestionOption(level=float(level), label=label, explanation=explanation))
    return tuple(options)


def make_question(row: pd.Series, phase: str, target_level: float | None = None) -> SkillQuestion:
    level = float(target_level if target_level is not None else row.required_level)
    description = _question_description(row)
    prompt = (
        f"Skill: {row.unique_skill_title}\n"
        f"What it means: {description}\n"
        f"Choose the closest match to your real work experience.\n"
        f"Dataset target for this role: level {level:g}."
    )
    return SkillQuestion(
        question_id=f"{phase}:{row.skill_id}",
        phase=phase,
        skill_id=str(row.skill_id),
        unique_skill_title=str(row.unique_skill_title),
        prompt=prompt,
        skill_description=description,
        target_level=level,
        tsc_ccs_code=str(row.tsc_ccs_code),
        source_row_number=int(row.source_row_number),
        options=build_options(level),
    )


def _question_description(row: pd.Series, limit: int = 220) -> str:
    for column in ("unique_skill_description", "proficiency_description"):
        value = getattr(row, column, "")
        if pd.notna(value) and str(value).strip():
            text = " ".join(str(value).split())
            if len(text) > limit:
                return text[: limit - 3].rstrip() + "..."
            return text
    return "No dataset description available for this skill."


def select_baseline_questions(requirements: pd.DataFrame, current_role_id: str, count: int = 10) -> list[SkillQuestion]:
    if count < 8 or count > 12:
        raise ValueError("Baseline questionnaire count must stay within the M3 8-12 range")
    role_rows = get_role_requirements(requirements, current_role_id).sort_values(
        ["required_level", "unique_skill_title"], ascending=[False, True]
    )
    selected = role_rows.head(count)
    return [make_question(row, phase="baseline") for _, row in selected.iterrows()]


def answer_question(question: SkillQuestion, selected_level: float, confidence: str = "scripted") -> SkillAnswer:
    option_by_level = {option.level: option for option in question.options}
    if selected_level not in option_by_level:
        allowed = sorted(option_by_level)
        raise ValueError(f"Invalid selected level {selected_level}; allowed levels are {allowed}")
    option = option_by_level[selected_level]
    return SkillAnswer(
        question_id=question.question_id,
        phase=question.phase,
        skill_id=question.skill_id,
        unique_skill_title=question.unique_skill_title,
        selected_level=float(selected_level),
        selected_label=option.label,
        confidence=confidence,
        explanation=(
            f"{question.unique_skill_title}: selected '{option.label}', mapped to level {selected_level:g}. "
            f"{option.explanation}"
        ),
    )


def answers_to_user_vector(answers: Sequence[SkillAnswer]) -> dict[str, float]:
    vector: dict[str, float] = {}
    for answer in answers:
        vector[answer.skill_id] = max(vector.get(answer.skill_id, 0.0), float(answer.selected_level))
    return vector


def apply_answers_to_vector(user_vector: Mapping[str, float], answers: Sequence[SkillAnswer]) -> dict[str, float]:
    updated = dict(user_vector)
    for answer in answers:
        updated[answer.skill_id] = max(updated.get(answer.skill_id, 0.0), float(answer.selected_level))
    return updated


def recommend_pathways(
    requirements: pd.DataFrame,
    user_vector: Mapping[str, float],
    current_role_id: str,
    count: int = 3,
) -> pd.DataFrame:
    ranked = score_all_roles(requirements, user_vector, exclude_role_ids={current_role_id})
    distinct = ranked.drop_duplicates(subset=["job_role", "sector", "track"]).head(count).reset_index(drop=True)
    if len(distinct) < count:
        raise ValueError(f"Only found {len(distinct)} pathway recommendations; expected {count}")
    return distinct


def select_target_gap_questions(
    requirements: pd.DataFrame,
    user_vector: Mapping[str, float],
    target_role_id: str,
    count: int = 5,
) -> tuple[list[SkillQuestion], pd.DataFrame]:
    if count < 3 or count > 5:
        raise ValueError("Follow-up questionnaire count must stay within the M3 3-5 range")
    target_requirements = get_role_requirements(requirements, target_role_id)
    _, gap_table = score_role_fit(user_vector, target_requirements)
    gaps = gap_table.loc[gap_table["gap"] > 0].head(count).copy()
    questions = [make_question(row, phase="followup", target_level=float(row.target_level)) for _, row in gaps.iterrows()]
    return questions, gaps.reset_index(drop=True)


def answer_effects(before_vector: Mapping[str, float], after_vector: Mapping[str, float], target_requirements: pd.DataFrame) -> pd.DataFrame:
    target = target_requirements[["skill_id", "unique_skill_title", "required_level", "tsc_ccs_code", "source_row_number"]].copy()
    target["before_level"] = target["skill_id"].map(before_vector).fillna(0.0).astype(float)
    target["after_level"] = target["skill_id"].map(after_vector).fillna(0.0).astype(float)
    target["level_change"] = target["after_level"] - target["before_level"]
    target["remaining_gap"] = (target["required_level"] - target["after_level"]).clip(lower=0.0)
    changed = target.loc[target["level_change"] > 0].sort_values(
        ["level_change", "required_level", "unique_skill_title"], ascending=[False, False, True]
    )
    return changed.reset_index(drop=True)

