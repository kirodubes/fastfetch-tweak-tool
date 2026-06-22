#!/bin/bash
set -euo pipefail

#####################################################################
# Author : Erik Dubois
# Website : https://kiroproject.be
# DO NOT JUST RUN THIS. EXAMINE AND JUDGE. RUN AT YOUR OWN RISK.
#
# Purpose:
#   Capture a real screenshot of every fastfetch preset and save one
#   image per preset to an output directory. For each preset under
#   /usr/share/fastfetch/presets (including the examples/ subdir) it
#   strips privacy-sensitive modules (public IP, local IP, DNS, wifi,
#   weather/location), opens an alacritty window running
#   `fastfetch -c <sanitized-preset>`, grabs that window with maim, and
#   trims the borders with imagemagick to <name>.jpg.
#
# Why:
#   The Preset Gallery tab in fastfetch-tweak-tool shows these images so
#   users pick a preset by look, not by name. fastfetch renders REAL
#   system info, so several presets embed the machine's public IP and
#   geolocation — those modules are scrubbed here before rendering so the
#   committed screenshots never leak network/location data, even when run
#   in a VM (NAT shares the host's real WAN IP).
#####################################################################

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# ── Colors ───────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
    RED="$(tput setaf 1)"; GREEN="$(tput setaf 2)"; YELLOW="$(tput setaf 3)"
    BLUE="$(tput setaf 4)"; CYAN="$(tput setaf 6)"; RESET="$(tput sgr0)"
else
    RED=""; GREEN=""; YELLOW=""; BLUE=""; CYAN=""; RESET=""
fi

# ── Logging ──────────────────────────────────────────────────────────────────
log_section() { echo "${GREEN}############ $* ############${RESET}"; }
log_info()    { echo "${BLUE}############ $* ############${RESET}"; }
log_warn()    { echo "${YELLOW}############ $* ############${RESET}"; }
log_error()   { echo "${RED}############ $* ############${RESET}"; }
log_success() { echo "${GREEN}############ $* ############${RESET}"; }

# ── Error handling ───────────────────────────────────────────────────────────
on_error() {
    echo "${RED}ERROR on line $1: $2${RESET}"
    sleep 10
}
trap 'on_error "$LINENO" "$BASH_COMMAND"' ERR

# ── Config ───────────────────────────────────────────────────────────────────
PRESET_DIR="/usr/share/fastfetch/presets"
OUT_DIR="${1:-$SCRIPT_DIR/preset_previews}"
WIN_CLASS="fftcap"
COLS=100
LINES=32
RENDER_WAIT=2.0   # seconds to let fastfetch finish drawing before the grab
HOLD=4            # seconds the alacritty window stays up
# Module types stripped from every preset before rendering (privacy).
DENY="publicip,localip,dns,wifi,weather"
# Terminal background colour keyed out to transparency in the final PNG. Must
# match alacritty's configured background (sample with: magick shot.png -format %c histogram:info:).
BG_COLOR="#111217"
WORK="$(mktemp -d)"
SCRUB="$WORK/scrub.py"

# ── Functions ────────────────────────────────────────────────────────────────
check_deps() {
    local missing=()
    for t in fastfetch alacritty maim xdotool magick python3; do
        command -v "$t" >/dev/null 2>&1 || missing+=("$t")
    done
    if ((${#missing[@]})); then
        log_error "Missing tools: ${missing[*]}"
        exit 1
    fi
    if [[ -z "${DISPLAY:-}" ]]; then
        log_error "No DISPLAY set — run this inside the VM's graphical session (or export DISPLAY=:0)"
        exit 1
    fi
}

# Write the JSONC scrubber. It strips // and /* */ comments (string-aware, so
# https:// survives) plus trailing commas, then drops any module whose type is
# in DENY, and prints clean JSON.
write_scrubber() {
    cat > "$SCRUB" <<'PY'
import json, sys

def strip_jsonc(src):
    out, i, n = [], 0, len(src)
    in_str = esc = False
    while i < n:
        c = src[i]
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True; out.append(c); i += 1; continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            i += 2
            while i < n and src[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            i += 2
            while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c); i += 1
    text = "".join(out)
    # drop trailing commas
    res, i, n = [], 0, len(text)
    in_str = esc = False
    while i < n:
        c = text[i]
        if in_str:
            res.append(c)
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == '"': in_str = False
            i += 1; continue
        if c == '"':
            in_str = True; res.append(c); i += 1; continue
        if c == ",":
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            if j < n and text[j] in "}]":
                i += 1; continue
        res.append(c); i += 1
    return "".join(res)

deny = set(sys.argv[2].split(","))
model = json.loads(strip_jsonc(open(sys.argv[1], encoding="utf-8").read()))
mods = model.get("modules")
if isinstance(mods, list):
    kept = []
    for m in mods:
        t = m if isinstance(m, str) else (m.get("type") if isinstance(m, dict) else None)
        if t in deny:
            continue
        kept.append(m)
    model["modules"] = kept
json.dump(model, sys.stdout, indent=2)
PY
}

capture_one() {
    local preset="$1" name="$2" win cfg="$WORK/cfg.jsonc"
    if ! python3 "$SCRUB" "$preset" "$DENY" > "$cfg" 2>/dev/null; then
        log_warn "scrub failed for $name — skipped"
        return
    fi
    alacritty --class "$WIN_CLASS" \
        -o "window.dimensions.columns=$COLS" \
        -o "window.dimensions.lines=$LINES" \
        -o "window.padding.x=12" -o "window.padding.y=12" \
        -e bash -c "fastfetch -c '$cfg' --pipe false; sleep $HOLD" &
    local apid=$!
    sleep "$RENDER_WAIT"
    win="$(xdotool search --class "$WIN_CLASS" 2>/dev/null | head -1 || true)"
    if [[ -z "$win" ]]; then
        log_warn "No window for $name — skipped"
        kill "$apid" 2>/dev/null || true
        return
    fi
    mkdir -p "$(dirname "$OUT_DIR/$name")"
    maim -i "$win" -u "$WORK/shot.png"
    xdotool windowkill "$win" 2>/dev/null || kill "$apid" 2>/dev/null || true
    # Trim, then key the terminal background out to transparency.
    magick "$WORK/shot.png" -trim +repage -alpha set -fuzz 12% \
        -transparent "$BG_COLOR" "$OUT_DIR/$name.png"
    log_info "captured $name.png"
}

capture_all() {
    mkdir -p "$OUT_DIR"
    local count=0 preset name
    while IFS= read -r preset; do
        name="${preset#"$PRESET_DIR"/}"
        name="${name%.jsonc}"
        capture_one "$preset" "$name"
        count=$((count + 1))
    done < <(find "$PRESET_DIR" -type f -name '*.jsonc' | sort)
    log_success "captured $count preset image(s) into $OUT_DIR"
}

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
    log_section "fastfetch preset preview capture"
    check_deps
    write_scrubber
    capture_all
    rm -rf "$WORK"
    log_success "$(basename "$0") done"
}

main "$@"
