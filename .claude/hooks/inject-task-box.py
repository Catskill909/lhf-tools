#!/usr/bin/env python3
"""SessionStart hook — put the doc routing table and HANDOFF.md's task box in
front of Claude, always.

`CLAUDE.md` line 3 already says "Read HANDOFF.md first". On 13 August 2026 that
instruction was loaded and ignored twice over: a session went straight to the
code, spent an evening "discovering" the 100-episode feed cap, episode rotation
and the archive becoming the only copy — all already written down, correctly, in
the task box — and raised a false alarm about data loss on the way. Later the
same session answered a client-facing question without reading
`docs/client-guide.md`, which already answered it, and framed it wrongly.

Two different failures, one cause: nothing routed to the document that held the
answer. So this injects both halves —

    docs/INDEX.md   which document to read for which subject
    HANDOFF.md      what is actually outstanding

An instruction in a file is advice. This is not: the harness runs it, so both
are in context before the first tool call whether or not anyone remembers.

Stdlib only, and silent on any failure — a broken hook must never be the reason
a session cannot start. Exiting 0 with no output simply injects nothing.
"""

import json
import os
import sys

HEADING = "## What actually needs doing"
INDEX_PATH = ""   # set in main() once the project root is known

PREFACE = """Injected automatically at session start: first the routing table
for this project's documents, then HANDOFF.md's task box.

**Use the routing table before answering questions about status, behaviour,
history, or anything client-facing.** The code says what the software does; it
does not say what was decided, promised, already measured, or deliberately not
built — and each of those has been got wrong here by reading code alone.

The task box is the whole of what is actionable: if something is not in it, it
is not a task. Everything else in these documents is recorded reasoning — parked
ideas, rejected options, trade-offs — and reads like a backlog without being one.

"""


def task_box(root):
    """HANDOFF.md's four buckets — the only place a task is real."""
    try:
        with open(os.path.join(root, "HANDOFF.md"), encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return ""

    start = next((i for i, l in enumerate(lines)
                  if l.startswith(HEADING)), None)
    if start is None:
        # The heading was renamed. Better to inject nothing than to guess at a
        # slice of the document and present the wrong thing as the task list.
        return ""

    # The box ends at the first horizontal rule after the heading.
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].strip() == "---"), len(lines))
    return "\n".join(lines[start:end]).strip()


def routing():
    """docs/INDEX.md in full — it is written to be read at this size."""
    try:
        with open(INDEX_PATH, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def main():
    global INDEX_PATH

    # CLAUDE_PROJECT_DIR is set by the harness; the fallback walks up from
    # .claude/hooks/ so this keeps working if it is ever run by hand.
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    INDEX_PATH = os.path.join(root, "docs", "INDEX.md")

    parts = [p for p in (routing(), task_box(root)) if p]
    if not parts:
        return

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": PREFACE + "\n\n---\n\n".join(parts),
        }
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:                                   # noqa: BLE001
        # Deliberately broad: this runs before the session exists, so an
        # unexpected failure here would be reported as a startup problem with
        # no obvious cause. Injecting nothing is always the safe outcome.
        pass
