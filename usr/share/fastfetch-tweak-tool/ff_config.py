"""JSONC read/write engine, structured model, backup, and prefs for fastfetch-tweak-tool.

This tool OWNS config.jsonc: it parses the file into a plain Python model, lets the GUI
mutate it, and writes back valid indented JSON. Hand-written comments are not preserved
on write (a backup is made first, and the Raw tab is the escape hatch).
"""

import json
import os
import re
import shutil
import subprocess

import log

CONFIG_PATH = os.path.expanduser("~/.config/fastfetch/config.jsonc")
BACKUP_PATH = os.path.expanduser("~/.config/fastfetch/config.jsonc.ftt-bak")
PREFS_PATH = os.path.expanduser("~/.config/fastfetch-tweak-tool/prefs.json")

# User presets live in a real fastfetch data path, so they also show up in
# `fastfetch --list-presets` and are usable directly via `fastfetch -c <name>`.
USER_PRESET_DIR = os.path.expanduser("~/.local/share/fastfetch/presets")
_PRESET_SEARCH_DIRS = [
    USER_PRESET_DIR,
    os.path.expanduser("~/.config/fastfetch/presets"),
    "/usr/local/share/fastfetch/presets",
    "/usr/share/fastfetch/presets",
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KIRO_DEFAULT = os.path.join(BASE_DIR, "data", "fastfetch", "config.jsonc")

SCHEMA_URL = "https://github.com/fastfetch-cli/fastfetch/raw/dev/doc/json_schema.json"


# ── JSONC parsing ────────────────────────────────────────────────────────────


def strip_jsonc(text):
    """Return JSON text with // and /* */ comments removed, respecting string literals."""
    out = []
    i = 0
    n = len(text)
    in_string = False
    escaped = False
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    cleaned = "".join(out)
    cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)
    return cleaned


def _empty_model():
    return {"$schema": SCHEMA_URL, "logo": {}, "display": {}, "modules": []}


def read_config():
    """Read config.jsonc into a model dict, or a sensible empty model if missing/invalid."""
    if not os.path.isfile(CONFIG_PATH):
        log.log_warn("No fastfetch config found — using empty model")
        return _empty_model()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.loads(strip_jsonc(f.read()))
        if not isinstance(data, dict):
            raise ValueError("config root is not an object")
        data.setdefault("$schema", SCHEMA_URL)
        data.setdefault("logo", {})
        data.setdefault("display", {})
        data.setdefault("modules", [])
        return data
    except Exception as e:
        log.log_error(f"Failed to parse fastfetch config: {e}")
        return _empty_model()


def read_config_text():
    """Return the raw config.jsonc text, or '' if it does not exist."""
    if not os.path.isfile(CONFIG_PATH):
        return ""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return f.read()


def serialize(model):
    """Return a model as a pretty-printed JSON (valid JSONC) string."""
    return json.dumps(model, indent=2, ensure_ascii=False) + "\n"


# ── Backup / write / restore ─────────────────────────────────────────────────


def backup_config():
    """Copy the current config to config.jsonc.ftt-bak before any write."""
    if os.path.isfile(CONFIG_PATH):
        shutil.copy2(CONFIG_PATH, BACKUP_PATH)
        log.log_info(f"Backup created: {BACKUP_PATH}")


def write_config(model):
    """Back up, then write the model back to config.jsonc as indented JSON."""
    backup_config()
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(serialize(model))
    log.log_success(f"Config written: {CONFIG_PATH}")


def write_config_text(text):
    """Back up, then write raw text to config.jsonc (used by the Raw tab)."""
    backup_config()
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(text)
    log.log_success(f"Config written (raw): {CONFIG_PATH}")


def validate_text(text):
    """Return (ok, error_message) for raw JSONC text without writing it."""
    try:
        json.loads(strip_jsonc(text))
        return True, ""
    except Exception as e:
        return False, str(e)


def restore_backup():
    """Restore config from config.jsonc.ftt-bak; return True if a backup existed."""
    if not os.path.isfile(BACKUP_PATH):
        log.log_warn("No backup found — nothing to restore")
        return False
    shutil.copy2(BACKUP_PATH, CONFIG_PATH)
    log.log_success(f"Restored from backup: {BACKUP_PATH}")
    return True


def reset_to_kiro_default():
    """Copy the bundled Kiro default over the user's config; return True on success."""
    if not os.path.isfile(KIRO_DEFAULT):
        log.log_error(f"Bundled default not found: {KIRO_DEFAULT}")
        return False
    backup_config()
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    shutil.copy2(KIRO_DEFAULT, CONFIG_PATH)
    log.log_success("Kiro default applied")
    return True


# ── Module model helpers ─────────────────────────────────────────────────────


def module_type(entry):
    """Return the module type name for a string or object module entry."""
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        return str(entry.get("type", ""))
    return ""


def module_options(entry):
    """Return the per-module option dict (object entries only; empty for strings)."""
    if isinstance(entry, dict):
        return {k: v for k, v in entry.items() if k != "type"}
    return {}


def without_public_ip(model):
    """Return a copy of the model with all publicip modules omitted (privacy)."""
    mods = model.get("modules", [])
    if not any(module_type(m) == "publicip" for m in mods):
        return model
    stripped = dict(model)
    stripped["modules"] = [m for m in mods if module_type(m) != "publicip"]
    return stripped


# ── fastfetch CLI catalogs ───────────────────────────────────────────────────


def fastfetch_installed():
    """Return True if the fastfetch binary is on PATH."""
    return shutil.which("fastfetch") is not None


def _run_fastfetch(args):
    try:
        result = subprocess.run(
            ["fastfetch", *args], capture_output=True, text=True, timeout=10
        )
        return result.stdout
    except Exception as e:
        log.debug_print(f"fastfetch {args} failed: {e}")
        return ""


def _natural_key(name):
    """Sort key that orders embedded digit runs numerically (examples/2 before examples/10)."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def list_modules():
    """Return a sorted list of available lowercase module type names from fastfetch."""
    names = []
    for line in _run_fastfetch(["--list-modules", "autocompletion"]).splitlines():
        name = line.split(":", 1)[0].strip()
        if name:
            names.append(name.lower())
    if not names:
        for line in _run_fastfetch(["--list-modules"]).splitlines():
            m = re.match(r"\s*\d+\)\s*([A-Za-z]+)", line)
            if m:
                names.append(m.group(1).lower())
    return sorted(set(names), key=_natural_key)


def list_logos():
    """Return a sorted list of built-in logo names from fastfetch (names may contain spaces)."""
    names = []
    for line in _run_fastfetch(["--list-logos", "autocompletion"]).splitlines():
        name = line.strip()
        if name:
            names.append(name)
    if not names:
        for raw in _run_fastfetch(["--list-logos"]).splitlines():
            names.extend(re.findall(r'"([^"]+)"', raw))
    return sorted(set(names), key=_natural_key)


def list_presets():
    """Return a sorted list of available preset names (e.g. 'neofetch', 'examples/13')."""
    names = []
    for line in _run_fastfetch(["--list-presets", "autocompletion"]).splitlines():
        name = line.strip()
        if name.endswith(".jsonc"):
            names.append(name[: -len(".jsonc")])
    return sorted(set(names), key=_natural_key)


# ── User presets / import / export ───────────────────────────────────────────


def resolve_preset_path(name):
    """Return the first existing <dir>/<name>.jsonc across the preset search dirs, or ''."""
    for directory in _PRESET_SEARCH_DIRS:
        path = os.path.join(directory, f"{name}.jsonc")
        if os.path.isfile(path):
            return path
    return ""


def sanitize_preset_name(name):
    """Return a filesystem-safe preset name (no path separators), or '' if empty."""
    safe = re.sub(r"[^A-Za-z0-9._-]", "-", name.strip()).strip("-.")
    return safe


def save_user_preset(name, model):
    """Write the model as a user preset; return the sanitized name, or '' if name is empty."""
    safe = sanitize_preset_name(name)
    if not safe:
        return ""
    os.makedirs(USER_PRESET_DIR, exist_ok=True)
    with open(os.path.join(USER_PRESET_DIR, f"{safe}.jsonc"), "w", encoding="utf-8") as f:
        f.write(serialize(model))
    log.log_success(f"Saved user preset: {safe}")
    return safe


def export_config(model, path):
    """Write the model to an arbitrary path (Export)."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(serialize(model))
    log.log_success(f"Exported config to {path}")


def read_model_file(path):
    """Read a .jsonc file into a model dict (Import); raises on invalid JSON."""
    with open(path, "r", encoding="utf-8") as f:
        return json.loads(strip_jsonc(f.read()))


# ── Preferences ──────────────────────────────────────────────────────────────


def load_prefs():
    """Return UI preferences dict from prefs.json, or empty dict if missing/invalid."""
    if not os.path.isfile(PREFS_PATH):
        return {}
    try:
        with open(PREFS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_prefs(prefs):
    """Write UI preferences dict to prefs.json."""
    os.makedirs(os.path.dirname(PREFS_PATH), exist_ok=True)
    with open(PREFS_PATH, "w", encoding="utf-8") as f:
        json.dump(prefs, f, indent=2)
