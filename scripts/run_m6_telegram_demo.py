"""Run a scripted M6 Telegram-style MVP flow."""

from __future__ import annotations

from pathlib import Path

from jobs_skills.telegram_bot import TelegramCareerBotService, response_to_dict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SESSION_ID = "demo"


def append_step(transcript: list[str], command: str, response) -> None:
    transcript.append(f"### {command}")
    transcript.append("")
    transcript.append(response.text)
    if response.buttons:
        transcript.append("")
        transcript.append("Buttons: " + ", ".join(f"[{button.label} -> {button.action}:{button.value}]" for button in response.buttons))
    if response.attachment_path:
        transcript.append("")
        transcript.append(f"Attachment: {response.attachment_path}")
    transcript.append("")


def main() -> int:
    service = TelegramCareerBotService(PROJECT_ROOT)
    transcript = ["# M6 Telegram Flow Demo", ""]

    response = service.start_assessment(SESSION_ID)
    append_step(transcript, "/start_assessment", response)

    response = service.select_current_role(SESSION_ID, "data_analyst_fs")
    append_step(transcript, "/select_current_role data_analyst_fs", response)

    session = service.get_session(SESSION_ID)
    while len(session.baseline_answers) < len(session.baseline_questions):
        question = session.baseline_questions[len(session.baseline_answers)]
        response = service.answer_question(SESSION_ID, question.target_level)
        append_step(transcript, f"/answer_question {question.target_level:g}", response)

    response = service.recommend_roles(SESSION_ID)
    append_step(transcript, "/recommend_roles", response)

    data_scientist = session.recommendations.loc[session.recommendations["job_role"].str.casefold().eq("data scientist")].iloc[0]
    response = service.choose_pathway(SESSION_ID, str(data_scientist.role_id))
    append_step(transcript, f"/choose_pathway {data_scientist.role_id}", response)

    while len(session.gap_answers) < len(session.gap_questions):
        question = session.gap_questions[len(session.gap_answers)]
        current_level = session.baseline_vector.get(question.skill_id, 0.0)
        selected_level = max(1.0, question.target_level - 1.0) if current_level <= 0 else min(question.target_level, current_level + 1.0)
        response = service.answer_gap_question(SESSION_ID, selected_level)
        append_step(transcript, f"/answer_gap_question {selected_level:g}", response)

    for command, handler in [
        ("/explain_score", service.explain_score),
        ("/show_gaps", service.show_gaps),
        ("/show_pathway", service.show_pathway),
        ("/generate_action_plan", service.generate_action_plan),
    ]:
        response = handler(SESSION_ID)
        append_step(transcript, command, response)

    output_path = PROJECT_ROOT / "data" / "processed" / "m6_telegram_flow_demo.md"
    output_path.write_text("\n".join(transcript), encoding="utf-8")

    final_score = service.explain_score(SESSION_ID)
    action_plan = service.generate_action_plan(SESSION_ID)
    print(f"baseline_answers={len(session.baseline_answers)}")
    print(f"recommendations={len(session.recommendations)}")
    print(f"selected_role_id={session.selected_role_id}")
    print(f"gap_answers={len(session.gap_answers)}")
    print(f"main_buttons={len(final_score.buttons)}")
    print(f"action_plan={action_plan.attachment_path}")
    print(f"output={output_path}")
    print(response_to_dict(final_score)["text"].splitlines()[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
