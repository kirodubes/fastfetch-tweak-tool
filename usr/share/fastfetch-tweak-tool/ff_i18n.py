"""Translations: gettext catalogs from usr/share/locale, in the chosen or system language, else English."""

import gettext
import os
from pathlib import Path

import ff_config

DOMAIN = "fastfetch-tweak-tool"
LOCALE_DIR = Path(__file__).resolve().parent.parent / "locale"

NAMES = {
    "en": "English",
    "nl": "Nederlands",
    "de": "Deutsch",
    "es": "Español",
    "fr": "Français",
    "pt_BR": "Português (Brasil)",
    "ru": "Русский",
    "hu": "Magyar",
    "it": "Italiano",
    "tr": "Türkçe",
    "pl": "Polski",
    "ro": "Română",
    "zh_CN": "简体中文",
    "ja": "日本語",
}


def available():
    """Return the language codes the app can show: English, then every language with a catalog."""
    return ["en", *sorted(p.parent.parent.name for p in LOCALE_DIR.glob(f"*/LC_MESSAGES/{DOMAIN}.mo"))]


def name(code):
    """Return the language's own name for code, or the code itself."""
    return NAMES.get(code) or NAMES.get(code.split("_")[0]) or code


def chosen():
    """Return the language saved in app preferences, or None to follow the system."""
    code = ff_config.load_prefs().get("language")
    return code if code in available() else None


def save_choice(code):
    """Save the app's language; None follows the system again."""
    prefs = ff_config.load_prefs()
    prefs["language"] = code
    ff_config.save_prefs(prefs)


def _system_language():
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "").split(":")[0].split(".")[0]
        if value:
            return value
    return "en"


_SIBLING = {"pt": "pt_BR", "zh": "zh_CN"}


def _shown(code):
    """Return the available catalog matching a system language code, else English."""
    codes = available()
    base = code.split("_")[0]
    for candidate in (code, base, _SIBLING.get(base)):
        if candidate in codes:
            return candidate
    return "en"


SYSTEM = _shown(_system_language())
ACTIVE = os.environ.get("FFTT_LANGUAGE") or chosen()
_SYSTEM_LANGUAGE_VAR = os.environ.get("LANGUAGE")
if ACTIVE:
    os.environ["LANGUAGE"] = ACTIVE

_translation = gettext.translation(DOMAIN, localedir=LOCALE_DIR, languages=[ACTIVE or SYSTEM], fallback=True)
_ = _translation.gettext
ngettext = _translation.ngettext


def N_(text):
    """Mark text for translation without translating it (a lookup key translated where it is shown)."""
    return text


def restore_environment():
    """Restore the session's LANGUAGE so a restarted app follows the system language."""
    if _SYSTEM_LANGUAGE_VAR is None:
        os.environ.pop("LANGUAGE", None)
    else:
        os.environ["LANGUAGE"] = _SYSTEM_LANGUAGE_VAR
