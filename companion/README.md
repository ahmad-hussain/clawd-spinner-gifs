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
- `install.sh` — setup. Run with no flags for an **interactive** flow (preview,
  then pick any mix of the three cues); or use flags (`--install-hooks` /
  `--print`, plus `--no-tray` / `--with-sound` / `--with-banner`) for scripts/agents.
- `chime.sh` — **optional** macOS sound cue (`done` / `needs-input`) via `afplay`,
  wired only by `--with-sound`. The two sounds (Glass / Funk) are editable at the
  top of the file; any `/System/Library/Sounds/` name works.
- `notify-banner.sh` — **optional** native macOS banner (`done` / `needs-input`),
  wired only by `--with-banner`. The title includes the session name (resolved
  from the hook's `session_id`) so you can tell which session it's about. Uses
  `terminal-notifier` (shows a custom icon) when installed, else falls back to
  `osascript`. Visual only — no sound.
- `banner-icon.png` *(optional, local)* — a custom icon for the banner. If present
  it overrides the generated default `../generated/clawd-icon.png`. Git-ignored
  (drop in any PNG).
- `.venv/` — one-time venv from `/usr/bin/python3` + `pyobjc-framework-Cocoa`.
  Git-ignored.
- The waiting mascot is a companion-only asset generated as
  `../generated/Clawd-_Waiting.gif` (the underscore prefix keeps it out of the
  random working pool). It's produced by `frames_notifying()` in the generator.

## Setup

Easiest — run the installer and follow the prompts (it previews the cues, lets
you pick any mix of tray / sound / banner, builds the venv, generates the GIFs,
and merges the chosen hooks into `~/.claude/settings.json` with a backup):

```sh
./companion/install.sh
```

Non-interactive (scripts / agents):

```sh
./companion/install.sh --install-hooks                 # tray only (default)
./companion/install.sh --install-hooks --with-sound    # tray + sound
./companion/install.sh --install-hooks --with-banner   # tray + banner
./companion/install.sh --install-hooks --no-tray --with-sound --with-banner
./companion/install.sh --print [flags]                 # print the hook JSON instead of merging
```

Restart Claude Code (or `/hooks`) afterward so the hooks load; new sessions pick
it up automatically. The tray uses these five hooks — `UserPromptSubmit`→`show.sh`,
`PreToolUse`/`PostToolUse`→`resume.sh`, `Notification`→`notify.sh`, `Stop`→`hide.sh`;
`--with-sound` adds `chime.sh` and `--with-banner` adds `notify-banner.sh` on
`Notification` (needs-input) and `Stop` (done). Preview one scene without hooks:
`companion/.venv/bin/python3 companion/clawd_companion.py preview Clawd-_Waiting.gif "demo"`

## Tuning

- `SIZE` (default 135) — mascot size in px. `GAP`, `MARGIN_RIGHT`, `MARGIN_BOTTOM`
  — tray spacing/placement. `IDLE_QUIT` — daemon idle-quit seconds. `NAME_MAX` —
  name-tag truncation.

## Notes

- macOS only (uses AppKit). The generator itself only needs Pillow and is
  cross-platform; only this companion is macOS-specific.
- **Banner icon:** `notify-banner.sh` shows a custom icon only via
  `terminal-notifier` (`brew install terminal-notifier`); with plain `osascript`
  the banner uses the "Script Editor" icon (the icon can't be changed). Drop a
  PNG at `companion/banner-icon.png` to use your own, else the generated
  `generated/clawd-icon.png` is used.
- **Claude Code's own notifications** are a separate, built-in option: enable
  `inputNeededNotifEnabled` / `agentPushNotifEnabled` in settings and grant Ghostty
  notification permission (System Settings → Notifications → Ghostty).
- **Trust model:** these scripts are wired into your *global* Claude Code config
  and run on every prompt/stop, so anyone who can edit them gets code execution
  on every turn. Keep `clawd_companion.py` / `*.sh` write-protected and re-audit
  if they change. (A security audit found no network, no secrets, no obfuscation,
  no dangerous calls — it only reads local GIFs + `~/.claude/sessions` names and
  draws a click-through panel.)
