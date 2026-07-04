#!/bin/sh
# One-shot setup for the Clawd working companion (macOS).
#
#   ./companion/install.sh                 # venv + deps + generate GIFs, then PRINT the hooks to add
#   ./companion/install.sh --install-hooks # also merge the hooks into ~/.claude/settings.json (backup first)
#
# Safe to re-run: the venv/deps/hook-merge steps are idempotent. Restart Claude
# Code afterward so the hooks load.
set -e

COMPANION="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$COMPANION/.." && pwd)"
VENV="$COMPANION/.venv"
PY_SYS="/usr/bin/python3"

echo "==> Clawd companion install"
echo "    repo:      $REPO"
echo "    companion: $COMPANION"

if [ "$(uname)" != "Darwin" ]; then
  echo "!!  The companion tray is macOS-only (uses AppKit). You can still generate"
  echo "    GIFs on any OS with Pillow; skipping companion venv/hooks."
  exit 0
fi

# 1. venv from the system python (needed for AppKit) + both deps (Pillow + PyObjC)
if [ ! -x "$VENV/bin/python3" ]; then
  echo "==> creating venv ($PY_SYS) at $VENV"
  "$PY_SYS" -m venv "$VENV"
fi
echo "==> installing deps (Pillow + pyobjc-framework-Cocoa)"
"$VENV/bin/python3" -m pip install --quiet --upgrade pip
"$VENV/bin/python3" -m pip install --quiet -r "$REPO/requirements.txt" -r "$COMPANION/requirements.txt"

# 2. generate the GIFs (generated/ is git-ignored, so produce them locally)
echo "==> generating GIFs"
"$VENV/bin/python3" "$REPO/generate_clawd_gifs.py" >/dev/null
echo "    $(ls "$REPO/generated"/Clawd-*.gif | wc -l | tr -d ' ') GIFs in $REPO/generated"

# 3. hooks — print, or (with --install-hooks) merge into ~/.claude/settings.json
MODE="print"
[ "$1" = "--install-hooks" ] && MODE="merge"

"$VENV/bin/python3" - "$COMPANION" "$MODE" <<'PYEOF'
import json, os, shutil, sys, time

companion, mode = sys.argv[1], sys.argv[2]
EVENTS = [("UserPromptSubmit", "show.sh"), ("PreToolUse", "resume.sh"),
          ("PostToolUse", "resume.sh"), ("Notification", "notify.sh"),
          ("Stop", "hide.sh")]

def entry(script):
    return {"type": "command", "command": os.path.join(companion, script), "async": True}

if mode == "print":
    hooks = {ev: [{"hooks": [entry(s)]}] for ev, s in EVENTS}
    print("\n==> Add these to the \"hooks\" object in ~/.claude/settings.json")
    print("    (merge into any existing hooks; then restart Claude Code):\n")
    print(json.dumps({"hooks": hooks}, indent=2))
else:
    path = os.path.expanduser("~/.claude/settings.json")
    settings = {}
    if os.path.exists(path):
        try:
            with open(path) as f:
                settings = json.load(f)
        except Exception as e:
            print(f"!!  could not parse {path}: {e}\n    Fix it or run without --install-hooks and merge by hand.")
            sys.exit(1)
        bak = f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.copy2(path, bak)
        print(f"==> backed up settings to {bak}")
    hooks = settings.setdefault("hooks", {})
    added = 0
    for ev, script in EVENTS:
        cmd = os.path.join(companion, script)
        arr = hooks.setdefault(ev, [])
        if not any(cmd in json.dumps(m) for m in arr):
            arr.append({"hooks": [entry(script)]})
            added += 1
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(settings, f, indent=2)
    print(f"==> merged {added} new hook(s) into {path} ({len(EVENTS) - added} already present)")
PYEOF

echo ""
echo "Done. Restart Claude Code so the hooks load."
