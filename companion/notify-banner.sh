#!/bin/sh
# Optional native macOS banner for the Clawd companion. Wired only by
# `install.sh --with-banner`, mapping:
#   Stop         -> notify-banner.sh done          (Claude finished a turn)
#   Notification -> notify-banner.sh needs-input   (Claude is waiting on you)
#
# The banner title includes the session's name (your /rename value, resolved from
# the hook's session_id) so you can tell which session it's about. Uses
# terminal-notifier (which shows the Clawd icon) when installed, else falls back
# to osascript. Visual only — no sound, so it never doubles a chime. Never fails
# the calling hook.
DIR="$(cd "$(dirname "$0")" && pwd)"

case "$1" in
  done)        MSG="All done ✅" ;;
  needs-input) MSG="Needs your input 👋" ;;
  *)           exit 0 ;;
esac

# Resolve the session name from the hook's stdin JSON (session_id → ~/.claude/sessions).
NAME=""
if [ ! -t 0 ]; then
  INPUT="$(cat 2>/dev/null)"
  if [ -n "$INPUT" ]; then
    NAME="$(printf '%s' "$INPUT" | /usr/bin/python3 -c '
import json, sys, os, glob
try: d = json.load(sys.stdin)
except Exception: d = {}
sid = str(d.get("session_id") or "")
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
print(name)
' 2>/dev/null)"
  fi
fi

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
