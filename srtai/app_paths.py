"""Where the app keeps settings, models, cache and logs.

Order of precedence:
1. The SRTAI_HOME environment variable.
2. Portable mode: a folder named ``SRTAI_data`` next to the executable/script.
3. The per-user data folder of the OS (%LOCALAPPDATA%\\SRTAITranslate on Windows).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from . import APP_ID

PORTABLE_DIR_NAME = "SRTAI_data"


def _app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    env = os.environ.get("SRTAI_HOME")
    if env:
        path = Path(env).expanduser()
    elif (_app_base_dir() / PORTABLE_DIR_NAME).is_dir():
        path = _app_base_dir() / PORTABLE_DIR_NAME
    elif sys.platform == "win32":
        root = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        path = Path(root) / APP_ID
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_ID
    else:
        root = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        path = Path(root) / APP_ID
    path.mkdir(parents=True, exist_ok=True)
    return path


def models_dir() -> Path:
    path = data_dir() / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_file() -> Path:
    return data_dir() / "settings.json"


def cache_file() -> Path:
    return data_dir() / "translation_cache.sqlite3"


def log_file() -> Path:
    return data_dir() / "srtai.log"


def resource_path(*parts: str) -> Path:
    """Path to a file shipped inside the package (works from source and from a PyInstaller build)."""
    meipass = getattr(sys, "_MEIPASS", None)
    base = Path(meipass) / "srtai" if meipass else Path(__file__).resolve().parent
    return base.joinpath(*parts)
