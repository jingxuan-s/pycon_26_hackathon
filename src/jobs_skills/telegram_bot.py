"""Telegram-style MVP interaction layer for the jobs-skills career pathway tool."""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Any

import pandas as pd

from jobs_skills.document_ingestion import document_text_from_pasted_input, extract_text_from_file
from jobs_skills.explainability import build_action_plan, load_skill_ka_items
from jobs_skills.explainer_agent import load_explainer_agent_from_env
from jobs_skills.pathway_graph import PathwayPolicy, build_transition_edge, derive_pathway_graph, dijkstra_path, path_edges, pathway_fit_percentage
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
from jobs_skills.resume_recommender import (
    ReviewedSkillProfile,
    TargetModeResult,
    add_profile_skill,
    build_profile_from_role,
    build_target_result_for_jd,
    build_target_result_for_role,
    edit_profile_level,
    load_resume_workflow_context,
    parse_resume_document,
    recommend_advance_targets,
    recommend_explore_targets,
    render_result_report_markdown,
    remove_profile_item,
    search_skills,
    valid_levels_for_skill,
    write_result_report,
)
from jobs_skills.related_skills import (
    RelatedSkillMatch,
    build_related_skill_notes,
    related_skill_debug_note,
    related_skill_normal_note,
)
from jobs_skills.scoring import ScoringPaths, get_role_requirements, load_role_skill_requirements, score_role_fit, select_role_id


@dataclass(frozen=True)
class CurrentRoleProfile:
    key: str
    label: str
    job_role: str
    sector: str
    track: str


REVIEW_PAGE_SIZE = 5


CURRENT_ROLE_PROFILES = (
    CurrentRoleProfile(
        key="data_analyst_fs",
        label="Data analyst",
        job_role="Data Analyst",
        sector="Financial Services",
        track="Digital and Data Analytics",
    ),
    CurrentRoleProfile(
        key="business_analyst_it",
        label="Business analyst",
        job_role="Associate Business Analyst",
        sector="Infocomm Technology",
        track="Strategy and Governance",
    ),
    CurrentRoleProfile(
        key="data_specialist_logistics",
        label="Data specialist",
        job_role="Logistics Data Specialist / Master Data Analyst",
        sector="Logistics",
        track="Logistics Process Improvement and Information System",
    ),
    CurrentRoleProfile(
        key="not_sure_demo",
        label="Not sure - use demo",
        job_role="Data Analyst",
        sector="Financial Services",
        track="Digital and Data Analytics",
    ),
)


@dataclass(frozen=True)
class InlineButton:
    label: str
    action: str
    value: str


@dataclass(frozen=True)
class BotResponse:
    text: str
    buttons: tuple[InlineButton, ...] = ()
    attachment_path: str | None = None
    attachment_name: str | None = None
    attachment_content: str | bytes | None = None


@dataclass
class SessionState:
    session_id: str
    current_role_id: str | None = None
    current_role_profile_key: str | None = None
    baseline_questions: list[SkillQuestion] = field(default_factory=list)
    baseline_answers: list[SkillAnswer] = field(default_factory=list)
    recommendations: pd.DataFrame | None = None
    selected_role_id: str | None = None
    gap_questions: list[SkillQuestion] = field(default_factory=list)
    gap_answers: list[SkillAnswer] = field(default_factory=list)
    baseline_vector: dict[str, float] = field(default_factory=dict)
    refined_vector: dict[str, float] = field(default_factory=dict)
    resume_profile: ReviewedSkillProfile | None = None
    resume_recommendations: pd.DataFrame | None = None
    resume_result: TargetModeResult | None = None
    resume_target_mode: str | None = None
    waiting_for_jd_text: bool = False
    resume_review_page: int = 0
    pending_text_mode: str | None = None
    pending_edit_index: int | None = None
    pending_add_skill_id: str | None = None
    pending_add_skill_title: str | None = None


class TelegramCareerBotService:
    """Pure-Python command handler surface for Telegram integration tests."""

    def __init__(self, project_root: Path, debug_mode: bool = False) -> None:
        self.paths = ScoringPaths.from_project_root(project_root)
        self.requirements = self._with_skill_descriptions(load_role_skill_requirements(self.paths.processed_dir))
        self.ka_items = load_skill_ka_items(self.paths.processed_dir)
        self.explainer = load_explainer_agent_from_env(project_root)
        self.resume_context = load_resume_workflow_context(project_root)
        self.sessions: dict[str, SessionState] = {}
        self.debug_mode = debug_mode

    def get_session(self, session_id: str) -> SessionState:
        return self.sessions.setdefault(session_id, SessionState(session_id=session_id))

    def start(self, session_id: str) -> BotResponse:
        session = self.get_session(session_id)
        self._reset_session(session)
        return BotResponse(
            "<b>Hi, I'm Casey the Career Auntie.</b>\n"
            "Come, we sort out your next career move step by step.\n\n"
            "I can help you read your skills, compare them with SkillsFuture roles, and turn the gaps into practical next actions.\n\n"
            "<b>Upload resume</b>\n"
            "I'll extract draft skills from your resume. You review first, then we score.\n\n"
            "<b>Search role</b>\n"
            "No resume? No problem. Pick a SkillsFuture role and we start from there.\n\n"
            "<b>First-time guide</b>\n"
            "New here? I'll explain how the recommender works before we begin.",
            (
                InlineButton("First-time guide", "first_time_user", ""),
                InlineButton("Upload resume", "start_resume", ""),
                InlineButton("Search role", "start_role_search", ""),
            ),
        )

    def first_time_user(self, session_id: str) -> BotResponse:
        self.get_session(session_id)
        return BotResponse(
            "<b>First-time guide</b>\n"
            "Hi, I'm Casey. I help you explore career pathways, compare yourself with a target role, "
            "and turn skill gaps into an action plan you can actually use.\n\n"
            "<b>How it works</b>\n"
            "1. Start with a resume upload or a dataset role search.\n"
            "2. Casey shows draft skills, but you review them before scoring.\n"
            "3. Choose a target role, explore pathways, advance in a similar track, or paste a JD.\n"
            "4. View suitability, skill gaps, and actions backed by SkillsFuture proficiency and K&A rows.\n\n"
            "<b>Privacy boundary</b>\n"
            "Raw resume and JD text is used at runtime only. Reports keep reviewed skills, evidence summaries, and scoring outputs.",
            (
                InlineButton("Upload resume", "start_resume", ""),
                InlineButton("Search role", "start_role_search", ""),
                InlineButton("Back", "start", ""),
            ),
        )

    def start_resume_flow(self, session_id: str) -> BotResponse:
        session = self.get_session(session_id)
        self._reset_session(session)
        return BotResponse(
            "<b>Resume pathway mode</b>\n"
            "Upload your resume as a PDF or DOCX.\n\n"
            "Casey will show a compact skill summary first, then you can review every skill before scoring.",
        )

    def parse_resume_upload(self, session_id: str, file_path: Path) -> BotResponse:
        session = self.get_session(session_id)
        self._reset_session(session)
        try:
            document = extract_text_from_file(file_path)
            profile = parse_resume_document(document, self.resume_context)
        finally:
            try:
                file_path.unlink(missing_ok=True)
            except OSError:
                pass
        session.resume_profile = profile
        return self._resume_profile_summary_response(session)

    def confirm_resume_skills(self, session_id: str) -> BotResponse:
        session = self.get_session(session_id)
        if session.resume_profile is None:
            return BotResponse("Upload a resume first with /start_resume.")
        return BotResponse(
            "<b>Skills confirmed for scoring.</b>\n"
            "Okay, now Casey can compare your profile properly.\n\n"
            "<b>Explore pathways</b>\n"
            "I'll automatically find nearby roles that fit your confirmed skills.\n\n"
            "<b>Advance roles</b>\n"
            "Want to move up in a similar track? I'll look for higher-level roles with manageable gaps.\n\n"
            "<b>Search target role</b>\n"
            "Already have a role in mind? Search the dataset role name and I'll compare it with your profile.\n\n"
            "<b>Paste JD</b>\n"
            "Applying for a job? Paste the job description and I'll compare your current skills against it.",
            self._resume_target_buttons(),
        )

    def review_resume_skills(self, session_id: str, page: int = 0) -> BotResponse:
        session = self.get_session(session_id)
        if session.resume_profile is None:
            return BotResponse("Upload a resume first with /start_resume.")
        session.resume_review_page = max(0, page)
        return self._resume_review_page_response(session)

    def edit_resume_skill(self, session_id: str, index_text: str) -> BotResponse:
        session = self.get_session(session_id)
        if session.resume_profile is None:
            return BotResponse("Upload a resume first with /start_resume.")
        index = int(index_text)
        if index < 0 or index >= len(session.resume_profile.items):
            return self._resume_review_page_response(session, note="That skill is no longer available.")
        session.pending_edit_index = index
        item = session.resume_profile.items[index]
        buttons = self._level_buttons_for_skill(item.skill_id, "resume_set_level", str(index)) + (
            InlineButton("Back to review", "resume_back_review", ""),
        )
        lines = [
            "<b>Set level</b>",
            f"{_h(item.unique_skill_title)}",
            f"Current level: {item.level:g}",
            "",
        ]
        lines.extend(self._skill_level_guidance_lines(item.skill_id))
        return BotResponse("\n".join(lines), buttons)

    def set_resume_skill_level(self, session_id: str, value: str) -> BotResponse:
        session = self.get_session(session_id)
        if session.resume_profile is None:
            return BotResponse("Upload a resume first with /start_resume.")
        index_text, level_text = value.split(":", 1)
        session.resume_profile = edit_profile_level(session.resume_profile, int(index_text), float(level_text), self.ka_items)
        session.pending_edit_index = None
        return self._resume_review_page_response(session, note="Skill level updated.")

    def remove_resume_skill(self, session_id: str, index_text: str) -> BotResponse:
        session = self.get_session(session_id)
        if session.resume_profile is None:
            return BotResponse("Upload a resume first with /start_resume.")
        session.resume_profile = remove_profile_item(session.resume_profile, int(index_text))
        max_page = max(0, (len(session.resume_profile.items) - 1) // REVIEW_PAGE_SIZE) if session.resume_profile.items else 0
        session.resume_review_page = min(session.resume_review_page, max_page)
        return self._resume_review_page_response(session, note="Skill removed.")

    def prompt_add_resume_skill(self, session_id: str) -> BotResponse:
        session = self.get_session(session_id)
        if session.resume_profile is None:
            return BotResponse("Upload a resume first with /start_resume.")
        session.pending_text_mode = "add_skill_search"
        return BotResponse(
            "Type a broad SkillsFuture capability, not only a specific tool or vendor.\n\n"
            "Examples: Programming and Coding for Python or SQL, Data Storytelling and Visualisation for Power BI or Tableau, Data Governance, or Stakeholder Management.",
            (InlineButton("Back to review", "resume_back_review", ""),),
        )

    def search_resume_add_skills(self, session_id: str, query: str) -> BotResponse:
        session = self.get_session(session_id)
        if session.resume_profile is None:
            session.pending_text_mode = None
            return BotResponse("Upload a resume first with /start_resume.")
        matches = search_skills(self.resume_context.skills, query, limit=5)
        if matches.empty:
            session.pending_text_mode = "add_skill_search"
            return BotResponse("No matching SkillsFuture skill found. Try a broader capability name such as Programming and Coding, Data Governance, Data Storytelling and Visualisation, or Stakeholder Management.", (InlineButton("Back to review", "resume_back_review", ""),))
        buttons = tuple(InlineButton(str(row.unique_skill_title)[:54], "resume_add_select", str(row.skill_id)) for row in matches.itertuples(index=False)) + (
            InlineButton("Back to review", "resume_back_review", ""),
        )
        lines = [f"Skill search: {query}", "SkillsFuture uses broad capability names. If you searched for a tool, tech stack, or work task, choose the closest broader skill below.", "Choose the skill to add:", ""]
        for index, row in enumerate(matches.itertuples(index=False), start=1):
            lines.append(f"{index}. {row.unique_skill_title}")
        return BotResponse("\n".join(lines), buttons)

    def select_resume_add_skill(self, session_id: str, skill_id: str) -> BotResponse:
        session = self.get_session(session_id)
        if session.resume_profile is None:
            return BotResponse("Upload a resume first with /start_resume.")
        matches = self.resume_context.skills.loc[self.resume_context.skills["skill_id"].astype(str).eq(str(skill_id))]
        if matches.empty:
            return self._resume_review_page_response(session, note="That skill could not be found.")
        row = matches.iloc[0]
        session.pending_add_skill_id = str(row.skill_id)
        session.pending_add_skill_title = str(row.unique_skill_title)
        session.pending_text_mode = None
        buttons = self._level_buttons_for_skill(str(row.skill_id), "resume_add_level", str(row.skill_id)) + (
            InlineButton("Back to review", "resume_back_review", ""),
        )
        lines = ["<b>Choose your current level</b>", f"{_h(row.unique_skill_title)}", ""]
        lines.extend(self._skill_level_guidance_lines(str(row.skill_id)))
        return BotResponse("\n".join(lines), buttons)

    def add_resume_skill_level(self, session_id: str, value: str) -> BotResponse:
        session = self.get_session(session_id)
        if session.resume_profile is None:
            return BotResponse("Upload a resume first with /start_resume.")
        skill_id, level_text = value.split(":", 1)
        session.resume_profile = add_profile_skill(session.resume_profile, self.resume_context.skills, skill_id, float(level_text), ka_items=self.ka_items)
        session.resume_review_page = max(0, (len(session.resume_profile.items) - 1) // REVIEW_PAGE_SIZE)
        session.pending_add_skill_id = None
        session.pending_add_skill_title = None
        return self._resume_review_page_response(session, note="Skill added.")

    def back_to_resume_review(self, session_id: str) -> BotResponse:
        session = self.get_session(session_id)
        session.pending_text_mode = None
        session.pending_edit_index = None
        session.pending_add_skill_id = None
        session.pending_add_skill_title = None
        return self.review_resume_skills(session_id, session.resume_review_page)

    def back_to_resume_targets(self, session_id: str) -> BotResponse:
        session = self.get_session(session_id)
        session.waiting_for_jd_text = False
        session.pending_text_mode = None
        return self.confirm_resume_skills(session_id)

    def confirm_back_to_start(self, session_id: str) -> BotResponse:
        self.get_session(session_id)
        return BotResponse(
            "<b>Back to start?</b>\nThis will clear the current skill review and restart the workflow.",
            (
                InlineButton("Yes, restart", "start", ""),
                InlineButton("No, return to review", "resume_back_review", ""),
            ),
        )

    def explain_resume_skills(self, session_id: str) -> BotResponse:
        session = self.get_session(session_id)
        if session.resume_profile is None:
            return BotResponse("Upload a resume first with /start_resume.")
        lines = ["<b>Why these skills?</b>", "I extracted evidence, mapped it to SkillsFuture skills, then capped uncertain levels before scoring.", ""]
        for item in session.resume_profile.items:
            lines.append(f"- <b>{_h(item.unique_skill_title)}</b> - Level {item.level:g}{_review_status_label(item)}")
            lines.append(f"  <i>Why:</i> {_h(_user_facing_skill_reason(item))}")
        lines.append("")
        lines.append("Use Review skills to edit levels, remove skills, or add missing SkillsFuture skills before scoring.")
        return BotResponse("\n".join(lines), self._resume_review_buttons())

    def start_resume_explore(self, session_id: str) -> BotResponse:
        session = self.get_session(session_id)
        if session.resume_profile is None:
            return BotResponse("Upload and confirm a resume first with /start_resume.")
        session.resume_target_mode = "explore_pathways"
        session.resume_recommendations = recommend_explore_targets(self.resume_context, session.resume_profile, count=6)
        return self._resume_recommendations_response(session, "Explore pathways")

    def start_resume_advance(self, session_id: str) -> BotResponse:
        session = self.get_session(session_id)
        if session.resume_profile is None:
            return BotResponse("Upload and confirm a resume first with /start_resume.")
        session.resume_target_mode = "advance_roles"
        session.resume_recommendations = recommend_advance_targets(self.resume_context, session.resume_profile, count=6)
        return self._resume_recommendations_response(session, "Advance roles")

    def choose_resume_target_role(self, session_id: str, role_id: str) -> BotResponse:
        session = self.get_session(session_id)
        if session.resume_profile is None or session.resume_recommendations is None:
            return BotResponse("Choose a resume target mode first.", self._resume_target_buttons())
        if role_id not in set(session.resume_recommendations["role_id"].astype(str)):
            return BotResponse("Choose one of the listed target buttons.", self._resume_target_buttons())
        mode = session.resume_target_mode or "explore_pathways"
        result = build_target_result_for_role(
            self.resume_context,
            session.resume_profile,
            role_id,
            mode,
            session.resume_recommendations,
        )
        session.resume_result = result
        return self._resume_result_response(result)

    def start_resume_jd_text(self, session_id: str) -> BotResponse:
        session = self.get_session(session_id)
        if session.resume_profile is None:
            return BotResponse("Upload and confirm a resume first with /start_resume.")
        session.waiting_for_jd_text = True
        return BotResponse(
            "Paste the job description in your next message.\n"
            "I will parse the JD, compare it with your confirmed resume skills, and return a compact suitability result.",
            (InlineButton("Back", "resume_back_targets", ""),),
        )

    def handle_resume_jd_text(self, session_id: str, text: str) -> BotResponse:
        session = self.get_session(session_id)
        if not session.waiting_for_jd_text:
            return BotResponse("Use /start_resume to upload a resume, or /start_assessment for the questionnaire flow.")
        if session.resume_profile is None:
            session.waiting_for_jd_text = False
            return BotResponse("Upload a resume first with /start_resume.")
        session.waiting_for_jd_text = False
        document = document_text_from_pasted_input(text, source_type="pasted_jd")
        result = build_target_result_for_jd(self.resume_context, session.resume_profile, document)
        session.resume_result = result
        return self._resume_result_response(result)

    def cancel_resume_jd_text(self, session_id: str) -> BotResponse:
        session = self.get_session(session_id)
        session.waiting_for_jd_text = False
        return BotResponse("JD paste cancelled.", self._resume_target_buttons() if session.resume_profile else ())

    def generate_resume_report(self, session_id: str, debug: bool = False) -> BotResponse:
        session = self.get_session(session_id)
        if session.resume_profile is None or session.resume_result is None:
            return BotResponse("Complete a resume target comparison first.")
        detail = "Telegram resume/JD pathway result."
        if debug:
            path = write_result_report(self.resume_context, session.resume_profile, session.resume_result, detail, report_mode="debug")
            return BotResponse("Generated debug report.", self._resume_result_buttons(), attachment_path=str(path))
        content = render_result_report_markdown(
            self.resume_context,
            session.resume_profile,
            session.resume_result,
            detail,
            report_mode="normal",
        )
        return BotResponse(
            "Generated report.",
            self._resume_result_buttons(),
            attachment_name="career_pathway_report.md",
            attachment_content=content,
        )

    def search_roles_entry(self, session_id: str, query: str, limit: int = 6) -> BotResponse:
        session = self.get_session(session_id)
        search_text = " ".join(query.split())
        if not search_text:
            session.pending_text_mode = "role_search"
            back = (InlineButton("Back", "resume_back_targets", ""),) if session.resume_profile is not None else (InlineButton("Back", "start", ""),)
            return BotResponse("Type the role or domain in your next message, for example data analyst. You can also use /search_roles data analyst.", back)
        matches = self._search_roles(search_text, limit=limit)
        if matches.empty:
            back = (InlineButton("Back", "resume_back_targets", ""),) if session.resume_profile is not None else (InlineButton("Back", "start", ""),)
            return BotResponse(f"No roles found for: {_h(search_text)}. Try a broader term like data, analyst, logistics, finance, or technology.", back)
        if session.resume_profile is None:
            lines = [f"<b>Role search:</b> {_h(search_text)}", "Choose a role to use as your starting skill profile:", ""]
            action = "resume_start_from_role"
        else:
            lines = [f"<b>Target role search:</b> {_h(search_text)}", "Choose a target role to compare with your confirmed skills:", ""]
            action = "resume_specific_role"
        buttons: list[InlineButton] = []
        for index, row in enumerate(matches.itertuples(index=False), start=1):
            lines.append(f"{index}. <b>{_h(row.job_role)}</b>")
            lines.append(f"   {_h(row.sector)} / {_h(row.track)}")
            buttons.append(InlineButton(self._role_button_label(row), action, str(row.role_id)))
        buttons.append(InlineButton("Back", "resume_back_targets" if session.resume_profile is not None else "start", ""))
        return BotResponse("\n".join(lines), tuple(buttons))

    def start_profile_from_role(self, session_id: str, role_id: str) -> BotResponse:
        session = self.get_session(session_id)
        if role_id not in set(self._role_catalog()["role_id"]):
            return BotResponse("I could not find that role. Try /search_roles <role or domain>.")
        self._reset_session(session)
        session.resume_profile = build_profile_from_role(self.resume_context, role_id)
        session.current_role_id = role_id
        return self._resume_profile_summary_response(session, intro="I built a draft skill profile from that dataset role. Review it before scoring.")

    def choose_resume_specific_role(self, session_id: str, role_id: str) -> BotResponse:
        session = self.get_session(session_id)
        if session.resume_profile is None:
            return BotResponse("Start with a resume upload or role search first.")
        result = build_target_result_for_role(self.resume_context, session.resume_profile, role_id, "specific_role")
        session.resume_target_mode = "specific_role"
        session.resume_result = result
        return self._resume_result_response(result)

    def handle_text_message(self, session_id: str, text: str) -> BotResponse:
        session = self.get_session(session_id)
        if session.pending_text_mode == "add_skill_search":
            return self.search_resume_add_skills(session_id, text)
        if session.waiting_for_jd_text:
            return self.handle_resume_jd_text(session_id, text)
        if session.pending_text_mode == "role_search":
            return self.search_roles_entry(session_id, text)
        return BotResponse("Use /start to begin, /start_resume to upload a resume, or /search_roles <role> to start from a role.")

    def start_assessment(self, session_id: str) -> BotResponse:
        session = self.get_session(session_id)
        self._reset_session(session)
        lines = [
            "Before skill questions",
            "Which current role is closest to you?",
            "This steers the first 10 baseline questions.",
            "If none fit, type /search_roles <role or domain>.",
            "If unsure, choose the demo option.",
        ]
        buttons = tuple(InlineButton(profile.label, "select_current_role", profile.key) for profile in CURRENT_ROLE_PROFILES)
        return BotResponse("\n".join(lines), buttons)

    def select_current_role(self, session_id: str, profile_key: str) -> BotResponse:
        session = self.get_session(session_id)
        profile = self._current_role_profile(profile_key)
        role_id = select_role_id(
            self.requirements,
            job_role=profile.job_role,
            sector=profile.sector,
            track=profile.track,
        )
        self._reset_session(session)
        session.current_role_profile_key = profile.key
        return self._start_role_baseline(session, role_id)

    def select_current_role_id(self, session_id: str, role_id: str) -> BotResponse:
        session = self.get_session(session_id)
        if role_id not in set(self._role_catalog()["role_id"]):
            return BotResponse("I could not find that role. Try /search_roles <role or domain>.")
        self._reset_session(session)
        session.current_role_profile_key = "searched_role"
        return self._start_role_baseline(session, role_id)

    def search_current_roles(self, session_id: str, query: str, limit: int = 5) -> BotResponse:
        search_text = " ".join(query.split())
        if not search_text:
            return BotResponse("Search for a current role like this:\n/search_roles data analyst\n/search_roles business analyst\n/search_roles logistics")
        matches = self._search_roles(search_text, limit=limit)
        if matches.empty:
            return BotResponse(f"No roles found for: {_h(search_text)}\nTry a broader term, such as data, analyst, business, logistics, finance, or technology.")
        lines = [f"<b>Role search:</b> {_h(search_text)}", "Choose the closest baseline role:", ""]
        buttons: list[InlineButton] = []
        for index, row in enumerate(matches.itertuples(index=False), start=1):
            label = self._role_button_label(row)
            lines.append(f"{index}. <b>{_h(row.job_role)}</b>")
            lines.append(f"   {_h(row.sector)} / {_h(row.track)}")
            buttons.append(InlineButton(label, "select_current_role_id", str(row.role_id)))
        return BotResponse("\n".join(lines), tuple(buttons))

    def answer_question(self, session_id: str, selected_level: float) -> BotResponse:
        session = self.get_session(session_id)
        if not session.baseline_questions:
            buttons = tuple(InlineButton(profile.label, "select_current_role", profile.key) for profile in CURRENT_ROLE_PROFILES)
            return BotResponse("Choose a current role first, or type /search_roles <role or domain>.", buttons)
        index = len(session.baseline_answers)
        if index >= len(session.baseline_questions):
            return BotResponse("Baseline is already complete. Use /recommend_roles.", self._main_buttons())
        question = session.baseline_questions[index]
        session.baseline_answers.append(answer_question(question, selected_level, confidence="telegram-demo"))
        if len(session.baseline_answers) < len(session.baseline_questions):
            next_question = session.baseline_questions[len(session.baseline_answers)]
            return self._question_response(next_question, len(session.baseline_answers) + 1, len(session.baseline_questions), "answer_question")
        session.baseline_vector = answers_to_user_vector(session.baseline_answers)
        return BotResponse(
            "Baseline complete. I can now recommend 3 pathway options from your answers.",
            (InlineButton("Recommend roles", "recommend_roles", "top3"),),
        )

    def recommend_roles(self, session_id: str) -> BotResponse:
        session = self.get_session(session_id)
        if not session.current_role_id or not session.baseline_vector:
            return BotResponse("Start with /start_assessment first.")
        session.recommendations = recommend_pathways(self.requirements, session.baseline_vector, session.current_role_id, count=3)
        insight = self.explainer.explain_recommendations(
            session.recommendations,
            current_role=self._role_by_id(session.current_role_id),
        )
        lines = [
            "Recommended pathways",
            "Why these: I compared your answered skill levels with each role's required skill levels.",
            "Higher fit means more of the target role is already covered.",
            "",
        ]
        buttons: list[InlineButton] = []
        for index, row in session.recommendations.reset_index(drop=True).iterrows():
            lines.append(f"{index + 1}. {row.job_role}")
            lines.append(f"   Fit: {row.suitability_percentage:.2f}% | matched {row.matched_skill_count}/{row.target_skill_count} skills | gaps {row.gap_skill_count}")
            buttons.append(InlineButton(str(row.job_role), "choose_pathway", str(row.role_id)))
        lines.append("")
        lines.append(insight.text)
        lines.append("")
        lines.append("Choose one pathway and I will ask 5 focused gap questions.")
        return BotResponse("\n".join(lines), tuple(buttons))

    def choose_pathway(self, session_id: str, role_id: str) -> BotResponse:
        session = self.get_session(session_id)
        if session.recommendations is None or role_id not in set(session.recommendations["role_id"]):
            return BotResponse("Choose one of the recommended pathway buttons first.")
        session.selected_role_id = role_id
        session.gap_questions, _ = select_target_gap_questions(self.requirements, session.baseline_vector, role_id, count=5)
        session.gap_answers = []
        selected = session.recommendations.loc[session.recommendations["role_id"].eq(role_id)].iloc[0]
        first = self._question_response(session.gap_questions[0], 1, len(session.gap_questions), "answer_gap_question")
        text = (
            f"Selected pathway: {selected.job_role}\n"
            "I will ask 5 follow-up questions about the largest skill gaps for this role.\n\n"
            f"{first.text}"
        )
        return BotResponse(text, first.buttons)

    def answer_gap_question(self, session_id: str, selected_level: float) -> BotResponse:
        session = self.get_session(session_id)
        index = len(session.gap_answers)
        if index >= len(session.gap_questions):
            return BotResponse("Follow-up is already complete.", self._main_buttons())
        question = session.gap_questions[index]
        session.gap_answers.append(answer_question(question, selected_level, confidence="telegram-demo-followup"))
        if len(session.gap_answers) < len(session.gap_questions):
            next_question = session.gap_questions[len(session.gap_answers)]
            return self._question_response(next_question, len(session.gap_answers) + 1, len(session.gap_questions), "answer_gap_question")
        session.refined_vector = apply_answers_to_vector(session.baseline_vector, session.gap_answers)
        summary, _ = self._selected_score(session)
        return BotResponse(
            f"Pathway assessment complete. Skill suitability is {summary.suitability_percentage:.2f}%.",
            self._main_buttons(),
        )

    def explain_score(self, session_id: str) -> BotResponse:
        session = self.get_session(session_id)
        active = self._try_active_score(session)
        if active is None:
            return BotResponse("Choose a target role or paste a JD first, then I can explain the score.", self._resume_target_buttons() if session.resume_profile else ())
        summary, gap_table = active
        related_notes = self._related_notes_for_session(session, gap_table)
        lines = [
            "<b>Why this score?</b>",
            f"<b>Target:</b> {_h(summary.job_role)}",
            f"<b>Suitability:</b> {summary.suitability_percentage:.2f}%",
            "",
        ]
        lines.extend(_plain_score_explanation_lines(summary, gap_table, html=True))
        related_lines = _related_note_lines(gap_table, related_notes, html=True, max_notes=3)
        if related_lines:
            lines.extend(["", "<b>Related evidence</b>"])
            lines.extend(related_lines)
        lines.extend(["", "Use Show skill gaps for the detailed comparison, or Generate report for the full audit trail."])
        return BotResponse("\n".join(lines), self._active_buttons(session))

    def show_gaps(self, session_id: str) -> BotResponse:
        session = self.get_session(session_id)
        active = self._try_active_score(session)
        if active is None:
            return BotResponse("Choose a target role or paste a JD first, then I can show skill gaps.", self._resume_target_buttons() if session.resume_profile else ())
        _, gap_table = active
        related_notes = self._related_notes_for_session(session, gap_table)
        gaps = gap_table.loc[gap_table["gap"] > 0].head(7)
        if gaps.empty:
            return BotResponse("No remaining skill gaps for the selected target role.", self._active_buttons(session))
        lines = ["<b>Top gaps</b>", "Current vs target level:", ""]
        for index, row in enumerate(gaps.itertuples(index=False), start=1):
            lines.append(
                f"{index}. <b>{_h(row.unique_skill_title)}</b>: "
                f"current {row.current_level:g}, target {row.target_level:g}, gap {row.gap:g}"
            )
            related = related_notes.get(str(row.skill_id))
            if related is not None:
                lines.append(f"   <i>Related evidence:</i> {_h(related.related_skill_title)}, level {related.related_level:g}.")
        lines.append("")
        lines.append("Generate action plan and Casey will turn these gaps into learning actions from the SkillsFuture K&A rows.")
        return BotResponse("\n".join(lines), self._active_buttons(session))

    def show_pathway(self, session_id: str) -> BotResponse:
        session = self.get_session(session_id)
        if not session.current_role_id or not session.selected_role_id:
            return BotResponse("Choose a pathway first.")
        edge = build_transition_edge(self.requirements, session.current_role_id, session.selected_role_id, PathwayPolicy())
        lines = [
            "Pathway logic",
            f"Pathway fit: {edge['edge_fit_percentage']:.2f}%",
            "This is a fast direct transition summary for Telegram.",
            "Full graph search remains available in the validation report.",
            "",
            f"{edge['source_job_role']} -> {edge['target_job_role']}",
            f"Skill suitability: {edge['skill_suitability_percentage']:.2f}%",
            f"Matched skills: {edge['matched_skill_count']}/{edge['target_skill_count']}",
        ]
        if edge["priority_gap_titles"]:
            lines.append(f"Priority gaps: {edge['priority_gap_titles']}")
        lines.extend(["", f"Assumptions: {edge['edge_assumptions']}"])
        return BotResponse("\n".join(lines), self._main_buttons())

    def generate_action_plan(self, session_id: str) -> BotResponse:
        session = self.get_session(session_id)
        active = self._try_active_score(session)
        if active is None:
            return BotResponse("Choose a target role or paste a JD first, then I can generate an action plan.", self._resume_target_buttons() if session.resume_profile else ())
        _, gap_table = active
        action_plan = build_action_plan(gap_table, self.ka_items, max_actions=5)
        related_notes = self._related_notes_for_session(session, gap_table)
        lines = _action_plan_markdown_lines(action_plan, related_notes, debug=self.debug_mode)
        content = "\n".join(lines) + "\n"
        if self.debug_mode:
            output_path = self.paths.processed_dir / f"m6_telegram_action_plan_{session.session_id}.md"
            output_path.write_text(content, encoding="utf-8")
            return BotResponse(
                f"Casey generated an action plan with {len(action_plan)} actions.",
                self._active_buttons(session),
                attachment_path=str(output_path),
            )
        return BotResponse(
            f"Casey generated an action plan with {len(action_plan)} actions.",
            self._active_buttons(session),
            attachment_name="career_action_plan.md",
            attachment_content=content,
        )

    def _start_role_baseline(self, session: SessionState, role_id: str) -> BotResponse:
        session.current_role_id = role_id
        session.baseline_questions = select_baseline_questions(self.requirements, session.current_role_id, count=10)
        role = self._role_by_id(role_id)
        first = self._question_response(session.baseline_questions[0], 1, len(session.baseline_questions), "answer_question")
        intro = (
            f"Current role baseline: {role.job_role}\n"
            f"Domain: {role.sector} / {role.track}\n"
            "Answer based on work you have actually done. Casey will use this as your baseline."
        )
        return BotResponse(f"{intro}\n\n{first.text}", first.buttons)

    def _role_catalog(self) -> pd.DataFrame:
        return self.requirements[["role_id", "sector", "track", "job_role"]].drop_duplicates().reset_index(drop=True)

    def _role_by_id(self, role_id: str) -> pd.Series:
        matches = self._role_catalog().loc[self._role_catalog()["role_id"].eq(role_id)]
        if matches.empty:
            raise ValueError(f"Unknown role_id={role_id!r}")
        return matches.iloc[0]

    def _search_roles(self, query: str, limit: int = 5) -> pd.DataFrame:
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

    def _role_button_label(self, row) -> str:
        text = f"{row.job_role} - {row.sector}"
        return text if len(text) <= 54 else text[:51].rstrip() + "..."

    def _with_skill_descriptions(self, requirements: pd.DataFrame) -> pd.DataFrame:
        skills_path = self.paths.processed_dir / "skills.csv"
        if not skills_path.exists() or "unique_skill_description" in requirements.columns:
            return requirements
        skills = pd.read_csv(skills_path, usecols=["skill_id", "unique_skill_description"])
        return requirements.merge(skills, on="skill_id", how="left")

    def _reset_session(self, session: SessionState) -> None:
        session.current_role_id = None
        session.current_role_profile_key = None
        session.baseline_questions = []
        session.baseline_answers = []
        session.recommendations = None
        session.selected_role_id = None
        session.gap_questions = []
        session.gap_answers = []
        session.baseline_vector = {}
        session.refined_vector = {}
        session.resume_profile = None
        session.resume_recommendations = None
        session.resume_result = None
        session.resume_target_mode = None
        session.waiting_for_jd_text = False
        session.resume_review_page = 0
        session.pending_text_mode = None
        session.pending_edit_index = None
        session.pending_add_skill_id = None
        session.pending_add_skill_title = None

    def _current_role_profile(self, profile_key: str) -> CurrentRoleProfile:
        for profile in CURRENT_ROLE_PROFILES:
            if profile.key == profile_key:
                return profile
        return CURRENT_ROLE_PROFILES[-1]

    def _try_active_score(self, session: SessionState):
        if session.resume_result is not None:
            return session.resume_result.selected_summary, session.resume_result.selected_gap_table
        if session.selected_role_id:
            return self._selected_score(session)
        return None

    def _related_notes_for_session(self, session: SessionState, gap_table: pd.DataFrame) -> dict[str, RelatedSkillMatch]:
        return build_related_skill_notes(gap_table, session.resume_profile, self.resume_context.skills)

    def _active_buttons(self, session: SessionState) -> tuple[InlineButton, ...]:
        return self._resume_result_buttons() if session.resume_result is not None else self._main_buttons()

    def _active_score(self, session: SessionState):
        active = self._try_active_score(session)
        if active is None:
            raise ValueError("No active score")
        return active

    def _selected_score(self, session: SessionState):
        if not session.selected_role_id:
            raise ValueError("No pathway selected")
        vector = session.refined_vector or session.baseline_vector
        target_requirements = get_role_requirements(self.requirements, session.selected_role_id)
        return score_role_fit(vector, target_requirements)

    def _level_buttons_for_skill(self, skill_id: str, action: str, value_prefix: str) -> tuple[InlineButton, ...]:
        levels = valid_levels_for_skill(self.ka_items, skill_id, include_zero=True)
        return tuple(InlineButton(f"Level {level:g}", action, f"{value_prefix}:{level:g}") for level in levels)

    def _skill_level_guidance_lines(self, skill_id: str) -> list[str]:
        lines = [
            "<b>Level guide</b>",
            "0: no usable evidence yet or never used before.",
            "1-2: basic exposure or guided use.",
            "3-4: can apply independently in regular work.",
            "5-6: advanced, complex, or lead-level proficiency.",
        ]
        skill_rows = self.ka_items.loc[self.ka_items["skill_id"].astype(str).eq(str(skill_id))].copy()
        if skill_rows.empty:
            lines.extend(["", "No dataset level guidance available for this skill."])
            return lines
        skill_rows["proficiency_level"] = pd.to_numeric(skill_rows["proficiency_level"], errors="coerce")
        skill_rows = skill_rows.dropna(subset=["proficiency_level"]).sort_values(["proficiency_level", "source_row_number"])
        if skill_rows.empty:
            lines.extend(["", "No dataset level guidance available for this skill."])
            return lines
        descriptions = (
            skill_rows.drop_duplicates("proficiency_level")
            .loc[:, ["proficiency_level", "proficiency_description", "tsc_ccs_code"]]
            .head(6)
        )
        if descriptions.empty:
            return lines
        code = str(descriptions.iloc[0].get("tsc_ccs_code", "")).strip()
        if code:
            lines.extend(["", f"<b>Dataset guidance</b> ({_h(code)})"])
        else:
            lines.extend(["", "<b>Dataset guidance</b>"])
        available_levels = [float(level) for level in descriptions["proficiency_level"].tolist()]
        if available_levels and set(available_levels) != set(range(1, 7)):
            rendered_levels = ", ".join(f"{level:g}" for level in available_levels)
            lines.append(f"Dataset rows available for this skill: levels {rendered_levels}.")
        for row in descriptions.itertuples(index=False):
            description = _full_guidance_text(str(row.proficiency_description))
            lines.append(f"Level {float(row.proficiency_level):g}: {_h(description)}")
        example = skill_rows.loc[skill_rows["ka_item"].astype(str).str.strip().ne("")].head(1)
        if not example.empty:
            ka_item = _full_guidance_text(str(example.iloc[0]["ka_item"]))
            lines.extend(["", f"<i>K&A example:</i> {_h(ka_item)}"])
        return lines

    def _selected_pathway(self, session: SessionState):
        if not session.current_role_id or not session.selected_role_id:
            raise ValueError("No selected pathway")
        graph = derive_pathway_graph(self.requirements, session.current_role_id, session.selected_role_id, PathwayPolicy(), max_edges_per_source=6)
        path, total_cost = dijkstra_path(graph, session.current_role_id, session.selected_role_id)
        selected_edges = path_edges(graph, path)
        fit = pathway_fit_percentage(total_cost, len(selected_edges))
        return graph, selected_edges, fit

    def _question_response(self, question: SkillQuestion, index: int, total: int, action: str) -> BotResponse:
        buttons = tuple(InlineButton(option.label, action, str(option.level)) for option in question.options)
        return BotResponse(f"Question {index}/{total}: {question.prompt}", buttons)

    def _resume_profile_summary_response(self, session: SessionState, intro: str | None = None) -> BotResponse:
        profile = session.resume_profile
        if profile is None:
            return BotResponse("Upload a resume first with /start_resume.")
        review_count = sum(1 for item in profile.items if item.uncertainty_flag)
        lines = []
        if intro:
            lines.extend([intro, ""])
        lines.extend([f"Casey found {len(profile.items)} possible skills.", "Please review them first before we score.", "", "<b>Top matches</b>"])
        for index, item in enumerate(profile.items[:5], start=1):
            lines.append(f"{index}. <b>{_h(item.unique_skill_title)}</b> - Level {item.level:g}{_review_status_label(item)}")
            lines.append(f"   <i>Why:</i> {_h(_user_facing_skill_reason(item))}")
        if len(profile.items) > 5:
            lines.append("")
            lines.append(f"Review all skills to see the remaining {len(profile.items) - 5} skill(s).")
        if review_count:
            lines.append("")
            lines.append(f"{review_count} skill(s) need review because Casey found uncertain or weak evidence.")
        lines.append("")
        lines.append('<b>Review and confirm the skill profile before scoring by clicking the "Review skills" button.</b>')
        return BotResponse("\n".join(lines), self._resume_review_buttons())

    def _resume_review_page_response(self, session: SessionState, note: str | None = None) -> BotResponse:
        profile = session.resume_profile
        if profile is None:
            return BotResponse("Upload a resume first with /start_resume.")
        total = len(profile.items)
        if total == 0:
            return BotResponse("No skills are currently in the profile. Add a skill before scoring.", (InlineButton("Add skill", "resume_add_skill", ""),))
        page_count = max(1, (total + REVIEW_PAGE_SIZE - 1) // REVIEW_PAGE_SIZE)
        page = min(max(session.resume_review_page, 0), page_count - 1)
        session.resume_review_page = page
        start = page * REVIEW_PAGE_SIZE
        end = min(total, start + REVIEW_PAGE_SIZE)
        lines = [
            f"<b>Review skills</b> ({start + 1}-{end} of {total})",
            "Casey found the draft skills, but you get final say before scoring.",
            "",
            "<b>Edit</b> changes a skill level.",
            "<b>Remove</b> deletes that skill from your profile.",
            "",
            "Example: <b>Edit 1</b> changes item 1 in the list below.",
            "",
            "<b>Add skill</b> searches broad SkillsFuture capability names; tools like Python or SQL usually map to Programming and Coding.",
            "<b>Continue</b> confirms this profile for scoring.",
            "<b>Back</b> returns to the previous page.",
            "<b>Back to start</b> goes back to the start of the workflow after confirmation.",
        ]
        if note:
            lines.extend(["", _h(note), ""])
        else:
            lines.append("")
        buttons: list[InlineButton] = []
        for display_index, item in enumerate(profile.items[start:end], start=start + 1):
            lines.append(f"{display_index}. <b>{_h(item.unique_skill_title)}</b> - Level {item.level:g}{_review_status_label(item)}")
            lines.append(f"   <i>Why:</i> {_h(_user_facing_skill_reason(item))}")
            lines.append("")
            zero_index = display_index - 1
            buttons.append(InlineButton(f"Edit {display_index}", "resume_edit_skill", str(zero_index)))
            buttons.append(InlineButton(f"Remove {display_index}", "resume_remove_skill", str(zero_index)))
        if page > 0:
            buttons.append(InlineButton("Back", "resume_review_page", str(page - 1)))
        if page < page_count - 1:
            buttons.append(InlineButton("Next", "resume_review_page", str(page + 1)))
        buttons.append(InlineButton("Add skill", "resume_add_skill", ""))
        buttons.append(InlineButton("Continue", "resume_confirm_skills", ""))
        buttons.append(InlineButton("Back to start", "resume_confirm_back_start", ""))
        return BotResponse("\n".join(lines), tuple(buttons))

    def _resume_recommendations_response(self, session: SessionState, title: str) -> BotResponse:
        recommendations = session.resume_recommendations
        if recommendations is None or recommendations.empty:
            return BotResponse("No target roles were generated. Try JD scoring instead.", self._resume_target_buttons())
        lines = [f"<b>{_h(title)}</b>", "Casey found these target options from your confirmed skills:", ""]
        buttons: list[InlineButton] = []
        for index, row in enumerate(recommendations.head(6).itertuples(index=False), start=1):
            lines.append(f"{index}. <b>{_h(row.job_role)}</b>")
            lines.append(f"   Fit: {float(row.suitability_percentage):.1f}%")
            sector_track = f"{row.sector} / {row.track}"
            if sector_track.strip(" /"):
                lines.append(f"   {_h(sector_track)}")
            buttons.append(InlineButton(str(row.job_role)[:54], "resume_choose_role", str(row.role_id)))
        lines.append("")
        lines.append("Choose a target and Casey will show the detailed comparison and actions. You can also paste a JD for direct suitability scoring.")
        buttons.append(InlineButton("Paste JD instead", "resume_jd_text", ""))
        buttons.append(InlineButton("Back", "resume_back_targets", ""))
        return BotResponse("\n".join(lines), tuple(buttons))

    def _resume_result_response(self, result: TargetModeResult) -> BotResponse:
        summary = result.selected_summary
        gaps = result.selected_gap_table.loc[result.selected_gap_table["gap"] > 0].head(3)
        lines = [
            f"<b>Suitability:</b> {summary.suitability_percentage:.1f}%",
            f"<b>Target:</b> {_h(summary.job_role)}",
            f"<b>Matched:</b> {summary.matched_skill_count}/{summary.target_skill_count} skills",
            f"<b>Gaps:</b> {summary.gap_skill_count}",
            "",
            "<b>Top gaps</b>",
        ]
        if gaps.empty:
            lines.append("No major gaps found.")
        for row in gaps.itertuples(index=False):
            lines.append(f"- {_h(row.unique_skill_title)}: you {row.current_level:g}, target {row.target_level:g}")
        lines.append("")
        lines.append("Use <b>Why this score?</b> if you want Casey to explain the result, or Generate report for the full audit trail.")
        return BotResponse("\n".join(lines), self._resume_result_buttons())

    def _resume_review_buttons(self) -> tuple[InlineButton, ...]:
        return (
            InlineButton("Review skills", "resume_review_page", "0"),
            InlineButton("Why these skills?", "resume_explain_skills", ""),
        )

    def _resume_target_buttons(self) -> tuple[InlineButton, ...]:
        return (
            InlineButton("Explore pathways", "resume_explore", ""),
            InlineButton("Advance roles", "resume_advance", ""),
            InlineButton("Search target role", "start_role_search", ""),
            InlineButton("Paste JD", "resume_jd_text", ""),
            InlineButton("Back to review", "resume_back_review", ""),
        )

    def _resume_result_buttons(self) -> tuple[InlineButton, ...]:
        buttons = [
            InlineButton("Why this score?", "explain_score", ""),
            InlineButton("Show skill gaps", "show_gaps", ""),
            InlineButton("Generate action plan", "generate_action_plan", ""),
            InlineButton("Generate report", "resume_report", ""),
            InlineButton("Back", "resume_back_targets", ""),
        ]
        if self.debug_mode:
            buttons.insert(3, InlineButton("Debug report", "resume_debug_report", ""))
        return tuple(buttons)

    def _main_buttons(self) -> tuple[InlineButton, ...]:
        return (
            InlineButton("Why this score?", "explain_score", ""),
            InlineButton("Show skill gaps", "show_gaps", ""),
            InlineButton("Show pathway", "show_pathway", ""),
            InlineButton("Generate action plan", "generate_action_plan", ""),
        )


def _review_status_label(item) -> str:
    reason = str(getattr(item, "reason", "")).casefold()
    source_type = str(getattr(item, "source_type", "")).casefold()
    mapping_type = str(getattr(item, "mapping_type", "")).casefold()
    if "user reviewed and set level" in reason:
        return " (edited)"
    if source_type == "user_added_skill" or mapping_type == "manual_dataset_skill" or "user added skill" in reason:
        return " (added)"
    return ""


def _full_guidance_text(value: str) -> str:
    return " ".join(str(value).split())


def _compact_reason(reason: str, limit: int = 115) -> str:
    cleaned = " ".join(str(reason).split())
    cleaned = cleaned.replace("User explicitly confirmed this parser-derived skill. Original reason: ", "")
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip() + "..."


def _h(value: object) -> str:
    return escape(str(value), quote=False)


def _plain_score_explanation_lines(summary, gap_table: pd.DataFrame, *, html: bool = False) -> list[str]:
    matched = gap_table.loc[gap_table["current_level"] > 0, "unique_skill_title"].head(6).astype(str).tolist()
    gaps = gap_table.loc[gap_table["gap"] > 0].head(3)
    lines = [f"You match {summary.matched_skill_count} of {summary.target_skill_count} target skills."]
    if matched:
        suffix = "." if len(matched) < 6 else ", and more."
        rendered = [_h(skill) for skill in matched] if html else matched
        lines.append("Matched skills: " + ", ".join(rendered) + suffix)
    if not gaps.empty:
        gap_bits = []
        for row in gaps.itertuples(index=False):
            title = _h(row.unique_skill_title) if html else str(row.unique_skill_title)
            gap_bits.append(f"{title} (you {row.current_level:g}, target {row.target_level:g})")
        lines.append("The score is pulled down mainly by: " + "; ".join(gap_bits) + ".")
    lines.append(f"Casey calculates {summary.suitability_percentage:.2f}% by comparing your covered target levels with the total levels required for this role.")
    return lines


def _related_note_lines(
    gap_table: pd.DataFrame,
    related_notes: dict[str, RelatedSkillMatch],
    *,
    html: bool = False,
    max_notes: int | None = None,
    debug: bool = False,
) -> list[str]:
    lines: list[str] = []
    count = 0
    gaps = gap_table.loc[gap_table["gap"] > 0]
    for gap in gaps.itertuples(index=False):
        related = related_notes.get(str(gap.skill_id))
        if related is None:
            continue
        note = related_skill_normal_note(related)
        if html:
            note = _h(note)
        lines.append(f"- {note}")
        if debug:
            debug_note = related_skill_debug_note(related)
            lines.append(f"  {debug_note if not html else _h(debug_note)}")
        count += 1
        if max_notes is not None and count >= max_notes:
            break
    return lines


def _action_plan_markdown_lines(
    action_plan: pd.DataFrame,
    related_notes: dict[str, RelatedSkillMatch],
    *,
    debug: bool = False,
) -> list[str]:
    lines = ["# Telegram Action Plan", "", "## Next Actions", ""]
    if action_plan.empty:
        lines.append("- No action items were generated because no target gaps were found.")
        return lines
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
            lines.extend(["Target proficiency:", _compact_reason(description, limit=320), ""])
        ka_item = str(getattr(row, "ka_item", "")).strip()
        if ka_item:
            lines.extend(["K&A focus:", _compact_reason(ka_item, limit=320), ""])
        lines.extend([
            "Action:",
            str(getattr(row, "practical_action", getattr(row, "next_action", ""))).strip(),
            "",
            "Evidence to build:",
            str(getattr(row, "evidence_to_build", "")).strip(),
            "",
        ])
        if debug:
            ka_source = getattr(row, "ka_source_row_number", "")
            role_source = getattr(row, "role_skill_source_row_number", "")
            lines.extend([f"Source: K&A row {ka_source}; role-skill row {role_source}.", ""])
    return lines


def _user_facing_skill_reason(item) -> str:
    text = f"{item.evidence} {item.reason}".casefold()
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
    return _compact_reason(item.reason, limit=160)


def response_to_dict(response: BotResponse) -> dict[str, Any]:
    return {
        "text": response.text,
        "buttons": [button.__dict__ for button in response.buttons],
        "attachment_path": response.attachment_path,
        "attachment_name": response.attachment_name,
        "has_attachment_content": response.attachment_content is not None,
    }

