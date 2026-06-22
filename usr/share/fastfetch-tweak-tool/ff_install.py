"""Package install/remove and shell-startup wiring for fastfetch-tweak-tool.

Adapted to stand alone from archlinux-tweak-tool's fastfetch.py (Brad Heffernan,
Erik Dubois, Cameron Percival). Runs as the normal user; package operations are
launched in a terminal so pacman can prompt for the sudo password.
"""

import os
import shutil
import subprocess

import log

PACMAN_CONF = "/etc/pacman.conf"
REPORTING_HEADER = "# reporting tools"

_TERMINALS = [
    ("alacritty", ["-e"]),
    ("kitty", ["-e"]),
    ("foot", ["-e"]),
    ("wezterm", ["-e"]),
    ("xterm", ["-e"]),
    ("konsole", ["-e"]),
    ("gnome-terminal", ["--"]),
    ("xfce4-terminal", ["-x"]),
]


# ── Shell startup files ──────────────────────────────────────────────────────


def shell_rc_path():
    """Return the startup file for the user's login shell, or None if unknown."""
    shell = os.path.basename(os.environ.get("SHELL", ""))
    candidates = {
        "bash": "~/.bashrc",
        "zsh": "~/.zshrc",
        "fish": "~/.config/fish/config.fish",
    }
    rc = candidates.get(shell)
    if rc:
        return os.path.expanduser(rc)
    for fallback in ("~/.bashrc", "~/.zshrc", "~/.config/fish/config.fish"):
        path = os.path.expanduser(fallback)
        if os.path.isfile(path):
            return path
    return None


def startup_state(rc=None):
    """Return (enabled, lolcat) for the fastfetch line in the shell rc."""
    rc = rc or shell_rc_path()
    if not rc or not os.path.isfile(rc):
        return False, False
    with open(rc, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("fastfetch"):
                return True, "lolcat" in stripped
    return False, False


def write_startup(enabled, lolcat, rc=None):
    """Add, update, or comment out the fastfetch line in a '# reporting tools' block."""
    rc = rc or shell_rc_path()
    if not rc:
        log.log_warn("No shell startup file found")
        return False

    new_line = "#fastfetch"
    if enabled:
        new_line = "fastfetch | lolcat" if lolcat else "fastfetch"

    lines = []
    if os.path.isfile(rc):
        with open(rc, "r", encoding="utf-8") as f:
            lines = f.readlines()

    header_idx = next(
        (i for i, ln in enumerate(lines) if REPORTING_HEADER in ln.lower()), -1
    )
    if header_idx == -1:
        if not enabled:
            return True
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append(f"\n{REPORTING_HEADER}\n{new_line}\n")
    else:
        ff_idx = next(
            (
                i
                for i in range(header_idx, len(lines))
                if lines[i].strip().startswith(("fastfetch", "#fastfetch"))
            ),
            -1,
        )
        if ff_idx == -1:
            lines.insert(header_idx + 1, new_line + "\n")
        else:
            lines[ff_idx] = new_line + "\n"

    os.makedirs(os.path.dirname(rc), exist_ok=True)
    with open(rc, "w", encoding="utf-8") as f:
        f.writelines(lines)
    log.log_success(f"Shell startup updated: {rc}")
    return True


# ── Package selection / operations ───────────────────────────────────────────


def _repo_active(name):
    try:
        with open(PACMAN_CONF, "r", encoding="utf-8") as f:
            return any(line.strip() == f"[{name}]" for line in f)
    except Exception:
        return False


def pick_fastfetch_package():
    """Return 'fastfetch-git' when chaotic-AUR/nemesis is active and has it, else 'fastfetch'."""
    if _repo_active("chaotic-aur") or _repo_active("nemesis_repo"):
        result = subprocess.run(
            ["pacman", "-Si", "fastfetch-git"], capture_output=True, text=True
        )
        if result.returncode == 0:
            log.log_info("chaotic-AUR/nemesis detected — using fastfetch-git")
            return "fastfetch-git"
    log.log_info("Using fastfetch (stable)")
    return "fastfetch"


def installed_fastfetch_package():
    """Return the installed fastfetch package name, or None."""
    for pkg in ("fastfetch-git", "fastfetch"):
        if subprocess.run(["pacman", "-Q", pkg], capture_output=True).returncode == 0:
            return pkg
    return None


def package_installed(pkg):
    """Return True if the given pacman package is installed."""
    return subprocess.run(["pacman", "-Q", pkg], capture_output=True).returncode == 0


def _find_terminal():
    for name, exec_flag in _TERMINALS:
        if shutil.which(name):
            return [name, *exec_flag]
    return None


def launch_in_terminal(argv):
    """Launch argv in a detected terminal emulator; return the Popen or None."""
    term = _find_terminal()
    if not term:
        log.log_error("No terminal emulator found to run package operations")
        return None
    cmd = [*term, "bash", "-c", " ".join(argv) + "; echo; read -p 'Press Enter to close...'"]
    log.log_info("Launching: " + " ".join(argv))
    return subprocess.Popen(cmd)


def install_package(pkg):
    """Launch a terminal to install a package with pacman; return the Popen or None."""
    return launch_in_terminal(["sudo", "pacman", "-S", "--needed", pkg])


def remove_package(pkg):
    """Launch a terminal to remove a package with pacman; return the Popen or None."""
    return launch_in_terminal(["sudo", "pacman", "-Rns", pkg])
