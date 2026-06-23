"""Validate the resume-first local workflow without requiring live agents."""

from __future__ import annotations

import faulthandler
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Validators should not spend tokens or expose secrets. The product still loads
# .env in normal runs, but this script forces fallback behavior.
os.environ["PARSER_AGENT_DISABLED"] = "1"
os.environ["EXPLAINER_AGENT_DISABLED"] = "1"

VALIDATOR_TIMEOUT_SECONDS = int(os.getenv("VALIDATOR_TIMEOUT_SECONDS", "45"))
LOG_PATH = PROJECT_ROOT / "data" / "processed" / "resume_recommender_validator.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
LOG_PATH.write_text(f"resume recommender validator started; timeout={VALIDATOR_TIMEOUT_SECONDS}s\n", encoding="utf-8")


def log(message: str) -> None:
    line = f"[validator] {message}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


faulthandler.dump_traceback_later(VALIDATOR_TIMEOUT_SECONDS, repeat=False, exit=True)
log("watchdog armed")
log("module imports starting")

from docx import Document
from reportlab.pdfgen import canvas

from jobs_skills.document_ingestion import document_text_from_pasted_input, extract_text_from_file
from jobs_skills.parser_agents import ParsedSkillEvidence, ParserResult, build_target_requirements_from_jd, parse_resume_text
from jobs_skills.scoring import nearest_role_neighbors_l1
from jobs_skills.resume_recommender import (
    _fuzzy_match_skill,
    _apply_requirement_level_guidance,
    _merge_agent_and_rule_results,
    add_profile_skill,
    build_target_result_for_jd,
    build_target_result_for_role,
    edit_profile_level,
    load_resume_workflow_context,
    parse_resume_document,
    parser_result_to_profile,
    recommend_advance_targets,
    recommend_explore_targets,
    remove_profile_item,
    search_roles,
    search_skills,
    valid_levels_for_skill,
    write_result_report,
)

log("module imports complete")


FRESH_GRAD_TEXT = """
PRIVATE_FULL_RESUME_TEXT_SHOULD_NOT_PERSIST
Education: Business analytics graduate.
Internship: assisted data analysis and data collection for customer reports using SQL.
Coursework project: built Python automation scripts and Power BI dashboards for sales trends.
Capstone project: created charts and visualisation to explain findings to stakeholders.
"""

EXPERIENCED_TEXT = """
PRIVATE_EXPERIENCED_RESUME_TEXT_SHOULD_NOT_PERSIST
Senior Data Analyst with 4 years experience.
Led data analytics projects, designed ETL data pipelines, and implemented predictive machine learning models.
Owned data governance checks and stakeholder management for cross-functional business users.
Developed Tableau dashboards and Python automation scripts for monthly performance reporting.
"""

JD_TEXT = """
PRIVATE_JOB_DESCRIPTION_TEXT_SHOULD_NOT_PERSIST
We need a Data Scientist to develop machine learning predictive models, design data pipelines,
build dashboards, apply data governance checks, and communicate findings with stakeholders.
The role must implement data analytics solutions and support business requirements.
"""


def main() -> None:
    started = time.perf_counter()
    def checkpoint(label: str) -> None:
        log(f"{label}: {time.perf_counter() - started:.2f}s")
    checkpoint("start")
    context = load_resume_workflow_context(PROJECT_ROOT)
    checkpoint("loaded context")
    processed_dir = context.paths.processed_dir
    before_files = {path.name for path in processed_dir.iterdir() if path.is_file()}

    tmp_path = PROJECT_ROOT / ".runtime" / "resume_validator"
    tmp_path.mkdir(parents=True, exist_ok=True)
    checkpoint(f"using temp dir {tmp_path}")
    fresh_docx = tmp_path / "fresh_grad_resume.docx"
    experienced_pdf = tmp_path / "experienced_resume.pdf"
    for stale_file in (fresh_docx, experienced_pdf):
        if stale_file.exists():
            stale_file.unlink()
    checkpoint("writing sample docx/pdf")
    write_docx(fresh_docx, FRESH_GRAD_TEXT)
    write_pdf(experienced_pdf, EXPERIENCED_TEXT)
    checkpoint("wrote sample docx/pdf")

    checkpoint("extracting sample docx/pdf")
    fresh_document = extract_text_from_file(fresh_docx)
    experienced_document = extract_text_from_file(experienced_pdf)
    assert "Coursework project" in fresh_document.text
    assert "Senior Data Analyst" in experienced_document.text
    checkpoint("extracted docx/pdf")

    checkpoint("parsing fresh grad profile")
    fresh_profile = parse_resume_document(fresh_document, context, use_agent=False)
    checkpoint("parsing experienced profile")
    experienced_profile = parse_resume_document(experienced_document, context, use_agent=False)
    assert len(fresh_profile.items) >= 3, f"Expected fresh grad skills, got {len(fresh_profile.items)}"
    assert len(experienced_profile.items) >= 4, f"Expected experienced skills, got {len(experienced_profile.items)}"
    checkpoint("parsed sample profiles")

    fuzzy_match = _fuzzy_match_skill("Programming and Coding", context.skills)
    assert fuzzy_match is not None, "Expected fuzzy matcher to map exact skill phrase"
    fallback_result = parse_resume_text("Built Python scripts for reporting automation.", context.skills)
    merged_result = _merge_agent_and_rule_results(
        {
            "shortlist_matches": [],
            "additional_suggestions": [
                {
                    "suggested_skill": "Programming and Coding",
                    "inferred_level": 5,
                    "confidence": 0.92,
                    "evidence": "Built Python scripts for reporting automation.",
                    "reason": "Agent suggested a missing coding skill from project evidence.",
                    "source_section": "project",
                }
            ],
        },
        fallback_result,
        context.skills,
        "resume",
        max_skills=20,
    )
    fuzzy_items = [item for item in merged_result.extracted_skills if item.mapping_type.startswith("agent_suggested_fuzzy")]
    assert fuzzy_items, "Expected agent additional suggestion to fuzzy-map into a SkillsFuture skill"
    assert max(item.inferred_level for item in fuzzy_items) <= 3.0, "Resume agent level-5 suggestion should be capped without strategic evidence"
    checkpoint("validated agent additional-suggestion fuzzy mapping and level cap")

    computational = context.skills.loc[context.skills["unique_skill_title"].astype(str).str.casefold().eq("computational modelling")]
    assert not computational.empty, "Expected Computational Modelling skill in normalized skills"
    computational_skill_id = str(computational.iloc[0].skill_id)
    assert valid_levels_for_skill(context.ka_items, computational_skill_id, include_zero=True) == (0.0, 3.0, 4.0, 5.0)

    high_parser_profile = parser_result_to_profile(
        ParserResult(
            source_type="resume",
            extracted_skills=(
                ParsedSkillEvidence(
                    skill_id=computational_skill_id,
                    unique_skill_title="Computational Modelling",
                    inferred_level=6.0,
                    confidence=0.90,
                    evidence="Led enterprise computational modelling work.",
                    reason="Synthetic high-level parser evidence.",
                    uncertainty_flag=False,
                    mapping_type="validator",
                    matched_phrase="computational modelling",
                ),
            ),
        ),
        source_type="resume",
        parser_source="validator",
        ka_items=context.ka_items,
    )
    assert high_parser_profile.items[0].level == 5.0, "Parser level above dataset max must cap to max K&A-backed level"
    assert any("capped from level 6 to 5" in note for note in high_parser_profile.parser_notes), "Parser cap must be auditable"

    low_parser_profile = parser_result_to_profile(
        ParserResult(
            source_type="resume",
            extracted_skills=(
                ParsedSkillEvidence(
                    skill_id=computational_skill_id,
                    unique_skill_title="Computational Modelling",
                    inferred_level=1.0,
                    confidence=0.90,
                    evidence="Course exposure to computational modelling.",
                    reason="Synthetic low-level parser evidence.",
                    uncertainty_flag=False,
                    mapping_type="validator",
                    matched_phrase="computational modelling",
                ),
            ),
        ),
        source_type="resume",
        parser_source="validator",
        ka_items=context.ka_items,
    )
    assert low_parser_profile.items[0].level == 1.0, "Parser level below dataset min must not be upgraded"
    assert low_parser_profile.items[0].uncertainty_flag, "Below-range parser level must be marked uncertain"

    jd_parser_result = ParserResult(
        source_type="job_description",
        extracted_skills=(
            ParsedSkillEvidence(
                skill_id=computational_skill_id,
                unique_skill_title="Computational Modelling",
                inferred_level=6.0,
                confidence=0.88,
                evidence="Requires advanced computational modelling ownership.",
                reason="Synthetic JD parser evidence.",
                uncertainty_flag=False,
                mapping_type="validator",
                matched_phrase="computational modelling",
            ),
        ),
    )
    jd_requirements = build_target_requirements_from_jd(jd_parser_result, context.skills)
    jd_requirements = _apply_requirement_level_guidance(jd_requirements, context.ka_items)
    assert float(jd_requirements.iloc[0].required_level) == 5.0, "JD target level above dataset max must cap before scoring"
    assert "capped from level 6 to 5" in str(jd_requirements.iloc[0].parser_reason), "JD cap must be auditable"

    no_ka_skill_ids = set(context.skills["skill_id"].astype(str)) - set(context.ka_items["skill_id"].dropna().astype(str))
    assert no_ka_skill_ids, "Expected at least one skill without K&A rows for fallback coverage"
    assert valid_levels_for_skill(context.ka_items, sorted(no_ka_skill_ids)[0], include_zero=True) == tuple(float(level) for level in range(0, 7))
    checkpoint("validated dataset-backed level policy")
    # Mandatory review operations: edit, remove, add.
    reviewed = edit_profile_level(fresh_profile, 0, 3.0)
    reviewed = remove_profile_item(reviewed, len(reviewed.items) - 1)
    programming = search_skills(context.skills, "Programming and Coding", limit=5)
    assert not programming.empty
    python_matches = search_skills(context.skills, "python", limit=5)
    assert not python_matches.empty and str(python_matches.iloc[0].unique_skill_title) == "Programming and Coding", "Python should suggest the broader SkillsFuture programming skill"
    software_programming = search_skills(context.skills, "software programming", limit=5)
    assert not software_programming.empty and str(software_programming.iloc[0].unique_skill_title) == "Programming and Coding", "Specific programming phrasing should map to the broader dataset skill"
    power_bi = search_skills(context.skills, "power bi", limit=5)
    assert not power_bi.empty and str(power_bi.iloc[0].unique_skill_title) == "Data Storytelling and Visualisation", "BI tools should suggest the broader visualisation skill"
    aws_matches = search_skills(context.skills, "aws", limit=5)
    assert not aws_matches.empty and all("law" not in str(title).casefold() for title in aws_matches["unique_skill_title"]), "Tool search should not match substrings like laws"
    excel_matches = search_skills(context.skills, "excel", limit=5)
    assert not excel_matches.empty and all("excellence" not in str(title).casefold() for title in excel_matches["unique_skill_title"]), "Tool search should not match substrings like excellence"
    reviewed = add_profile_skill(reviewed, context.skills, str(programming.iloc[0].skill_id), 3.0)
    assert reviewed.to_user_vector(), "Reviewed profile should produce user vector"
    checkpoint("review operations")

    current_role = search_roles(context.requirements, "Data Analyst", limit=5)
    data_scientist = search_roles(context.requirements, "Data Scientist", limit=5)
    assert not current_role.empty
    assert not data_scientist.empty
    current_role_id = str(current_role.iloc[0].role_id)
    target_role_id = str(data_scientist.iloc[0].role_id)

    checkpoint("ranking explore targets")
    explore = recommend_explore_targets(context, reviewed, current_role_id=current_role_id, count=3)
    checkpoint("ranking advance targets")
    advance = recommend_advance_targets(context, reviewed, current_role_id=current_role_id, count=3)
    assert len(explore) == 3
    assert len(advance) >= 1
    for column in ("vector_distance", "shared_skill_count", "compared_skill_count"):
        assert column in explore.columns, f"Explore recommendations missing nearest-neighbour column: {column}"
    assert explore["shared_skill_count"].min() >= 1, "Explore should not return zero-overlap nearest-neighbour roles"
    nearest = nearest_role_neighbors_l1(
        context.requirements,
        reviewed.to_user_vector(),
        exclude_role_ids={current_role_id},
        limit=20,
        min_shared_skill_count=2,
    )
    if len(nearest) < len(explore):
        nearest = nearest_role_neighbors_l1(
            context.requirements,
            reviewed.to_user_vector(),
            exclude_role_ids={current_role_id},
            limit=20,
            min_shared_skill_count=1,
        )
    nearest_ids = set(nearest["role_id"].astype(str))
    assert set(explore["role_id"].astype(str)).issubset(nearest_ids), "Explore results must be re-ranked from the overlap-filtered top-20 nearest-neighbour shortlist"
    assert "vector_distance" not in advance.columns, "Advance roles should not use nearest-neighbour discovery yet"
    checkpoint("ranked explore/advance targets")

    checkpoint("building explore result")
    explore_result = build_target_result_for_role(
        context,
        reviewed,
        str(explore.iloc[0].role_id),
        "explore_pathways",
        explore,
        current_role_id=current_role_id,
    )
    checkpoint("building advance result")
    advance_result = build_target_result_for_role(
        context,
        reviewed,
        str(advance.iloc[0].role_id),
        "advance_roles",
        advance,
        current_role_id=current_role_id,
    )
    checkpoint("building specific role result")
    specific_result = build_target_result_for_role(
        context,
        reviewed,
        target_role_id,
        "specific_role",
        current_role_id=current_role_id,
    )
    checkpoint("building JD result")
    jd_result = build_target_result_for_jd(
        context,
        experienced_profile,
        document_text_from_pasted_input(JD_TEXT, source_type="pasted_jd"),
        use_agent=False,
    )

    for result in (explore_result, advance_result, specific_result, jd_result):
        assert 0.0 <= result.selected_summary.suitability_percentage <= 100.0
        assert result.parser_source
        assert result.score_explanation.source.startswith("rule-based fallback")
        assert result.selected_gap_table is not None
    checkpoint("built target results")

    report_path = write_result_report(context, reviewed, specific_result, "Validator specific role target.")
    report_text = report_path.read_text(encoding="utf-8")
    assert "Suitability" in report_text
    assert "https://jobsandskills.skillsfuture.gov.sg/frameworks/interactive-skills-frameworks" in report_text
    assert "PRIVATE_FULL_RESUME_TEXT_SHOULD_NOT_PERSIST" not in report_text
    assert "PRIVATE_JOB_DESCRIPTION_TEXT_SHOULD_NOT_PERSIST" not in report_text
    checkpoint("wrote report")
    for generated_file in (fresh_docx, experienced_pdf):
        if generated_file.exists():
            generated_file.unlink()
    checkpoint("deleted synthetic source docs")

    new_files = [path for path in processed_dir.iterdir() if path.is_file() and path.name not in before_files]
    forbidden = (
        "PRIVATE_FULL_RESUME_TEXT_SHOULD_NOT_PERSIST",
        "PRIVATE_EXPERIENCED_RESUME_TEXT_SHOULD_NOT_PERSIST",
        "PRIVATE_JOB_DESCRIPTION_TEXT_SHOULD_NOT_PERSIST",
    )
    for path in new_files:
        if path.suffix.casefold() not in {".md", ".csv", ".json"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for sentinel in forbidden:
            assert sentinel not in text, f"Raw sentinel leaked into {path}"

    checkpoint("privacy scan complete")
    faulthandler.cancel_dump_traceback_later()
    print("Resume-first workflow validator passed")
    print(f"Fresh grad parsed skills: {len(fresh_profile.items)}")
    print(f"Experienced parsed skills: {len(experienced_profile.items)}")
    print(f"Explore targets tested: {len(explore)}")
    print(f"Advance targets tested: {len(advance)}")
    print(f"Report generated: {report_path}")


def write_docx(path: Path, text: str) -> None:
    document = Document()
    for line in text.strip().splitlines():
        document.add_paragraph(line.strip())
    document.save(path)


def write_pdf(path: Path, text: str) -> None:
    pdf = canvas.Canvas(str(path))
    y = 780
    for line in text.strip().splitlines():
        pdf.drawString(50, y, line.strip())
        y -= 18
    pdf.save()


if __name__ == "__main__":
    main()


