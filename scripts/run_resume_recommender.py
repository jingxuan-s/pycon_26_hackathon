"""Run the resume-first local career workflow in a terminal."""

from __future__ import annotations

from dataclasses import replace
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jobs_skills.document_ingestion import document_text_from_pasted_input, extract_text_from_file
from jobs_skills.resume_recommender import (
    ReviewedSkillProfile,
    add_profile_skill,
    build_profile_from_role,
    build_target_result_for_jd,
    build_target_result_for_role,
    edit_profile_level,
    load_resume_workflow_context,
    parse_resume_document,
    recommend_advance_targets,
    recommend_explore_targets,
    remove_profile_item,
    search_roles,
    search_skills,
    write_result_report,
)


def main() -> None:
    context = load_resume_workflow_context(PROJECT_ROOT)
    print("Resume-First Local Career Workflow")
    print("Raw resume/JD text is read at runtime only. Reports store extracted skills and short evidence snippets.")
    print("All MVP skill weights are 1.0. Agents parse/explain only; scoring stays deterministic.")

    profile, current_role_id = choose_starting_profile(context)
    profile = review_profile(context, profile)
    if not profile.items:
        raise SystemExit("No confirmed skills remain. Add at least one skill before scoring.")

    result, detail = choose_target_mode(context, profile, current_role_id)
    report_path = write_result_report(context, profile, result, target_mode_detail=detail)
    result = result.__class__(**{**result.__dict__, "report_path": report_path})
    print_result(result, report_path)


def choose_starting_profile(context):
    while True:
        print("\nStart with:")
        print("  1. Upload resume file (.pdf or .docx)")
        print("  2. Choose/search a current or aspiring role")
        choice = input("Select 1 or 2: ").strip()
        if choice == "1":
            path = input("Resume file path: ").strip().strip('"')
            document = extract_text_from_file(path)
            profile = parse_resume_document(document, context)
            return profile, None
        if choice == "2":
            role = choose_role(context, prompt="Search current/aspiring role")
            profile = build_profile_from_role(context, str(role.role_id))
            return profile, str(role.role_id)
        print("Please choose 1 or 2.")


def review_profile(context, profile: ReviewedSkillProfile) -> ReviewedSkillProfile:
    print("\nMandatory skill review")
    print("Confirm what the parser/role baseline found. Commands: Enter=continue, e N LEVEL, r N, a QUERY, c N, c all")
    while True:
        print_profile(profile)
        command = input("Review command: ").strip()
        if not command:
            unresolved = [item for item in profile.items if item.uncertainty_flag]
            if unresolved:
                print(f"Resolve {len(unresolved)} skill(s) marked 'confirm' before scoring. Use e N LEVEL, r N, c N, or c all.")
                continue
            return profile
        parts = command.split(maxsplit=2)
        action = parts[0].casefold()
        try:
            if action == "e" and len(parts) == 3:
                profile = edit_profile_level(profile, int(parts[1]) - 1, float(parts[2]))
            elif action == "r" and len(parts) == 2:
                profile = remove_profile_item(profile, int(parts[1]) - 1)
            elif action == "a" and len(parts) >= 2:
                query = parts[1] if len(parts) == 2 else parts[1] + " " + parts[2]
                profile = add_skill_interactively(context, profile, query)
            elif action == "c" and len(parts) >= 2:
                profile = confirm_profile_items(profile, parts[1])
            else:
                print("Use Enter, e N LEVEL, r N, a QUERY, c N, or c all.")
        except Exception as exc:
            print(f"Could not apply command: {exc}")


def confirm_profile_items(profile: ReviewedSkillProfile, selector: str) -> ReviewedSkillProfile:
    items = list(profile.items)
    normalized = selector.strip().casefold()
    if normalized == "all":
        confirmed = [
            replace(
                item,
                confidence=max(item.confidence, 0.85),
                uncertainty_flag=False,
                reason=f"User explicitly confirmed this parser-derived skill. Original reason: {item.reason}",
            )
            for item in items
        ]
        return ReviewedSkillProfile(
            items=tuple(confirmed),
            parser_source=profile.parser_source,
            parser_notes=tuple(profile.parser_notes) + ("User explicitly confirmed all unresolved parser-derived skills.",),
        )
    if not normalized.isdigit():
        raise ValueError("Use c N or c all.")
    index = int(normalized) - 1
    if index < 0 or index >= len(items):
        raise IndexError(f"Profile item index out of range: {index + 1}")
    item = items[index]
    items[index] = replace(
        item,
        confidence=max(item.confidence, 0.85),
        uncertainty_flag=False,
        reason=f"User explicitly confirmed this parser-derived skill. Original reason: {item.reason}",
    )
    return ReviewedSkillProfile(
        items=tuple(items),
        parser_source=profile.parser_source,
        parser_notes=tuple(profile.parser_notes) + (f"User explicitly confirmed {item.unique_skill_title}.",),
    )

def print_profile(profile: ReviewedSkillProfile) -> None:
    print("\nConfirmed draft skills")
    print(f"Parser source: {profile.parser_source}")
    print(f"Parser mode: {parser_mode_label(profile.parser_source)}")
    if not profile.items:
        print("  No skills in profile yet.")
        return
    for index, item in enumerate(profile.items, start=1):
        flag = "confirm" if item.uncertainty_flag else "ok"
        print(f"  {index}. {item.unique_skill_title} | level {item.level:g} | confidence {item.confidence:.2f} | {flag}")
        print(f"     Document: {item.source_type}; inferred section: {item.source_section}; mapping: {item.mapping_type}")
        print(f"     Reason: {item.reason}")
        print(f"     Evidence: {item.evidence}")


def parser_mode_label(parser_source: str) -> str:
    source = parser_source.casefold()
    if "agent-assisted" in source:
        return "agent-assisted extraction; dataset skill mapping was still checked before scoring"
    if "parser agent failed" in source:
        return "rule-based extraction because the parser agent was attempted but failed"
    if "agent disabled" in source:
        return "rule-based extraction because the parser agent is disabled"
    if "no parser agent token" in source:
        return "rule-based extraction because no parser agent token is configured"
    if "dataset role baseline" in source:
        return "dataset role baseline, not resume parsing"
    return "rule-based extraction"


def add_skill_interactively(context, profile: ReviewedSkillProfile, query: str) -> ReviewedSkillProfile:
    matches = search_skills(context.skills, query, limit=8)
    if matches.empty:
        print("No matching skills found. Try a broader keyword.")
        return profile
    for index, row in enumerate(matches.itertuples(index=False), start=1):
        description = str(getattr(row, "unique_skill_description", ""))
        if len(description) > 150:
            description = description[:147].rstrip() + "..."
        print(f"  {index}. {row.unique_skill_title}")
        if description:
            print(f"     {description}")
    selected = input("Select skill number, or blank to cancel: ").strip()
    if not selected:
        return profile
    if not selected.isdigit() or not (1 <= int(selected) <= len(matches)):
        print("Invalid skill selection.")
        return profile
    level = float(input("Set level 0-6: ").strip())
    row = matches.iloc[int(selected) - 1]
    return add_profile_skill(profile, context.skills, str(row.skill_id), level)


def choose_target_mode(context, profile: ReviewedSkillProfile, current_role_id: str | None):
    while True:
        print("\nTarget mode:")
        print("  1. Explore other pathways")
        print("  2. Advance to next-level roles")
        print("  3. Choose a specific dataset role")
        print("  4. Upload/paste JD for suitability scoring")
        choice = input("Select 1-4: ").strip().casefold()
        if choice == "1":
            recommendations = recommend_explore_targets(context, profile, current_role_id=current_role_id, count=15)
            selected_role_id = choose_from_recommendations(recommendations)
            if selected_role_id is None:
                continue
            return build_target_result_for_role(
                context, profile, selected_role_id, "explore_pathways", recommendations, current_role_id=current_role_id
            ), "Explore mode ranks roles by deterministic skill suitability, with near-duplicate role families de-prioritised in the first page."
        if choice == "2":
            recommendations = recommend_advance_targets(context, profile, current_role_id=current_role_id, count=15)
            selected_role_id = choose_from_recommendations(recommendations)
            if selected_role_id is None:
                continue
            return build_target_result_for_role(
                context, profile, selected_role_id, "advance_roles", recommendations, current_role_id=current_role_id
            ), "Advance mode prefers same sector/track when a current dataset role is known, with near-duplicate role families de-prioritised in the first page."
        if choice == "3":
            role = choose_role(context, prompt="Search target role", allow_back=True)
            if role is None:
                continue
            return build_target_result_for_role(
                context, profile, str(role.role_id), "specific_role", current_role_id=current_role_id
            ), f"Specific dataset role selected: {role.job_role}."
        if choice == "4":
            jd_choice = choose_jd_document()
            if jd_choice is None:
                continue
            document, detail = jd_choice
            return build_target_result_for_jd(context, profile, document), detail
        print("Please choose 1, 2, 3, or 4.")


def choose_from_recommendations(recommendations, page_size: int = 3) -> str | None:
    if recommendations.empty:
        raise SystemExit("No recommendations were generated.")
    page_start = 0
    while True:
        page_end = min(page_start + page_size, len(recommendations))
        print("\nRecommended target roles")
        print(f"Showing {page_start + 1}-{page_end} of {len(recommendations)}. Commands: number=select, m=more, p=previous, b=back")
        page = recommendations.iloc[page_start:page_end]
        for offset, row in enumerate(page.itertuples(index=False), start=page_start + 1):
            print(
                f"  {offset}. {row.job_role} - {float(row.suitability_percentage):.2f}% fit; "
                f"matched {int(row.matched_skill_count)}/{int(row.target_skill_count)}; gaps {int(row.gap_skill_count)}"
            )
            print(f"     {row.sector} / {row.track}")
        raw = input("Choose target, m for more, p for previous, b to go back [1]: ").strip().casefold() or "1"
        if raw in {"b", "back"}:
            return None
        if raw in {"m", "more", "n", "next"}:
            if page_end >= len(recommendations):
                print("No more recommendations in this shortlist.")
            else:
                page_start = page_end
            continue
        if raw in {"p", "prev", "previous"}:
            page_start = max(0, page_start - page_size)
            continue
        if raw.isdigit() and 1 <= int(raw) <= len(recommendations):
            return str(recommendations.iloc[int(raw) - 1].role_id)
        print("Invalid selection.")


def choose_role(context, prompt: str, allow_back: bool = False):
    while True:
        suffix = " (blank or b to go back)" if allow_back else ""
        query = input(f"{prompt}{suffix}: ").strip()
        if allow_back and query.casefold() in {"", "b", "back"}:
            return None
        matches = search_roles(context.requirements, query, limit=8)
        if matches.empty:
            print("No matching roles found. Try a broader term such as data, analyst, logistics, finance, or technology.")
            continue
        for index, row in enumerate(matches.itertuples(index=False), start=1):
            print(f"  {index}. {row.job_role}")
            print(f"     {row.sector} / {row.track}")
        raw = input("Select role number, blank to search again, or b to go back: ").strip().casefold()
        if allow_back and raw in {"b", "back"}:
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(matches):
            return matches.iloc[int(raw) - 1]


def choose_jd_document():
    while True:
        print("\nJD input:")
        print("  1. Upload JD file (.pdf or .docx)")
        print("  2. Paste JD text")
        print("  b. Back to target mode")
        choice = input("Select 1, 2, or b: ").strip().casefold()
        if choice in {"b", "back"}:
            return None
        if choice == "1":
            path = input("JD file path, or b to go back: ").strip().strip('"')
            if path.casefold() in {"b", "back"}:
                return None
            return extract_text_from_file(path), f"JD file parsed from {Path(path).name}."
        if choice == "2":
            print("Paste JD text. End with a single line containing only END. Use BACK alone to return.")
            lines: list[str] = []
            while True:
                line = input()
                if line.strip() == "END":
                    break
                if not lines and line.strip().casefold() in {"back", "b"}:
                    return None
                lines.append(line)
            return document_text_from_pasted_input("\n".join(lines), source_type="pasted_jd"), "Pasted JD text scored at runtime."
        print("Please choose 1, 2, or b.")


def print_result(result, report_path: Path) -> None:
    summary = result.selected_summary
    print("\nResult")
    print(f"Target: {summary.job_role}")
    print(f"Suitability: {summary.suitability_percentage:.2f}%")
    if result.pathway_edge and "edge_fit_percentage" in result.pathway_edge:
        print(f"Pathway fit: {float(result.pathway_edge['edge_fit_percentage']):.2f}%")
    print(f"Matched skills: {summary.matched_skill_count}/{summary.target_skill_count}")
    print(f"Skills below target: {summary.gap_skill_count}")
    print("\nWhy this score")
    print(result.score_explanation.text)
    print(f"Explanation source: {result.score_explanation.source}")
    print("\nTop gaps")
    gaps = result.selected_gap_table.loc[result.selected_gap_table["gap"] > 0].head(5)
    if gaps.empty:
        print("  No remaining gaps.")
    for row in gaps.itertuples(index=False):
        print(f"  - {row.unique_skill_title}: current {row.current_level:g}, target {row.target_level:g}, gap {row.gap:g}")
    print("\nNext actions")
    if result.action_plan.empty:
        print("  No action items generated.")
    for row in result.action_plan.itertuples(index=False):
        print(f"  - {row.skill}: {row.next_action}")
    print(f"\nFull result report: {report_path}")


if __name__ == "__main__":
    main()







