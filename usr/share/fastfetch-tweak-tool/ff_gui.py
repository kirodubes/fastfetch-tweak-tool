"""GTK4 GUI for fastfetch-tweak-tool — Notebook tabs plus a live VTE preview."""

import os
import random
import shutil
import subprocess
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, GObject, Gtk  # noqa: E402

try:
    gi.require_version("Vte", "3.91")
    from gi.repository import Vte

    _VTE_AVAILABLE = True
except (ImportError, ValueError, Exception):
    _VTE_AVAILABLE = False

import ff_config as cfg  # noqa: E402
import ff_install as install  # noqa: E402
import ff_logos as catalog  # noqa: E402
import ff_options as ffopts  # noqa: E402
import log  # noqa: E402

PREVIEW_PATH = os.path.expanduser("~/.cache/fastfetch-tweak-tool/preview.jsonc")

# Common fastfetch color values offered in the appearance combos.
_COLORS = [
    "default", "black", "red", "green", "yellow", "blue", "magenta", "cyan", "white",
    "1", "2", "3", "4", "5", "6", "9", "10", "11", "12", "13", "14",
]
_CUSTOM_COLOR = "custom…"  # dropdown sentinel: reveals the hex/SGR entry + colour picker

# "pokemon" is a UI-only pseudo-type: it maps to fastfetch's real "file" type (see _TYPE_ALIAS),
# detected on reload by the source path. The model never stores "pokemon".
_LOGO_TYPES = ["builtin", "small", "none", "file", "pokemon", "kiroart", "data", "sixel", "kitty", "chafa"]
_TYPE_ALIAS = {"pokemon": "file", "kiroart": "file"}

# Human-friendly labels shown in the Type dropdown; the config value stays the raw key.
_LOGO_TYPE_LABELS = {
    "builtin": "Big ASCII",
    "small": "Small ASCII",
    "none": "None",
    "file": "Text file",
    "pokemon": "Pokémon",
    "kiroart": "Kiro art",
    "data": "Inline text",
    "sixel": "Sixel image",
    "kitty": "Kitty image",
    "chafa": "Chafa image",
}

# Module types that may legitimately appear more than once — never filtered from the picker.
_REPEATABLE_MODULES = {"break", "custom", "command"}


# ── Small helpers ────────────────────────────────────────────────────────────


def _label(text, css_class=None, markup=False, wrap=False, max_chars=None):
    """Create a left-aligned Gtk.Label with optional CSS class, markup or wrapping."""
    lbl = Gtk.Label()
    if markup:
        lbl.set_markup(text)
    else:
        lbl.set_label(text)
    lbl.set_xalign(0.0)
    if css_class:
        lbl.add_css_class(css_class)
    if wrap:
        lbl.set_wrap(True)
    if max_chars is not None:
        lbl.set_max_width_chars(max_chars)
    return lbl


def _searchable_dropdown(strings):
    """Return a Gtk.DropDown over the given strings with a working search box."""
    dropdown = Gtk.DropDown.new_from_strings(strings)
    dropdown.set_expression(
        Gtk.PropertyExpression.new(Gtk.StringObject, None, "string")
    )
    dropdown.set_enable_search(True)
    return dropdown


def _scrolled(child):
    sw = Gtk.ScrolledWindow()
    sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    sw.set_child(child)
    sw.set_vexpand(True)
    return sw


def _row(spacing=8):
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=spacing)
    box.set_margin_start(10)
    box.set_margin_end(10)
    box.set_margin_top(4)
    box.set_margin_bottom(4)
    return box


def _notify(window, message):
    log.log_info(message)
    if hasattr(window, "status_label"):
        window.status_label.set_text(message)


# ── Build ────────────────────────────────────────────────────────────────────


def _normalize_model(model):
    """Coerce a freshly-loaded model into a shape the widgets can rely on.

    Some presets set a section to ``null`` (e.g. ``"logo": null``) or omit ``modules``.
    A null value breaks both ``model.get(k, {})`` (returns ``None``, not the default) and
    ``model.setdefault(k, {})`` (returns the existing ``None``), so drop null top-level keys
    and guarantee ``modules`` is a list.
    """
    if not isinstance(model, dict):
        model = {}
    for key in [k for k, v in model.items() if v is None]:
        del model[key]
    if not isinstance(model.get("modules"), list):
        model["modules"] = []
    return model


def build(window, ff_version):
    """Assemble the full UI on the given window."""
    window.model = _normalize_model(cfg.read_config())
    window.ff_version = ff_version
    window.hide_public_ip = bool(cfg.load_prefs().get("hide_public_ip", True))
    # Widget registries for reload-sync — init before any tab builds (used across tabs).
    window.enum_combos = []
    window.setting_switches = []
    window.setting_spins = []

    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

    header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    header.set_margin_start(12)
    header.set_margin_end(12)
    header.set_margin_top(10)
    header.set_margin_bottom(8)
    title = _label("Fastfetch Tweak Tool")
    title.set_name("title")
    title.set_hexpand(True)
    short = _short_version(ff_version)
    ver_text = f"fastfetch v{short}" if short[:1].isdigit() else f"fastfetch {short}"
    lbl_version = _label(ver_text, css_class="info-label")
    lbl_version.set_valign(Gtk.Align.CENTER)
    btn_quit = Gtk.Button(label="Quit")
    btn_quit.connect("clicked", lambda _w: window.close())
    header.append(title)
    header.append(lbl_version)
    header.append(btn_quit)
    root.append(header)
    root.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

    split = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
    split.set_vexpand(True)
    split.set_wide_handle(True)

    notebook = Gtk.Notebook()
    notebook.set_hexpand(True)
    notebook.set_size_request(280, -1)
    notebook.append_page(_presets_tab(window), _label("Start / Presets"))
    notebook.append_page(_preset_gallery_tab(window), _label("Preset Gallery"))
    notebook.append_page(_modules_tab(window), _label("Modules"))
    notebook.append_page(_logo_tab(window), _label("Logo"))
    notebook.append_page(_appearance_tab(window), _label("Appearance"))
    notebook.append_page(_install_tab(window), _label("Install & Enable"))
    notebook.append_page(_raw_tab(window), _label("Raw"))

    split.set_start_child(notebook)
    split.set_end_child(_preview_pane(window))
    split.set_resize_start_child(True)
    split.set_resize_end_child(True)
    # Honour each child's minimum size request so the handle can't be dragged far enough
    # to collapse a pane to zero width (the preview vanishing off the right edge).
    split.set_shrink_start_child(False)
    split.set_shrink_end_child(False)
    _init_split_position(window, split)

    root.append(split)
    root.append(_action_bar(window))
    window.set_child(root)

    _refresh_preview(window)


def _short_version(version):
    """Reduce a fastfetch version like '2.64.2-44-debug' to its major.minor ('2.64')."""
    parts = version.split(".")
    if len(parts) >= 2 and parts[0].isdigit():
        return f"{parts[0]}.{parts[1].split('-')[0]}"
    return version


def _init_split_position(window, split):
    """Centre the divider at 50/50 until the user drags it, then keep that ratio on resize."""
    window._split_timer_started = False
    state = {"width": -1, "pos": -1, "ratio": None}  # ratio None → still following 50/50

    def _tick():
        width = split.get_width()
        if width <= 1:
            return True  # not allocated yet
        if width != state["width"]:
            # Window/tile resize: reapply the user's chosen ratio, or centre if untouched.
            state["width"] = width
            ratio = 0.5 if state["ratio"] is None else state["ratio"]
            split.set_position(int(width * ratio))
            state["pos"] = split.get_position()
            return True
        if split.get_position() != state["pos"]:
            # Steady width but the handle moved → a real drag; remember it as a ratio so it
            # survives later resizes instead of snapping back to centre.
            state["pos"] = split.get_position()
            state["ratio"] = state["pos"] / width
        return True

    def _start_timer(_pane):
        if not window._split_timer_started:
            window._split_timer_started = True
            GLib.timeout_add(200, _tick)

    split.connect("map", _start_timer)


def _action_bar(window):
    bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    bar.set_margin_start(10)
    bar.set_margin_end(10)
    bar.set_margin_top(6)
    bar.set_margin_bottom(6)

    window.status_label = _label("Ready", css_class="info-label")
    window.status_label.set_hexpand(True)
    bar.append(window.status_label)

    btn_reload = Gtk.Button(label="Reload")
    btn_reload.connect("clicked", lambda _w: _reload(window))
    btn_preview = Gtk.Button(label="Refresh preview")
    btn_preview.connect("clicked", lambda _w: _refresh_preview(window))
    btn_apply = Gtk.Button(label="Apply")
    btn_apply.add_css_class("suggested-action")
    btn_apply.connect("clicked", lambda _w: _apply(window))

    bar.append(btn_reload)
    bar.append(btn_preview)
    bar.append(btn_apply)
    return bar


# ── Modules tab ──────────────────────────────────────────────────────────────


def _modules_tab(window):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    box.append(_label("<b>Shown modules</b> — order matches output; select a row to edit options",
                      markup=True))

    window.modules_list = Gtk.ListBox()
    window.modules_list.add_css_class("theme-list")
    window.modules_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
    window.modules_list.connect("row-selected", lambda _lb, _r: _show_module_options(window))
    box.append(_scrolled(window.modules_list))

    add_row = _row()
    window.add_module_combo = Gtk.DropDown.new_from_strings(["(none)"])
    window.add_module_combo.set_hexpand(True)
    btn_add = Gtk.Button(label="Add module")
    btn_add.connect("clicked", lambda _w: _add_module(window))
    add_row.append(window.add_module_combo)
    add_row.append(btn_add)
    box.append(add_row)
    _refresh_add_module_combo(window)

    window.module_options_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    box.append(_label("<b>Options for selected module</b>", markup=True))
    box.append(_label(
        "<span foreground='#e8820c'><b>↵ Press Enter in a text field to apply it.</b></span> "
        "Switches and colour pickers apply instantly.", markup=True))
    box.append(window.module_options_box)

    _rebuild_modules_list(window)
    box.set_margin_start(6)
    box.set_margin_end(6)
    box.set_margin_top(6)
    return box


def _rebuild_modules_list(window):
    lb = window.modules_list
    child = lb.get_first_child()
    while child:
        lb.remove(child)
        child = lb.get_first_child()

    for idx, entry in enumerate(window.model["modules"]):
        row = Gtk.ListBoxRow()
        line = _row()
        grip = _label("⠿", css_class="info-label")
        grip.set_tooltip_text("Drag to reorder")
        line.append(grip)
        name = cfg.module_type(entry) or "(unknown)"
        suffix = "  ⚙" if isinstance(entry, dict) and cfg.module_options(entry) else ""
        line.append(_label(name + suffix, css_class="detail-name"))
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        line.append(spacer)

        btn_del = Gtk.Button(label="✕")
        btn_del.add_css_class("flat")
        btn_del.connect("clicked", lambda _w, i=idx: _remove_module(window, i))
        line.append(btn_del)

        row.set_child(line)
        _attach_module_dnd(window, row, idx)
        lb.append(row)

    if window.model["modules"]:
        lb.append(_drop_sentinel(window))


def _drop_sentinel(window):
    row = Gtk.ListBoxRow()
    row.set_selectable(False)
    hint = _label("↧ drop here to move to the end", css_class="info-label")
    hint.set_margin_start(10)
    hint.set_margin_top(2)
    hint.set_margin_bottom(2)
    row.set_child(hint)
    target = Gtk.DropTarget.new(GObject.TYPE_INT, Gdk.DragAction.MOVE)
    target.connect(
        "drop",
        lambda _t, value, _x, _y: _on_module_drop(window, value, len(window.model["modules"])),
    )
    row.add_controller(target)
    return row


def _attach_module_dnd(window, row, index):
    source = Gtk.DragSource()
    source.set_actions(Gdk.DragAction.MOVE)
    source.connect("prepare", lambda _s, _x, _y: _drag_prepare(index))
    row.add_controller(source)

    target = Gtk.DropTarget.new(GObject.TYPE_INT, Gdk.DragAction.MOVE)
    target.connect("drop", lambda _t, value, _x, _y: _on_module_drop(window, value, index))
    row.add_controller(target)


def _drag_prepare(index):
    value = GObject.Value(GObject.TYPE_INT, index)
    return Gdk.ContentProvider.new_for_value(value)


def _on_module_drop(window, source_index, target_index):
    mods = window.model["modules"]
    if source_index == target_index or not 0 <= source_index < len(mods):
        return False
    item = mods.pop(source_index)
    if source_index < target_index:
        target_index -= 1
    mods.insert(target_index, item)
    _rebuild_modules_list(window)
    _clear_box(window.module_options_box)
    _notify(window, f"Moved {cfg.module_type(item)} to position {target_index + 1}")
    return True


def _available_modules(window):
    """Module types offered in the picker: those not already added, plus repeatable ones."""
    present = {cfg.module_type(m) for m in window.model.get("modules", [])}
    return [m for m in (catalog.modules() or []) if m in _REPEATABLE_MODULES or m not in present]


def _refresh_add_module_combo(window):
    combo = getattr(window, "add_module_combo", None)
    if combo is None:
        return
    window.add_module_names = _available_modules(window)
    combo.set_model(Gtk.StringList.new(window.add_module_names or ["(all added)"]))


def _add_module(window):
    names = getattr(window, "add_module_names", None)
    if not names:
        return
    index = window.add_module_combo.get_selected()
    if not 0 <= index < len(names):
        return
    name = names[index]
    window.model["modules"].append(name)
    _rebuild_modules_list(window)
    _refresh_add_module_combo(window)
    _notify(window, f"Added module: {name}")


def _remove_module(window, index):
    mods = window.model["modules"]
    if 0 <= index < len(mods):
        removed = cfg.module_type(mods.pop(index))
        _rebuild_modules_list(window)
        _refresh_add_module_combo(window)
        _clear_box(window.module_options_box)
        _notify(window, f"Removed module: {removed}")


def _show_module_options(window):
    _clear_box(window.module_options_box)
    row = window.modules_list.get_selected_row()
    if row is None:
        return
    index = row.get_index()
    entry = window.model["modules"][index]
    mtype = cfg.module_type(entry)
    options = cfg.module_options(entry)

    window.module_options_box.append(_label("<b>Common</b>", markup=True))
    for key, kind, label in ffopts.UNIVERSAL:
        window.module_options_box.append(_curated_row(window, index, options, key, kind, label))

    type_opts = ffopts.MODULE_OPTIONS.get(mtype, [])
    if type_opts:
        window.module_options_box.append(_label(f"<b>{mtype} options</b>", markup=True))
        for key, kind, label in type_opts:
            window.module_options_box.append(_curated_row(window, index, options, key, kind, label))

    curated = ffopts.curated_keys(mtype)
    extra = {k: v for k, v in options.items() if k not in curated}
    expander = Gtk.Expander(label="Advanced (raw keys)")
    adv = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    for key, value in extra.items():
        adv.append(_option_row(window, index, key, value))

    add = _row()
    key_entry = Gtk.Entry()
    key_entry.set_placeholder_text("option key (e.g. percent, separator)")
    val_entry = Gtk.Entry()
    val_entry.set_placeholder_text("value (true/false/number/text)")
    btn = Gtk.Button(label="Add option")
    btn.connect("clicked", lambda _w: _add_option(window, index, key_entry, val_entry))
    add.append(key_entry)
    add.append(val_entry)
    add.append(btn)
    adv.append(add)
    expander.set_child(adv)
    window.module_options_box.append(expander)


def _curated_row(window, index, options, key, kind, label):
    line = _row()
    line.append(_label(label + ":"))
    value = options.get(key)
    if kind == "bool":
        sw = Gtk.Switch()
        sw.set_active(bool(value))
        sw.set_halign(Gtk.Align.START)
        sw.set_hexpand(True)
        sw.connect(
            "notify::active",
            lambda s, _p: _set_option_value(window, index, key, True)
            if s.get_active() else _del_option(window, index, key),
        )
        line.append(sw)
    elif kind == "color":
        widget, _set = _color_editor(
            value,
            lambda v: _set_option_value(window, index, key, v) if v else _del_option(window, index, key),
        )
        widget.set_hexpand(True)
        widget.set_halign(Gtk.Align.START)
        line.append(widget)
    else:
        ent = Gtk.Entry()
        ent.set_hexpand(True)
        ent.set_text(_value_to_text(value) if value is not None else "")
        ent.connect(
            "activate",
            lambda e: _set_option_value(window, index, key, _text_to_value(e.get_text()))
            if e.get_text().strip() else _del_option(window, index, key),
        )
        line.append(ent)
    return line


def _option_row(window, index, key, value):
    line = _row()
    line.append(_label(key + ":"))
    entry = Gtk.Entry()
    entry.set_text(_value_to_text(value))
    entry.set_hexpand(True)
    entry.connect("activate", lambda e: _set_option(window, index, key, e.get_text()))
    line.append(entry)
    btn = Gtk.Button(label="✕")
    btn.add_css_class("flat")
    btn.connect("clicked", lambda _w: _del_option(window, index, key))
    line.append(btn)
    return line


def _ensure_object_module(window, index):
    entry = window.model["modules"][index]
    if isinstance(entry, str):
        entry = {"type": entry}
        window.model["modules"][index] = entry
    return entry


def _add_option(window, index, key_entry, val_entry):
    key = key_entry.get_text().strip()
    if not key or val_entry.get_text().strip().lower() in ("null", "none"):
        return
    entry = _ensure_object_module(window, index)
    entry[key] = _text_to_value(val_entry.get_text())
    _rebuild_modules_list(window)
    window.modules_list.select_row(window.modules_list.get_row_at_index(index))


def _set_option(window, index, key, text):
    if text.strip().lower() in ("null", "none"):
        _del_option(window, index, key)
        return
    entry = _ensure_object_module(window, index)
    entry[key] = _text_to_value(text)
    _notify(window, f"Set {key} = {text}")


def _set_option_value(window, index, key, value):
    """Set a raw option value; rebuild the list only when the key's presence changes."""
    entry = window.model["modules"][index]
    had = isinstance(entry, dict) and key in entry
    _ensure_object_module(window, index)[key] = value
    if not had:
        _rebuild_modules_list(window)
        window.modules_list.select_row(window.modules_list.get_row_at_index(index))


def _del_option(window, index, key):
    entry = window.model["modules"][index]
    if isinstance(entry, dict) and key in entry:
        del entry[key]
        if list(entry.keys()) == ["type"]:
            window.model["modules"][index] = entry["type"]
    _rebuild_modules_list(window)
    window.modules_list.select_row(window.modules_list.get_row_at_index(index))


# ── Logo + Appearance tabs ───────────────────────────────────────────────────


def _logo_tab(window):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    box.set_margin_start(6)
    box.set_margin_end(6)
    box.set_margin_top(6)

    box.append(_label("<b>Logo</b>", markup=True))

    type_row = _row()
    type_row.append(_label("Type:"))
    window.logo_type = Gtk.DropDown.new_from_strings([_LOGO_TYPE_LABELS[t] for t in _LOGO_TYPES])
    current_type = _ui_logo_type(window.model.get("logo"))
    if current_type in _LOGO_TYPES:
        window.logo_type.set_selected(_LOGO_TYPES.index(current_type))
    window.logo_type.connect("notify::selected", lambda _d, _p: _set_logo_type(window))
    type_row.append(window.logo_type)
    window.logo_current_label = _label("", css_class="info-label")
    window.logo_current_label.set_margin_start(10)
    type_row.append(window.logo_current_label)
    _refresh_current_logo_label(window)
    type_spacer = Gtk.Box()
    type_spacer.set_hexpand(True)
    type_row.append(type_spacer)
    btn_random = Gtk.Button(label="🎲 Random")
    btn_random.set_tooltip_text("Pick a random logo — built-in, Pokémon or Kiro art")
    btn_random.connect("clicked", lambda _w: _random_logo(window))
    type_row.append(btn_random)
    box.append(type_row)

    logo_row = _row()
    logo_row.append(_label("Built-in logo:"))
    logos = catalog.logos() or ["(none)"]
    window.logo_source = _searchable_dropdown(logos)
    window.logo_source.set_hexpand(True)
    src = str((window.model.get("logo") or {}).get("source", ""))
    if src in logos:
        window.logo_source.set_selected(logos.index(src))
    window.logo_source.connect("notify::selected", lambda _d, _p: _set_logo_source(window))
    logo_row.append(window.logo_source)
    window.logo_builtin_row = logo_row
    box.append(logo_row)

    bundled_row = _row()
    bundled_row.append(_label("Bundled image:"))
    window.logo_bundled_names = _bundled_logo_images()
    window.logo_bundled = _searchable_dropdown(window.logo_bundled_names or ["(none bundled)"])
    window.logo_bundled.set_hexpand(True)
    cur_base = os.path.basename(str((window.model.get("logo") or {}).get("source", "")))
    if cur_base in window.logo_bundled_names:
        window.logo_bundled.set_selected(window.logo_bundled_names.index(cur_base))
    window.logo_bundled.connect("notify::selected", lambda _d, _p: _set_logo_bundled(window))
    bundled_row.append(window.logo_bundled)
    window.logo_bundled_row = bundled_row
    box.append(bundled_row)

    file_row = _row()
    file_row.append(_label("Custom image:"))
    window.logo_file_label = _label("(none)", css_class="info-label")
    window.logo_file_label.set_hexpand(True)
    btn_file = Gtk.Button(label="Choose file…")
    btn_file.connect("clicked", lambda _w: _choose_logo_file(window))
    file_row.append(window.logo_file_label)
    file_row.append(btn_file)
    window.logo_file_row = file_row
    box.append(file_row)

    window.pokemon_names = _pokemon_names()
    poke_row = _row()
    poke_row.append(_label("Pokémon:"))
    window.pokemon_dd = _searchable_dropdown(window.pokemon_names or ["(none)"])
    window.pokemon_dd.set_hexpand(True)
    poke_row.append(window.pokemon_dd)
    window.pokemon_size = Gtk.DropDown.new_from_strings(_POKEMON_SIZES)
    poke_row.append(window.pokemon_size)
    window.pokemon_shiny = Gtk.CheckButton(label="Shiny")
    poke_row.append(window.pokemon_shiny)
    btn_poke = Gtk.Button(label="Use")
    btn_poke.connect("clicked", lambda _w: _set_logo_pokemon(window))
    poke_row.append(btn_poke)
    window.pokemon_row = poke_row
    box.append(poke_row)
    _refresh_pokemon_controls(window)

    art_row = _row()
    art_row.append(_label("Kiro art:"))
    window.kiroart_names = _kiro_art_names()
    window.kiroart_dd = _searchable_dropdown(window.kiroart_names or ["(none)"])
    window.kiroart_dd.set_hexpand(True)
    art_row.append(window.kiroart_dd)
    btn_art = Gtk.Button(label="Use")
    btn_art.connect("clicked", lambda _w: _set_logo_kiroart(window))
    art_row.append(btn_art)
    window.kiroart_row = art_row
    box.append(art_row)

    inline_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    inline_row.append(_label("Inline text (ASCII art stored in the config):"))

    text_row = _row()
    text_row.append(_label("Text:"))
    window.gen_entry = Gtk.Entry()
    window.gen_entry.set_hexpand(True)
    window.gen_entry.set_placeholder_text("Type text, then Generate")
    window.gen_entry.connect("activate", lambda _e: _generate_text(window))
    text_row.append(window.gen_entry)
    inline_row.append(text_row)

    gen_bar = _row()
    gen_bar.append(_label("Tool:"))
    window.gen_tool = Gtk.DropDown.new_from_strings(_TEXT_TOOLS)
    window.gen_tool.connect("notify::selected", lambda _d, _p: _refresh_gen_controls(window))
    gen_bar.append(window.gen_tool)
    window.gen_variant_label = _label("Font:")
    gen_bar.append(window.gen_variant_label)
    window.gen_variant_names = _figlet_fonts()
    window.gen_variant = _searchable_dropdown(window.gen_variant_names)
    gen_bar.append(window.gen_variant)
    window.gen_rainbow = Gtk.CheckButton(label="Rainbow")
    gen_bar.append(window.gen_rainbow)
    window.gen_btn = Gtk.Button(label="Generate")
    window.gen_btn.connect("clicked", lambda _w: _generate_text(window))
    gen_bar.append(window.gen_btn)
    window.gen_kiro_btn = Gtk.Button(label="Insert Kiro figlet")
    window.gen_kiro_btn.connect("clicked", lambda _w: _generate_text(window, "Kiro"))
    gen_bar.append(window.gen_kiro_btn)
    inline_row.append(gen_bar)

    window.gen_hint = _label("", css_class="info-label", wrap=True, max_chars=60)
    inline_row.append(window.gen_hint)
    _refresh_gen_controls(window)

    window.logo_inline_view = Gtk.TextView()
    window.logo_inline_view.set_monospace(True)
    window.logo_inline_view.set_wrap_mode(Gtk.WrapMode.NONE)
    inline_buf = window.logo_inline_view.get_buffer()
    logo_d = window.model.get("logo") or {}
    if str(logo_d.get("type", "")) in _INLINE_LOGO_TYPES:
        inline_buf.set_text(str(logo_d.get("source", "")))
    inline_buf.connect("changed", lambda b: _set_logo_inline(window, b))
    inline_sw = Gtk.ScrolledWindow()
    inline_sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    inline_sw.set_min_content_height(90)
    inline_sw.set_child(window.logo_inline_view)
    inline_row.append(inline_sw)
    window.logo_inline_row = inline_row
    box.append(inline_row)

    pos_row = _row()
    pos_row.append(_label("Logo position:"))
    window.logo_position = Gtk.DropDown.new_from_strings(_LOGO_POSITIONS)
    cur_pos = str((window.model.get("logo") or {}).get("position", "left"))
    if cur_pos in _LOGO_POSITIONS:
        window.logo_position.set_selected(_LOGO_POSITIONS.index(cur_pos))
    window.logo_position.connect("notify::selected", lambda _d, _p: _set_logo_position(window))
    pos_row.append(window.logo_position)

    window.logo_dim_rows = [
        pos_row,
        _spin_row(window, "Logo width", ("logo", "width"), 0, 200),
        _spin_row(window, "Logo height", ("logo", "height"), 0, 200),
        _spin_row(window, "Logo padding top", ("logo", "padding", "top"), 0, 50),
        _spin_row(window, "Logo padding left", ("logo", "padding", "left"), 0, 50),
    ]
    for row in window.logo_dim_rows:
        box.append(row)

    _apply_logo_type_state(window)

    help_text = (
        "<b>Logo type — where the logo comes from:</b>\n"
        "• <b>Big ASCII</b> / <b>Small ASCII</b>: a logo built into fastfetch, picked in “Built-in logo”.\n"
        "• <b>Text file</b>: your own ASCII-art text file, picked in “Custom image”.\n"
        "• <b>Pokémon</b>: a pokemon-colorscripts critter, picked in the “Pokémon” row.\n"
        "• <b>Kiro art</b>: a bundled Kiro ASCII/ANSI logo, picked in the “Kiro art” row.\n"
        "• <b>Inline text</b>: ASCII art typed/generated into the box, stored in the config.\n"
        "• <b>Sixel</b> / <b>Kitty</b> / <b>Chafa</b>: render a real image, picked in “Bundled image” or “Custom image”.\n"
        "• <b>None</b>: no logo at all.\n"
        "Tip: use a transparent <b>PNG</b> (not JPG) so the logo shows with no background box.\n"
        "Tip: real images (Sixel/Kitty) need a graphics-capable terminal — kitty, Ghostty, "
        "Konsole, WezTerm, foot. <b>Alacritty shows no images</b>; use <b>Chafa</b> there (image "
        "rendered as coloured text)."
    )
    help_label = _label(help_text, css_class="info-label", markup=True, wrap=True, max_chars=60)
    help_label.set_margin_top(12)
    box.append(help_label)

    return _scrolled(box)


_TEMPUNIT_CHOICES = [("C", "Celsius"), ("F", "Fahrenheit"), ("K", "Kelvin")]
_BINPREFIX_CHOICES = [("iec", "IEC — 1024 (KiB)"), ("si", "SI — 1000 (kB)"), ("jedec", "JEDEC — 1024 (KB)")]
_MAXPREFIX_CHOICES = [(p, p) for p in ("B", "kB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")]
_KEY_TYPE_CHOICES = [("none", "None"), ("string", "Text"), ("icon", "Icon"), ("both", "Both")]


def _appearance_tab(window):
    window.color_combos = {}
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    box.set_margin_start(6)
    box.set_margin_end(6)
    box.set_margin_top(6)

    box.append(_label("<b>Appearance</b>", markup=True))

    sep_row = _row()
    sep_row.append(_label("Separator:"))
    window.separator_entry = Gtk.Entry()
    window.separator_entry.set_text(str((window.model.get("display") or {}).get("separator", ": ")))
    window.separator_entry.set_hexpand(True)
    window.separator_entry.connect(
        "changed", lambda e: _set_path(window, ("display", "separator"), e.get_text())
    )
    sep_row.append(window.separator_entry)
    box.append(sep_row)

    box.append(_color_row(window, "Key color", ("display", "color", "keys")))
    box.append(_color_row(window, "Title color", ("display", "color", "title")))
    box.append(_color_row(window, "Output color", ("display", "color", "output")))
    box.append(_color_row(window, "Separator color", ("display", "color", "separator")))
    box.append(_switch_setting_row(window, "Bright ANSI colors", ("display", "brightColor")))

    box.append(_label("<b>Key style</b>", markup=True))
    box.append(_spin_row(window, "Key width", ("display", "key", "width"), 0, 60))
    box.append(_enum_setting_row(window, "Key style", ("display", "key", "type"), _KEY_TYPE_CHOICES))
    box.append(_spin_row(window, "Key left padding", ("display", "key", "paddingLeft"), 0, 20))

    box.append(_label("<b>Sizes &amp; temperature</b>", markup=True))
    box.append(_enum_setting_row(window, "Size binary prefix", ("display", "size", "binaryPrefix"), _BINPREFIX_CHOICES))
    box.append(_enum_setting_row(window, "Largest size unit", ("display", "size", "maxPrefix"), _MAXPREFIX_CHOICES))
    box.append(_enum_setting_row(window, "Temperature unit", ("display", "temp", "unit"), _TEMPUNIT_CHOICES))

    box.append(_label("<b>Threshold colors</b>", markup=True))
    box.append(_label("Colour percentages and temperatures by severity.", css_class="dim-label"))
    for state in ("green", "yellow", "red"):
        box.append(_color_row(window, f"Percent {state}", ("display", "percent", "color", state)))
    for state in ("green", "yellow", "red"):
        box.append(_color_row(window, f"Temp {state}", ("display", "temp", "color", state)))

    return _scrolled(box)


def _spin_row(window, label, path, low, high):
    line = _row()
    line.append(_label(label + ":"))
    adj = Gtk.Adjustment(lower=low, upper=high, step_increment=1)
    spin = Gtk.SpinButton()
    spin.set_adjustment(adj)
    spin.set_value(float(_get_path(window, path) or 0))
    spin.connect(
        "value-changed",
        lambda s: _set_path(window, path, int(s.get_value()), drop_zero=True),
    )
    window.setting_spins.append((path, spin))
    line.append(spin)
    return line


def _enum_combo(value, choices, on_change):
    """Return a DropDown over choices=[(value, label), ...] with a leading '(default)' clearing the key."""
    vals = [None] + [v for v, _label in choices]
    combo = Gtk.DropDown.new_from_strings(["(default)"] + [label for _v, label in choices])
    if value in vals:
        combo.set_selected(vals.index(value))
    combo.connect("notify::selected", lambda d, _p: on_change(vals[d.get_selected()]))
    return combo


def _enum_setting_row(window, label, path, choices):
    line = _row()
    line.append(_label(label + ":"))
    combo = _enum_combo(_get_path(window, path), choices, lambda v: _set_path(window, path, v))
    combo.set_hexpand(True)
    combo.set_halign(Gtk.Align.START)
    window.enum_combos.append((path, combo, [None] + [v for v, _label in choices]))
    line.append(combo)
    return line


def _switch_setting_row(window, label, path):
    """A labelled switch writing an explicit bool (on=true, off=false) to a display path."""
    line = _row()
    line.append(_label(label + ":"))
    spacer = Gtk.Box()
    spacer.set_hexpand(True)
    line.append(spacer)
    switch = Gtk.Switch()
    switch.set_active(bool(_get_path(window, path)))
    switch.connect("notify::active", lambda s, _p: _set_path(window, path, s.get_active()))
    window.setting_switches.append((path, switch))
    line.append(switch)
    return line


def _rgba_to_hex(rgba):
    return "#%02x%02x%02x" % (round(rgba.red * 255), round(rgba.green * 255), round(rgba.blue * 255))


def _color_editor(value, on_change):
    """Return (widget, set_value): named-colour dropdown + GTK picker + free hex/SGR entry.

    fastfetch accepts named colours, hex (#rrggbb), and raw SGR (e.g. 38;5;208 / 38;2;r;g;b).
    on_change(colour_or_None) fires on any change; set_value(colour_or_None) updates the widget
    without emitting (used on reload).
    """
    names = _COLORS + [_CUSTOM_COLOR]
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    dropdown = Gtk.DropDown.new_from_strings(names)
    entry = Gtk.Entry()
    entry.set_placeholder_text("#hex / SGR")
    entry.set_max_width_chars(12)
    button = Gtk.ColorDialogButton.new(Gtk.ColorDialog())
    state = {"guard": True}

    def current_value():
        sel = names[dropdown.get_selected()]
        if sel == _CUSTOM_COLOR:
            return entry.get_text().strip() or None
        return None if sel == "default" else sel

    def emit():
        if not state["guard"]:
            on_change(current_value())

    def set_value(v):
        state["guard"] = True
        text = "" if v is None else str(v)
        if text == "" or text == "default":
            dropdown.set_selected(_COLORS.index("default"))
            entry.set_visible(False)
        elif text in _COLORS:
            dropdown.set_selected(_COLORS.index(text))
            entry.set_visible(False)
        else:
            dropdown.set_selected(names.index(_CUSTOM_COLOR))
            entry.set_text(text)
            entry.set_visible(True)
            rgba = Gdk.RGBA()
            if text.startswith("#") and rgba.parse(text):
                button.set_rgba(rgba)
        state["guard"] = False

    def on_dropdown(_d, _p):
        entry.set_visible(names[dropdown.get_selected()] == _CUSTOM_COLOR)
        emit()

    def on_button(_b, _p):
        if state["guard"]:
            return
        state["guard"] = True
        dropdown.set_selected(names.index(_CUSTOM_COLOR))
        entry.set_text(_rgba_to_hex(button.get_rgba()))
        entry.set_visible(True)
        state["guard"] = False
        on_change(current_value())

    dropdown.connect("notify::selected", on_dropdown)
    entry.connect("activate", lambda _e: emit())
    button.connect("notify::rgba", on_button)
    set_value(value)

    box.append(dropdown)
    box.append(button)
    box.append(entry)
    return box, set_value


def _color_row(window, label, path):
    line = _row()
    line.append(_label(label + ":"))
    widget, set_value = _color_editor(_get_path(window, path), lambda v: _set_path(window, path, v))
    window.color_combos[path] = set_value
    line.append(widget)
    return line


_BUILTIN_LOGO_TYPES = {"builtin", "small"}
_FILE_LOGO_TYPES = {"file", "sixel", "kitty", "chafa"}
_INLINE_LOGO_TYPES = {"data"}
_IMAGE_LOGO_TYPES = {"sixel", "kitty", "chafa"}
_LOGO_IMG_EXTS = (".png", ".jpg", ".jpeg", ".svg", ".gif", ".bmp")
_LOGO_POSITIONS = ["left", "top", "right"]  # fastfetch logo.position (no "bottom")


_FIGLET_FONT_DIR = "/usr/share/figlet/fonts"
_COWFILE_DIR = "/usr/share/cowsay/cows"
_TEXT_TOOLS = ["figlet", "toilet", "cowsay", "botsay"]  # ASCII-art text generators
_POKEMON_BASE = "/opt/pokemon-colorscripts/colorscripts"
_POKEMON_SIZES = ["small", "large"]

# Optional packages that aren't in the base Arch repos — what to tell the user if missing.
_OPTIONAL_REPO_HINT = {
    "pokemon-colorscripts-git": "the chaotic-aur or cachyos repo",
}


def _pokemon_names():
    """Return sorted pokemon-colorscripts names, or [] if the package isn't installed."""
    try:
        return sorted(os.listdir(os.path.join(_POKEMON_BASE, "small", "regular")))
    except OSError:
        return []


def _kiro_art_dir():
    return os.path.join(cfg.BASE_DIR, "data", "ascii")


def _kiro_art_names():
    """Return sorted bundled Kiro ASCII/ANSI art filenames."""
    try:
        return sorted(f for f in os.listdir(_kiro_art_dir()) if f.endswith(".txt"))
    except OSError:
        return []


def _ui_logo_type(logo):
    """Map the stored logo to the Type dropdown value, surfacing the file-based pseudo-types."""
    logo = logo or {}
    real = str(logo.get("type", "builtin"))
    src = str(logo.get("source", ""))
    if real == "file":
        if src.startswith(_POKEMON_BASE):
            return "pokemon"
        if src.startswith(_kiro_art_dir()):
            return "kiroart"
    return real


def _logo_summary(logo):
    """One-line description of the active logo for the 'in use' indicator."""
    if isinstance(logo, str):
        return f"Built-in — {logo}" if logo else "Built-in"
    logo = logo or {}
    ui = _ui_logo_type(logo)
    label = _LOGO_TYPE_LABELS.get(ui, ui)
    real = str(logo.get("type", "builtin"))
    src = str(logo.get("source", ""))
    if real == "data":
        detail = "inline text"
    elif real in ("builtin", "small"):
        detail = src
    elif src:
        detail = os.path.basename(src)
    else:
        detail = ""
    return f"{label} — {detail}" if detail else label


def _refresh_current_logo_label(window):
    """Update the dim 'in use' label next to Type from the on-disk config."""
    if not hasattr(window, "logo_current_label"):
        return
    window.logo_current_label.set_text(f"in use: {_logo_summary(cfg.read_config().get('logo'))}")


def _bundled_logo_images():
    """Return sorted basenames of the image files bundled in data/logo/."""
    logo_dir = os.path.join(cfg.BASE_DIR, "data", "logo")
    try:
        names = os.listdir(logo_dir)
    except OSError:
        return []
    return sorted(n for n in names if n.lower().endswith(_LOGO_IMG_EXTS))


_FIGLET_FONT_SKIP = {"mini", "mnemonic", "ivrit"}


def _figlet_fonts():
    """Return installed figlet font names, 'standard' first as the default."""
    try:
        names = sorted(
            f[:-4] for f in os.listdir(_FIGLET_FONT_DIR)
            if f.endswith(".flf") and f[:-4] not in _FIGLET_FONT_SKIP
        )
    except OSError:
        return ["standard"]
    if "standard" in names:
        names.remove("standard")
        names.insert(0, "standard")
    return names or ["standard"]


_TOILET_FONT_DIR = "/usr/share/figlet"  # toilet ships its .tlf fonts here (not the figlet /fonts subdir)


def _toilet_fonts():
    """Return toilet's own .tlf font names, a nice one first."""
    try:
        names = sorted(f[:-4] for f in os.listdir(_TOILET_FONT_DIR) if f.endswith(".tlf"))
    except OSError:
        return ["future"]
    for pref in ("future", "pagga", "emboss", "bigmono9"):
        if pref in names:
            names.remove(pref)
            names.insert(0, pref)
            break
    return names or ["future"]


def _cowfiles():
    """Return installed cowsay cowfile names, 'default' first."""
    try:
        names = sorted(f[:-4] for f in os.listdir(_COWFILE_DIR) if f.endswith(".cow"))
    except OSError:
        return ["default"]
    if "default" in names:
        names.remove("default")
        names.insert(0, "default")
    return names or ["default"]


def _apply_logo_type_state(window):
    """Grey out the logo rows that don't apply to the selected logo type."""
    value = _LOGO_TYPES[window.logo_type.get_selected()]
    window.logo_builtin_row.set_sensitive(value in _BUILTIN_LOGO_TYPES)
    window.logo_bundled_row.set_sensitive(value in _IMAGE_LOGO_TYPES)
    window.logo_file_row.set_sensitive(value in _FILE_LOGO_TYPES)
    window.pokemon_row.set_sensitive(value == "pokemon")
    window.kiroart_row.set_sensitive(value == "kiroart")
    window.logo_inline_row.set_sensitive(value in _INLINE_LOGO_TYPES)
    has_logo = value != "none"
    for row in window.logo_dim_rows:
        row.set_sensitive(has_logo)


def _set_logo_inline(window, buffer):
    start, end = buffer.get_bounds()
    window.model.setdefault("logo", {})["source"] = buffer.get_text(start, end, False)


def _gen_variants(tool):
    """Return (label, variant-list) for the given text tool; botsay has no variants."""
    if tool == "figlet":
        return "Font:", _figlet_fonts()
    if tool == "toilet":
        return "Font:", _toilet_fonts()
    if tool == "cowsay":
        return "Cowfile:", _cowfiles()
    return "", []


def _refresh_gen_controls(window):
    """Sync the text-generator controls to the selected tool and its install state."""
    if not hasattr(window, "gen_btn"):
        return False
    tool = _TEXT_TOOLS[window.gen_tool.get_selected()]
    ok = bool(shutil.which(tool))
    label, variants = _gen_variants(tool)
    has_variants = bool(variants)
    window.gen_variant_label.set_text(label)
    window.gen_variant_label.set_visible(has_variants)
    window.gen_variant.set_visible(has_variants)
    if has_variants and variants != window.gen_variant_names:
        window.gen_variant_names = variants
        window.gen_variant.set_model(Gtk.StringList.new(variants))
    window.gen_entry.set_sensitive(ok)
    window.gen_variant.set_sensitive(ok and has_variants)
    window.gen_rainbow.set_sensitive(ok and bool(shutil.which("lolcat")))
    window.gen_btn.set_sensitive(ok)
    window.gen_kiro_btn.set_sensitive(ok)
    window.gen_kiro_btn.set_label(f"Insert Kiro {tool}")
    window.gen_hint.set_visible(not ok)
    window.gen_hint.set_markup(
        f'<span foreground="#e8820c">{tool} not installed — install it on the Install &amp; Enable tab</span>')
    return False


def _generate_text(window, override=None):
    text = (override if override is not None else window.gen_entry.get_text()).strip()
    if not text:
        return
    tool = _TEXT_TOOLS[window.gen_tool.get_selected()]
    if not shutil.which(tool):
        _notify(window, f"{tool} not installed — install it on the Install & Enable tab")
        return
    font = window.gen_variant_names[window.gen_variant.get_selected()]
    if tool == "figlet":
        # -w 1000 overrules figlet's 80-column default so the art never wraps into stacked blocks.
        cmd = ["figlet", "-f", font, "-w", "1000", text]
    elif tool == "toilet":
        cmd = ["toilet", "-f", font, "-w", "1000", text]
    elif tool == "cowsay":
        cmd = ["cowsay", "-f", font, text]
    else:
        cmd = ["botsay", text]
    rainbow = window.gen_rainbow.get_active() and bool(shutil.which("lolcat"))

    def work():
        try:
            art = subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
            if rainbow:
                # -f forces colour even though output isn't a TTY; bakes ANSI colour into the art.
                art = subprocess.run(["lolcat", "-f"], input=art, capture_output=True, text=True, timeout=10).stdout
            GLib.idle_add(_apply_generated, window, art)
        except (OSError, subprocess.SubprocessError) as exc:
            GLib.idle_add(_notify, window, f"{tool} failed: {exc}")

    threading.Thread(target=work, daemon=True).start()


def _apply_generated(window, art):
    window.logo_inline_view.get_buffer().set_text(art)
    window.model.setdefault("logo", {})["type"] = "data"
    window.logo_type.set_selected(_LOGO_TYPES.index("data"))
    return False


def _random_logo(window):
    """Pick a random logo from whatever's available — built-in, Pokémon, or Kiro art."""
    pools = []
    logos = catalog.logos()
    if logos:
        pools.append("builtin")
    if getattr(window, "pokemon_names", None):
        pools.append("pokemon")
    if getattr(window, "kiroart_names", None):
        pools.append("kiroart")
    if not pools:
        return
    kind = random.choice(pools)
    if kind == "builtin":
        src = random.choice(logos)
        logo = window.model.setdefault("logo", {})
        logo["type"] = "builtin"
        logo["source"] = src
        window.logo_source.set_selected(logos.index(src))
        window.logo_type.set_selected(_LOGO_TYPES.index("builtin"))
        _notify(window, f"Random logo: {src}")
    elif kind == "pokemon":
        window.pokemon_shiny.set_active(random.randrange(8) == 0)
        window.pokemon_dd.set_selected(random.randrange(len(window.pokemon_names)))
        _set_logo_pokemon(window)
    else:
        window.kiroart_dd.set_selected(random.randrange(len(window.kiroart_names)))
        _set_logo_kiroart(window)


def _set_logo_position(window):
    window.model.setdefault("logo", {})["position"] = _LOGO_POSITIONS[window.logo_position.get_selected()]


def _sync_source_for_type(window, value):
    """Point logo.source at the picker that owns the new type, clearing a stale path."""
    logo = window.model.setdefault("logo", {})
    if value in ("builtin", "small"):
        logos = catalog.logos()
        if logos:
            logo["source"] = logos[window.logo_source.get_selected()]
    elif value == "pokemon":
        if getattr(window, "pokemon_names", None):
            logo["source"] = _pokemon_path(window)
    elif value == "kiroart":
        if getattr(window, "kiroart_names", None):
            logo["source"] = _kiro_art_path(window)
    elif value == "data":
        buf = window.logo_inline_view.get_buffer()
        start, end = buf.get_bounds()
        logo["source"] = buf.get_text(start, end, False)
    elif value == "none":
        logo.pop("source", None)
    # file / sixel / kitty / chafa: source comes from the Custom image / Bundled image pickers.


def _set_logo_type(window):
    value = _LOGO_TYPES[window.logo_type.get_selected()]
    window.model.setdefault("logo", {})["type"] = _TYPE_ALIAS.get(value, value)
    if not getattr(window, "_suppress_source_sync", False):
        _sync_source_for_type(window, value)
    _apply_logo_type_state(window)
    if value == "chafa" and not shutil.which("chafa"):
        _notify(window, "chafa not installed — install it on the Install & Enable tab to render image logos")
    else:
        _notify(window, f"Logo type: {_LOGO_TYPE_LABELS[value]}")


def _set_logo_source(window):
    logos = catalog.logos()
    if not logos:
        return
    window.model.setdefault("logo", {})["source"] = logos[window.logo_source.get_selected()]


def _refresh_pokemon_controls(window):
    """Show/repopulate the Pokémon picker based on whether pokemon-colorscripts is installed."""
    if not hasattr(window, "pokemon_row"):
        return False
    names = _pokemon_names()
    window.pokemon_row.set_visible(bool(names))
    if names and names != window.pokemon_names:
        window.pokemon_names = names
        window.pokemon_dd.set_model(Gtk.StringList.new(names))
    return False


def _pokemon_path(window):
    name = window.pokemon_names[window.pokemon_dd.get_selected()]
    size = _POKEMON_SIZES[window.pokemon_size.get_selected()]
    variant = "shiny" if window.pokemon_shiny.get_active() else "regular"
    return os.path.join(_POKEMON_BASE, size, variant, name)


def _set_logo_pokemon(window):
    if not window.pokemon_names:
        return
    name = window.pokemon_names[window.pokemon_dd.get_selected()]
    logo = window.model.setdefault("logo", {})
    logo["source"] = _pokemon_path(window)
    logo["type"] = "file"
    window.logo_type.set_selected(_LOGO_TYPES.index("pokemon"))
    _notify(window, f"Pokémon logo: {name}")


def _kiro_art_path(window):
    return os.path.join(_kiro_art_dir(), window.kiroart_names[window.kiroart_dd.get_selected()])


def _set_logo_kiroart(window):
    if not window.kiroart_names:
        return
    name = window.kiroart_names[window.kiroart_dd.get_selected()]
    logo = window.model.setdefault("logo", {})
    logo["source"] = _kiro_art_path(window)
    logo["type"] = "file"
    window.logo_type.set_selected(_LOGO_TYPES.index("kiroart"))
    _notify(window, f"Kiro art: {name}")


def _set_logo_bundled(window):
    names = window.logo_bundled_names
    if not names:
        return
    name = names[window.logo_bundled.get_selected()]
    logo = window.model.setdefault("logo", {})
    logo["source"] = os.path.join(cfg.BASE_DIR, "data", "logo", name)
    if str(logo.get("type", "")) not in _IMAGE_LOGO_TYPES:
        logo["type"] = "chafa"
        window.logo_type.set_selected(_LOGO_TYPES.index("chafa"))
    _notify(window, f"Logo image: {name}")


def _choose_logo_file(window):
    dialog = Gtk.FileDialog()

    def done(d, result):
        try:
            file = d.open_finish(result)
        except GLib.Error:
            return
        path = file.get_path()
        window.logo_file_label.set_text(path)
        logo = window.model.setdefault("logo", {})
        logo["source"] = path
        if str(logo.get("type", "builtin")) in ("builtin", "small", "none"):
            logo["type"] = "file"
            window.logo_type.set_selected(_LOGO_TYPES.index("file"))

    dialog.open(window, None, done)


# ── Install & Enable tab ─────────────────────────────────────────────────────


def _install_tab(window):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    box.set_margin_start(10)
    box.set_margin_end(10)
    box.set_margin_top(6)

    window.flash_gen = {}

    box.append(_label("<b>Fastfetch</b>", markup=True))
    ff_row = _row()
    installed = cfg.fastfetch_installed()
    window.ff_msg = _label("")
    spacer = Gtk.Box()
    spacer.set_hexpand(True)
    window.ff_installed = _label("<b>installed</b>" if installed else "", markup=True,
                                 css_class="info-label")
    btn_install = Gtk.Button(label="Install")
    btn_install.connect("clicked", lambda _w: _install_fastfetch(window))
    btn_remove = Gtk.Button(label="Remove")
    btn_remove.add_css_class("destructive-action")
    btn_remove.connect("clicked", lambda _w: _remove_fastfetch(window))
    ff_row.append(window.ff_msg)
    ff_row.append(spacer)
    ff_row.append(window.ff_installed)
    ff_row.append(btn_install)
    ff_row.append(btn_remove)
    box.append(ff_row)

    box.append(_label("<b>Shell startup</b>", markup=True))
    rc = install.shell_rc_path()
    box.append(_label(f"Target: {rc or 'no shell rc found'}", css_class="info-label"))

    enabled, lolcat = install.startup_state()
    window.startup_switch = _switch_row(box, "Run fastfetch on shell startup", enabled,
                                        lambda active: _toggle_startup(window, active))
    window.lolcat_switch = _switch_row(box, "Pipe through lolcat (rainbow)", lolcat,
                                       lambda active: _toggle_lolcat(window, active))
    window.lolcat_switch.set_sensitive(enabled)

    box.append(_label("<b>Optional features</b>", markup=True))
    window.optional_status = {}
    window.optional_msg = {}
    for pkg, desc in (
        ("chafa", "image logos as ASCII art"),
        ("imagemagick", "sixel / kitty image logos"),
        ("figlet", "generate ASCII-art text logos"),
        ("toilet", "fancy ASCII-art text logos"),
        ("cowsay", "speech-bubble text logos"),
        ("botsay", "robot text logos"),
        ("pokemon-colorscripts-git", "Pokémon logos"),
        ("lolcat", "rainbow output pipe"),
        ("ddcutil", "external-display brightness"),
    ):
        opt = _row()
        opt.append(_label(f"{pkg} — {desc}"))
        sp1 = Gtk.Box()
        sp1.set_hexpand(True)
        opt.append(sp1)
        msg = _label("")
        window.optional_msg[pkg] = msg
        opt.append(msg)
        sp2 = Gtk.Box()
        sp2.set_hexpand(True)
        opt.append(sp2)
        status = _label("", css_class="info-label")
        window.optional_status[pkg] = status
        opt.append(status)
        btn = Gtk.Button(label="Install")
        btn.connect("clicked", lambda _w, p=pkg: _install_optional(window, p))
        opt.append(btn)
        box.append(opt)
    _refresh_optional_status(window)

    box.append(_label("<b>Privacy</b>", markup=True))
    window.hide_ip_switch = _switch_row(
        box, "Omit public IP module from saved config",
        getattr(window, "hide_public_ip", True),
        lambda active: _toggle_hide_public_ip(window, active))
    box.append(_label(
        "When on, Apply writes config.jsonc without the publicip module, so your real IP "
        "can't leak from your config — e.g. while recording or sharing your screen.",
        css_class="info-label", wrap=True, max_chars=60))

    return _scrolled(box)


def _toggle_hide_public_ip(window, active):
    window.hide_public_ip = active
    prefs = cfg.load_prefs()
    prefs["hide_public_ip"] = active
    cfg.save_prefs(prefs)
    _notify(window, "Public IP will be omitted from saved config" if active
            else "Public IP will be written to saved config")


def _refresh_optional_status(window):
    for pkg, label in getattr(window, "optional_status", {}).items():
        label.set_markup("<b>installed</b>" if install.package_installed(pkg) else "")


def _flash_message(window, key, label, text):
    """Show a transient orange message on `label` for 3 seconds (keyed for repeat-click safety)."""
    if label is None:
        return
    gen = window.flash_gen.get(key, 0) + 1
    window.flash_gen[key] = gen
    label.set_markup(f'<span foreground="#e8820c">{text}</span>')

    def _clear():
        if window.flash_gen.get(key) == gen:
            label.set_text("")
        return False

    GLib.timeout_add(3000, _clear)


def _switch_row(box, label, active, callback):
    line = _row()
    line.append(_label(label))
    spacer = Gtk.Box()
    spacer.set_hexpand(True)
    line.append(spacer)
    switch = Gtk.Switch()
    switch.set_active(active)
    switch.connect("notify::active", lambda s, _p: callback(s.get_active()))
    line.append(switch)
    box.append(line)
    return switch


def _toggle_startup(window, active):
    if not cfg.fastfetch_installed() and active:
        _notify(window, "Install fastfetch first")
        window.startup_switch.set_active(False)
        return
    if not active and window.lolcat_switch.get_active():
        window.lolcat_switch.set_active(False)  # lolcat makes no sense without startup → follow off
    install.write_startup(active, window.lolcat_switch.get_active())
    window.lolcat_switch.set_sensitive(active)
    _notify(window, f"Shell startup {'enabled' if active else 'disabled'}")


def _toggle_lolcat(window, active):
    if active and not install.installed_fastfetch_package():
        pass
    install.write_startup(window.startup_switch.get_active(), active)
    _notify(window, f"lolcat pipe {'enabled' if active else 'disabled'}")


def _install_fastfetch(window):
    if cfg.fastfetch_installed():
        _flash_message(window, "fastfetch", window.ff_msg, "already installed")
        return
    pkg = install.pick_fastfetch_package()
    _run_pkg_op(window, install.install_package, pkg, f"Installing {pkg}…")


def _remove_fastfetch(window):
    if not cfg.fastfetch_installed():
        _flash_message(window, "fastfetch", window.ff_msg, "not installed")
        return
    pkg = install.installed_fastfetch_package() or "fastfetch"
    _run_pkg_op(window, install.remove_package, pkg, f"Removing {pkg}…")


def _install_optional(window, pkg):
    if install.package_installed(pkg):
        _flash_message(window, pkg, window.optional_msg.get(pkg), "already installed")
        return
    if not install.package_in_repos(pkg):
        hint = _OPTIONAL_REPO_HINT.get(pkg)
        msg = f"needs {hint}" if hint else "not available in your repos"
        _flash_message(window, pkg, window.optional_msg.get(pkg), msg)
        return
    _run_pkg_op(window, install.install_package, pkg, f"Installing {pkg}…")


def _run_pkg_op(window, func, pkg, message):
    _notify(window, message)
    process = func(pkg)

    def wait():
        if process:
            process.wait()
        catalog.clear()
        GLib.idle_add(_refresh_install_status, window)

    threading.Thread(target=wait, daemon=True).start()


def _refresh_install_status(window):
    installed = cfg.fastfetch_installed()
    window.ff_installed.set_markup("<b>installed</b>" if installed else "")
    _refresh_optional_status(window)
    _refresh_gen_controls(window)
    _refresh_pokemon_controls(window)
    _notify(window, "Package operation finished")
    return False


# ── Start / Presets tab ──────────────────────────────────────────────────────


def _presets_tab(window):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    box.set_margin_start(10)
    box.set_margin_end(10)
    box.set_margin_top(6)

    intro = _label(
        "<b>Start here</b> — load an example preset or the Kiro default, watch the live "
        "preview, then tweak it on the Modules and Logo &amp; Appearance tabs. Nothing is "
        "written until you Apply — and before applying we always save a backup of your "
        "current config to <tt>config.jsonc.ftt-bak</tt>, so you can Restore backup any time.",
        markup=True, wrap=True, max_chars=60)
    box.append(intro)

    box.append(_label("<b>Presets</b> — load into the editor, then Apply", markup=True))
    preset_row = _row()
    presets = catalog.presets() or ["(none)"]
    window.preset_combo = _searchable_dropdown(presets)
    window.preset_combo.set_hexpand(True)
    btn_load = Gtk.Button(label="Load preset")
    btn_load.connect("clicked", lambda _w: _load_preset(window))
    preset_row.append(window.preset_combo)
    preset_row.append(btn_load)
    box.append(preset_row)

    quick = _row()
    btn_kiro = Gtk.Button(label="Kiro default")
    btn_kiro.connect("clicked", lambda _w: _load_kiro(window))
    btn_restore = Gtk.Button(label="Restore backup")
    btn_restore.connect("clicked", lambda _w: _restore(window))
    quick.append(btn_kiro)
    quick.append(btn_restore)
    box.append(quick)

    box.append(_label("<b>Your presets</b> — save the current editor as a reusable preset, "
                      "or share it via export/import", markup=True, wrap=True, max_chars=60))
    save_row = _row()
    window.user_preset_name = Gtk.Entry()
    window.user_preset_name.set_placeholder_text("preset name")
    window.user_preset_name.set_hexpand(True)
    btn_save = Gtk.Button(label="Save current as preset")
    btn_save.connect("clicked", lambda _w: _save_user_preset(window))
    save_row.append(window.user_preset_name)
    save_row.append(btn_save)
    box.append(save_row)

    io_row = _row()
    btn_export = Gtk.Button(label="Export…")
    btn_export.connect("clicked", lambda _w: _export_config(window))
    btn_import = Gtk.Button(label="Import…")
    btn_import.connect("clicked", lambda _w: _import_config(window))
    io_row.append(btn_export)
    io_row.append(btn_import)
    box.append(io_row)

    return box


# ── Raw tab ──────────────────────────────────────────────────────────────────


def _raw_tab(window):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    box.set_margin_start(10)
    box.set_margin_end(10)
    box.set_margin_top(6)

    box.append(_label("<b>Raw config.jsonc</b> — edits here preserve comments", markup=True))
    window.raw_view = Gtk.TextView()
    window.raw_view.set_monospace(True)
    window.raw_view.get_buffer().set_text(cfg.read_config_text() or cfg.serialize(window.model))
    box.append(_scrolled(window.raw_view))

    raw_actions = _row()
    btn_raw_reload = Gtk.Button(label="Reload from file")
    btn_raw_reload.connect("clicked", lambda _w: _raw_reload(window))
    btn_raw_save = Gtk.Button(label="Validate & save raw")
    btn_raw_save.connect("clicked", lambda _w: _raw_save(window))
    raw_actions.append(btn_raw_reload)
    raw_actions.append(btn_raw_save)
    box.append(raw_actions)

    return box


def _load_preset(window):
    presets = catalog.presets()
    if not presets:
        return
    _load_preset_named(window, presets[window.preset_combo.get_selected()])


def _load_preset_named(window, name):
    import json

    path = cfg.resolve_preset_path(name)
    if not path:
        _notify(window, f"Preset not found: {name}")
        return
    with open(path, "r", encoding="utf-8") as f:
        window.model = _normalize_model(json.loads(cfg.strip_jsonc(f.read())))
    _reload_widgets(window)
    _refresh_preview(window)
    _notify(window, f"Loaded preset: {name}")


def _refresh_presets(window):
    """Invalidate the preset cache and repopulate the dropdown + gallery."""
    catalog.clear()
    names = catalog.presets() or ["(none)"]
    window.preset_combo.set_model(Gtk.StringList.new(names))
    if hasattr(window, "gallery_flow"):
        _populate_gallery(window)


def _save_user_preset(window):
    saved = cfg.save_user_preset(window.user_preset_name.get_text(), window.model)
    if not saved:
        _notify(window, "Enter a preset name first")
        return
    window.user_preset_name.set_text("")
    _refresh_presets(window)
    _notify(window, f"Saved preset: {saved}")


def _export_config(window):
    dialog = Gtk.FileDialog()
    dialog.set_initial_name("config.jsonc")

    def done(d, result):
        try:
            file = d.save_finish(result)
        except GLib.Error:
            return
        cfg.export_config(window.model, file.get_path())
        _notify(window, f"Exported to {file.get_path()}")

    dialog.save(window, None, done)


def _import_config(window):
    dialog = Gtk.FileDialog()

    def done(d, result):
        try:
            file = d.open_finish(result)
        except GLib.Error:
            return
        try:
            raw = cfg.read_model_file(file.get_path())
        except Exception as e:
            _notify(window, f"Import failed: {e}")
            return
        window.model = _normalize_model(raw)
        _reload_widgets(window)
        _refresh_preview(window)
        _notify(window, f"Imported {file.get_path()}")

    dialog.open(window, None, done)


# ── Preset gallery ───────────────────────────────────────────────────────────

# Pre-captured preset screenshots (one <name>.jpg per preset), generated by
# tools/capture-preset-previews.sh inside a clean VM so no real system info ships.
PREVIEW_IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images", "preset_previews")
_THUMB_W, _THUMB_H = 320, 200


def _preset_gallery_tab(window):
    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    outer.set_margin_start(10)
    outer.set_margin_end(10)
    outer.set_margin_top(6)

    header = _row()
    intro = _label(
        "<b>Preset gallery</b> — a real screenshot of each preset. Click <b>Load</b> to pull one "
        "into the editor; nothing is written until you Apply.", markup=True)
    intro.set_wrap(True)
    intro.set_hexpand(True)
    header.append(intro)
    btn_refresh = Gtk.Button(label="Refresh")
    btn_refresh.set_tooltip_text("Re-scan the preview-image folder after capturing new screenshots")
    btn_refresh.connect("clicked", lambda _w: _populate_gallery(window))
    header.append(btn_refresh)
    outer.append(header)

    # All / Normal / Small logo filter (grouped toggles, like the alacritty-tweak-tool tone filter).
    window.gallery_filter = "all"
    filter_row = _row()
    filter_row.append(_label("Logo:"))
    btn_all = Gtk.ToggleButton(label="All")
    btn_all.set_active(True)
    btn_normal = Gtk.ToggleButton(label="Normal")
    btn_normal.set_group(btn_all)
    btn_small = Gtk.ToggleButton(label="Small")
    btn_small.set_group(btn_all)

    def _on_filter(_b):
        window.gallery_filter = (
            "small" if btn_small.get_active() else "normal" if btn_normal.get_active() else "all")
        window.gallery_flow.invalidate_filter()

    for b in (btn_all, btn_normal, btn_small):
        b.connect("toggled", _on_filter)
        filter_row.append(b)
    outer.append(filter_row)

    window.gallery_status = _label("", css_class="info-label")
    outer.append(window.gallery_status)

    window.gallery_flow = Gtk.FlowBox()
    window.gallery_flow.set_selection_mode(Gtk.SelectionMode.NONE)
    window.gallery_flow.set_max_children_per_line(4)
    window.gallery_flow.set_column_spacing(8)
    window.gallery_flow.set_row_spacing(8)
    window.gallery_flow.set_homogeneous(True)
    window.gallery_flow.set_filter_func(lambda fbchild: _gallery_filter_match(window, fbchild))
    outer.append(_scrolled(window.gallery_flow))

    _populate_gallery(window)
    return outer


def _gallery_filter_match(window, fbchild):
    flt = getattr(window, "gallery_filter", "all")
    if flt == "all":
        return True
    is_small = getattr(fbchild.get_child(), "ftt_small", False)
    return is_small if flt == "small" else not is_small


def _preset_is_small(name):
    """True if the preset renders fastfetch's small (compact) logo."""
    import json

    path = cfg.resolve_preset_path(name)
    if not path:
        return False
    try:
        with open(path, encoding="utf-8") as f:
            logo = (json.loads(cfg.strip_jsonc(f.read())) or {}).get("logo")
    except Exception:
        return False
    return isinstance(logo, dict) and logo.get("type") == "small"


def _populate_gallery(window):
    flow = window.gallery_flow
    while (child := flow.get_first_child()) is not None:
        flow.remove(child)

    presets = catalog.presets() or []
    have = small = 0
    for name in presets:
        img = os.path.join(PREVIEW_IMG_DIR, f"{name}.png")
        if os.path.isfile(img):
            have += 1
        cell = _thumb_cell(window, name, img if os.path.isfile(img) else None)
        cell.ftt_small = _preset_is_small(name)
        small += cell.ftt_small
        flow.append(cell)
    flow.invalidate_filter()

    status = window.gallery_status
    if not presets:
        status.set_text("No presets found.")
    elif have == 0:
        status.set_markup(
            "No preview images yet — run <tt>tools/capture-preset-previews.sh</tt> in a VM, "
            "drop the <tt>.png</tt>s into <tt>images/preset_previews/</tt>, then Refresh.")
    else:
        status.set_text(
            f"{have} of {len(presets)} presets have a preview image  ·  "
            f"{len(presets) - small} normal, {small} small logo")


def _thumb_cell(window, name, img_path):
    cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    cell.add_css_class("card")
    cell.set_halign(Gtk.Align.CENTER)

    # Fixed-size clipped frame: guarantees every cell has the same footprint so
    # images can never overflow into a neighbouring cell.
    frame = Gtk.Box()
    frame.set_size_request(_THUMB_W, _THUMB_H)
    frame.set_overflow(Gtk.Overflow.HIDDEN)
    frame.set_halign(Gtk.Align.CENTER)
    frame.set_valign(Gtk.Align.CENTER)

    picture = None
    if img_path:
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(img_path, _THUMB_W, _THUMB_H)
            picture = Gtk.Picture.new_for_paintable(Gdk.Texture.new_for_pixbuf(pixbuf))
            picture.set_content_fit(Gtk.ContentFit.CONTAIN)
            picture.set_can_shrink(True)
            picture.set_hexpand(True)
            picture.set_vexpand(True)
        except Exception as e:
            log.log_warn(f"Could not load preview {img_path}: {e}")
    if picture is not None:
        frame.append(picture)
    else:
        ph = _label("no preview yet", css_class="info-label")
        ph.set_halign(Gtk.Align.CENTER)
        ph.set_valign(Gtk.Align.CENTER)
        ph.set_hexpand(True)
        frame.append(ph)
    cell.append(frame)

    footer = _row()
    footer.append(_label(name, css_class="info-label"))
    spacer = Gtk.Box()
    spacer.set_hexpand(True)
    footer.append(spacer)
    btn = Gtk.Button(label="Load")
    btn.connect("clicked", lambda _w, n=name: _load_preset_named(window, n))
    footer.append(btn)
    cell.append(footer)
    return cell


def _load_kiro(window):
    import json

    with open(cfg.KIRO_DEFAULT, "r", encoding="utf-8") as f:
        window.model = _normalize_model(json.loads(cfg.strip_jsonc(f.read())))
    _reload_widgets(window)
    _refresh_preview(window)
    _notify(window, "Loaded Kiro default")


def _restore(window):
    if cfg.restore_backup():
        _reload(window)
        _notify(window, "Restored from backup")
    else:
        _notify(window, "No backup to restore")


def _raw_reload(window):
    window.raw_view.get_buffer().set_text(cfg.read_config_text())
    _notify(window, "Raw view reloaded from file")


def _raw_save(window):
    buf = window.raw_view.get_buffer()
    text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
    ok, err = cfg.validate_text(text)
    if not ok:
        _notify(window, f"Invalid JSON — not saved: {err}")
        return
    cfg.write_config_text(text)
    window.model = _normalize_model(cfg.read_config())
    _reload_widgets(window)
    _refresh_preview(window)
    _notify(window, "Raw config saved")


# ── Live preview ─────────────────────────────────────────────────────────────


_PREVIEW_BG = "#343844"


def _apply_vte_theme(vte):
    """Paint the VTE preview a fixed background colour (matching the app surface)."""
    def _set(_w=None):
        sc = vte.get_style_context()
        ok_fg, fg = sc.lookup_color("window_fg_color")
        if not ok_fg:
            fg = Gdk.RGBA()
            fg.parse("#ffffff")
        bg = Gdk.RGBA()
        bg.parse(_PREVIEW_BG)
        vte.set_color_foreground(fg)
        vte.set_color_background(bg)
        if hasattr(vte, "set_clear_background"):
            vte.set_clear_background(True)  # paint the solid background

    _set()
    vte.connect("realize", _set)  # re-apply once theme foreground resolves


def _preview_pane(window):
    window.show_public_ip = False
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    box.set_size_request(420, -1)

    header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    header.append(_label("<b>Live preview</b>", markup=True))
    spacer = Gtk.Box()
    spacer.set_hexpand(True)
    header.append(spacer)
    window.public_ip_btn = Gtk.Button(label="Show public IP")
    window.public_ip_btn.add_css_class("flat")
    window.public_ip_btn.set_tooltip_text(
        "Public IP is hidden in the preview by default — reveal it only when you are not "
        "sharing your screen or recording."
    )
    window.public_ip_btn.set_visible(False)
    window.public_ip_btn.connect("clicked", lambda _w: _toggle_public_ip(window))
    header.append(window.public_ip_btn)
    box.append(header)

    if _VTE_AVAILABLE:
        try:
            window.vte = Vte.Terminal()
            window.vte.set_vexpand(True)
            window.vte.set_hexpand(True)
            _apply_vte_theme(window.vte)
            box.append(window.vte)
        except Exception as e:
            log.log_warn(f"VTE init failed: {e}")
            window.vte = None
            box.append(_preview_fallback(window))
    else:
        window.vte = None
        box.append(_preview_fallback(window))

    box.set_margin_start(6)
    box.set_margin_end(6)
    box.set_margin_top(6)
    box.set_margin_bottom(6)
    return box


def _preview_fallback(window):
    inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    inner.set_vexpand(True)
    inner.append(_label("vte4 not installed — preview disabled.", css_class="info-label"))
    btn = Gtk.Button(label="Preview in terminal")
    btn.connect("clicked", lambda _w: _preview_external(window))
    inner.append(btn)
    return inner


def _guarded_preview_model(window):
    """Return a preview copy with publicip modules masked unless the user opted in."""
    model = window.model
    if getattr(window, "show_public_ip", False):
        return model
    mods = model.get("modules", [])
    if not any(cfg.module_type(m) == "publicip" for m in mods):
        return model
    masked = []
    for m in mods:
        if cfg.module_type(m) == "publicip":
            key = m.get("key", "Public IP") if isinstance(m, dict) else "Public IP"
            masked.append({"type": "custom", "key": key,
                           "format": "(hidden — click ‘Show public IP’)"})
        else:
            masked.append(m)
    guarded = dict(model)
    guarded["modules"] = masked
    return guarded


def _update_public_ip_btn(window):
    btn = getattr(window, "public_ip_btn", None)
    if btn is None:
        return
    has_publicip = any(cfg.module_type(m) == "publicip" for m in window.model.get("modules", []))
    btn.set_visible(has_publicip)
    btn.set_label("Hide public IP" if window.show_public_ip else "Show public IP")


def _toggle_public_ip(window):
    if window.show_public_ip:
        window.show_public_ip = False
        _refresh_preview(window)
        return
    dialog = Gtk.AlertDialog()
    dialog.set_modal(True)
    dialog.set_message("Reveal your public IP in the preview?")
    dialog.set_detail(
        "Your real public IP address will be fetched and shown in the live preview. "
        "Do not do this while sharing your screen or recording — it would expose your IP. "
        "It is hidden again the next time you open the tool."
    )
    dialog.set_buttons(["Cancel", "Reveal public IP"])
    dialog.set_cancel_button(0)
    dialog.set_default_button(0)
    dialog.choose(window, None, lambda d, res, _u=None: _on_public_ip_choice(window, d, res))


def _on_public_ip_choice(window, dialog, result):
    try:
        choice = dialog.choose_finish(result)
    except GLib.Error:
        return
    if choice == 1:
        window.show_public_ip = True
        _refresh_preview(window)


def _write_preview_file(window):
    os.makedirs(os.path.dirname(PREVIEW_PATH), exist_ok=True)
    with open(PREVIEW_PATH, "w", encoding="utf-8") as f:
        f.write(cfg.serialize(_guarded_preview_model(window)))


def _refresh_preview(window):
    if not cfg.fastfetch_installed():
        _notify(window, "fastfetch not installed — preview unavailable")
        return
    _update_public_ip_btn(window)
    _write_preview_file(window)
    vte = getattr(window, "vte", None)
    if vte is None:
        return
    # --pipe false forces fastfetch to emit colours/decorations; without it the VTE
    # render comes out monochrome and doesn't match the captured gallery thumbnails.
    command = f"fastfetch -c {PREVIEW_PATH} --pipe false; echo; echo '[preview]'"
    try:
        vte.reset(True, True)
        vte.spawn_async(
            Vte.PtyFlags.DEFAULT,
            os.path.expanduser("~"),
            ["/bin/bash", "-c", command],
            None,
            GLib.SpawnFlags.DEFAULT,
            None,
            None,
            -1,
            None,
            None,
        )
    except Exception as e:
        log.log_warn(f"Preview spawn failed: {e}")


def _preview_external(window):
    if not cfg.fastfetch_installed():
        _notify(window, "fastfetch not installed")
        return
    _write_preview_file(window)
    install.launch_in_terminal(["fastfetch", "-c", PREVIEW_PATH])


# ── Apply / reload ───────────────────────────────────────────────────────────


def _apply(window):
    model = window.model
    if getattr(window, "hide_public_ip", True):
        model = cfg.without_public_ip(model)
    cfg.write_config(model)
    _refresh_preview(window)
    _refresh_current_logo_label(window)
    if model is not window.model:
        _notify(window, "Configuration applied (public IP module omitted)")
    else:
        _notify(window, "Configuration applied")


def _reload(window):
    window.model = _normalize_model(cfg.read_config())
    _reload_widgets(window)
    _refresh_preview(window)
    _refresh_current_logo_label(window)
    _notify(window, "Reloaded from config.jsonc")


def _reload_widgets(window):
    _rebuild_modules_list(window)
    _refresh_add_module_combo(window)
    _clear_box(window.module_options_box)
    if hasattr(window, "separator_entry"):
        window.separator_entry.set_text(str((window.model.get("display") or {}).get("separator", ": ")))
    if hasattr(window, "logo_type"):
        current_type = _ui_logo_type(window.model.get("logo"))
        window._suppress_source_sync = True
        if current_type in _LOGO_TYPES:
            window.logo_type.set_selected(_LOGO_TYPES.index(current_type))
        window._suppress_source_sync = False
        _apply_logo_type_state(window)
    if hasattr(window, "logo_inline_view"):
        logo_d = window.model.get("logo") or {}
        inline_text = str(logo_d.get("source", "")) if str(logo_d.get("type", "")) in _INLINE_LOGO_TYPES else ""
        window.logo_inline_view.get_buffer().set_text(inline_text)
    if hasattr(window, "logo_source"):
        logos = catalog.logos() or ["(none)"]
        src = str((window.model.get("logo") or {}).get("source", ""))
        if src in logos:
            window.logo_source.set_selected(logos.index(src))
    if hasattr(window, "logo_bundled") and window.logo_bundled_names:
        cur_base = os.path.basename(str((window.model.get("logo") or {}).get("source", "")))
        if cur_base in window.logo_bundled_names:
            window.logo_bundled.set_selected(window.logo_bundled_names.index(cur_base))
    if hasattr(window, "kiroart_dd") and window.kiroart_names:
        art_base = os.path.basename(str((window.model.get("logo") or {}).get("source", "")))
        if art_base in window.kiroart_names:
            window.kiroart_dd.set_selected(window.kiroart_names.index(art_base))
    if hasattr(window, "logo_position"):
        cur_pos = str((window.model.get("logo") or {}).get("position", "left"))
        if cur_pos in _LOGO_POSITIONS:
            window.logo_position.set_selected(_LOGO_POSITIONS.index(cur_pos))
    for path, set_value in getattr(window, "color_combos", {}).items():
        set_value(_get_path(window, path))
    for path, combo, vals in getattr(window, "enum_combos", []):
        cur = _get_path(window, path)
        combo.set_selected(vals.index(cur) if cur in vals else 0)
    for path, switch in getattr(window, "setting_switches", []):
        switch.set_active(bool(_get_path(window, path)))
    for path, spin in getattr(window, "setting_spins", []):
        spin.set_value(float(_get_path(window, path) or 0))
    if hasattr(window, "raw_view"):
        window.raw_view.get_buffer().set_text(cfg.read_config_text() or cfg.serialize(window.model))


# ── Value coercion ───────────────────────────────────────────────────────────


def _value_to_text(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _text_to_value(text):
    text = text.strip()
    if text.lower() in ("true", "false"):
        return text.lower() == "true"
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def _get_path(window, path):
    node = window.model
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
        if node is None:
            return None
    return node


def _set_path(window, path, value, drop_zero=False):
    if value is None or (drop_zero and value == 0):
        _del_path(window, path)
        return
    node = window.model
    for key in path[:-1]:
        node = node.setdefault(key, {})
    node[path[-1]] = value


def _del_path(window, path):
    node = window.model
    for key in path[:-1]:
        node = node.get(key) if isinstance(node, dict) else None
        if node is None:
            return
    if isinstance(node, dict):
        node.pop(path[-1], None)


def _clear_box(box):
    child = box.get_first_child()
    while child:
        box.remove(child)
        child = box.get_first_child()
