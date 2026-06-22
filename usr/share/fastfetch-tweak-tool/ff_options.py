"""Curated per-module option schema for the Modules tab (pure data, no GTK).

Each entry is ``(key, kind, label)`` where ``kind`` is one of ``bool`` / ``text`` /
``color``. Object-valued keys (e.g. ``percent``, ``separator`` sub-keys) are left to
the Advanced raw-key editor on purpose — they need a nested editor this schema avoids.
Keys verified against ``fastfetch --gen-config-full``.
"""

# Keys valid on (nearly) every module — rendered first, for all module types.
UNIVERSAL = [
    ("key", "text", "Key label"),
    ("keyIcon", "text", "Key icon"),
    ("keyColor", "color", "Key color"),
    ("format", "text", "Format"),
    ("outputColor", "color", "Output color"),
]

# Per-type curated scalar options. Modules not listed here fall through to
# UNIVERSAL + the Advanced editor.
MODULE_OPTIONS = {
    "cpu": [
        ("temp", "bool", "Show temperature"),
        ("showPeCoreCount", "bool", "Show P/E core count"),
        ("tempSensor", "text", "Temp sensor"),
    ],
    "gpu": [
        ("temp", "bool", "Show temperature"),
        ("driverSpecific", "bool", "Driver-specific info"),
        ("hideType", "text", "Hide type (integrated/discrete)"),
    ],
    "disk": [
        ("showRegular", "bool", "Show regular volumes"),
        ("showExternal", "bool", "Show external volumes"),
        ("showHidden", "bool", "Show hidden volumes"),
        ("showReadOnly", "bool", "Show read-only volumes"),
        ("useAvailable", "bool", "Use available (not free) space"),
        ("folders", "text", "Folders (':'-separated)"),
    ],
    "battery": [
        ("temp", "bool", "Show temperature"),
    ],
    "localip": [
        ("showIpv4", "bool", "Show IPv4"),
        ("showIpv6", "bool", "Show IPv6"),
        ("showMac", "bool", "Show MAC"),
        ("compact", "bool", "Compact (one line)"),
        ("defaultRouteOnly", "bool", "Default route only"),
        ("namePrefix", "text", "Interface name prefix"),
    ],
    "swap": [
        ("separate", "bool", "Separate swap from memory"),
    ],
    "wm": [
        ("detectPlugin", "bool", "Detect plugins"),
    ],
    "title": [
        ("fqdn", "bool", "Use fully-qualified hostname"),
    ],
}


def curated_keys(module_type):
    """Return the set of keys this schema renders as dedicated widgets for a type."""
    keys = {key for key, _kind, _label in UNIVERSAL}
    keys.update(key for key, _kind, _label in MODULE_OPTIONS.get(module_type, []))
    return keys
