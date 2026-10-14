"""Colours, fonts and the CustomTkinter theme.

Visual idea: a projection booth. Blue-slate panels, and one colour borrowed from
subtitles themselves: the classic subtitle yellow, used for the live preview
"screen" and for the main action only. Type is Atkinson Hyperlegible, a typeface
designed for legibility (bundled, SIL Open Font License).
"""
from __future__ import annotations

import logging
import sys
import tkinter.font as tkfont

import customtkinter as ctk

from .. import app_paths

log = logging.getLogger(__name__)

# (light, dark) pairs, the format CustomTkinter expects.
BG = ("#E9ECF2", "#1A1F2B")
SURFACE = ("#FFFFFF", "#222838")
RAISED = ("#F3F5F9", "#2C3346")
BORDER = ("#CDD3DF", "#3A4258")
TEXT = ("#1E2433", "#E8EAF0")
MUTED = ("#5B6478", "#9AA3B8")
SELECTED = ("#C9D0DE", "#46507A")      # selected tab in segmented controls
ACCENT = "#F4CE3B"               # subtitle yellow (buttons, progress, preview text)
ACCENT_HOVER = "#E2BB22"
ON_ACCENT = "#1A1F2B"
LINK = ("#7A5C00", "#F4CE3B")
SUCCESS = ("#1F8A5B", "#4CC38A")
ERROR = ("#C23B33", "#F2766F")
SCREEN = "#0E1117"               # the preview screen stays dark in both modes
SCREEN_ORIGINAL = "#8C93A3"

RADIUS = 8
_fonts_loaded = False
UI_FAMILY = "Segoe UI"
MONO_FAMILY = "Consolas"


def _register_bundled_fonts() -> None:
    """Make the bundled TTF files available to Tk without installing them."""
    font_dir = app_paths.resource_path("assets", "fonts")
    files = sorted(font_dir.glob("*.ttf")) if font_dir.is_dir() else []
    if not files:
        return
    try:
        if sys.platform == "win32":
            import ctypes

            FR_PRIVATE = 0x10
            for f in files:
                ctypes.windll.gdi32.AddFontResourceExW(str(f), FR_PRIVATE, 0)
        elif sys.platform.startswith("linux"):
            import ctypes
            import ctypes.util

            lib = ctypes.util.find_library("fontconfig")
            if lib:
                fc = ctypes.CDLL(lib)
                for f in files:
                    fc.FcConfigAppFontAddFile(None, str(f).encode())
    except Exception:
        log.debug("Could not register bundled fonts", exc_info=True)


def setup(root, appearance: str = "system") -> None:
    global _fonts_loaded, UI_FAMILY, MONO_FAMILY
    if not _fonts_loaded:
        _register_bundled_fonts()
        _fonts_loaded = True
    families = set(tkfont.families(root))
    for candidate in ("Atkinson Hyperlegible", "Segoe UI", "SF Pro Text", "Helvetica Neue", "DejaVu Sans"):
        if candidate in families:
            UI_FAMILY = candidate
            break
    for candidate in ("Cascadia Mono", "Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono"):
        if candidate in families:
            MONO_FAMILY = candidate
            break
    ctk.set_appearance_mode(appearance if appearance in ("dark", "light") else "system")


def font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=UI_FAMILY, size=size, weight=weight)


def mono(size: int = 11) -> ctk.CTkFont:
    return ctk.CTkFont(family=MONO_FAMILY, size=size)


def pick(pair) -> str:
    """Resolve a (light, dark) pair for plain Tk widgets."""
    if isinstance(pair, str):
        return pair
    return pair[1] if ctk.get_appearance_mode().lower() == "dark" else pair[0]
