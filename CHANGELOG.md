# Changelog

All notable changes to fastfetch-tweak-tool are documented here.

## 2026.06.18

### What Changed
- **Curated per-module options** — the Modules tab options panel is no longer a bare
  free-form key/value editor. It now renders dedicated widgets in three sections: a
  **Common** block (key label/icon/color, format, output color) valid on every module, a
  **`<type>` options** block of high-value curated keys for cpu/gpu/disk/battery/localip/
  swap/wm/title, and an **Advanced (raw keys)** expander that keeps full free-form reach
  for anything uncurated. Bool keys are toggles, text keys are entries, color keys reuse
  the appearance color dropdown.
- **New Preset Gallery tab (real, transparent screenshots).** A second tab beside Start / Presets
  shows a real captured screenshot of each preset in a `FlowBox` grid, each cell a `Gtk.Picture`
  inside a fixed-size clipped frame (loaded via `GdkPixbuf.new_from_file_at_size`, the same
  approach as ATT's zsh-theme previews) with a **Load** button that reuses the shared
  `_load_preset_named` path. Presets without a captured image show a "no preview yet" placeholder,
  and a **Refresh** button re-scans the image folder. Built as a separate tab on purpose, to test
  alongside the existing dropdown. All 37 presets captured (6 top-level + 31 `examples/`).
  - Modelled on ATT: the images are **pre-captured**, not rendered live. An earlier attempt that
    parsed fastfetch's ANSI output into Pango thumbnails was dropped — it couldn't show logos and
    didn't look like the real thing.
  - **Transparent PNGs** — the terminal background (`#111217`) is keyed out to transparency, so a
    preview sits directly on the GTK theme background (no black "card" rectangle) and adapts to
    any theme, matching the look of a transparent terminal over the wallpaper.
  - **Fixed-size clipped cells** — each image lives in a `_THUMB_W`×`_THUMB_H` frame with
    `overflow: hidden`, so cells can't bleed into each other (fixed an overlap bug).
  - **Capture tooling** — `tools/capture-preset-previews.sh` (run **inside a clean VirtualBox VM**)
    scrubs privacy-sensitive modules from each preset, opens it in alacritty, grabs the window with
    `maim`/`xdotool`, trims + keys out the background with imagemagick, and writes
    `images/preset_previews/<name>.png`.
  - **Privacy scrub (critical)** — fastfetch renders real system info, and several presets
    (`all`, `ci`, `archey`, …) embed the machine's **public IP + geolocation**; a VM does not hide
    this because NAT shares the host's real WAN IP. The capture script now strips `publicip`,
    `localip`, `dns`, `wifi`, and `weather` modules (string-aware JSONC parse) **before** rendering,
    so no committed screenshot can leak network/location data.
- **Start / Presets intro now mentions the auto-backup.** The onboarding text reassures users
  that before every Apply the current config is saved to `config.jsonc.ftt-bak`, which the
  Restore backup button can roll back to — surfacing behaviour that was already happening
  silently in `write_config`.
- **Dropped "(not yet applied)" from load notifications.** Loading a preset / Kiro default now just
  says "Loaded preset: X" — loading is obviously not saving, and the config is only written on Apply.
- **Live preview background set to `#343844`.** The VTE preview no longer renders on hard black —
  it paints a fixed `#343844` background (matching the app surface) with the foreground from the GTK
  theme (`window_fg_color`, on realize). (Transparency was tried first but dropped in favour of a
  fixed colour.)
- **Preset Gallery logo filter (All / Normal / Small).** Grouped toggle buttons on the gallery
  filter the grid by logo kind, modelled on the alacritty-tweak-tool tone filter (`set_group` +
  `FlowBox.set_filter_func`/`invalidate_filter`). "Small" matches presets whose `logo.type` is
  `small` (16 of 37); "Normal" is the rest (21); "All" shows everything. The status line reports
  the normal/small split.
- **Live preview now renders in colour.** The VTE preview ran `fastfetch -c <cfg>` with no
  `--pipe` flag; fastfetch auto-detected the pty as non-colour (like a pipe) and emitted
  monochrome output, so the preview didn't match the colourful gallery thumbnails. Added
  `--pipe false` to force colours/decorations (verified: 18 → 165 ANSI escapes).
- **Fixed crash when loading a preset whose section is `null`.** Loading certain presets (e.g.
  `examples/4`, which has `"logo": null`) raised `AttributeError: 'NoneType' object has no
  attribute 'get'` in `_reload_widgets` — `model.get("logo", {})` returns the `None` value when
  the key is present-but-null (the `{}` default only applies when the key is absent). Added
  `_normalize_model()` (drops null top-level keys, guarantees `modules` is a list) applied at
  every model-load point, and hardened the nested reads to `(model.get(k) or {})`. Verified across
  all 37 presets + synthetic null-section models. This path is shared by the gallery and the
  Start/Presets dropdown, so both are fixed.
- **Split-pane no longer collapses the live preview.** The divider between the editor and
  the preview could be dragged fully to the right, shrinking the preview to zero width and
  hiding it entirely. Both Paned children now have `shrink` disabled so each pane's minimum
  size request is honoured (preview floored at 420px, notebook at 360px) — the handle can
  no longer drag a pane out of existence.
- **Bug fixes from the v1 hands-on review:**
  - Drag-and-drop could never land a module in the **last** slot — added a drop-only
    sentinel row at the bottom of the modules list that inserts at the end.
  - After a reorder, the per-module options panel kept stale row indices and could write
    to the wrong module — the panel is now cleared on drop.
  - Reload / Load-Preset / Restore left the logo and color dropdowns showing their old
    selection while the model changed underneath — they are now re-synced from the freshly
    loaded model.
  - The free-form Advanced path now treats a typed `null`/`none` as "drop the key".
- **Tab reorder — presets-first onboarding flow.** The old combined "Presets & Raw" tab is
  split: a new **Start / Presets** tab is now the **first** tab (load an example preset or
  the Kiro default, watch the live preview, then tweak), and the raw JSONC editor moves to
  its own **Raw** tab at the **end**. New order: Start / Presets → Modules → Logo &
  Appearance → Install & Enable → Raw.
- **Load preset / Kiro default now repaint the live preview immediately** — no separate
  "Refresh preview" click needed for the pick-an-example flow. (The manual Refresh preview
  button stays for Modules/Appearance edits, which don't auto-refresh.)
- **Natural sort for catalogs** — preset / logo / module dropdowns now order embedded numbers
  numerically (`examples/2 … examples/9, examples/10, examples/11 …`) instead of the old
  lexicographic order (`examples/1, examples/10, examples/11, examples/2 …`).
- **Public IP privacy guard** — the live preview now **masks any `publicip` module by default**,
  showing a `(hidden — click 'Show public IP')` placeholder instead of fetching/printing the
  real address. A **Show public IP** toggle appears in the preview header only when a publicip
  module is present; revealing requires confirming a dialog that warns about screen-sharing /
  recording. The opt-in is session-only (hidden again on next launch). The saved config is never
  altered — the guard is preview-display only.
- **50/50 resizable preview split** — the window is now a `Gtk.Paned` with a visible drag handle
  between the settings notebook and the live-preview pane (previously the preview was a fixed
  pane that could be pushed off-screen with no resize affordance). It opens centred at 50/50 and
  re-centres on window/tile resize until you drag the handle, after which your chosen split is
  respected.
- **Optional features show install state** — each Optional-features row (chafa, imagemagick,
  lolcat, ddcutil) now shows a bold **installed** indicator when the package is present. Pressing
  **Install** on an already-installed package flashes a transient orange **already installed**
  message on that row for 3 seconds (instead of launching pacman). The indicators refresh after
  any package operation.
- **Same guard on the Fastfetch Install/Remove buttons** — clicking **Install** when fastfetch is
  already installed flashes orange **already installed**, and **Remove** when it is not installed
  flashes orange **not installed**, both for 3 seconds, with no pacman launch. The transient-flash
  helper is now shared by the Fastfetch row and the optional-feature rows. The Fastfetch row also
  shows the same bold **installed** indicator (next to its buttons) as the optional rows; the
  old redundant left-aligned "Installed / Not installed" text was removed in favour of it.
- **Add-module picker hides modules you already have** — the "Add module" dropdown now lists only
  module types not already in the list, so you can't accidentally add a duplicate `cpu`/`os`/etc.
  Repeatable types (`break`, `custom`, `command`) always stay available. The dropdown refreshes
  live on add/remove and on reload/preset/restore.

- **Content header with title, fastfetch version & Quit** — mirroring alacritty-tweak-tool, the
  window body now has a top header: the app title on the left, the installed fastfetch version
  shortened to **major.minor** (e.g. `fastfetch v2.64` from `2.64.2-44-debug`) and a **Quit**
  button on the right. The bottom status bar no longer repeats the version (now just the
  notification area, starting at "Ready").

- **lolcat switch follows shell-startup off** — turning off "Run fastfetch on shell startup" now
  also switches off "Pipe through lolcat" (and greys it out), since the pipe is meaningless without
  the startup line. Re-enabling startup leaves lolcat off until you turn it back on.

### Technical Details
- New `ff_options.py` — a pure-data schema (no GTK), mirroring the `ff_logos.py` catalog
  style: `UNIVERSAL` keys plus a `MODULE_OPTIONS` table of `(key, kind, label)` tuples
  (`kind` ∈ `bool`/`text`/`color`), verified against `fastfetch --gen-config-full`.
  Object-valued keys (`percent`, `separator.*`) are deliberately left to the Advanced
  editor to avoid a nested sub-editor in v1. `curated_keys(type)` filters which keys the
  Advanced expander still shows.
- `_show_module_options` rewritten to render the three sections; `_color_combo` was
  factored out of `_color_row` so the appearance tab and the curated panel share one
  color widget. Curated edits go through `_set_option_value` (a presence-aware setter that
  rebuilds the list only when a key is added/removed, preserving focus for value edits) and
  the existing `_del_option` downgrade-to-string, keeping the string↔object round-trip intact.
- Verified non-interactively: engine read→write→read round-trip on a copy of the real
  config (model stable, `config.jsonc.ftt-bak` written, distinct from ATT's backup);
  curated `cpu` string ↔ `{type,temp}` ↔ string round-trip; and a GTK smoke test that
  builds the window, selects modules, and toggles a curated Switch ON/OFF (string→object
  upgrade and object→string downgrade both survive the mid-signal list rebuild).

### Files Modified
- `usr/share/fastfetch-tweak-tool/ff_options.py` (new)
- `usr/share/fastfetch-tweak-tool/ff_gui.py` (curated options + tab split + preset auto-preview
  + public-IP guard + Paned 50/50 layout)
- `usr/share/fastfetch-tweak-tool/ff_config.py` (natural sort for catalogs)
- `usr/share/fastfetch-tweak-tool/ff_install.py` (package_installed helper)
- `CHANGELOG.md`

## 2026.06.17

### What Changed
- Initial build of the standalone **fastfetch-tweak-tool** GTK4 application — a dedicated,
  much deeper successor to the single fastfetch tab in archlinux-tweak-tool. Full v1:
  config engine, four-tab GUI, live preview, install/enable wiring.
- **Modules tab** — show/hide, **drag-and-drop reorder** (grip handle per row), and
  per-module key/value options.
- **Logo & Appearance tab** — built-in logo browser (500+), custom image logos, logo
  size/padding, separator, key/title/output colors, key width.
- **Install & Enable tab** — install/remove fastfetch (smart fastfetch-git vs fastfetch
  pick), shell-startup toggle, lolcat pipe, optional-dependency installers.
- **Presets & Raw tab** — load bundled presets / Kiro default, restore backup, and a
  comment-preserving raw JSONC editor with validate-on-save.
- **Live preview** — embedded VTE renders real fastfetch output; falls back to a
  "preview in terminal" button when vte4 is absent.
- **Root guard** — the launcher and Python entry both refuse to run as root, so the
  config is always written to the invoking user's `~/.config/fastfetch`.

### Technical Details
- Mirrors the alacritty-tweak-tool architecture: `Gtk.Application` + HeaderBar + Notebook,
  shared `log.py`, `att.css`, prefs-on-close, optional VTE preview.
- Config engine **owns** `config.jsonc`: a string-aware stripper removes `//` and `/* */`
  comments + trailing commas (without touching `https://` inside strings), parses to a
  structured model (`logo`/`display`/`modules`, each module a string or object), and
  writes back valid indented JSON. Backs up to `config.jsonc.ftt-bak` before every write
  — a distinct name from ATT's `config.jsonc-bak` so the tools coexist.
- Catalogs (modules/logos/presets) are read from `fastfetch --list-* autocompletion` and
  cached in `ff_logos.py`.
- Searchable logo/preset dropdowns set a `Gtk.PropertyExpression` on `StringObject.string`;
  `enable_search` alone does not filter without an expression.
- Preview file lives in `~/.cache/fastfetch-tweak-tool/preview.jsonc` (per-user, never /tmp).
- Install/shell-startup logic adapted to stand alone from ATT's `fastfetch.py`; pacman runs
  in a detected terminal (Popen in a daemon thread), never via in-app sudo/pkexec.
- KIRO repo conventions: `up.sh`/`setup.sh`/`common/` copied from alacritty-tweak-tool;
  intended for nemesis_repo as `fastfetch-tweak-tool` (same `usr/`-tree packaging).

### Files Modified
- New repo at `/home/erik/KIRO/fastfetch-tweak-tool`: scaffold + metadata (README,
  CHANGELOG, CLAUDE.md, LICENSE, up.sh, setup.sh, common/, .flake8, .gitignore, .ignore,
  .vscode, kiro.jpg), launcher `usr/bin/fastfetch-tweak-tool`, desktop entry, bundled
  `data/fastfetch/config.jsonc`, and modules `fastfetch-tweak-tool.py`, `ff_config.py`,
  `ff_gui.py`, `ff_install.py`, `ff_logos.py`, `log.py`, `att.css`.
