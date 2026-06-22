#!/usr/bin/env python3
"""Fastfetch Tweak Tool — GTK4 config editor for the Fastfetch system-info tool."""

import os
import subprocess
import sys

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import ff_config  # noqa: E402
import ff_gui as gui_module  # noqa: E402
import log  # noqa: E402


def _fastfetch_version():
    """Return the installed fastfetch version string, or 'not installed'."""
    try:
        out = subprocess.run(
            ["fastfetch", "--version"], capture_output=True, text=True, timeout=3
        )
        parts = out.stdout.strip().split()
        return parts[1] if len(parts) >= 2 else out.stdout.strip()
    except Exception:
        return "not installed"


class FastfetchTweakApp(Gtk.Application):
    """GTK4 application entry point for fastfetch-tweak-tool."""

    def __init__(self):
        super().__init__(application_id="com.kiro.fastfetch-tweak-tool")
        self.connect("activate", self.on_activate)

    def on_activate(self, _app):
        window = Main(self)
        window.present()


class Main(Gtk.ApplicationWindow):
    """Main application window."""

    def __init__(self, app):
        super().__init__(application=app, title="Fastfetch Tweak Tool")
        prefs = ff_config.load_prefs()
        self.set_default_size(
            prefs.get("window_width", 1000), prefs.get("window_height", 640)
        )
        self.connect("close-request", self._on_close)
        self._load_css()
        self._build_headerbar()
        gui_module.build(self, _fastfetch_version())
        log.log_timing("GUI built")
        log.log_section("Fastfetch Tweak Tool started")

    def _on_close(self, _widget):
        prefs = ff_config.load_prefs()
        prefs["window_width"] = self.get_width()
        prefs["window_height"] = self.get_height()
        ff_config.save_prefs(prefs)
        return False

    def _build_headerbar(self):
        headerbar = Gtk.HeaderBar()
        headerbar.set_show_title_buttons(True)
        self.set_titlebar(headerbar)

    def _load_css(self):
        css_path = os.path.join(BASE_DIR, "att.css")
        if not os.path.isfile(css_path):
            return
        provider = Gtk.CssProvider()
        provider.load_from_path(css_path)
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )


def main():
    """Run the application."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        log.log_error(
            "Refusing to run as root — the config must be written to your own "
            "~/.config/fastfetch. Run as your normal user."
        )
        sys.exit(1)
    argv = sys.argv
    if "--debug" in argv:
        log.DEBUG = True
        argv = [a for a in argv if a != "--debug"]
        log.log_section("Debug mode enabled")
    if "--dev" in argv:
        log.DEV = True
        argv = [a for a in argv if a != "--dev"]
    app = FastfetchTweakApp()
    sys.exit(app.run(argv))


if __name__ == "__main__":
    main()
