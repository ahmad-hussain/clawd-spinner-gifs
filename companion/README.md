# Clawd Working Companion

A **per-session status beacon** for Claude Code (macOS). Each active Claude
session gets its own Clawd mascot in a small tray stacked in the bottom-right
corner. A mascot is present while that session is working and disappears when the
session finishes its turn — so from another app (Slack, browser, …) you can
glance and see which sessions are still busy, and its disappearance is your
"that answer's ready" signal. When a session is blocked waiting on your input,
its mascot switches to a gentle **hop with a red `!`** ("needs you"), and its
name tag turns amber.

Each mascot is tagged with the session's name — your `/rename` value (resolved
from `~/.claude/sessions/*.json` by `session_id`), or a stable random name like
`brave-otter` for unnamed sessions.

## How it works

- **Thin hook subcommands** write/update/remove one small JSON state file per
  session under `$TMPDIR/clawd-companion/sessions/`, keyed by the `session_id`
  the hook receives on stdin:
  - `show`   (UserPromptSubmit) → state = working (random scene)
  - `notify` (Notification)     → state = waiting (hop + `!`), but ONLY when Claude
    is blocked mid-turn needing input (a question / permission prompt). Claude
    Code's Notification hook also fires on the 60s idle timeout *after* a turn
    ends — when no active-turn state file exists — so that case is ignored
    (idle ≠ "your turn").
  - `resume` (PreToolUse + PostToolUse) → flip waiting → working once Claude resumes
    after you answer. PostToolUse fires the instant `AskUserQuestion` returns your
    answer (so answer-then-text-only turns clear too, not just answer-then-more-tools);
    PreToolUse clears it snappily when the next tool runs after a permission grant.
    Fast-path: only spawns Python if some session is actually waiting.
  - `hide`   (Stop)             → remove the session's file
  Each (except `resume`) also makes sure the daemon is running.
- **One long-lived daemon** (`clawd_companion.py daemon`) owns the tray: it polls
  the state dir and renders one borderless, transparent, always-on-top NSPanel
  per active session — floating over fullscreen Spaces, no Dock icon, no
  focus-steal, click-through. It compacts the stack as sessions come and go, and
  quits itself after a few minutes idle. Only one daemon runs at a time (flock).

## Files

- `clawd_companion.py` — subcommands `show | notify | hide | daemon | preview`.
- `show.sh` / `notify.sh` / `resume.sh` / `hide.sh` — thin hook wrappers (derive
  their own dir, pass stdin through, always `exit 0` so they can never stall a turn).
- `.venv/` — one-time venv from `/usr/bin/python3` + `pyobjc-framework-Cocoa`.
  Git-ignored.
- The waiting mascot is a companion-only asset generated as
  `../generated/Clawd-_Waiting.gif` (the underscore prefix keeps it out of the
  random working pool). It's produced by `frames_notifying()` in the generator.

## Setup

```sh
/usr/bin/python3 -m venv companion/.venv
companion/.venv/bin/python3 -m pip install -r companion/requirements.txt
```

Then add to `~/.claude/settings.json` (absolute paths; `async`):

```json
{
  "hooks": {
    "UserPromptSubmit": [ { "hooks": [ { "type": "command", "command": "~/Documents/cc-gifs/companion/show.sh",   "async": true } ] } ],
    "PreToolUse":       [ { "hooks": [ { "type": "command", "command": "~/Documents/cc-gifs/companion/resume.sh", "async": true } ] } ],
    "PostToolUse":      [ { "hooks": [ { "type": "command", "command": "~/Documents/cc-gifs/companion/resume.sh", "async": true } ] } ],
    "Notification":     [ { "hooks": [ { "type": "command", "command": "~/Documents/cc-gifs/companion/notify.sh", "async": true } ] } ],
    "Stop":             [ { "hooks": [ { "type": "command", "command": "~/Documents/cc-gifs/companion/hide.sh",   "async": true } ] } ]
  }
}
```

Restart Claude Code (or `/hooks`) so the hooks load. New sessions pick it up
automatically. Preview a specific scene without hooks:
`companion/.venv/bin/python3 companion/clawd_companion.py preview Clawd-_Waiting.gif "demo"`

## Tuning

- `SIZE` (default 135) — mascot size in px. `GAP`, `MARGIN_RIGHT`, `MARGIN_BOTTOM`
  — tray spacing/placement. `IDLE_QUIT` — daemon idle-quit seconds. `NAME_MAX` —
  name-tag truncation.

## Notes

- macOS only (uses AppKit). The generator itself only needs Pillow and is
  cross-platform; only this companion is macOS-specific.
- **Trust model:** these scripts are wired into your *global* Claude Code config
  and run on every prompt/stop, so anyone who can edit them gets code execution
  on every turn. Keep `clawd_companion.py` / `*.sh` write-protected and re-audit
  if they change. (A security audit found no network, no secrets, no obfuscation,
  no dangerous calls — it only reads local GIFs + `~/.claude/sessions` names and
  draws a click-through panel.)
