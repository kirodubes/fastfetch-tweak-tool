"""Curated per-module option schema for the Modules tab (pure data, no GTK).

Each entry is ``(key, kind, label)`` where ``kind`` is one of ``bool`` / ``text`` /
``color`` / ``icon`` (a free entry plus a searchable Nerd Font icon dropdown).
Object-valued keys (e.g. ``percent``, ``separator`` sub-keys) are left to
the Advanced raw-key editor on purpose — they need a nested editor this schema avoids.
Keys verified against ``fastfetch --gen-config-full``.
"""

# Keys valid on (nearly) every module — rendered first, for all module types.
UNIVERSAL = [
    ("key", "text", "Key label"),
    ("keyIcon", "icon", "Key icon"),
    ("keyColor", "color", "Key color"),
    ("keyWidth", "text", "Key width (0 = off)"),
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
    "command": [
        ("text", "text", "Command text"),
        ("shell", "text", "Shell"),
        ("param", "text", "Parameter"),
        ("useStdErr", "bool", "Use stderr instead of stdout"),
        ("parallel", "bool", "Run in parallel"),
        ("splitLines", "bool", "Split output into lines"),
    ],
    "physicaldisk": [
        ("namePrefix", "text", "Name prefix filter"),
        ("hideVirtual", "bool", "Hide virtual disks"),
        ("hideUnused", "bool", "Hide unused disks"),
        ("temp", "bool", "Show temperature"),
    ],
    "netio": [
        ("namePrefix", "text", "Interface name prefix"),
        ("defaultRouteOnly", "bool", "Default route only"),
        ("detectTotal", "bool", "Detect total I/O"),
        ("waitTime", "text", "Sample wait time (ms)"),
    ],
    "weather": [
        ("location", "text", "Location"),
        ("timeout", "text", "Timeout (ms)"),
        ("outputFormat", "text", "wttr.in format string"),
    ],
    "publicip": [
        ("url", "text", "Custom URL"),
        ("timeout", "text", "Timeout (ms)"),
        ("ipv6", "bool", "Use IPv6"),
    ],
    "loadavg": [
        ("ndigits", "text", "Decimal places"),
        ("compact", "bool", "Compact (one line)"),
    ],
    "display": [
        ("compactType", "text", "Compact type"),
        ("preciseRefreshRate", "bool", "Precise refresh rate"),
        ("order", "text", "Sort order"),
    ],
    "diskio": [
        ("namePrefix", "text", "Device name prefix"),
        ("detectTotal", "bool", "Detect total I/O"),
        ("waitTime", "text", "Sample wait time (ms)"),
    ],
    "cpuusage": [
        ("separate", "bool", "Per-core usage"),
        ("waitTime", "text", "Sample wait time (ms)"),
    ],
    "codec": [
        ("splitGPU", "bool", "Split per GPU"),
        ("useVulkan", "bool", "Use Vulkan"),
        ("showType", "text", "Show type"),
    ],
    "brightness": [
        ("ddcciSleep", "text", "DDC/CI sleep (ms)"),
        ("compact", "bool", "Compact"),
    ],
    "users": [
        ("compact", "bool", "Compact (one line)"),
        ("myselfOnly", "bool", "Current user only"),
    ],
    "sound": [
        ("soundType", "text", "Sound device type"),
    ],
    "packages": [
        ("combined", "bool", "Combine duplicate managers"),
    ],
    "bluetooth": [
        ("showDisconnected", "bool", "Show disconnected devices"),
    ],
}


def curated_keys(module_type):
    """Return the set of keys this schema renders as dedicated widgets for a type."""
    keys = {key for key, _kind, _label in UNIVERSAL}
    keys.update(key for key, _kind, _label in MODULE_OPTIONS.get(module_type, []))
    return keys
