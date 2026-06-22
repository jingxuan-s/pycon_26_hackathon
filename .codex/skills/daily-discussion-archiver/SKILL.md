---
name: daily-discussion-archiver
description: Compact Codex conversation history into daily human-AI collaboration summaries and raw markdown archives for judging/process evidence. Use when the user asks to summarize, compact, archive, preserve, or export daily discussions, chat logs, interaction logs, Human-AI collaboration records, process evidence, or judging submission notes into docs/daily_discussion/YYYY-MM-DD.md and raw archive files.
---

# Daily Discussion Archiver

## Workflow

Use this skill to create two artifacts for a project day:

- Compact summary: `docs/daily_discussion/YYYY-MM-DD.md`
- Raw markdown archive: `docs/daily_discussion/raw/YYYY-MM-DD.md`

Default to the current workspace as the project root unless the user gives another repo/path. Use the local current date unless the user names a date.

## Capture Rules

1. Preserve raw conversation before summarizing when possible.
2. Prefer exact thread retrieval if the Codex app exposes thread tools. If needed, search for `read_thread` or related thread tools and use them to collect the conversation.
3. If exact full-thread access is unavailable, archive the visible conversation context and clearly note at the top of the raw archive that it is context-limited.
4. Do not invent messages, timestamps, or participants. Summaries may synthesize decisions, but raw archives must only include available conversation content.
5. If the user requires a legally/administratively complete raw log and the full thread is unavailable, ask the user to export or provide the full log.

## Summary Content

Write the compact daily summary as Markdown with these sections when relevant:

```markdown
# Daily Discussion Summary - YYYY-MM-DD

## Purpose
## Main Decisions
## Dataset / Technical Findings
## Product Direction
## Architecture Decisions
## Explainability Decisions
## Judging / Process Notes
## Open Questions
## Next Actions
```

Keep the summary compact and evidence-oriented. Focus on decisions, tradeoffs, rationale, validation, and how human-AI collaboration shaped the product.

## Raw Archive Format

Write the raw archive as Markdown. Use a short header, then transcript content:

```markdown
# Raw Conversation Archive - YYYY-MM-DD

Project: <project name or path>
Archive note: <complete thread / context-limited / user-provided export>

---

## Transcript

<raw markdown transcript>
```

When formatting raw messages manually, use this simple pattern:

```markdown
### User

<message>

### Assistant

<message>

### Tool / Artifact Notes

<important tool actions or generated file references, if visible>
```

## Writing Files

Use `scripts/write_daily_discussion.py` to write both artifacts consistently. Prepare temporary files containing the summary markdown and raw archive markdown, then run:

```bash
python scripts/write_daily_discussion.py \
  --project-root /path/to/project \
  --date YYYY-MM-DD \
  --summary-text-file /path/to/summary.md \
  --raw-text-file /path/to/raw.md
```

Optional arguments:

```bash
--summary-dir docs/daily_discussion
--raw-dir docs/daily_discussion/raw
--mode overwrite
```

Use `--mode append` only when intentionally adding a new section to an existing day. Default to overwrite so the summary and raw archive represent the latest complete daily compaction.

## Completion Checklist

Before final response:

- Confirm both files exist.
- Report the exact paths written.
- Mention if the raw archive is complete or context-limited.
- Do not paste the full raw archive into chat unless the user asks.