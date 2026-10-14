"""Settings: API keys, servers, performance, appearance, data and about."""
from __future__ import annotations

import threading
import webbrowser

import customtkinter as ctk

from .. import REPO_URL, __version__, app_paths
from ..core.cache import TranslationCache
from ..engines import providers
from ..settings import Settings, get_api_key, set_api_key
from . import theme, updates
from .i18n import LANGUAGES, t
from .widgets import Link, hint, open_path, section_title


class SettingsPage(ctk.CTkScrollableFrame):
    def __init__(self, master, settings: Settings, on_change=None):
        super().__init__(master, fg_color=theme.SURFACE, corner_radius=theme.RADIUS)
        self.settings = settings
        self.on_change = on_change
        self.grid_columnconfigure(1, weight=1)
        self._row_counter = 0

        self._add_section(t("API keys"))
        hint(self, t("Keys are stored in your system's credential store, never in plain text."), wrap=700).grid(
            row=self._next_row(), column=0, columnspan=4, sticky="w", padx=20, pady=(0, 6))
        self.key_entries = {}
        for prov in providers.PROVIDERS:
            if not prov.needs_key:
                continue
            r = self._next_row()
            ctk.CTkLabel(self, text=prov.name, font=theme.font(13), text_color=theme.TEXT, anchor="w").grid(
                row=r, column=0, sticky="w", padx=(20, 10), pady=4)
            entry = ctk.CTkEntry(self, show="•", height=30, font=theme.font(13), fg_color=theme.RAISED,
                                 border_color=theme.BORDER, text_color=theme.TEXT)
            key = get_api_key(prov.id)
            if key:
                entry.insert(0, key)
            entry.grid(row=r, column=1, sticky="ew", pady=4)
            button = ctk.CTkButton(self, text=t("Save"), width=70, height=30, font=theme.font(13),
                                   fg_color=theme.RAISED, hover_color=theme.BORDER, text_color=theme.TEXT)
            button.configure(command=lambda p=prov.id, e=entry, b=button: self._save_key(p, e, b))
            button.grid(row=r, column=2, padx=6, pady=4)
            Link(self, t("Get a key"), url=prov.key_url).grid(row=r, column=3, sticky="w", padx=(4, 20))
            self.key_entries[prov.id] = entry

        self._add_section(t("Servers"))
        self.url_entries = {}
        for pid, label in (("custom", t("Custom OpenAI-compatible server")), ("ollama", "Ollama"),
                           ("lmstudio", "LM Studio")):
            r = self._next_row()
            ctk.CTkLabel(self, text=label, font=theme.font(13), text_color=theme.TEXT, anchor="w").grid(
                row=r, column=0, sticky="w", padx=(20, 10), pady=4)
            entry = ctk.CTkEntry(self, height=30, font=theme.font(13), fg_color=theme.RAISED,
                                 border_color=theme.BORDER, text_color=theme.TEXT,
                                 placeholder_text=providers.get(pid).base_url or "http://localhost:8000/v1")
            if settings.base_urls.get(pid):
                entry.insert(0, settings.base_urls[pid])
            entry.grid(row=r, column=1, columnspan=2, sticky="ew", pady=4)
            entry.bind("<FocusOut>", lambda e, p=pid, w=entry: self._save_url(p, w))
            self.url_entries[pid] = entry

        self._add_section(t("Performance"))
        r = self._next_row()
        self._add_row_label(t("Parallel requests (cloud)"), r)
        self.workers = self._small_entry(r, settings.workers.get("*", ""), "4")
        r = self._next_row()
        self._add_row_label(t("Lines per request (cloud)"), r)
        self.batch = self._small_entry(r, settings.batch_sizes.get("*", ""), t("Blank = automatic"))
        r = self._next_row()
        self._add_row_label(t("Offline engine device"), r)
        self._devices = {"auto": t("Automatic"), "cpu": t("Processor (CPU)"), "cuda": t("NVIDIA GPU")}
        self.device = ctk.CTkOptionMenu(self, values=list(self._devices.values()), font=theme.font(13), width=200,
                                        fg_color=theme.RAISED, button_color=theme.BORDER, text_color=theme.TEXT,
                                        command=lambda v: self._save_perf())
        self.device.set(self._devices.get(settings.offline_device, t("Automatic")))
        self.device.grid(row=r, column=1, sticky="w", pady=4)

        self._add_section(t("Appearance"))
        r = self._next_row()
        self._add_row_label(t("Theme"), r)
        self._themes = {"system": t("System"), "dark": t("Dark"), "light": t("Light")}
        self.theme_menu = ctk.CTkSegmentedButton(
            self, values=list(self._themes.values()), font=theme.font(13), command=self._set_theme,
            selected_color=theme.SELECTED, selected_hover_color=theme.SELECTED, text_color=theme.TEXT,
            unselected_color=theme.RAISED, unselected_hover_color=theme.BORDER, fg_color=theme.RAISED)
        self.theme_menu.set(self._themes.get(settings.appearance, t("System")))
        self.theme_menu.grid(row=r, column=1, sticky="w", pady=4)
        r = self._next_row()
        self._add_row_label(t("App language"), r)
        self._langs = {"": t("System"), **LANGUAGES}
        self.lang_menu = ctk.CTkOptionMenu(self, values=list(self._langs.values()), font=theme.font(13), width=200,
                                           fg_color=theme.RAISED, button_color=theme.BORDER, text_color=theme.TEXT,
                                           command=self._set_lang)
        self.lang_menu.set(self._langs.get(settings.ui_language, t("System")))
        self.lang_menu.grid(row=r, column=1, sticky="w", pady=4)
        self.lang_hint = hint(self, "", wrap=400)
        self.lang_hint.grid(row=r, column=2, columnspan=2, sticky="w", padx=8)

        self._add_section(t("Data"))
        r = self._next_row()
        self.memory_label = ctk.CTkLabel(self, text="", font=theme.font(13), text_color=theme.TEXT, anchor="w")
        self.memory_label.grid(row=r, column=0, columnspan=2, sticky="w", padx=20, pady=4)
        ctk.CTkButton(self, text=t("Clear memory"), width=130, height=30, font=theme.font(13), fg_color=theme.RAISED,
                      hover_color=theme.BORDER, text_color=theme.TEXT, command=self._clear_memory).grid(
            row=r, column=2, columnspan=2, sticky="w", padx=6)
        r = self._next_row()
        ctk.CTkButton(self, text=t("Open data folder"), width=160, height=30, font=theme.font(13),
                      fg_color=theme.RAISED, hover_color=theme.BORDER, text_color=theme.TEXT,
                      command=lambda: open_path(app_paths.data_dir())).grid(row=r, column=0, sticky="w", padx=20,
                                                                            pady=4)
        self._refresh_memory()

        self._add_section(t("About"))
        r = self._next_row()
        ctk.CTkLabel(self, text=t("Version {version}", version=__version__), font=theme.font(13),
                     text_color=theme.TEXT, anchor="w").grid(row=r, column=0, sticky="w", padx=20, pady=4)
        Link(self, t("Project page on GitHub"), url=REPO_URL).grid(row=r, column=1, sticky="w")
        r = self._next_row()
        self.update_label = hint(self, "", wrap=500)
        ctk.CTkButton(self, text=t("Check for updates"), width=170, height=30, font=theme.font(13),
                      fg_color=theme.RAISED, hover_color=theme.BORDER, text_color=theme.TEXT,
                      command=self._check_updates).grid(row=r, column=0, sticky="w", padx=20, pady=(4, 24))
        self.update_label.grid(row=r, column=1, columnspan=3, sticky="w", pady=(4, 24))

    # -- layout helpers
    def _next_row(self) -> int:
        self._row_counter += 1
        return self._row_counter

    def _add_section(self, text: str) -> None:
        section_title(self, text).grid(row=self._next_row(), column=0, columnspan=4, sticky="w", padx=20, pady=(18, 4))

    def _add_row_label(self, text: str, row: int) -> None:
        ctk.CTkLabel(self, text=text, font=theme.font(13), text_color=theme.TEXT, anchor="w").grid(
            row=row, column=0, sticky="w", padx=(20, 10), pady=4)

    def _small_entry(self, row: int, value, placeholder: str) -> ctk.CTkEntry:
        entry = ctk.CTkEntry(self, width=120, height=30, font=theme.font(13), fg_color=theme.RAISED,
                             border_color=theme.BORDER, text_color=theme.TEXT, placeholder_text=placeholder)
        if value:
            entry.insert(0, str(value))
        entry.grid(row=row, column=1, sticky="w", pady=4)
        entry.bind("<FocusOut>", lambda e: self._save_perf())
        return entry

    # -- actions
    def _save_key(self, provider_id: str, entry: ctk.CTkEntry, button: ctk.CTkButton) -> None:
        set_api_key(provider_id, entry.get())
        button.configure(text=t("Saved"))
        self.after(1500, lambda: button.configure(text=t("Save")))
        if self.on_change:
            self.on_change()

    def _save_url(self, provider_id: str, entry: ctk.CTkEntry) -> None:
        value = entry.get().strip()
        if value:
            self.settings.base_urls[provider_id] = value
        else:
            self.settings.base_urls.pop(provider_id, None)
        self.settings.save()

    def _save_perf(self) -> None:
        for entry, store in ((self.workers, self.settings.workers), (self.batch, self.settings.batch_sizes)):
            raw = entry.get().strip()
            if raw.isdigit() and int(raw) > 0:
                store["*"] = min(int(raw), 16 if store is self.settings.workers else 200)
            else:
                store.pop("*", None)
        inv = {v: k for k, v in self._devices.items()}
        self.settings.offline_device = inv.get(self.device.get(), "auto")
        self.settings.save()

    def _set_theme(self, label: str) -> None:
        inv = {v: k for k, v in self._themes.items()}
        self.settings.appearance = inv.get(label, "system")
        ctk.set_appearance_mode(self.settings.appearance)
        self.settings.save()

    def _set_lang(self, label: str) -> None:
        inv = {v: k for k, v in self._langs.items()}
        self.settings.ui_language = inv.get(label, "")
        self.settings.save()
        self.lang_hint.configure(text=t("Restart the app to apply the new language."))

    def _refresh_memory(self) -> None:
        cache = TranslationCache(app_paths.cache_file())
        n = cache.count()
        cache.close()
        self.memory_label.configure(text=t("Translation memory: {n} saved lines.", n=f"{n:,}"))

    def _clear_memory(self) -> None:
        cache = TranslationCache(app_paths.cache_file())
        cache.clear()
        cache.close()
        self._refresh_memory()

    def _check_updates(self) -> None:
        def work():
            info = updates.latest_release()
            if info is None:
                msg, url = t("Could not check for updates."), None
            elif updates.is_newer(info["version"]):
                msg, url = t("Update available: {version}", version=info["version"]), info["url"]
            else:
                msg, url = t("You have the latest version."), None
            self.after(0, lambda: self._show_update(msg, url))

        threading.Thread(target=work, daemon=True).start()

    def _show_update(self, msg: str, url: str | None) -> None:
        self.update_label.configure(text=msg, text_color=theme.LINK if url else theme.MUTED,
                                    cursor="hand2" if url else "")
        if url:
            self.update_label.bind("<Button-1>", lambda e: webbrowser.open(url))
