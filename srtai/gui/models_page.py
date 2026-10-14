"""Download and remove offline models and Ollama models."""
from __future__ import annotations

import threading
import webbrowser
from tkinter import messagebox

import customtkinter as ctk

from .. import app_paths
from ..engines.base import CancelledError
from ..engines.offline import cuda_available
from ..models import catalog, downloader
from ..models.ollama_client import OLLAMA_DOWNLOAD_URL, OllamaClient
from ..settings import Settings
from . import theme
from .i18n import current as ui_lang
from .i18n import t
from .widgets import hint, open_path, section_title


def _stars(n: int) -> str:
    return "●" * n + "○" * (3 - n)


class ModelRow(ctk.CTkFrame):
    def __init__(self, master, page: "ModelsPage", model: catalog.OfflineModel):
        super().__init__(master, fg_color=theme.RAISED, corner_radius=6)
        self.page, self.model = page, model
        self.cancel_event: threading.Event | None = None
        self.grid_columnconfigure(0, weight=1)
        title = ctk.CTkLabel(self, text=model.name, font=theme.font(14, "bold"), text_color=theme.TEXT, anchor="w")
        title.grid(row=0, column=0, sticky="w", padx=14, pady=(10, 0))
        desc = model.description_pt if ui_lang() == "pt-BR" else model.description
        hint(self, desc, wrap=520).grid(row=1, column=0, sticky="w", padx=14)
        meta = (t("{size} download, needs about {ram} GB of RAM", size=model.size_label, ram=f"{model.ram_gb:g}")
                + f"      {t('Quality')} {_stars(model.quality)}   {t('Speed')} {_stars(model.speed)}")
        ctk.CTkLabel(self, text=meta, font=theme.font(12), text_color=theme.MUTED, anchor="w").grid(
            row=2, column=0, sticky="w", padx=14, pady=(2, 0))
        self.status = ctk.CTkLabel(self, text="", font=theme.font(12), text_color=theme.MUTED, anchor="w")
        self.status.grid(row=3, column=0, sticky="w", padx=14, pady=(2, 0))
        self.bar = ctk.CTkProgressBar(self, height=6, progress_color=theme.ACCENT, fg_color=theme.BORDER)
        self.bar.set(0)
        self.button = ctk.CTkButton(self, text="", width=110, height=34, font=theme.font(13),
                                    command=self._action)
        self.button.grid(row=0, column=1, rowspan=3, padx=14, pady=10)
        self.refresh()

    def refresh(self) -> None:
        installed = downloader.is_installed(self.model.id)
        if self.cancel_event is not None:
            self.button.configure(text=t("Cancel"), fg_color=theme.RAISED, hover_color=theme.BORDER,
                                  text_color=theme.TEXT, border_width=1, border_color=theme.BORDER)
        elif installed:
            size = downloader.installed_size(self.model.id) / 1e6
            self.status.configure(text=f"{t('Installed')} ({size:,.0f} MB)", text_color=theme.SUCCESS)
            self.button.configure(text=t("Delete"), fg_color=theme.RAISED, hover_color=theme.BORDER,
                                  text_color=theme.TEXT, border_width=1, border_color=theme.BORDER)
        else:
            self.status.configure(text=t("License: {license}", license=self.model.license), text_color=theme.MUTED)
            self.button.configure(text=t("Download"), fg_color=theme.RAISED, hover_color=theme.BORDER,
                                  text_color=theme.TEXT, border_width=2, border_color=theme.ACCENT)

    def _action(self) -> None:
        if self.cancel_event is not None:
            self.cancel_event.set()
            return
        if downloader.is_installed(self.model.id):
            if messagebox.askyesno(t("Delete"), t("Delete {name}?", name=self.model.name)):
                downloader.delete_model(self.model.id)
                self.refresh()
            return
        self._download()

    def _download(self) -> None:
        self.cancel_event = threading.Event()
        self.bar.grid(row=4, column=0, columnspan=2, sticky="ew", padx=14, pady=(4, 10))
        self.refresh()

        def progress(done: int, total: int, _name: str) -> None:
            self.after(0, lambda: self._on_progress(done, total))

        def work():
            error = None
            try:
                downloader.install_model(self.model.id, progress, self.cancel_event)
            except CancelledError:
                error = t("Download paused. Click Download to resume.")
            except Exception as exc:
                error = str(exc)
            self.after(0, lambda: self._finished(error))

        threading.Thread(target=work, daemon=True).start()

    def _on_progress(self, done: int, total: int) -> None:
        if total:
            self.bar.set(done / total)
        self.status.configure(text=t("Downloading {done} of {total} MB", done=f"{done / 1e6:,.0f}",
                                     total=f"{total / 1e6:,.0f}"), text_color=theme.TEXT)

    def _finished(self, error: str | None) -> None:
        self.cancel_event = None
        self.bar.grid_remove()
        self.refresh()
        if error:
            self.status.configure(text=error, text_color=theme.ERROR)
        self.page.on_models_changed()


class OllamaRow(ctk.CTkFrame):
    def __init__(self, master, page: "ModelsPage", suggestion: catalog.OllamaSuggestion):
        super().__init__(master, fg_color=theme.RAISED, corner_radius=6)
        self.page, self.s = page, suggestion
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=f"{suggestion.tag}   {suggestion.size_label}", font=theme.font(14, "bold"),
                     text_color=theme.TEXT, anchor="w").grid(row=0, column=0, sticky="w", padx=14, pady=(10, 0))
        desc = suggestion.description_pt if ui_lang() == "pt-BR" else suggestion.description
        hint(self, desc, wrap=520).grid(row=1, column=0, sticky="w", padx=14, pady=(0, 2))
        self.status = ctk.CTkLabel(self, text="", font=theme.font(12), text_color=theme.MUTED, anchor="w")
        self.status.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 8))
        self.bar = ctk.CTkProgressBar(self, height=6, progress_color=theme.ACCENT, fg_color=theme.BORDER)
        self.button = ctk.CTkButton(self, text=t("Download"), width=110, height=34, font=theme.font(13),
                                    command=self._action)
        self.button.grid(row=0, column=1, rowspan=3, padx=14, pady=10)
        self.cancel_event: threading.Event | None = None
        self.set_state(installed=False, running=False)

    def set_state(self, installed: bool, running: bool) -> None:
        self.installed = installed
        if self.cancel_event is not None:
            return
        if installed:
            self.button.configure(text=t("Delete"), fg_color=theme.RAISED, hover_color=theme.BORDER,
                                  text_color=theme.TEXT, border_width=1, border_color=theme.BORDER, state="normal")
            self.status.configure(text=t("Installed"), text_color=theme.SUCCESS)
        else:
            self.button.configure(text=t("Download"), fg_color=theme.RAISED, hover_color=theme.BORDER,
                                  text_color=theme.TEXT, border_width=2,
                                  border_color=theme.ACCENT if running else theme.BORDER,
                                  state="normal" if running else "disabled")
            self.status.configure(text="", text_color=theme.MUTED)

    def _action(self) -> None:
        client = self.page.ollama()
        if self.cancel_event is not None:
            self.cancel_event.set()
            return
        if self.installed:
            if messagebox.askyesno(t("Delete"), t("Delete {name}?", name=self.s.tag)):
                threading.Thread(target=lambda: (self._safe(client.delete, self.s.tag),
                                                 self.after(0, self.page.refresh_ollama)), daemon=True).start()
            return
        self.cancel_event = threading.Event()
        self.button.configure(text=t("Cancel"), fg_color=theme.RAISED, text_color=theme.TEXT)
        self.bar.set(0)
        self.bar.grid(row=3, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 10))

        def progress(msg, frac):
            self.after(0, lambda: self._on_progress(msg, frac))

        def work():
            err = None
            try:
                client.pull(self.s.tag, progress=progress, cancel_event=self.cancel_event)
            except CancelledError:
                err = t("Download paused. Click Download to resume.")
            except Exception as exc:
                err = str(exc)
            self.after(0, lambda: self._finished(err))

        threading.Thread(target=work, daemon=True).start()

    def _safe(self, fn, *args):
        try:
            fn(*args)
        except Exception as exc:
            self.after(0, lambda: self.status.configure(text=str(exc), text_color=theme.ERROR))

    def _on_progress(self, msg: str, frac):
        if isinstance(frac, (int, float)):
            self.bar.set(frac)
        self.status.configure(text=msg, text_color=theme.TEXT)

    def _finished(self, err):
        self.cancel_event = None
        self.bar.grid_remove()
        if err:
            self.status.configure(text=err, text_color=theme.ERROR)
        self.page.refresh_ollama()


class ModelsPage(ctk.CTkScrollableFrame):
    def __init__(self, master, settings: Settings, on_change=None):
        super().__init__(master, fg_color=theme.SURFACE, corner_radius=theme.RADIUS)
        self.settings = settings
        self.on_change = on_change
        self.grid_columnconfigure(0, weight=1)

        section_title(self, t("Offline models")).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 2))
        hint(self, t("Translate without internet. Each model is downloaded once and kept in {path}.",
                     path=app_paths.models_dir()), wrap=760).grid(row=1, column=0, sticky="w", padx=20)
        gpu = cuda_available()
        hint(self, t("NVIDIA GPU found: translations will use it.") if gpu else
             t("No NVIDIA GPU found: translations run on the processor (CPU)."), wrap=760).grid(
            row=2, column=0, sticky="w", padx=20, pady=(2, 8))
        self.rows: list[ModelRow] = []
        r = 3
        for model in catalog.OFFLINE_MODELS:
            row = ModelRow(self, self, model)
            row.grid(row=r, column=0, sticky="ew", padx=20, pady=4)
            self.rows.append(row)
            r += 1
        ctk.CTkButton(self, text=t("Open models folder"), width=170, height=32, font=theme.font(13),
                      fg_color=theme.RAISED, hover_color=theme.BORDER, text_color=theme.TEXT,
                      command=lambda: open_path(app_paths.models_dir())).grid(row=r, column=0, sticky="w",
                                                                              padx=20, pady=(6, 20))
        r += 1

        section_title(self, t("Ollama (local AI models)")).grid(row=r, column=0, sticky="w", padx=20, pady=(8, 2))
        r += 1
        hint(self, t("Ollama runs AI models on your own PC. Install it, keep it open, and download models here."),
             wrap=760).grid(row=r, column=0, sticky="w", padx=20)
        r += 1
        status_row = ctk.CTkFrame(self, fg_color="transparent")
        status_row.grid(row=r, column=0, sticky="ew", padx=20, pady=(6, 6))
        self.ollama_status = ctk.CTkLabel(status_row, text="", font=theme.font(13), text_color=theme.TEXT)
        self.ollama_status.pack(side="left")
        ctk.CTkButton(status_row, text=t("Refresh"), width=90, height=30, font=theme.font(13), fg_color=theme.RAISED,
                      hover_color=theme.BORDER, text_color=theme.TEXT, command=self.refresh_ollama).pack(side="right")
        self.get_ollama = ctk.CTkButton(status_row, text=t("Get Ollama"), width=110, height=30, font=theme.font(13),
                                        fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                                        text_color=theme.ON_ACCENT,
                                        command=lambda: webbrowser.open(OLLAMA_DOWNLOAD_URL))
        r += 1
        self.ollama_rows: list[OllamaRow] = []
        for s in catalog.OLLAMA_SUGGESTIONS:
            row = OllamaRow(self, self, s)
            row.grid(row=r, column=0, sticky="ew", padx=20, pady=4)
            self.ollama_rows.append(row)
            r += 1
        self.installed_label = hint(self, "", wrap=760)
        self.installed_label.grid(row=r, column=0, sticky="w", padx=20, pady=(6, 20))
        self.refresh_ollama()

    def ollama(self) -> OllamaClient:
        return OllamaClient(self.settings.base_url_for("ollama"))

    def refresh_ollama(self) -> None:
        client = self.ollama()

        def work():
            version = client.version()
            names = []
            if version:
                try:
                    names = client.list_models()
                except Exception:
                    names = []
            self.after(0, lambda: self._ollama_state(version, names))

        threading.Thread(target=work, daemon=True).start()

    def _ollama_state(self, version, names) -> None:
        if version:
            self.ollama_status.configure(text=t("Ollama {version} is running.", version=version),
                                         text_color=theme.SUCCESS)
            self.get_ollama.pack_forget()
        else:
            self.ollama_status.configure(text=t("Ollama isn't running."), text_color=theme.MUTED)
            self.get_ollama.pack(side="right", padx=6)
        normalized = {n if ":" in n else f"{n}:latest" for n in names}
        for row in self.ollama_rows:
            row.set_state(row.s.tag in normalized, bool(version))
        if version:
            self.installed_label.configure(
                text=t("Installed in Ollama: {names}", names=", ".join(names)) if names
                else t("No models installed in Ollama yet."))
        else:
            self.installed_label.configure(text="")

    def on_models_changed(self) -> None:
        if self.on_change:
            self.on_change()
