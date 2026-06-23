#!/usr/bin/env python3
"""Regenerate data/nerd_icons.json — the curated Key-icon dropdown set.

Extracts glyphs from the installed Hack Nerd Font so the codepoints are correct by
construction (never hand-typed). Picks a system-info-relevant subset: explicit
hardware/OS/time/network icons plus the whole `linux-*` distro-logo family and the
common `dev-*` distro logos. Missing explicit names are dropped and reported.

Requires fontTools (dev-time only — NOT a runtime dependency of the app):
    python3 tools/gen-nerd-icons.py
"""
import json
import os
import sys

from fontTools.ttLib import TTFont

FONT_CANDIDATES = [
    "/usr/share/fonts/TTF/HackNerdFontMono-Regular.ttf",
    "/usr/share/fonts/TTF/HackNerdFont-Regular.ttf",
]
OUT = os.path.join(os.path.dirname(__file__), "..", "usr", "share",
                   "fastfetch-tweak-tool", "data", "nerd_icons.json")

EXPLICIT = [
    "oct-cpu", "md-cpu_64_bit", "fa-microchip", "md-chip", "fa-memory", "md-memory",
    "md-harddisk", "md-zip_disk", "md-database", "cod-database",
    "md-expansion_card_variant", "md-video_input_component", "md-monitor", "fa-desktop",
    "md-desktop_classic", "md-desktop_tower", "md-television",
    "md-server", "fa-server", "fa-laptop", "md-laptop", "md-keyboard", "md-mouse", "md-fan",
    "md-usb",
    "fa-network_wired", "md-ethernet", "fa-ethernet", "md-wifi", "fa-wifi", "md-server_network",
    "md-console_network", "md-ip_network", "md-router_network", "md-lan", "md-access_point",
    "fa-linux", "dev-linux", "cod-terminal", "md-console", "md-console_line", "dev-bash", "md-bash",
    "cod-terminal_bash", "dev-powershell", "md-powershell", "fa-terminal", "md-cog", "cod-gear",
    "cod-settings", "fa-gear", "md-application_braces",
    "md-dock_window", "cod-window", "cod-multiple_windows", "md-view_dashboard",
    "fa-clock_o", "md-clock_outline", "md-av_timer", "cod-calendar", "md-calendar", "fa-hourglass_half",
    "md-timer_outline",
    "fa-temperature_high", "md-temperature_celsius", "fae-thermometer", "md-thermometer",
    "md-battery", "fa-battery_full", "iec-power", "md-power_plug", "md-flash",
    "cod-package", "md-package", "md-package_variant", "md-package_variant_closed", "md-update",
    "md-download", "cod-cloud_download",
    "cod-home", "md-home", "cod-folder", "md-folder", "fa-folder", "md-sd", "md-micro_sd",
    "cod-heart", "fa-heart", "cod-star_full", "fa-star", "fa-music", "md-bug", "cod-bug",
    "md-information", "fa-info_circle", "md-cube_outline", "md-shield_check", "fa-shield",
    "dev-python", "dev-rust", "dev-docker", "dev-git", "cod-git_commit", "dev-firefox", "dev-chrome",
    "dev-apple", "dev-windows", "dev-android", "dev-raspberry_pi", "dev-nodejs", "fa-github",
    "dev-vim", "dev-neovim", "dev-go", "dev-react",
]


def main():
    font_path = next((p for p in FONT_CANDIDATES if os.path.isfile(p)), None)
    if not font_path:
        sys.exit("Hack Nerd Font not found — install ttf-hack-nerd")
    name2cp = {g: cp for cp, g in TTFont(font_path).getBestCmap().items()}

    distro = sorted(g for g in name2cp if g.startswith("linux-") and not g.endswith("_inverse"))
    distro += sorted(g for g in name2cp if g.startswith("dev-") and any(d in g for d in (
        "archlinux", "ubuntu", "debian", "fedora", "manjaro", "centos", "rocky", "alma", "mint")))

    icons, seen, missing = [], set(), []
    for g in EXPLICIT + distro:
        if g in seen:
            continue
        seen.add(g)
        cp = name2cp.get(g)
        if cp is None:
            missing.append(g)
            continue
        icons.append([g, chr(cp)])
    icons.sort()

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(icons, f, ensure_ascii=False, indent=0)
        f.write("\n")
    print(f"wrote {len(icons)} icons to {os.path.normpath(OUT)}")
    if missing:
        print(f"dropped {len(missing)} missing names: {missing}")


if __name__ == "__main__":
    main()
