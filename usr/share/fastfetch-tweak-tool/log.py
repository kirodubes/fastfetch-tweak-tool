"""Colored console logging and debug helpers for fastfetch-tweak-tool."""

import sys
import time

DEBUG = False
DEV = False

_t0 = time.perf_counter()

if sys.stdout.isatty():
    _RESET = "\033[0m"
    _BOLD = "\033[1m"
    _GREEN = "\033[32m"
    _CYAN = "\033[36m"
    _YELLOW = "\033[33m"
    _RED = "\033[31m"
    _BLUE = "\033[34m"
else:
    _RESET = _BOLD = _GREEN = _CYAN = _YELLOW = _RED = _BLUE = ""

_SEP = "─" * 60


def log_section(msg):
    """Print a bold green section header with separator lines."""
    print(f"\n{_GREEN}{_BOLD}{_SEP}{_RESET}")
    print(f"{_GREEN}{_BOLD}  {msg}{_RESET}")
    print(f"{_GREEN}{_BOLD}{_SEP}{_RESET}")


def log_subsection(msg):
    """Print a cyan subsection header."""
    print(f"\n{_CYAN}{_BOLD}── {msg} ──{_RESET}")


def log_info(msg):
    """Print a blue informational message."""
    print(f"{_BLUE}[INFO]{_RESET} {msg}")


def log_success(msg):
    """Print a green success message."""
    print(f"{_GREEN}[OK]{_RESET}   {msg}")


def log_warn(msg):
    """Print a yellow warning message."""
    print(f"{_YELLOW}[WARN]{_RESET} {msg}")


def log_error(msg):
    """Print a red error message to stderr."""
    print(f"{_RED}[ERR]{_RESET}  {msg}", file=sys.stderr)


def debug_print(msg):
    """Print only when DEBUG mode is active."""
    if DEBUG:
        print(f"{_CYAN}[DBG]{_RESET}  {msg}")


def log_timing(stage):
    """Print elapsed ms since startup in DEBUG mode."""
    if DEBUG:
        elapsed = (time.perf_counter() - _t0) * 1000
        print(f"{_CYAN}[TIMING]{_RESET} {stage}: {elapsed:.1f} ms")
