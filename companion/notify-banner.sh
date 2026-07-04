#!/bin/sh
# Optional native macOS banner for the Clawd companion. Wired only by
# `install.sh --with-banner`, mapping:
#   Stop         -> notify-banner.sh done          (Claude finished a turn)
#   Notification -> notify-banner.sh needs-input   (Claude is waiting on you)
#
# For "needs-input" it fires only on a genuine mid-turn block (a question /
# permission prompt), NOT on Claude Code's 60-second idle "waiting for your input"
# nudge — matching the tray, so idle sitting doesn't pop a banner. The title
# includes the session name (from the hook's session_id). Uses terminal-notifier
# (shows the Clawd icon) when installed, else osascript. Visual only — no sound.
# Never fails the calling hook.
DIR="$(cd "$(dirname "$0")" && pwd)"
EVENT="$1"
case "$EVENT" in
  done)        MSG="All done ✅" ;;
  needs-input) MSG="Needs your input 👋" ;;
  *)           exit 0 ;;
esac

# From the hook's stdin JSON: resolve the session name, and decide whether to skip
# (the idle-timeout notification for needs-input isn't a real block).
NAME=""; SKIP="0"
if [ ! -t 0 ]; then
  INPUT="$(cat 2>/dev/null)"
  if [ -n "$INPUT" ]; then
    RES="$(printf '%s' "$INPUT" | /usr/bin/python3 -c '
import json, sys, os, glob
event = sys.argv[1] if len(sys.argv) > 1 else ""
try: d = json.load(sys.stdin)
except Exception: d = {}
sid = str(d.get("session_id") or "")
msg = str(d.get("message") or "")
name = ""
if sid:
    mt = -1
    for p in glob.glob(os.path.expanduser("~/.claude/sessions/*.json")):
        try:
            o = json.load(open(p)); m = os.path.getmtime(p)
        except Exception:
            continue
        if o.get("sessionId") == sid and m > mt:
            mt = m; name = (o.get("name") or "").strip()
# Idle nudge ("Claude is waiting for your input") is not a mid-turn block — skip it.
skip = event == "needs-input" and "waiting for your input" in msg.lower()
print(("1" if skip else "0") + "|" + name)
' "$EVENT" 2>/dev/null)"
    SKIP="${RES%%|*}"
    NAME="${RES#*|}"
  fi
fi
[ "$SKIP" = "1" ] && exit 0

TITLE="Claude Code"
[ -n "$NAME" ] && TITLE="Claude Code · $NAME"

# Icon: a local companion/banner-icon.png (your own) overrides the generated
# default (generated/clawd-icon.png). Only used by terminal-notifier.
ICON=""
for c in "$DIR/banner-icon.png" "$DIR/../generated/clawd-icon.png"; do
  [ -f "$c" ] && { ICON="$c"; break; }
done

if command -v terminal-notifier >/dev/null 2>&1; then
  set -- -title "$TITLE" -message "$MSG"
  [ -n "$ICON" ] && set -- "$@" -contentImage "$ICON"
  terminal-notifier "$@" >/dev/null 2>&1 &
else
  osascript -e "display notification \"$MSG\" with title \"$TITLE\"" >/dev/null 2>&1 &
fi
exit 0
