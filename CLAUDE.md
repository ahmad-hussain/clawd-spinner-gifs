# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A creative playground for generating Clawd (Claude Code mascot) pixel art spinner GIFs. The project produces animated GIF spinners that display during Claude Code loading states — each with a whimsical "-ing" word and a unique Clawd scene.

## Project Structure

- `generate_clawd_gifs.py` — Unified generator script: draws Clawd pixel art, defines both full `frames_*()` animations and compact `sc_*()` scenes, and outputs transparent GIFs
- `generated/` — Runtime output directory for generated GIFs (kept out of git)
- `spinner-words.md` — Catalog of `195` spinner entries (`195` drawn ✅, `0` pending ⏳, `9` repo extensions ★) with status tracking and a short description per verb. Cross-checked against Claude Code `2.1.201`'s 186 default `spinnerVerbs` — all 186 official verbs now have GIFs.
- `companion/` — macOS "working companion": a per-session status-beacon tray that shows a Clawd mascot for each active Claude Code session (via `UserPromptSubmit`/`Notification`/`Stop` hooks). See `companion/README.md`. `clawd_companion.py` (daemon + hook subcommands), `show.sh`/`notify.sh`/`hide.sh`, `requirements.txt` (PyObjC); `.venv/` is git-ignored
- `README.md` — Public repo overview and usage guide
- `AGENTS.md` — Pointer file for Codex and other coding agents, redirects to `CLAUDE.md`
- `requirements.txt` — Minimal runtime dependency list (`Pillow`)
- `LICENSE` — MIT license for repository code
- `.gitignore` — Excludes `generated/`, `*.gif`, `*.png`, `*.jpg`, `*.jpeg`, `.DS_Store`, `__pycache__/`
- Local-only reference screenshots, reference GIFs, and sticker/source assets are intentionally excluded from this public repository

## Setup (fresh machine, incl. companion)

**Agent instruction — if asked to "set up this repo":** on macOS, run `./companion/install.sh --install-hooks` (it builds the venv, generates the GIFs, and merges the hooks), then tell the user to **restart Claude Code**. On non-macOS, or for GIFs only, do steps 1–3 of the manual list below and skip the companion hooks. The rest of this section is the manual fallback / reference.

To stand the whole thing up on a new **macOS** machine — GIFs plus the per-session working-companion beacon — the one-shot installer does everything:

```bash
./companion/install.sh --install-hooks
```

This builds `companion/.venv` (system `/usr/bin/python3` + PyObjC, required for AppKit), installs `Pillow` + `pyobjc-framework-Cocoa`, generates all GIFs into `generated/` (git-ignored), and merges the five hooks into `~/.claude/settings.json` (timestamped backup first; idempotent; preserves existing hooks). Then **restart Claude Code**. Omit `--install-hooks` to print the hook JSON for manual merging instead. Add `--with-sound` to also wire optional done/needs-input system sounds via `companion/chime.sh` (Glass/Funk defaults, editable; off by default so it won't double existing audio hooks).

Manual equivalent (what the installer automates):
1. `/usr/bin/python3 -m venv companion/.venv` — system python is required for GUI/AppKit access
2. `companion/.venv/bin/python3 -m pip install -r requirements.txt -r companion/requirements.txt`
3. `companion/.venv/bin/python3 generate_clawd_gifs.py`
4. Add five `async` hooks to `~/.claude/settings.json`, each pointing at the **absolute** path of the script (the scripts self-resolve their own dir, so only these command paths matter):
   - `UserPromptSubmit` → `companion/show.sh` (mark session working)
   - `PreToolUse` → `companion/resume.sh` (flip waiting→working when the next tool runs after a permission grant)
   - `PostToolUse` → `companion/resume.sh` (flip waiting→working the instant `AskUserQuestion` returns — covers answer-then-text-only turns)
   - `Notification` → `companion/notify.sh` (needs-your-input → waving mascot)
   - `Stop` → `companion/hide.sh` (turn done → remove the mascot)
5. Restart Claude Code so the hooks load.

GIFs only (any OS, no companion): `pip install -r requirements.txt` then `python3 generate_clawd_gifs.py`. Full companion details are in `companion/README.md`.

## GIF Generation

```bash
python3 generate_clawd_gifs.py
```

- Requires: `Pillow` (`pip install Pillow`)
- Output: official spinner GIFs at `generated/Clawd-{Word}.gif` (400×400px, transparent background, 170ms per frame)
- Default compact scenes render at `6` frames, but some handcrafted `frames_*()` scenes now use longer timelines
- Known longer animations:
  - `Catapulting` — `8` frames
  - `Cultivating` — `12` frames
  - `Germinating` — `12` frames
  - `Gesticulating` — `8` frames
  - `Cascading` — `10` frames
  - `Channelling` — `8` frames
  - `Choreographing` — `8` frames
  - `Hatching` — `10` frames
  - `Nucleating` — `8` frames
  - `Osmosing` — `8` frames
  - `Prestidigitating` — `8` frames
  - `Recombobulating` — `8` frames
  - `Wrangling` — `8` frames
  - `Whirlpooling` — `10` frames
  - `Unfurling` — `8` frames
  - `Topsy-turvying` — `10` frames
  - `Transmuting` — `8` frames
  - `Tinkering` — `8` frames
  - `Thundering` — `8` frames
- The generator currently produces `195` spinner GIFs (`186` official spinner verbs + `9` repo extensions) plus `1` companion-only asset (`Clawd-_Waiting.gif`, the underscore-prefixed "needs your input" mascot excluded from the random pool); all official verbs from Claude Code `2.1.201` are now covered (`0` pending)
- `generate_clawd_gifs.py` supports two internal scene styles:
  - handcrafted `frames_*()` functions that return complete frame lists
  - compact `sc_*()` scene functions rendered through `make_frames()`
- `main()` merges both generator styles into one output registry
- Current pipeline:
  - pixel font + shared color constants
  - grid-based `draw_clawd()` and scene helpers
  - `frames_*()` or `sc_*()` scene construction
  - `make_frames()` for compact scene wrapping
  - `main()` registry merge and batch generation
  - `save_gif()` palette conversion and animated GIF export
- `Clawd-Dancing.gif` and other visual references remain local-only assets and are excluded from this public repository

### Clawd Character Spec

- Grid: 12×8 blocks (16px each), head 8 wide, arms extend 2 blocks each side
- Color: CORAL `(212, 132, 90)`, eyes BLACK
- `draw_clawd(draw, ox, oy)` — ox,oy is head top-left corner
- `draw_clawd()` now also supports optional palette overrides and simple face variants (wink / cheeky expression) for special scenes like storm flashes or tomfoolery
- Variants: `draw_clawd_head_only`, `draw_mini_clawd`

### Shared Helpers

- `draw_text()` — pixel font renderer (5×7 glyphs, scale=4px default)
- `draw_loading_label()` — animated spinner label renderer with pulsing `*` and progressive loading dots
- `draw_steam()` / `draw_bubbles()` / `draw_sweat_drop()` — ambient effects
- `draw_gear()` / `draw_thought_bubble()` / `draw_music_note()` / `draw_stick_figure()` — scene props
- `draw_lightbulb()` / `draw_brain_icon()` — specialized helpers for ideation / cerebrating scenes
- `draw_spotlight()` / `draw_sigil_ring()` — shared stage-lighting and ritual/science ring helpers used across multiple magical scenes
- `draw_storm_cloud()` / `draw_lightning_bolt()` — storm and lightning helpers
- `draw_data_card()` / `draw_crystal()` / `draw_fancy_flower()` — specialized helpers for data-wrangling, transmutation, and ornate flower scenes
- `draw_heart()` / `draw_playing_card()` / `draw_dancer_figure()` — additional scene props for romance, magic-trick, and choreography scenes
- `draw_clawd_face()` / `draw_clawd_accessories()` / `draw_clawd_icon_accessory()` — Clawd face variant and accessory compositing helpers
- `draw_clawd_chef_hat()` / `draw_clawd_wizard_hat()` / `draw_clawd_helmet()` / `draw_clawd_headphones()` — costume headgear helpers for cooking, wizarding, spelunking, and music scenes
- `draw_clawd_camera()` / `draw_clawd_magnifier()` / `draw_clawd_tool()` — hand-held prop helpers for various scenes
- Frame-driven animation state is passed explicitly through `frame` arguments; the generator no longer relies on a shared global current-frame variable for auto-blinks or accessory timing, and longer custom scenes can keep blink cadence aligned to their own frame counts
- `save_gif()` — uses a hybrid export path: a fixed full-corpus palette for the fast path, plus a small protected fallback allowlist that still uses the older per-GIF shared palette; both paths keep transparent backgrounds via an explicit transparency index after magenta-key compositing

### Adding a New Spinner

1. Choose a generator style:
   - write a `frames_wordname()` function returning a custom-length RGBA `Image` frame list, or
   - write a compact `sc_wordname(draw, f, img)` scene function and render it via `make_frames()` for the default `6`-frame flow
2. Register the new word in the matching generator registry inside `main()`
3. Run `python3 generate_clawd_gifs.py`
