# cc-gifs

Pixel-art spinner GIF generator for Clawd, the Claude Code mascot.

## Disclaimer

This repository is an unofficial technical/art experiment. The code in this repository is released under the MIT License, but `Claude`, `Claude Code`, `Clawd`, and related mascot or brand imagery remain the intellectual property and/or trademarks of Anthropic. The MIT license here applies to the repository code only and does not grant rights to Anthropic branding or character assets. Generated mascot imagery should be treated as learning/showcase material unless you have separate permission for other uses.

## What’s Included

- `generate_clawd_gifs.py`: the unified generator for all official Clawd spinner scenes
- `spinner-words.md`: the catalog of 195 spinner entries (195 drawn, 0 pending) with a short description and status per verb
- `CLAUDE.md` and `AGENTS.md`: working notes and agent-facing repository instructions
- `requirements.txt`: minimal runtime dependency list
- `companion/`: optional macOS "working companion" — a per-session Clawd status beacon (see [companion/README.md](./companion/README.md))
- `LICENSE`: MIT license for repository code

## What’s Not Included

- Generated GIF files
- Local JPG/PNG reference images
- Other local source assets used during experimentation

Those files are intentionally ignored in git so this public repo stays lightweight and code-focused.

## Setup

**Full setup (macOS — GIFs + working companion), one command:**

```bash
git clone git@github.com:ahmad-hussain/cc-gifs.git ~/Documents/cc-gifs
cd ~/Documents/cc-gifs
./companion/install.sh --install-hooks    # builds the venv, generates the GIFs, wires the companion hooks
#                              --with-sound  # (optional) also add done / needs-input system sounds
# then restart Claude Code
```

Run `./companion/install.sh` *without* `--install-hooks` to print the hook JSON for manual review instead of merging it. The installer is idempotent and safe to re-run.

**GIFs only (any OS, no companion):**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 generate_clawd_gifs.py
```

> **Setting up with an AI agent?** Clone the repo, open Claude Code inside it, and ask it to *"set up this repo."* `CLAUDE.md` carries the exact steps (one-command installer + manual fallback + the hooks) for the agent to follow.

## Usage

```bash
python3 generate_clawd_gifs.py
```

Generated GIFs are written to:

```text
generated/Clawd-{Word}.gif
```

The generator currently draws **195 spinner scenes** (186 official Claude Code spinner verbs + 9 repo extensions) — every official verb from Claude Code `2.1.201` is covered — plus **1 companion-only asset** (`Clawd-_Waiting.gif`, a "needs your input" mascot used by the optional macOS companion, see `companion/`). Most compact scenes render as 6-frame loops at 170ms per frame, while some handcrafted scenes use longer timelines.

## Working Companion (macOS)

`companion/` is an optional macOS **status beacon**: while a Claude Code session is working, a Clawd mascot floats in the bottom-right corner (over other apps and fullscreen Spaces). It waves with a red `!` when Claude needs your input, and disappears when the turn ends. Multiple concurrent sessions stack into a tray, each tagged with its session name (`/rename` value). See [companion/README.md](./companion/README.md).

**Setup (one command):**

```bash
./companion/install.sh --install-hooks               # build venv, generate GIFs, merge hooks into ~/.claude/settings.json (backed up first)
./companion/install.sh --install-hooks --with-sound   # ...plus optional done/needs-input system sounds (Glass/Funk, editable in chime.sh)
# ...or review first — this prints the hook JSON to add by hand instead:
./companion/install.sh
```

Then restart Claude Code. The installer builds `companion/.venv` (PyObjC), generates the GIFs, and wires five hooks — `UserPromptSubmit` (working), `PreToolUse`/`PostToolUse` (resume after you answer), `Notification` (needs input), `Stop` (done). macOS only; the generator itself is cross-platform. Sound is **opt-in** via `--with-sound` (off by default, so it won't double any audio hooks you already have); a native macOS banner is also possible — see `companion/README.md`.

## Project Structure

```text
.
├── .gitignore
├── AGENTS.md
├── CLAUDE.md
├── LICENSE
├── README.md
├── generate_clawd_gifs.py
├── requirements.txt
├── spinner-words.md
├── companion/    # optional macOS working-companion tray (.venv ignored by git)
└── generated/    # runtime output, ignored by git
```

## Notes on the Generator

- The script uses Pillow to draw each frame directly as pixel art.
- Clawd scenes are split between:
  - handcrafted `frames_*()` functions that return full frame lists
  - compact `sc_*()` functions wrapped by `make_frames()`
- `main()` merges both styles and exports animated transparent GIFs through `save_gif()`.

For more repo-specific implementation details, see [CLAUDE.md](./CLAUDE.md).

## Spinner Catalog

The full word list lives in [spinner-words.md](./spinner-words.md).

It includes:

- official word numbering
- a short description per verb
- generation status tracking

### Catalog Scope

The catalog now covers the **full** upstream Claude Code default `spinnerVerbs` set. Anthropic does not publish the canonical list, and the defaults shift between versions (e.g. Claude Code `2.1.42` was reported as 185 verbs, `2.1.153` had 187, and `2.1.201` has **186**).

Concretely, against Claude Code `2.1.201` (verb list extracted from the installed binary):

- **186** official defaults are drawn ✅ — full coverage, no gaps
- **0** official defaults remain pending ⏳
- **9** entries are repo extensions outside the current official defaults: `Conjuring`, `Divining`, `Evaporating`, `Hustling`, `Jiving`, `Scheming`, `Shucking`, `Sussing`, `Wizarding`

Upstream may add or rename verbs in future versions; when that happens, new gaps can be closed by adding scenes the same way.

## Credits

Created in collaboration with coding agents across multiple refinement passes.
