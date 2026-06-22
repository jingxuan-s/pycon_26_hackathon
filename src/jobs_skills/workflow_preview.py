"""Local workflow preview tools for questionnaire and UX review."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from textwrap import shorten
from typing import Iterable

import pandas as pd

from jobs_skills.explainability import build_action_plan, load_skill_ka_items
from jobs_skills.questionnaire import (
    SkillQuestion,
    answer_question,
    answers_to_user_vector,
    recommend_pathways,
    select_baseline_questions,
    select_target_gap_questions,
)
from jobs_skills.scoring import ScoringPaths, get_role_requirements, load_role_skill_requirements, score_role_fit, select_role_id


@dataclass(frozen=True)
class WorkflowPreviewConfig:
    current_job_role: str = "Data Analyst"
    current_sector: str = "Financial Services"
    current_track: str = "Digital and Data Analytics"
    target_job_role: str = "Data Scientist"
    target_sector: str = "Financial Services"
    target_track: str = "Digital and Data Analytics"
    baseline_count: int = 10
    followup_count: int = 5
    compact_description_limit: int = 118
    telegram_message_limit: int = 420


@dataclass(frozen=True)
class QuestionPreview:
    index: int
    total: int
    question: SkillQuestion
    compact_prompt: str
    full_prompt: str
    compact_description: str
    full_dataset_description: str
    flags: tuple[str, ...]


@dataclass(frozen=True)
class WorkflowPreview:
    markdown: str
    issue_count: int
    output_path: Path


def build_local_workflow_preview(project_root: Path, output_path: Path | None = None, config: WorkflowPreviewConfig | None = None) -> WorkflowPreview:
    selected_config = config or WorkflowPreviewConfig()
    paths = ScoringPaths.from_project_root(project_root)
    requirements = _with_skill_descriptions(load_role_skill_requirements(paths.processed_dir), paths.processed_dir)
    ka_items = load_skill_ka_items(paths.processed_dir)

    current_role_id = select_role_id(
        requirements,
        job_role=selected_config.current_job_role,
        sector=selected_config.current_sector,
        track=selected_config.current_track,
    )
    target_role_id = select_role_id(
        requirements,
        job_role=selected_config.target_job_role,
        sector=selected_config.target_sector,
        track=selected_config.target_track,
    )

    baseline_descriptions = _description_lookup(requirements, current_role_id)
    target_descriptions = _description_lookup(requirements, target_role_id)

    baseline_questions = select_baseline_questions(requirements, current_role_id, count=selected_config.baseline_count)
    baseline_answers = [answer_question(question, question.target_level, confidence="local-preview") for question in baseline_questions]
    baseline_vector = answers_to_user_vector(baseline_answers)
    recommendations = recommend_pathways(requirements, baseline_vector, current_role_id, count=3)

    followup_questions, _ = select_target_gap_questions(
        requirements,
        baseline_vector,
        target_role_id,
        count=selected_config.followup_count,
    )
    followup_answers = []
    for question in followup_questions:
        selected_level = max(1.0, question.target_level - 1.0)
        followup_answers.append(answer_question(question, selected_level, confidence="local-preview-followup"))

    target_requirements = get_role_requirements(requirements, target_role_id)
    summary, gap_table = score_role_fit(baseline_vector, target_requirements)
    action_plan = build_action_plan(gap_table, ka_items, max_actions=selected_config.followup_count)

    baseline_previews = preview_questions(
        baseline_questions,
        selected_config,
        phase_label="baseline",
        full_descriptions=baseline_descriptions,
    )
    followup_previews = preview_questions(
        followup_questions,
        selected_config,
        phase_label="follow-up",
        full_descriptions=target_descriptions,
    )
    issues = _collect_flags(baseline_previews) + _collect_flags(followup_previews)

    markdown = render_workflow_preview(
        config=selected_config,
        current_role_id=current_role_id,
        target_role_id=target_role_id,
        recommendations=recommendations,
        baseline_previews=baseline_previews,
        followup_previews=followup_previews,
        summary=summary,
        gap_table=gap_table,
        action_plan=action_plan,
        issues=issues,
    )
    selected_output = output_path or paths.processed_dir / "local_workflow_preview.md"
    selected_output.parent.mkdir(parents=True, exist_ok=True)
    selected_output.write_text(markdown, encoding="utf-8")
    return WorkflowPreview(markdown=markdown, issue_count=len(issues), output_path=selected_output)


def preview_questions(
    questions: Iterable[SkillQuestion],
    config: WorkflowPreviewConfig,
    phase_label: str,
    full_descriptions: dict[str, str] | None = None,
) -> list[QuestionPreview]:
    question_list = list(questions)
    previews: list[QuestionPreview] = []
    for index, question in enumerate(question_list, start=1):
        full_description = (full_descriptions or {}).get(question.skill_id, question.skill_description)
        compact_description = compact_skill_description(full_description, limit=config.compact_description_limit)
        compact_prompt = (
            f"Question {index}/{len(question_list)}\n"
            f"Skill: {question.unique_skill_title}\n"
            f"In simple terms: {compact_description}\n"
            "Choose the option closest to evidence from your work."
        )
        flags = question_flags(
            question=question,
            compact_prompt=compact_prompt,
            full_prompt=full_description,
            phase_label=phase_label,
            telegram_message_limit=config.telegram_message_limit,
        )
        previews.append(
            QuestionPreview(
                index=index,
                total=len(question_list),
                question=question,
                compact_prompt=compact_prompt,
                full_prompt=question.prompt,
                compact_description=compact_description,
                full_dataset_description=full_description,
                flags=tuple(flags),
            )
        )
    return previews


def compact_skill_description(text: str, limit: int = 118) -> str:
    normalized = " ".join(str(text or "").split())
    if not normalized:
        return "No short description available yet."

    candidate = _first_sentence(normalized)
    if len(candidate) <= limit:
        return _ensure_sentence(candidate)

    trimmed = _trim_secondary_clause(candidate)
    if len(trimmed) <= limit:
        return _ensure_sentence(trimmed)

    shortened = shorten(trimmed, width=limit, placeholder="")
    shortened = _strip_hanging_words(shortened.rstrip(" ,;:-"))
    if shortened:
        return _ensure_sentence(shortened)
    return _ensure_sentence(normalized[:limit].rstrip(" ,;:-"))


def question_flags(
    question: SkillQuestion,
    compact_prompt: str,
    full_prompt: str,
    phase_label: str,
    telegram_message_limit: int,
) -> list[str]:
    flags: list[str] = []
    if len(compact_prompt) > telegram_message_limit:
        flags.append(f"{phase_label} compact prompt is {len(compact_prompt)} chars; target <= {telegram_message_limit}")
    if len(full_prompt) > telegram_message_limit:
        flags.append(f"{phase_label} full dataset prompt is {len(full_prompt)} chars; keep out of Telegram")
    if "..." in compact_prompt:
        flags.append(f"{phase_label} compact prompt contains ellipsis-style truncation")
    if len(question.unique_skill_title) > 52:
        flags.append(f"{phase_label} skill title is long and may need a display alias")
    if compact_prompt.split("In simple terms:", 1)[-1].split("Choose the option", 1)[0].strip()[-1:] not in {".", "?", "!"}:
        flags.append(f"{phase_label} compact description does not end as a sentence")
    if len(question.options) > 6:
        flags.append(f"{phase_label} has {len(question.options)} answer options; review button density")
    return flags


def render_workflow_preview(
    config: WorkflowPreviewConfig,
    current_role_id: str,
    target_role_id: str,
    recommendations: pd.DataFrame,
    baseline_previews: list[QuestionPreview],
    followup_previews: list[QuestionPreview],
    summary,
    gap_table: pd.DataFrame,
    action_plan: pd.DataFrame,
    issues: list[str],
) -> str:
    lines: list[str] = [
        "# Local Workflow Preview",
        "",
        "Purpose: refine the assessment workflow, wording, presentation, and user experience before pushing changes into Telegram.",
        "",
        "## Preview Scope",
        "",
        f"- Current role: {config.current_sector} / {config.current_track} / {config.current_job_role}",
        f"- Current role id: `{current_role_id}`",
        f"- Target role: {config.target_sector} / {config.target_track} / {config.target_job_role}",
        f"- Target role id: `{target_role_id}`",
        "- Scoring formulas are unchanged; this artifact reviews presentation only.",
        "",
        "## Product UX Decisions To Review",
        "",
        "- Telegram should show compact prompts only.",
        "- Full dataset descriptions should appear in reports or a local review artifact, not the chat flow.",
        "- Users should see answer labels in plain language while the level mapping remains auditable.",
        "- Recommendation and score explanations should summarize the key reason first, then offer details on request.",
        "",
    ]

    lines.extend(render_questions("Baseline Questions", baseline_previews))
    lines.extend(render_recommendations(recommendations))
    lines.extend(render_questions("Selected-Pathway Follow-Up Questions", followup_previews))
    lines.extend(render_score_and_actions(summary, gap_table, action_plan))
    lines.extend(render_ux_flags(issues))
    return "\n".join(lines) + "\n"


def render_questions(title: str, previews: list[QuestionPreview]) -> list[str]:
    lines = [f"## {title}", ""]
    for preview in previews:
        question = preview.question
        lines.extend(
            [
                f"### Q{preview.index}. {question.unique_skill_title}",
                "",
                "Telegram compact:",
                "",
                "```text",
                preview.compact_prompt,
                "```",
                "",
                "Answer options:",
                "",
            ]
        )
        for option in question.options:
            lines.append(f"- Level {option.level:g}: {option.label} - {option.explanation}")
        lines.extend(
            [
                "",
                "Full dataset detail:",
                "",
                f"> {preview.full_dataset_description}",
                "",
                f"Source: `{question.tsc_ccs_code}`, role-skill row `{question.source_row_number}`",
                "",
            ]
        )
        if preview.flags:
            lines.append("UX flags:")
            lines.extend(f"- {flag}" for flag in preview.flags)
            lines.append("")
    return lines


def render_recommendations(recommendations: pd.DataFrame) -> list[str]:
    lines = ["## Recommendation Presentation", ""]
    for row in recommendations.reset_index(drop=True).itertuples(index=True):
        lines.append(
            f"{row.Index + 1}. {row.job_role} - {row.suitability_percentage:.2f}% fit; "
            f"matched {row.matched_skill_count}/{row.target_skill_count} skills; {row.gap_skill_count} gaps."
        )
        lines.append(f"   Context: {row.sector} / {row.track}")
    lines.extend(
        [
            "",
            "Recommended compact message pattern:",
            "",
            "```text",
            "Recommended pathways",
            "1. Role name - fit %, matched skills, gap count",
            "Why shown: ranked by your answered skill levels against target role requirements.",
            "Choose one path to answer 3-5 focused gap questions.",
            "```",
            "",
        ]
    )
    return lines


def render_score_and_actions(summary, gap_table: pd.DataFrame, action_plan: pd.DataFrame) -> list[str]:
    lines = [
        "## Score And Action Plan Presentation",
        "",
        f"Skill suitability: {summary.suitability_percentage:.2f}%",
        f"Matched skills: {summary.matched_skill_count}/{summary.target_skill_count}",
        f"Gap skills: {summary.gap_skill_count}",
        f"Gap cost: {summary.gap_cost:.2f}",
        "",
        "Top gaps:",
        "",
    ]
    for row in gap_table.loc[gap_table["gap"] > 0].head(5).itertuples(index=False):
        lines.append(f"- {row.unique_skill_title}: you {row.current_level:g}, target {row.target_level:g}, gap {row.gap:g}")
    lines.extend(["", "Action plan preview:", ""])
    for row in action_plan.itertuples(index=False):
        lines.append(f"- {row.skill}: {row.next_action}")
    lines.append("")
    return lines


def render_ux_flags(issues: list[str]) -> list[str]:
    lines = ["## UX Flags", ""]
    if not issues:
        lines.append("No compact prompt issues found against the current local rules.")
        lines.append("")
        return lines
    for issue in issues:
        lines.append(f"- {issue}")
    lines.append("")
    return lines


def _collect_flags(previews: list[QuestionPreview]) -> list[str]:
    flags: list[str] = []
    for preview in previews:
        flags.extend([f"Q{preview.index} {preview.question.unique_skill_title}: {flag}" for flag in preview.flags])
    return flags


def _description_lookup(requirements: pd.DataFrame, role_id: str) -> dict[str, str]:
    role_rows = get_role_requirements(requirements, role_id)
    descriptions: dict[str, str] = {}
    for row in role_rows.itertuples(index=False):
        for column in ("unique_skill_description", "proficiency_description"):
            value = getattr(row, column, "")
            if pd.notna(value) and str(value).strip():
                descriptions[str(row.skill_id)] = " ".join(str(value).split())
                break
    return descriptions


def _with_skill_descriptions(requirements: pd.DataFrame, processed_dir: Path) -> pd.DataFrame:
    skills_path = processed_dir / "skills.csv"
    if not skills_path.exists() or "unique_skill_description" in requirements.columns:
        return requirements
    skills = pd.read_csv(skills_path, usecols=["skill_id", "unique_skill_description"])
    return requirements.merge(skills, on="skill_id", how="left")


def _ensure_sentence(text: str) -> str:
    stripped = text.strip().rstrip(" ,;:-")
    if not stripped:
        return stripped
    if stripped[-1] in ".?!":
        return stripped
    return stripped + "."


def _trim_secondary_clause(text: str) -> str:
    lower = text.casefold()
    for marker in (" in order to ", " in line with ", " according to ", " to enable ", " to support "):
        index = lower.find(marker)
        if index > 40:
            return text[:index].rstrip(" ,;:-") + "."
    return text


def _strip_hanging_words(text: str) -> str:
    cleaned = text.rstrip(" ,;:-")
    last_comma = cleaned.rfind(",")
    if last_comma > 40 and len(cleaned) - last_comma <= 24:
        cleaned = cleaned[:last_comma].rstrip(" ,;:-")

    hanging_words = {"and", "or", "to", "with", "for", "of", "in", "on", "as", "the", "a", "an", "by"}
    words = cleaned.split()
    while words and words[-1].casefold().strip(" ,;:-.") in hanging_words:
        words.pop()
    return " ".join(words).rstrip(" ,;:-")


def _first_sentence(text: str) -> str:
    for separator in (". ", "; ", ": "):
        if separator in text:
            return text.split(separator, 1)[0].strip().rstrip(".;:") + "."
    return text
