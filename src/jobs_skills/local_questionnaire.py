"""Interactive local questionnaire runner for the jobs-skills MVP."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

import pandas as pd

from jobs_skills.explainability import build_action_plan, load_skill_ka_items
from jobs_skills.explainer_agent import ExplanationResult, load_explainer_agent_from_env
from jobs_skills.pathway_graph import PathwayPolicy, build_transition_edge
from jobs_skills.questionnaire import (
    SkillAnswer,
    SkillQuestion,
    answer_question,
    answers_to_user_vector,
    apply_answers_to_vector,
    recommend_pathways,
    select_baseline_questions,
    select_target_gap_questions,
)
from jobs_skills.scoring import ScoringPaths, get_role_requirements, load_role_skill_requirements, score_role_fit, select_role_id
from jobs_skills.workflow_preview import compact_skill_description


InputFunc = Callable[[str], str]
OutputFunc = Callable[[str], None]


@dataclass(frozen=True)
class RoleChoice:
    label: str
    job_role: str
    sector: str
    track: str


@dataclass(frozen=True)
class LocalQuestionnaireResult:
    current_role_id: str
    selected_role_id: str
    suitability_percentage: float
    pathway_fit_percentage: float
    baseline_answer_count: int
    followup_answer_count: int
    report_path: Path


DEFAULT_ROLE_CHOICES = (
    RoleChoice(
        label="Data analyst",
        job_role="Data Analyst",
        sector="Financial Services",
        track="Digital and Data Analytics",
    ),
    RoleChoice(
        label="Business analyst",
        job_role="Associate Business Analyst",
        sector="Infocomm Technology",
        track="Strategy and Governance",
    ),
    RoleChoice(
        label="Logistics data specialist",
        job_role="Logistics Data Specialist / Master Data Analyst / Master Data Executive",
        sector="Logistics",
        track="Logistics Process Improvement and Information System",
    ),
)


class LocalQuestionnaireRunner:
    """Run the hybrid questionnaire in a terminal-friendly local flow."""

    def __init__(
        self,
        project_root: Path,
        input_func: InputFunc = input,
        output_func: OutputFunc = print,
        baseline_count: int = 10,
        followup_count: int = 5,
    ) -> None:
        self.project_root = project_root.resolve()
        self.input_func = input_func
        self.output_func = output_func
        self.baseline_count = baseline_count
        self.followup_count = followup_count
        self.paths = ScoringPaths.from_project_root(self.project_root)
        self.requirements = self._with_skill_descriptions(load_role_skill_requirements(self.paths.processed_dir))
        self.ka_items = load_skill_ka_items(self.paths.processed_dir)
        self.explainer = load_explainer_agent_from_env(self.project_root)

    def run(self) -> LocalQuestionnaireResult:
        self._print_header()
        current_role_id = self._choose_current_role()
        current_role = self._role_by_id(current_role_id)
        self._say("")
        self._say(f"Current role baseline: {current_role.job_role}")
        self._say(f"Domain: {current_role.sector} / {current_role.track}")
        self._say("Answer based on evidence from work, school, projects, or hands-on practice.")

        baseline_questions = select_baseline_questions(self.requirements, current_role_id, count=self.baseline_count)
        baseline_answers = self._ask_questions(baseline_questions, phase_title="Baseline")
        baseline_vector = answers_to_user_vector(baseline_answers)

        recommendations = recommend_pathways(self.requirements, baseline_vector, current_role_id, count=3)
        selected_role_id = self._choose_recommendation(recommendations, current_role=current_role)
        selected_role = self._role_by_id(selected_role_id)

        self._say("")
        self._say(f"Selected pathway: {selected_role.job_role}")
        self._say("Now answer a few focused questions about the largest gaps for that pathway.")
        followup_questions, _ = select_target_gap_questions(
            self.requirements,
            baseline_vector,
            selected_role_id,
            count=self.followup_count,
        )
        followup_answers = self._ask_questions(followup_questions, phase_title="Follow-up")
        refined_vector = apply_answers_to_vector(baseline_vector, followup_answers)

        target_requirements = get_role_requirements(self.requirements, selected_role_id)
        summary, gap_table = score_role_fit(refined_vector, target_requirements)
        edge = build_transition_edge(self.requirements, current_role_id, selected_role_id, PathwayPolicy())
        action_plan = build_action_plan(gap_table, self.ka_items, max_actions=5)
        score_insight = self.explainer.explain_score(summary, gap_table)
        report_path = self._write_report(
            current_role=current_role,
            selected_role=selected_role,
            baseline_answers=baseline_answers,
            followup_answers=followup_answers,
            summary=summary,
            gap_table=gap_table,
            edge=edge,
            action_plan=action_plan,
            score_insight=score_insight,
        )

        self._print_result(summary, gap_table, edge, action_plan, report_path, score_insight)
        return LocalQuestionnaireResult(
            current_role_id=current_role_id,
            selected_role_id=selected_role_id,
            suitability_percentage=summary.suitability_percentage,
            pathway_fit_percentage=float(edge["edge_fit_percentage"]),
            baseline_answer_count=len(baseline_answers),
            followup_answer_count=len(followup_answers),
            report_path=report_path,
        )

    def _print_header(self) -> None:
        self._say("Local Career Pathway Questionnaire")
        self._say("This runs the same questionnaire and scoring logic without Telegram.")
        self._say("All MVP skill weights are 1.0. You can stop with Ctrl+C.")

    def _choose_current_role(self) -> str:
        while True:
            self._say("")
            self._say("Choose your closest current role:")
            for index, choice in enumerate(DEFAULT_ROLE_CHOICES, start=1):
                self._say(f"  {index}. {choice.label} - {choice.sector} / {choice.track}")
            self._say("  s. Search roles")
            selected = self._ask("Select 1-3, or s to search [1]: ").strip().casefold() or "1"
            if selected == "s":
                role_id = self._search_and_choose_role()
                if role_id:
                    return role_id
                continue
            if selected in {"1", "2", "3"}:
                choice = DEFAULT_ROLE_CHOICES[int(selected) - 1]
                return select_role_id(
                    self.requirements,
                    job_role=choice.job_role,
                    sector=choice.sector,
                    track=choice.track,
                )
            self._say("Please enter 1, 2, 3, or s.")

    def _search_and_choose_role(self) -> str | None:
        while True:
            query = self._ask("Search current role/domain, or blank to go back: ").strip()
            if not query:
                return None
            matches = self._search_roles(query, limit=8)
            if matches.empty:
                self._say("No matching roles found. Try a broader term such as data, analyst, logistics, finance, or technology.")
                continue
            self._say("")
            self._say(f"Search results for: {query}")
            for index, row in enumerate(matches.itertuples(index=False), start=1):
                self._say(f"  {index}. {row.job_role}")
                self._say(f"     {row.sector} / {row.track}")
            selected = self._ask("Select a result number, or blank to search again: ").strip()
            if not selected:
                continue
            if selected.isdigit() and 1 <= int(selected) <= len(matches):
                return str(matches.iloc[int(selected) - 1].role_id)
            self._say("Invalid selection.")

    def _ask_questions(self, questions: Iterable[SkillQuestion], phase_title: str) -> list[SkillAnswer]:
        question_list = list(questions)
        answers: list[SkillAnswer] = []
        for index, question in enumerate(question_list, start=1):
            self._say("")
            self._say(f"{phase_title} question {index}/{len(question_list)}")
            self._say(f"Skill: {question.unique_skill_title}")
            self._say(f"In simple terms: {compact_skill_description(question.skill_description)}")
            self._say("Choose the closest match to your real experience:")
            for option in question.options:
                self._say(f"  {option.level:g}. {option.label}")
            level = self._ask_level(question)
            answer = answer_question(question, level, confidence="local-interactive")
            answers.append(answer)
            self._say(f"Recorded: {answer.selected_label} -> level {answer.selected_level:g}")
        return answers

    def _ask_level(self, question: SkillQuestion) -> float:
        allowed = {option.level for option in question.options}
        allowed_text = ", ".join(f"{level:g}" for level in sorted(allowed))
        while True:
            raw = self._ask(f"Enter level ({allowed_text}): ").strip()
            try:
                level = float(raw)
            except ValueError:
                self._say("Please enter one of the listed numbers.")
                continue
            if level in allowed:
                return level
            self._say("Please enter one of the listed numbers.")

    def _choose_recommendation(self, recommendations: pd.DataFrame, current_role: pd.Series) -> str:
        self._say("")
        self._say("Recommended pathways")
        self._say("Why these: ranked by your answered skill levels against each role's required skill levels.")
        for index, row in enumerate(recommendations.itertuples(index=False), start=1):
            self._say(
                f"  {index}. {row.job_role} - {row.suitability_percentage:.2f}% fit; "
                f"matched {row.matched_skill_count}/{row.target_skill_count}; gaps {row.gap_skill_count}"
            )
            self._say(f"     {row.sector} / {row.track}")
        recommendation_insight = self.explainer.explain_recommendations(recommendations, current_role=current_role)
        self._say("")
        self._say(recommendation_insight.text)
        self._say(f"Explanation source: {recommendation_insight.source}")
        while True:
            raw = self._ask("Choose pathway 1-3 [1]: ").strip() or "1"
            if raw.isdigit() and 1 <= int(raw) <= len(recommendations):
                return str(recommendations.iloc[int(raw) - 1].role_id)
            self._say("Please enter 1, 2, or 3.")

    def _print_result(
        self,
        summary,
        gap_table: pd.DataFrame,
        edge: dict[str, object],
        action_plan: pd.DataFrame,
        report_path: Path,
        score_insight: ExplanationResult,
    ) -> None:
        self._say("")
        self._say("Assessment result")
        self._say(f"Target role: {summary.job_role}")
        self._say(f"Skill suitability: {summary.suitability_percentage:.2f}%")
        self._say(f"Pathway fit: {float(edge['edge_fit_percentage']):.2f}%")
        self._say(f"Matched skills: {summary.matched_skill_count}/{summary.target_skill_count}")
        self._say(f"Skills below target: {summary.gap_skill_count}")
        self._say("")
        self._say(score_insight.text)
        self._say(f"Explanation source: {score_insight.source}")
        self._say("")
        self._say("Top gaps")
        gaps = gap_table.loc[gap_table["gap"] > 0].head(5)
        if gaps.empty:
            self._say("  No remaining gaps for this selected role.")
        for row in gaps.itertuples(index=False):
            self._say(f"  - {row.unique_skill_title}: you {row.current_level:g}, target {row.target_level:g}, gap {row.gap:g}")
        self._say("")
        self._say("Next actions")
        for row in action_plan.itertuples(index=False):
            self._say(f"  - {row.skill}: {row.next_action}")
        self._say("")
        self._say(f"Full result report: {report_path}")

    def _write_report(
        self,
        current_role: pd.Series,
        selected_role: pd.Series,
        baseline_answers: list[SkillAnswer],
        followup_answers: list[SkillAnswer],
        summary,
        gap_table: pd.DataFrame,
        edge: dict[str, object],
        action_plan: pd.DataFrame,
        score_insight: ExplanationResult,
    ) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.paths.processed_dir / f"local_questionnaire_result_{timestamp}.md"
        lines = [
            "# Local Questionnaire Result",
            "",
            "## Roles",
            "",
            f"- Current role: {current_role.job_role} ({current_role.sector} / {current_role.track})",
            f"- Selected target: {selected_role.job_role} ({selected_role.sector} / {selected_role.track})",
            "",
            "## Scores",
            "",
            f"- Skill suitability: {summary.suitability_percentage:.2f}%",
            f"- Pathway fit: {float(edge['edge_fit_percentage']):.2f}%",
            f"- Matched skills: {summary.matched_skill_count}/{summary.target_skill_count}",
            f"- Skills below target: {summary.gap_skill_count}",
            "- All MVP skill weights are 1.0.",
            "",
            "## Score Explanation",
            "",
            score_insight.text,
            "",
            f"Explanation source: {score_insight.source}",
            "",
            "## Baseline Answers",
            "",
        ]
        lines.extend(_answer_lines(baseline_answers))
        lines.extend(["", "## Follow-up Answers", ""])
        lines.extend(_answer_lines(followup_answers))
        lines.extend(["", "## Top Gaps", ""])
        for row in gap_table.loc[gap_table["gap"] > 0].head(10).itertuples(index=False):
            lines.append(f"- {row.unique_skill_title}: current {row.current_level:g}, target {row.target_level:g}, gap {row.gap:g}")
        lines.extend(["", "## Action Plan", ""])
        for row in action_plan.itertuples(index=False):
            lines.append(f"- {row.skill}: {row.next_action}")
            lines.append(f"  Source: K&A row {row.ka_source_row_number}; role-skill row {row.role_skill_source_row_number}.")
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return output_path

    def _role_catalog(self) -> pd.DataFrame:
        return self.requirements[["role_id", "sector", "track", "job_role"]].drop_duplicates().reset_index(drop=True)

    def _role_by_id(self, role_id: str) -> pd.Series:
        matches = self._role_catalog().loc[self._role_catalog()["role_id"].eq(role_id)]
        if matches.empty:
            raise ValueError(f"Unknown role_id={role_id!r}")
        return matches.iloc[0]

    def _search_roles(self, query: str, limit: int = 8) -> pd.DataFrame:
        catalog = self._role_catalog().copy()
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

    def _with_skill_descriptions(self, requirements: pd.DataFrame) -> pd.DataFrame:
        skills_path = self.paths.processed_dir / "skills.csv"
        if not skills_path.exists() or "unique_skill_description" in requirements.columns:
            return requirements
        skills = pd.read_csv(skills_path, usecols=["skill_id", "unique_skill_description"])
        return requirements.merge(skills, on="skill_id", how="left")

    def _ask(self, prompt: str) -> str:
        return self.input_func(prompt)

    def _say(self, text: str) -> None:
        self.output_func(text)


def _answer_lines(answers: list[SkillAnswer]) -> list[str]:
    if not answers:
        return ["- No answers recorded."]
    return [f"- {answer.unique_skill_title}: {answer.selected_label} (level {answer.selected_level:g})" for answer in answers]
