"""Cached fastfetch catalogs (logos, presets, modules) for the GUI."""

import ff_config

_cache = {}


def logos():
    """Return the cached list of built-in logo names."""
    if "logos" not in _cache:
        _cache["logos"] = ff_config.list_logos()
    return _cache["logos"]


def presets():
    """Return the cached list of preset names."""
    if "presets" not in _cache:
        _cache["presets"] = ff_config.list_presets()
    return _cache["presets"]


def modules():
    """Return the cached list of available module type names."""
    if "modules" not in _cache:
        _cache["modules"] = ff_config.list_modules()
    return _cache["modules"]


def module_descriptions():
    """Return the cached {module name: one-line description} map."""
    if "module_desc" not in _cache:
        _cache["module_desc"] = ff_config.list_module_descriptions()
    return _cache["module_desc"]


def nerd_icons():
    """Return the cached list of (name, glyph) curated Nerd Font icons."""
    if "nerd_icons" not in _cache:
        _cache["nerd_icons"] = ff_config.load_nerd_icons()
    return _cache["nerd_icons"]


def clear():
    """Drop all cached catalogs (call after installing fastfetch)."""
    _cache.clear()
