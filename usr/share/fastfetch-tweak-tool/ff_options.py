"""Curated per-module option schema for the Modules tab (pure data, no GTK).

Each entry is ``(key, kind, label)`` where ``kind`` is one of ``bool`` / ``text`` /
``color`` / ``icon`` (free entry + searchable Nerd Font icon dropdown that *replaces*
the value) / ``icontext`` (same dropdown but *inserts* the glyph at the cursor, for
label/format text). Object-valued keys (e.g. ``percent``, ``separator`` sub-keys) are left to
the Advanced raw-key editor on purpose — they need a nested editor this schema avoids.
Keys verified against ``fastfetch --gen-config-full``.
"""

from ff_i18n import N_

# Keys valid on (nearly) every module — rendered first, for all module types.
UNIVERSAL = [
    ("key", "icontext", N_("Key label")),
    ("keyIcon", "icon", N_("Key icon")),
    ("keyColor", "color", N_("Key color")),
    ("keyWidth", "text", N_("Key width (0 = off)")),
    ("format", "text", N_("Format")),
    ("outputColor", "color", N_("Output color")),
]

# Per-type curated scalar options. Modules not listed here fall through to
# UNIVERSAL + the Advanced editor.
MODULE_OPTIONS = {
    "cpu": [
        ("temp", "bool", N_("Show temperature")),
        ("showPeCoreCount", "bool", N_("Show P/E core count")),
        ("tempSensor", "text", N_("Temp sensor")),
    ],
    "gpu": [
        ("temp", "bool", N_("Show temperature")),
        ("driverSpecific", "bool", N_("Driver-specific info")),
        ("hideType", "text", N_("Hide type (integrated/discrete)")),
    ],
    "disk": [
        ("showRegular", "bool", N_("Show regular volumes")),
        ("showExternal", "bool", N_("Show external volumes")),
        ("showHidden", "bool", N_("Show hidden volumes")),
        ("showReadOnly", "bool", N_("Show read-only volumes")),
        ("useAvailable", "bool", N_("Use available (not free) space")),
        ("folders", "text", N_("Folders (':'-separated)")),
    ],
    "battery": [
        ("temp", "bool", N_("Show temperature")),
    ],
    "localip": [
        ("showIpv4", "bool", N_("Show IPv4")),
        ("showIpv6", "bool", N_("Show IPv6")),
        ("showMac", "bool", N_("Show MAC")),
        ("compact", "bool", N_("Compact (one line)")),
        ("defaultRouteOnly", "bool", N_("Default route only")),
        ("namePrefix", "text", N_("Interface name prefix")),
    ],
    "swap": [
        ("separate", "bool", N_("Separate swap from memory")),
    ],
    "wm": [
        ("detectPlugin", "bool", N_("Detect plugins")),
    ],
    "title": [
        ("fqdn", "bool", N_("Use fully-qualified hostname")),
    ],
    "command": [
        ("text", "text", N_("Command text")),
        ("shell", "text", N_("Shell")),
        ("param", "text", N_("Parameter")),
        ("useStdErr", "bool", N_("Use stderr instead of stdout")),
        ("parallel", "bool", N_("Run in parallel")),
        ("splitLines", "bool", N_("Split output into lines")),
    ],
    "physicaldisk": [
        ("namePrefix", "text", N_("Name prefix filter")),
        ("hideVirtual", "bool", N_("Hide virtual disks")),
        ("hideUnused", "bool", N_("Hide unused disks")),
        ("temp", "bool", N_("Show temperature")),
    ],
    "netio": [
        ("namePrefix", "text", N_("Interface name prefix")),
        ("defaultRouteOnly", "bool", N_("Default route only")),
        ("detectTotal", "bool", N_("Detect total I/O")),
        ("waitTime", "text", N_("Sample wait time (ms)")),
    ],
    "weather": [
        ("location", "text", N_("Location")),
        ("timeout", "text", N_("Timeout (ms)")),
        ("outputFormat", "text", N_("wttr.in format string")),
    ],
    "publicip": [
        ("url", "text", N_("Custom URL")),
        ("timeout", "text", N_("Timeout (ms)")),
        ("ipv6", "bool", N_("Use IPv6")),
    ],
    "loadavg": [
        ("ndigits", "text", N_("Decimal places")),
        ("compact", "bool", N_("Compact (one line)")),
    ],
    "display": [
        ("compactType", "text", N_("Compact type")),
        ("preciseRefreshRate", "bool", N_("Precise refresh rate")),
        ("order", "text", N_("Sort order")),
    ],
    "diskio": [
        ("namePrefix", "text", N_("Device name prefix")),
        ("detectTotal", "bool", N_("Detect total I/O")),
        ("waitTime", "text", N_("Sample wait time (ms)")),
    ],
    "cpuusage": [
        ("separate", "bool", N_("Per-core usage")),
        ("waitTime", "text", N_("Sample wait time (ms)")),
    ],
    "codec": [
        ("splitGPU", "bool", N_("Split per GPU")),
        ("useVulkan", "bool", N_("Use Vulkan")),
        ("showType", "text", N_("Show type")),
    ],
    "brightness": [
        ("ddcciSleep", "text", N_("DDC/CI sleep (ms)")),
        ("compact", "bool", N_("Compact")),
    ],
    "users": [
        ("compact", "bool", N_("Compact (one line)")),
        ("myselfOnly", "bool", N_("Current user only")),
    ],
    "sound": [
        ("soundType", "text", N_("Sound device type")),
    ],
    "packages": [
        ("combined", "bool", N_("Combine duplicate managers")),
    ],
    "bluetooth": [
        ("showDisconnected", "bool", N_("Show disconnected devices")),
    ],
}


def curated_keys(module_type):
    """Return the set of keys this schema renders as dedicated widgets for a type."""
    keys = {key for key, _kind, _label in UNIVERSAL}
    keys.update(key for key, _kind, _label in MODULE_OPTIONS.get(module_type, []))
    return keys
