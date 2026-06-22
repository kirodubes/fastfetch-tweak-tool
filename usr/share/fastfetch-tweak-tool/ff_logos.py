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


def clear():
    """Drop all cached catalogs (call after installing fastfetch)."""
    _cache.clear()
