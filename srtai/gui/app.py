"""Main window."""
from __future__ import annotations

import logging
import logging.handlers
import sys
import threading
import webbrowser
from tkinter import messagebox

import customtkinter as ctk

from .. import APP_NAME, __version__, app_paths
from ..settings import Settings
from . import i18n, theme, updates
from .i18n import t

log = logging.getLogger(__name__)

try:  # drag and drop is optional
    from tkinterdnd2 import DND_FILES, TkinterDnD

    _DND = True
except Exception:  # pragma: no cover
    _DND = False


def _setup_logging() -> None:
    handler = logging.handlers.RotatingFileHandler(app_paths.log_file(), maxBytes=1_000_000, backupCount=2,
                                                   encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


_Base = (ctk.CTk, TkinterDnD.DnDWrapper) if _DND else (ctk.CTk,)


class App(*_Base):  # type: ignore[misc]
    def __init__(self, initial_paths: list[str] | None = None):
        super().__init__()
        self.dnd_ok = False
        if _DND:
            try:
                self.TkdndVersion = TkinterDnD._require(self)
                self.dnd_ok = True
            except Exception:
                log.info("Drag and drop not available", exc_info=True)

        self.settings = Settings.load()
        i18n.set_language(self.settings.ui_language)
        theme.setup(self, self.settings.appearance)

        self.title(APP_NAME)
        self.geometry(self.settings.geometry or "1180x800")
        self.minsize(980, 680)
        self.configure(fg_color=theme.BG)
        self._set_icon()

        self._build_top_bar()
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=16, pady=(0, 14))
        self.body.grid_columnconfigure(0, weight=1)
        self.body.grid_rowconfigure(0, weight=1)

        from .translate_page import TranslatePage

        self.translate_page = TranslatePage(self.body, self.settings)
        self.pages = {"translate": self.translate_page}
        self.translate_page.grid(row=0, column=0, sticky="nsew")
        self._enable_drop()
        if initial_paths:
            self.translate_page.add_paths(initial_paths)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(1500, self._check_updates_quietly)

    # -- chrome
    def _set_icon(self) -> None:
        try:
            ico = app_paths.resource_path("assets", "icon.ico")
            png = app_paths.resource_path("assets", "icon.png")
            if sys.platform == "win32" and ico.exists():
                self.iconbitmap(default=str(ico))
            elif png.exists():
                from tkinter import PhotoImage

                self._icon_img = PhotoImage(file=str(png))
                self.iconphoto(True, self._icon_img)
        except Exception:
            log.debug("Could not set icon", exc_info=True)

    def _build_top_bar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent", height=56)
        bar.pack(fill="x", padx=16, pady=(12, 10))
        title = ctk.CTkFrame(bar, fg_color="transparent")
        title.pack(side="left")
        ctk.CTkLabel(title, text="SRT AI Translator", font=theme.font(20, "bold"), text_color=theme.TEXT).pack(
            side="left")
        ctk.CTkLabel(title, text=__version__, font=theme.font(12), text_color=theme.MUTED).pack(
            side="left", padx=(8, 0), pady=(6, 0))
        self._nav_labels = {"translate": t("Translate"), "models": t("Models"), "settings": t("Settings")}
        self.nav = ctk.CTkSegmentedButton(
            bar, values=list(self._nav_labels.values()), command=self._navigate, font=theme.font(13), height=34,
            selected_color=theme.SELECTED, selected_hover_color=theme.SELECTED, text_color=theme.TEXT,
            unselected_color=theme.SURFACE, unselected_hover_color=theme.RAISED, fg_color=theme.SURFACE)
        self.nav.set(self._nav_labels["translate"])
        self.nav.pack(side="right")
        self.update_label = ctk.CTkLabel(bar, text="", font=theme.font(12), text_color=theme.LINK, cursor="hand2")
        self.update_label.pack(side="right", padx=16)

    def _navigate(self, label: str) -> None:
        key = next(k for k, v in self._nav_labels.items() if v == label)
        if key not in self.pages:
            if key == "models":
                from .models_page import ModelsPage

                self.pages[key] = ModelsPage(self.body, self.settings, on_change=self._models_changed)
            else:
                from .settings_page import SettingsPage

                self.pages[key] = SettingsPage(self.body, self.settings, on_change=self._models_changed)
        for name, page in self.pages.items():
            if name == key:
                page.grid(row=0, column=0, sticky="nsew")
            else:
                page.grid_remove()
        if key == "translate":
            self.translate_page._update_status_hint()

    def _models_changed(self) -> None:
        self.translate_page._update_status_hint()

    # -- drag and drop
    def _enable_drop(self) -> None:
        if not self.dnd_ok:
            return
        targets = [self, *self.translate_page.files.drop_widgets()]
        for widget in targets:
            try:
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                log.debug("drop target failed for %s", widget, exc_info=True)

    def _on_drop(self, event) -> None:
        paths = list(self.tk.splitlist(event.data))
        self.nav.set(self._nav_labels["translate"])
        self._navigate(self._nav_labels["translate"])
        self.translate_page.add_paths(paths)

    # -- updates
    def _check_updates_quietly(self) -> None:
        def work():
            info = updates.latest_release()
            if info and updates.is_newer(info["version"]):
                self.after(0, lambda: self._show_update(info))

        threading.Thread(target=work, daemon=True).start()

    def _show_update(self, info: dict) -> None:
        self.update_label.configure(text=t("Update available: {version}", version=info["version"]))
        self.update_label.bind("<Button-1>", lambda e: webbrowser.open(info["url"]))

    # -- closing
    def _on_close(self) -> None:
        if self.translate_page.is_busy():
            if not messagebox.askyesno(APP_NAME, t("A translation is running. Stop it and quit?")):
                return
            if self.translate_page.translator:
                self.translate_page.translator.cancel()
        try:
            self.translate_page._save_options()
            self.settings.geometry = self.geometry()
            self.settings.save()
        except Exception:
            log.debug("Could not save settings on exit", exc_info=True)
        self.destroy()


def run(argv: list[str] | None = None) -> int:
    _setup_logging()
    if sys.platform == "win32":
        try:  # crisp text on high-DPI screens and a proper taskbar icon
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MaloneFreak.SRTAITranslate")
        except Exception:
            pass
    paths = [a for a in (argv or []) if a.lower().endswith(".srt") or not a.startswith("-")]
    app = App(paths)
    app.mainloop()
    return 0
