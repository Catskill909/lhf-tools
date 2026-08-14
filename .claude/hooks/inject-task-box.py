#!/usr/bin/env python3
"""SessionStart hook — put HANDOFF.md's task box in front of Claude, always.

`CLAUDE.md` line 3 already says "Read HANDOFF.md first". On 13 August 2026 that
instruction was loaded and ignored: a session went straight to the code, spent
an evening "discovering" the 100-episode feed cap, episode rotation and the
archive becoming the only copy — all of it already written down, correctly, in
the task box — and raised a false alarm about data loss on the way.

An instruction in a file is advice. This is not: the harness runs it, so the
four buckets and the open ASK threads are in context before the first tool call
whether or not anyone remembers to look.

Stdlib only, and silent on any failure — a broken hook must never be the reason
a session cannot start. Exiting 0 with no output simply injects nothing.
"""

import json
import os
import sys

HEADING = "## What actually needs doing"

PREFACE = """The task box from HANDOFF.md, injected automatically at session
start. This is the whole of what is actionable in this project: if something is
not in here, it is not a task — everything else in these documents is recorded
reasoning (parked ideas, rejected options, trade-offs) and is easy to mistake
for a backlog.

Read it before starting any audit or diagnosis. It usually already contains the
answer, and it says which questions are known-open and waiting on someone else.

"""


def main():
    # CLAUDE_PROJECT_DIR is set by the harness; the fallback walks up from
    # .claude/hooks/ so this keeps working if it is ever run by hand.
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    try:
        with open(os.path.join(root, "HANDOFF.md"), encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return  # No HANDOFF.md here — nothing to say.

    start = next((i for i, l in enumerate(lines)
                  if l.startswith(HEADING)), None)
    if start is None:
        # The heading was renamed. Better to inject nothing than to guess at a
        # slice of the document and present the wrong thing as the task list.
        return

    # The box ends at the first horizontal rule after the heading.
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].strip() == "---"), len(lines))

    box = "\n".join(lines[start:end]).strip()
    if not box:
        return

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": PREFACE + box,
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
