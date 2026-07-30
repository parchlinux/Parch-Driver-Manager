import gettext
import locale
import os
from typing import Optional

APP_ID = "com.parchlinux.DriverManager"
DOMAIN = "parch-driver-manager"
RTL_LANGUAGES = {"fa", "ar", "he", "ur"}


def _get_locale_dir() -> str:
    return os.path.join(os.path.dirname(__file__), "locale")


def get_language() -> str:
    env_lang = os.environ.get("PARCH_DM_LANG")
    if env_lang:
        return env_lang
    try:
        lang, _ = locale.getlocale(locale.LC_MESSAGES)
        if lang:
            return lang.split("_")[0]
    except Exception:
        pass
    try:
        lang = os.environ.get("LANG", "en_US").split("_")[0]
        return lang
    except Exception:
        return "en"


_current_lang: str = ""

try:
    locale.setlocale(locale.LC_ALL, "")
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, "C.UTF-8")
    except locale.Error:
        locale.setlocale(locale.LC_ALL, "C")

_current_lang = get_language()
if _current_lang not in ("fa", "en", "ar", "he", "ur"):
    _current_lang = "en"

try:
    _trans = gettext.translation(DOMAIN, _get_locale_dir(), languages=[_current_lang])
    _trans.install()
    _ = _trans.gettext
except Exception:
    import builtins
    builtins.__dict__["_"] = lambda msg: msg
    _ = lambda msg: msg


def is_rtl() -> bool:
    return _current_lang in RTL_LANGUAGES
