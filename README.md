<p align="center">
  <img src="kiro.jpg" alt="Kiro" width="220" />
</p>

# Fastfetch Tweak Tool

A GTK4 graphical configuration editor for [Fastfetch](https://github.com/fastfetch-cli/fastfetch), the fast neofetch-style system information tool.

Configure which modules show and in what order, browse and pick a logo, tune colors and separators, and wire fastfetch into your shell startup — with a live preview of the result. All changes write to `~/.config/fastfetch/config.jsonc`.

## Features

- **Modules tab** — show/hide modules, **reorder** them, and edit per-module options
- **Logo & Appearance tab** — browse 500+ built-in logos or pick a custom image; tune key/title/separator colors, key width, and separator string
- **Install / Enable tab** — install or remove fastfetch, add it to your bash/zsh/fish startup, optional lolcat pipe, and install optional dependencies that unlock features
- **Presets & Raw tab** — apply bundled presets or the Kiro default, restore a backup, or edit the raw JSONC directly
- **Live preview** — embedded terminal renders real fastfetch output as you tweak (requires `vte4`)

## A note on comments

This tool owns `config.jsonc`: it parses the file, applies your changes, and writes
back clean JSON. **Hand-written `//` comments are not preserved on save** — a backup
is written to `config.jsonc.ftt-bak` before every write, and the Raw tab lets you edit
the file directly if you want to keep comments. This is a deliberate trade-off that
enables reordering and per-module editing. (The backup name differs from
archlinux-tweak-tool's `config.jsonc-bak`, so the two tools coexist safely.)

## Installation

Add the nemesis_repo to `/etc/pacman.conf`:

```ini
[nemesis_repo]
SigLevel = Never
Server = https://erikdubois.github.io/$repo/$arch
```

Then install:

```bash
sudo pacman -S fastfetch-tweak-tool
```

## Requirements

- `python-gobject` + `gtk4` — the GUI toolkit
- `fastfetch` — the tool being configured (installable from the app)
- `vte4` — `sudo pacman -S vte4` (optional; enables the live preview panel)
- `chafa` / `imagemagick` (optional) — image logo support
- `lolcat` (optional) — rainbow output pipe on shell startup

## Running

```bash
# Via launcher (after installation)
fastfetch-tweak-tool

# Directly from the source tree
python3 usr/share/fastfetch-tweak-tool/fastfetch-tweak-tool.py

# With debug output
python3 usr/share/fastfetch-tweak-tool/fastfetch-tweak-tool.py --debug
```

No sudo required — runs as the current user. Package install/remove is done by
launching pacman in a terminal.

<!-- KIRO-FUNDING-FOOTER:START — managed by Kiro-HQ/cascade-readme-footer.sh -->
## Help fund Kiro

Everything I build here stays free and open — always. If Kiro or any of these
tools have ever saved you time or taught you something, a small monthly
contribution helps keep the work going. Donations target break-even, nothing
more — the core always stays free for everyone.

- GitHub Sponsors: https://github.com/sponsors/erikdubois
- Patreon: https://www.patreon.com/c/kiroproject
- YouTube memberships: https://www.youtube.com/@ErikDubois/join
- Ko-fi: https://ko-fi.com/erikdubois
- PayPal: https://www.paypal.me/erikdubois
<!-- KIRO-FUNDING-FOOTER:END -->

## License

GPL-3.0 — see [LICENSE](LICENSE)
