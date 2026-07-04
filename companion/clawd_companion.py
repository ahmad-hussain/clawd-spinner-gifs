#!/usr/bin/env python3
"""Clawd working companion — a per-session status-beacon tray for Claude Code.

Each active Claude session gets its own Clawd mascot stacked in the bottom-right
corner. A mascot is present while that session is working and disappears when the
session finishes its turn — so from another app (Slack, browser, …) you can glance
and see which sessions are still busy. When a session is blocked waiting on your
input, its mascot gets a "!" badge. Each mascot is tagged with the session's name
(your `/rename` value, or a stable random name for unnamed sessions).

Architecture:
  - Thin hook subcommands write/update/remove one small JSON state file per
    session, keyed by the hook's `session_id` (read from stdin):
        show   (UserPromptSubmit) -> state = working
        notify (Notification)     -> state = waiting
        hide   (Stop)             -> remove the session's file
    Each also makes sure the daemon is running.
  - One long-lived `daemon` owns the tray: it polls the state dir and renders one
    borderless, transparent, always-on-top NSPanel per active session, floating
    over fullscreen Spaces, with no Dock icon and no focus-steal.

Subcommands: show | notify | hide | daemon | preview [gif] [name]
Runs on companion/.venv (built from /usr/bin/python3) with pyobjc-framework-Cocoa.
"""

import glob
import hashlib
import json
import os
import random
import select
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
GENERATED_DIR = os.path.join(HERE, "..", "generated")
WAITING_GIF = os.path.join(GENERATED_DIR, "Clawd-_Waiting.gif")  # "needs your input" mascot
STATE_DIR = os.path.join(tempfile.gettempdir(), "clawd-companion")
SESS_DIR = os.path.join(STATE_DIR, "sessions")
LOCK_PATH = os.path.join(STATE_DIR, "daemon.lock")
CLAUDE_SESSIONS_DIR = os.path.expanduser("~/.claude/sessions")

NAME_MAX = 20  # display name truncation

# tray layout (px)
SIZE = 135
TAG_H = 14           # extra height above the mascot for the name tag (which rests on the frame's top edge)
GAP = 10
MARGIN_RIGHT = 16
MARGIN_BOTTOM = 12
OPACITY = 0.65       # 0.0–1.0 overall opacity of each mascot (incl. its name tag); 1.0 = fully solid
POLL = 0.25
IDLE_QUIT = 180  # daemon quits after this many seconds with zero active sessions
STALE_SECS = 90  # prune a headless (claude -p / SDK) session's mascot after this
                 # long without an update — those never fire Stop to remove it

_ADJ = ["brave", "calm", "clever", "cozy", "eager", "fuzzy", "jolly", "lucky",
        "mellow", "nimble", "plucky", "snug", "sunny", "witty", "zesty", "brisk",
        "perky", "spry", "bubbly", "chirpy"]
_NOUN = ["otter", "fox", "kiwi", "panda", "newt", "wren", "yak", "moth", "lynx",
         "tern", "seal", "crow", "ibex", "koi", "vole", "wolf", "bee", "owl",
         "cub", "hare"]


# --- shared helpers --------------------------------------------------------
def _ensure_dirs():
    os.makedirs(SESS_DIR, exist_ok=True)


def _read_hook_input():
    """Read the hook's JSON payload from stdin without ever blocking."""
    try:
        if sys.stdin is None or sys.stdin.closed or sys.stdin.isatty():
            return {}
        r, _, _ = select.select([sys.stdin], [], [], 0.6)
        if not r:
            return {}
        raw = sys.stdin.read()
    except Exception:
        return {}
    if raw and raw.strip():
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return {}


def _session_id(data):
    return str(data.get("session_id") or "default")


def _random_name(sid):
    h = int(hashlib.md5(sid.encode()).hexdigest(), 16)
    return f"{_ADJ[h % len(_ADJ)]}-{_NOUN[(h // len(_ADJ)) % len(_NOUN)]}"


def _session_name(sid):
    """Resolve the /rename display name from Claude's session registry; else a
    stable random name."""
    best, best_mt = None, -1.0
    try:
        for fn in os.listdir(CLAUDE_SESSIONS_DIR):
            if not fn.endswith(".json"):
                continue
            p = os.path.join(CLAUDE_SESSIONS_DIR, fn)
            try:
                o = json.load(open(p))
                mt = os.path.getmtime(p)
            except Exception:
                continue
            if o.get("sessionId") == sid and mt > best_mt:
                best, best_mt = o, mt
    except FileNotFoundError:
        pass
    name = (best or {}).get("name") or ""
    name = name.strip()
    if not name:
        name = _random_name(sid)
    if len(name) > NAME_MAX:
        name = name[:NAME_MAX - 1] + "…"
    return name


def _registry_map():
    """{sessionId: entrypoint} from ~/.claude/sessions. Interactive terminal sessions
    use entrypoint 'cli'; SDK / headless sessions (e.g. a Slack bridge driving the
    Agent SDK) use an 'sdk*' entrypoint — we skip mascots for those, since they reply
    through their own channel and never fire Stop to clean up."""
    m = {}
    for p in glob.glob(os.path.expanduser("~/.claude/sessions/*.json")):
        try:
            o = json.load(open(p))
        except Exception:
            continue
        sid = o.get("sessionId")
        if sid:
            m[sid] = str(o.get("entrypoint") or "")
    return m


def _is_sdk_session(sid, regmap=None):
    ep = (regmap if regmap is not None else _registry_map()).get(sid, "")
    return ep.lower().startswith("sdk")


def _pick_gif():
    # Underscore-prefixed files (e.g. Clawd-_Waiting.gif) are special companion
    # assets, not spinner scenes — keep them out of the random working pool.
    gifs = [g for g in glob.glob(os.path.join(GENERATED_DIR, "Clawd-*.gif"))
            if not os.path.basename(g).startswith("Clawd-_")]
    return random.choice(gifs) if gifs else None


def _sess_path(sid):
    safe = "".join(c for c in sid if c.isalnum() or c in "-_")[:80] or "default"
    return os.path.join(SESS_DIR, safe + ".json")


def _atomic_write(path, obj):
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


def _daemon_alive():
    try:
        pid = int(open(LOCK_PATH).read().strip() or 0)
    except Exception:
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _ensure_daemon():
    if _daemon_alive():
        return
    subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "daemon"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)


# --- hook subcommands ------------------------------------------------------
def cmd_show(data):
    _ensure_dirs()
    sid = _session_id(data)
    if _is_sdk_session(sid):
        return  # SDK / headless session (e.g. Slack bridge) → no mascot at all
    gif = _pick_gif()
    if not gif:
        return
    _atomic_write(_sess_path(sid), {
        "sid": sid, "gif": gif, "name": _session_name(sid), "state": "working"})
    _ensure_daemon()


def cmd_notify(data):
    """Mark a session 'waiting on your input' — but ONLY when Claude is blocked
    mid-turn (a question or a permission prompt). Claude Code's Notification hook
    also fires on the 60s idle timeout after a finished turn; we must NOT treat
    that as 'your turn'. We distinguish by turn lifecycle: a mid-turn block still
    has this session's 'working' state file (created by `show` on
    UserPromptSubmit and only removed by `hide` on Stop); the idle timeout fires
    after Stop, when no such file exists."""
    _ensure_dirs()
    sid = _session_id(data)
    p = _sess_path(sid)
    if not os.path.exists(p):
        return  # no active turn → idle-after-done notification; leave the tray alone
    try:
        obj = json.load(open(p))
    except Exception:
        return
    obj["state"] = "waiting"
    _atomic_write(p, obj)
    _ensure_daemon()


def cmd_hide(data):
    sid = _session_id(data)
    try:
        os.remove(_sess_path(sid))
    except FileNotFoundError:
        pass


def cmd_resume(data):
    """Flip a session back to 'working' once Claude resumes after a mid-turn block
    (a question/permission the user just answered). Driven by both PreToolUse and
    PostToolUse: PostToolUse fires the instant AskUserQuestion returns the answer
    (so answer-then-text-only turns clear too, not just answer-then-more-tools);
    PreToolUse clears it snappily when the next tool runs after a permission grant.
    No-op unless the session is currently 'waiting', so it's cheap per tool event."""
    sid = _session_id(data)
    p = _sess_path(sid)
    if not os.path.exists(p):
        return
    try:
        obj = json.load(open(p))
    except Exception:
        return
    if obj.get("state") == "waiting":
        obj["state"] = "working"
        _atomic_write(p, obj)


# --- the tray daemon -------------------------------------------------------
def cmd_daemon():
    _ensure_dirs()
    import fcntl
    lockf = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return  # another daemon already owns the tray
    lockf.write(str(os.getpid()))
    lockf.flush()

    import objc
    from AppKit import (
        NSApplication, NSApplicationActivationPolicyAccessory, NSPanel, NSImageView,
        NSImage, NSTextField, NSColor, NSFont, NSScreen, NSView,
        NSBackingStoreBuffered, NSStatusWindowLevel, NSTextAlignmentCenter,
        NSWindowStyleMaskBorderless, NSWindowStyleMaskNonactivatingPanel,
        NSWindowCollectionBehaviorCanJoinAllSpaces, NSWindowCollectionBehaviorFullScreenAuxiliary,
        NSWindowCollectionBehaviorStationary, NSWindowCollectionBehaviorIgnoresCycle,
        NSImageScaleProportionallyUpOrDown,
    )
    from Foundation import NSObject, NSTimer, NSMakeRect, NSMakePoint

    def rounded_field(frame, text, bg, fg, font, radius):
        f = NSTextField.alloc().initWithFrame_(frame)
        f.setStringValue_(text)
        f.setBezeled_(False)
        f.setEditable_(False)
        f.setSelectable_(False)
        f.setDrawsBackground_(False)
        f.setAlignment_(NSTextAlignmentCenter)
        f.setTextColor_(fg)
        f.setFont_(font)
        f.setWantsLayer_(True)
        f.layer().setCornerRadius_(radius)
        f.layer().setBackgroundColor_(bg.CGColor())
        return f

    def make_panel():
        style = NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, SIZE, SIZE + TAG_H), style, NSBackingStoreBuffered, False)
        panel.setLevel_(NSStatusWindowLevel)
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setHasShadow_(False)
        panel.setAlphaValue_(OPACITY)
        panel.setIgnoresMouseEvents_(True)
        panel.setFloatingPanel_(True)
        panel.setBecomesKeyOnlyIfNeeded_(True)
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
            | NSWindowCollectionBehaviorStationary
            | NSWindowCollectionBehaviorIgnoresCycle)
        content = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, SIZE, SIZE + TAG_H))
        panel.setContentView_(content)
        iv = NSImageView.alloc().initWithFrame_(NSMakeRect(0, 0, SIZE, SIZE))
        iv.setImageScaling_(NSImageScaleProportionallyUpOrDown)
        iv.setAnimates_(True)
        content.addSubview_(iv)
        return panel, content, iv

    name_bg = NSColor.colorWithCalibratedWhite_alpha_(0.10, 0.82)
    wait_bg = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.95, 0.55, 0.05, 0.96)
    white = NSColor.whiteColor()
    name_font = NSFont.systemFontOfSize_(11)

    class Tray(NSObject):
        def init(self):
            self = objc.super(Tray, self).init()
            if self is None:
                return None
            self.cells = {}
            self.idle_since = None
            return self

        def tick_(self, timer):
            self.reconcile()

        def reconcile(self):
            try:
                files = [f for f in os.listdir(SESS_DIR) if f.endswith(".json")]
            except FileNotFoundError:
                files = []
            regmap = _registry_map()
            now = time.time()
            desired = {}
            for fn in files:
                p = os.path.join(SESS_DIR, fn)
                try:
                    rec = json.load(open(p))
                    mt = os.path.getmtime(p)
                except Exception:
                    continue
                sid = rec.get("sid") or fn[:-5]
                # Drop SDK/headless sessions (no mascot for those), and prune ghosts
                # that de-registered without firing Stop, once stale.
                if _is_sdk_session(sid, regmap) or (sid not in regmap and (now - mt) > STALE_SECS):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
                    continue
                desired[sid] = (rec, mt)

            for sid in list(self.cells):
                if sid not in desired:
                    self.cells[sid]["panel"].orderOut_(None)
                    self.cells[sid]["panel"].close()
                    del self.cells[sid]

            for sid, (rec, mt) in desired.items():
                state = rec.get("state", "working")
                name = rec.get("name", "")
                waiting = state == "waiting"
                # waiting sessions swap to the dedicated "come here" waving mascot
                disp_gif = WAITING_GIF if (waiting and os.path.exists(WAITING_GIF)) else rec.get("gif")
                cell = self.cells.get(sid)
                if cell is None:
                    panel, content, iv = make_panel()
                    cell = {"panel": panel, "content": content, "iv": iv,
                            "gif": None, "label": None, "label_key": None, "mt": mt}
                    self.cells[sid] = cell
                cell["mt"] = mt
                if disp_gif and disp_gif != cell["gif"]:
                    img = NSImage.alloc().initWithContentsOfFile_(disp_gif)
                    if img is not None:
                        cell["iv"].setImage_(img)
                        cell["iv"].setAnimates_(True)
                    cell["gif"] = disp_gif
                # name tag — turns amber with a "!" prefix when waiting on input
                label_key = (name, waiting)
                if label_key != cell["label_key"]:
                    if cell["label"] is not None:
                        cell["label"].removeFromSuperview()
                    text = ("! " + name) if waiting else name
                    lbl = rounded_field(NSMakeRect(6, SIZE - 6, SIZE - 12, 18),
                                        text, wait_bg if waiting else name_bg,
                                        white, name_font, 9)
                    cell["content"].addSubview_(lbl)
                    cell["label"] = lbl
                    cell["label_key"] = label_key

            # stack bottom-right, oldest nearest the corner
            vf = NSScreen.mainScreen().visibleFrame()
            x = vf.origin.x + vf.size.width - SIZE - MARGIN_RIGHT
            for i, (sid, cell) in enumerate(sorted(self.cells.items(), key=lambda kv: kv[1]["mt"])):
                y = vf.origin.y + MARGIN_BOTTOM + i * (SIZE + TAG_H + GAP)
                cell["panel"].setFrameOrigin_(NSMakePoint(x, y))
                cell["panel"].orderFrontRegardless()

            if not desired:
                if self.idle_since is None:
                    self.idle_since = time.time()
                elif time.time() - self.idle_since > IDLE_QUIT:
                    NSApplication.sharedApplication().terminate_(None)
            else:
                self.idle_since = None

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    tray = Tray.alloc().init()
    tray.reconcile()
    NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
        POLL, tray, b"tick:", None, True)
    app.run()


def cmd_preview(argv):
    """One-off single mascot for visual testing: preview [gif] [name]."""
    _ensure_dirs()
    sid = "preview"
    gif = None
    name = None
    if len(argv) > 0:
        arg = argv[0]
        cand = arg if os.path.isabs(arg) else os.path.join(GENERATED_DIR, arg)
        if os.path.exists(cand):
            gif = cand
    if len(argv) > 1:
        name = argv[1]
    if gif is None:
        gif = _pick_gif()
    if not gif:
        return
    _atomic_write(_sess_path(sid), {
        "sid": sid, "gif": gif, "name": name or "preview", "state": "working"})
    _ensure_daemon()


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "daemon":
        cmd_daemon()
    elif cmd == "show":
        cmd_show(_read_hook_input())
    elif cmd == "notify":
        cmd_notify(_read_hook_input())
    elif cmd == "hide":
        cmd_hide(_read_hook_input())
    elif cmd == "resume":
        cmd_resume(_read_hook_input())
    elif cmd == "preview":
        cmd_preview(sys.argv[2:])
    # unknown/no command: no-op


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
