# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

Fastfetch Tweak Tool is a standalone GTK4 Python application for configuring
[Fastfetch](https://github.com/fastfetch-cli/fastfetch). It provides a graphical
interface for module selection/ordering, logo choice, colors/separators, and shell
startup — writing to `~/.config/fastfetch/config.jsonc`.

It is the deeper, standalone successor to the single fastfetch tab inside
archlinux-tweak-tool (`fastfetch.py` + `fastfetch_gui.py`), which can only
comment/uncomment whole module lines.

- **Language**: Python 3.8+
- **GUI Framework**: GTK4 (4.6+) + VTE 3.91 for embedded terminal preview (optional)
- **Entry Point**: `usr/share/fastfetch-tweak-tool/fastfetch-tweak-tool.py`
- **Launcher**: `usr/bin/fastfetch-tweak-tool`
- **Desktop Entry**: `usr/share/applications/fastfetch-tweak-tool.desktop`
- **Runs as normal user** — no sudo, no pkexec; package install/remove launches pacman
  in a terminal (Popen in a daemon thread)

## Config engine — the tool OWNS config.jsonc

`ff_config.py` parses `~/.config/fastfetch/config.jsonc` (strips `//` + `/* */`
comments and trailing commas), builds a structured model, and writes back valid
indented JSON. **Hand-written comments are dropped on save.** Mitigations:
- Backup to `config.jsonc.ftt-bak` before every write — **distinct** from ATT's
  `config.jsonc-bak` so both tools coexist on the same `config.jsonc`.
- A Raw tab edits the file directly for users who want to keep comments.

The `modules` array preserves order = on-screen order; each entry is a **string**
(`"cpu"`) or an **object** with per-module keys (e.g. `{"type": "cpu", "temp": true}`).

## Architecture

```
usr/share/fastfetch-tweak-tool/
├── fastfetch-tweak-tool.py   # Entry point: GTK Application + Main window
├── ff_config.py              # JSONC R/W engine, structured model, backup, prefs
├── ff_gui.py                 # GUI: Notebook tabs + widgets + VTE preview
├── ff_logos.py               # logo + preset catalog (from fastfetch CLI)
├── ff_install.py             # install/remove/shell-startup/lolcat (ported from ATT)
├── log.py                    # logging: log_section / log_info / log_success / ...
├── att.css                   # GTK4 stylesheet
└── data/fastfetch/config.jsonc   # bundled Kiro default
```

### Data Locations

| What             | Path                                            |
|------------------|-------------------------------------------------|
| Fastfetch config | `~/.config/fastfetch/config.jsonc`              |
| Config backup    | `~/.config/fastfetch/config.jsonc.ftt-bak`      |
| App preferences  | `~/.config/fastfetch-tweak-tool/prefs.json`     |
| Bundled default  | `/usr/share/fastfetch-tweak-tool/data/fastfetch/config.jsonc` |

## Development Patterns

- All output via `log.py` (never `print()`); `--debug` / `--dev` flags.
- GTK4 callbacks: unused signal params named `_widget`.
- Never `subprocess.call()` from a GUI callback — use `Popen` in a daemon thread.
- Ampersands in `set_markup()` must be escaped as `&amp;`.

### Code Style

- `ruff check` must pass before any Python work is considered done; auto-fix without asking.
- Max line length 120; `snake_case` / `PascalCase`.
- One-line PEP257 docstrings on public functions/methods; none on `_`-prefixed private.
- Section dividers (`# ── Name ──────`) only in functions 50+ lines.

### Frozen Files

`usr/bin/fastfetch-tweak-tool` — never edit without an explicit file-specific instruction.

## Running

```bash
python3 usr/share/fastfetch-tweak-tool/fastfetch-tweak-tool.py --debug
fastfetch-tweak-tool        # via launcher after install
```

## Project Status — last updated 2026.06.17 (continue here tomorrow)

**State: full v1 built, launches cleanly, ruff clean, committed locally (NOT pushed).**
Built in one session from the approved plan
(`~/.claude/plans/wiggly-stargazing-galaxy.md`).

### What works (verified)
- App launches with no traceback; window builds all four tabs + live preview pane.
- `ff_config.py` engine round-trips the real `~/.config/fastfetch/config.jsonc`; the
  serialized model renders as valid fastfetch output. JSONC stripper is string-aware
  (keeps `https://`, drops `//` + `/* */` + trailing commas). Self-tested.
- Catalogs parse: 75 modules, 529 logos, 37 presets (from `--list-* autocompletion`).
- `ruff check` clean on all 6 `.py`; `.desktop` validates.
- Root guard in launcher + Python entry (refuses EUID 0 → config always in user home).
- Logo/preset dropdown search fixed (needs `Gtk.PropertyExpression`, not just `enable_search`).
- Modules tab uses **drag-and-drop** reorder (grip handle ⠿), not arrow buttons.

### Verified only by launch, NOT by hands-on interaction (test tomorrow)
- Drag-and-drop drop position (the before/after index math in `_on_module_drop` — if a
  drop lands one slot off, that's the spot to tweak).
- Live VTE preview actually rendering fastfetch inside the embedded terminal on a real
  desktop session (spawn path in `_refresh_preview`); kitty/sixel image-logo fallback.
- Install/remove + shell-startup + lolcat flows end-to-end (terminal launch in
  `ff_install.py` — `launch_in_terminal` terminal detection on chadwm/alacritty).
- Per-module options UX (free-form key/value editor) and color combos writing the
  expected `display.color.*` keys.
- FileDialog logo picker (`_choose_logo_file`).

### Next steps / TODO for tomorrow
1. Hands-on test pass of the five items above; fix whatever's rough.
2. Decide the per-module options UX — free-form key/value is power-user-ish; consider
   curated common options per module type (temp, format, etc.).
3. M8 packaging: add `fastfetch-tweak-tool` to the nemesis_repo/kiro_repo build pipeline
   (same `usr/`-tree layout as alacritty-tweak-tool). Deps: `python-gobject`, `gtk4`;
   optdepends `vte4`, `fastfetch`, `chafa`, `imagemagick`, `lolcat`.
4. Create the GitHub repo `kirodubes/fastfetch-tweak-tool`, then `up.sh` to push
   (remote already set to `git@github.com-kiro:kirodubes/fastfetch-tweak-tool`).
5. `sudo rm /tmp/ftt-preview.jsonc` (stale root-owned file from the first test run).
6. Consider adding `fastfetch-tweak-tool` to HQ MASTER_TODO so it's tracked ecosystem-wide.

### Key files / where things live
- Engine: `ff_config.py` (read/write/backup/catalogs). Preview file:
  `~/.cache/fastfetch-tweak-tool/preview.jsonc`. Backup: `config.jsonc.ftt-bak`.
- GUI: `ff_gui.py` — `build()` assembles Notebook + preview; tabs are
  `_presets_tab` (Start / Presets, first) / `_modules_tab` / `_appearance_tab` /
  `_install_tab` / `_raw_tab` (Raw, last); DnD in
  `_attach_module_dnd` / `_on_module_drop`; preview in `_refresh_preview`.
- Install/shell: `ff_install.py` (ported from ATT, stands alone).

### Quick run / test
```bash
cd /home/erik/KIRO/fastfetch-tweak-tool
python3 usr/share/fastfetch-tweak-tool/fastfetch-tweak-tool.py --debug
ruff check usr/share/fastfetch-tweak-tool/*.py
```
