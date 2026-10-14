"""The main page: files, engine, languages, options, live preview and progress."""
from __future__ import annotations

import queue
import re
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from .. import app_paths, languages
from ..core.cache import TranslationCache
from ..core.pipeline import Event, SubtitleTranslator
from ..engines import ConfigError, EngineError, create_engine, list_models, providers
from ..models import catalog, downloader
from ..settings import Settings, get_api_key, set_api_key
from ..subtitles.text import strip_tags
from . import theme
from .i18n import current as ui_lang
from .i18n import plural, t
from .widgets import (Collapsible, FileQueue, LanguagePicker, LinesTable, Link, SubtitleScreen, hint,
                      reveal_file, section_title)

CATEGORIES = [(providers.CLOUD, "Cloud API"), (providers.LOCAL, "Local AI"), (providers.OFFLINE, "Offline")]


def _fmt_eta(seconds: float) -> str:
    seconds = int(max(0, seconds))
    if seconds < 60:
        return f"{seconds} s"
    if seconds < 3600:
        return f"{seconds // 60} min {seconds % 60:02d} s"
    return f"{seconds // 3600} h {seconds % 3600 // 60:02d} min"


class TranslatePage(ctk.CTkFrame):
    def __init__(self, master, settings: Settings):
        super().__init__(master, fg_color="transparent")
        self.settings = settings
        self.events: "queue.Queue[Event]" = queue.Queue()
        self.translator: SubtitleTranslator | None = None
        self._job_thread: threading.Thread | None = None
        self._progress_start: dict[str, float] = {}
        self._results = []

        self.grid_columnconfigure(0, weight=5, uniform="cols")
        self.grid_columnconfigure(1, weight=6, uniform="cols")
        self.grid_rowconfigure(0, weight=3)
        self.grid_rowconfigure(1, weight=2, minsize=190)

        self.files = FileQueue(self, on_change=self._update_action, on_add=self._add_files,
                               on_add_folder=self._add_folder)
        self.files.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))

        self.engine_panel = ctk.CTkScrollableFrame(self, fg_color=theme.SURFACE, corner_radius=theme.RADIUS)
        self.engine_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 8))
        self.engine_panel.grid_columnconfigure(1, weight=1)
        self._build_engine_panel(self.engine_panel)

        self._build_screen()
        self._build_action_bar()
        self._apply_provider(initial=True)
        self._update_action()
        self.after(80, self._poll_events)

    # ------------------------------------------------------------------ UI
    def _row_label(self, parent, text, row):
        ctk.CTkLabel(parent, text=text, font=theme.font(13), text_color=theme.MUTED, anchor="w").grid(
            row=row, column=0, sticky="w", padx=(16, 10), pady=6)

    def _build_engine_panel(self, p) -> None:
        s = self.settings
        section_title(p, t("Engine")).grid(row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(12, 6))
        self.category = ctk.CTkSegmentedButton(
            p, values=[t(label) for _, label in CATEGORIES], command=self._on_category, font=theme.font(13),
            selected_color=theme.SELECTED, selected_hover_color=theme.SELECTED, text_color=theme.TEXT,
            unselected_color=theme.RAISED, unselected_hover_color=theme.BORDER, fg_color=theme.RAISED, height=32)
        self.category.grid(row=1, column=0, columnspan=3, sticky="ew", padx=16, pady=(0, 8))

        self._row_label(p, t("Provider"), 2)
        self.provider_menu = ctk.CTkOptionMenu(p, values=[""], command=self._on_provider_name, font=theme.font(13),
                                               dropdown_font=theme.font(13), fg_color=theme.RAISED,
                                               button_color=theme.BORDER, button_hover_color=theme.MUTED,
                                               text_color=theme.TEXT, height=32)
        self.provider_menu.grid(row=2, column=1, columnspan=2, sticky="ew", padx=(0, 16), pady=6)

        self._row_label(p, t("Model"), 3)
        self.model_box = ctk.CTkComboBox(p, values=[""], command=self._on_model, font=theme.font(13),
                                         dropdown_font=theme.font(13), height=32, border_color=theme.BORDER,
                                         button_color=theme.BORDER, fg_color=theme.RAISED, text_color=theme.TEXT)
        self.model_box.grid(row=3, column=1, sticky="ew", pady=6)
        self.model_box.bind("<FocusOut>", lambda e: self._on_model(self.model_box.get()))
        self.refresh_btn = ctk.CTkButton(p, text="↻", width=34, height=32, font=theme.font(15),
                                         fg_color=theme.RAISED, hover_color=theme.BORDER, text_color=theme.TEXT,
                                         command=self._refresh_models)
        self.refresh_btn.grid(row=3, column=2, padx=(6, 16), pady=6)

        # API key / server URL row (shown depending on provider)
        self.key_label = ctk.CTkLabel(p, text=t("API key"), font=theme.font(13), text_color=theme.MUTED, anchor="w")
        self.key_label.grid(row=4, column=0, sticky="w", padx=(16, 10), pady=6)
        self.key_entry = ctk.CTkEntry(p, show="•", font=theme.font(13), height=32, fg_color=theme.RAISED,
                                      border_color=theme.BORDER, text_color=theme.TEXT)
        self.key_entry.grid(row=4, column=1, sticky="ew", pady=6)
        self.key_save = ctk.CTkButton(p, text=t("Save"), width=64, height=32, font=theme.font(13),
                                      fg_color=theme.RAISED, hover_color=theme.BORDER, text_color=theme.TEXT,
                                      command=self._save_key)
        self.key_save.grid(row=4, column=2, padx=(6, 16), pady=6)
        self.key_entry.bind("<Return>", lambda e: self._save_key())

        info = ctk.CTkFrame(p, fg_color="transparent")
        info.grid(row=5, column=0, columnspan=3, sticky="ew", padx=16, pady=(0, 4))
        self.status_hint = hint(info, "", wrap=380)
        self.status_hint.pack(side="left", fill="x", expand=True)
        self.key_link = Link(info, t("Get a key"))
        self.key_link.pack(side="right")

        # Languages
        langs = ctk.CTkFrame(p, fg_color="transparent")
        langs.grid(row=6, column=0, columnspan=3, sticky="ew", padx=16, pady=(10, 6))
        langs.grid_columnconfigure((1, 4), weight=1)
        ctk.CTkLabel(langs, text=t("From"), font=theme.font(13), text_color=theme.MUTED).grid(row=0, column=0,
                                                                                            padx=(0, 8))
        self.src_picker = LanguagePicker(langs, s.job.source_lang, allow_auto=True, on_change=self._on_src)
        self.src_picker.grid(row=0, column=1, sticky="ew")
        ctk.CTkButton(langs, text="⇄", width=34, height=34, font=theme.font(15), fg_color="transparent",
                      hover_color=theme.RAISED, text_color=theme.TEXT, command=self._swap).grid(row=0, column=2,
                                                                                               padx=6)
        ctk.CTkLabel(langs, text=t("To"), font=theme.font(13), text_color=theme.MUTED).grid(row=0, column=3,
                                                                                          padx=(0, 8))
        self.tgt_picker = LanguagePicker(langs, s.job.target_lang, on_change=self._on_tgt)
        self.tgt_picker.grid(row=0, column=4, sticky="ew")

        # More options
        more = Collapsible(p, t("More options"))
        more.grid(row=7, column=0, columnspan=3, sticky="ew", padx=10, pady=(8, 12))
        self._build_options(more.body)

    def _build_options(self, body) -> None:
        job = self.settings.job
        body.grid_columnconfigure(1, weight=1)
        pad = dict(padx=(6, 6), pady=4)

        ctk.CTkLabel(body, text=t("Notes about the video"), font=theme.font(13), text_color=theme.TEXT,
                     anchor="w").grid(row=0, column=0, columnspan=3, sticky="w", **pad)
        self.notes = ctk.CTkTextbox(body, height=56, font=theme.font(13), fg_color=theme.RAISED,
                                    border_color=theme.BORDER, border_width=1, text_color=theme.TEXT, wrap="word")
        self.notes.grid(row=1, column=0, columnspan=3, sticky="ew", **pad)
        self.notes.insert("1.0", job.context_notes)
        hint(body, t("Helps AI engines choose the right words. Example: sci-fi series, casual teenage characters."),
             wrap=440).grid(row=2, column=0, columnspan=3, sticky="w", padx=6)

        ctk.CTkLabel(body, text=t("Glossary"), font=theme.font(13), text_color=theme.TEXT, anchor="w").grid(
            row=3, column=0, columnspan=3, sticky="w", padx=6, pady=(10, 4))
        self.glossary = ctk.CTkTextbox(body, height=56, font=theme.font(13), fg_color=theme.RAISED,
                                       border_color=theme.BORDER, border_width=1, text_color=theme.TEXT, wrap="none")
        self.glossary.grid(row=4, column=0, columnspan=3, sticky="ew", **pad)
        self.glossary.insert("1.0", job.glossary)
        hint(body, t("One per line. A name to keep: Winterfell. A fixed translation: King's Landing = Porto Real."),
             wrap=440).grid(row=5, column=0, columnspan=3, sticky="w", padx=6)

        grid = ctk.CTkFrame(body, fg_color="transparent")
        grid.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        grid.grid_columnconfigure(1, weight=1)
        r = 0

        def label(text):
            ctk.CTkLabel(grid, text=text, font=theme.font(13), text_color=theme.MUTED, anchor="w").grid(
                row=r, column=0, sticky="w", padx=6, pady=4)

        label(t("Formality"))
        self._formality_values = {"default": t("Default"), "formal": t("Formal"), "informal": t("Informal")}
        self.formality = ctk.CTkOptionMenu(grid, values=list(self._formality_values.values()), font=theme.font(13),
                                           fg_color=theme.RAISED, button_color=theme.BORDER, text_color=theme.TEXT,
                                           command=lambda v: self._save_options(), width=160, height=30)
        self.formality.set(self._formality_values.get(job.formality, t("Default")))
        self.formality.grid(row=r, column=1, sticky="w", padx=6, pady=4)
        r += 1
        label(t("Characters per line"))
        self.max_line = ctk.CTkEntry(grid, width=70, height=30, font=theme.font(13), fg_color=theme.RAISED,
                                     border_color=theme.BORDER, text_color=theme.TEXT)
        self.max_line.insert(0, str(job.max_line_length))
        self.max_line.grid(row=r, column=1, sticky="w", padx=6, pady=4)
        self.max_line.bind("<FocusOut>", lambda e: self._save_options())
        r += 1
        label(t("Save to"))
        out_row = ctk.CTkFrame(grid, fg_color="transparent")
        out_row.grid(row=r, column=1, sticky="ew", padx=6, pady=4)
        out_row.grid_columnconfigure(0, weight=1)
        self.out_dir = ctk.CTkEntry(out_row, height=30, font=theme.font(13), fg_color=theme.RAISED,
                                    border_color=theme.BORDER, text_color=theme.TEXT,
                                    placeholder_text=t("Same folder as the original"))
        if job.output_dir:
            self.out_dir.insert(0, job.output_dir)
        self.out_dir.grid(row=0, column=0, sticky="ew")
        self.out_dir.bind("<FocusOut>", lambda e: self._save_options())
        ctk.CTkButton(out_row, text=t("Browse"), width=80, height=30, font=theme.font(13), fg_color=theme.RAISED,
                      hover_color=theme.BORDER, text_color=theme.TEXT, command=self._browse_out).grid(
            row=0, column=1, padx=(6, 0))
        r += 1
        label(t("File name"))
        self.pattern = ctk.CTkEntry(grid, height=30, font=theme.font(13), fg_color=theme.RAISED,
                                    border_color=theme.BORDER, text_color=theme.TEXT)
        self.pattern.insert(0, job.filename_pattern)
        self.pattern.grid(row=r, column=1, sticky="ew", padx=6, pady=4)
        self.pattern.bind("<FocusOut>", lambda e: self._save_options())
        r += 1

        self.switches = {}
        for key, text in (
            ("remove_sdh", t("Remove hearing-impaired notes ([music], NAME:)")),
            ("bilingual", t("Bilingual subtitles (original below the translation)")),
            ("merge_sentences", t("Join sentences split across subtitles (offline and DeepL)")),
            ("use_cache", t("Reuse earlier translations (faster, cheaper)")),
        ):
            sw = ctk.CTkSwitch(grid, text=text, font=theme.font(13), text_color=theme.TEXT,
                               progress_color=theme.ACCENT, command=self._save_options)
            if getattr(job, key):
                sw.select()
            sw.grid(row=r, column=0, columnspan=2, sticky="w", padx=6, pady=5)
            self.switches[key] = sw
            r += 1
        for box in (self.notes, self.glossary):
            box.bind("<FocusOut>", lambda e: self._save_options())

    def _build_screen(self) -> None:
        wrap = ctk.CTkFrame(self, fg_color=theme.SCREEN, corner_radius=theme.RADIUS)
        wrap.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(0, 8))
        bar = ctk.CTkFrame(wrap, fg_color="transparent")
        bar.pack(fill="x", padx=10, pady=(8, 0))
        self.view_switch = ctk.CTkSegmentedButton(
            bar, values=[t("Preview"), t("All lines")], command=self._switch_view, font=theme.font(12), height=26,
            selected_color="#2C3346", selected_hover_color="#3A4258", unselected_color="#141822",
            unselected_hover_color="#2C3346", fg_color="#141822", text_color="#D9DCE4")
        self.view_switch.set(t("Preview"))
        self.view_switch.pack(side="left")
        self.detected_label = ctk.CTkLabel(bar, text="", font=theme.font(12), text_color="#8C93A3")
        self.detected_label.pack(side="right")
        self.screen_holder = ctk.CTkFrame(wrap, fg_color=theme.SCREEN, height=180)
        self.screen_holder.pack(fill="both", expand=True, padx=2, pady=(4, 6))
        self.screen = SubtitleScreen(self.screen_holder, height=170)
        self.table = LinesTable(self.screen_holder)
        self.screen.pack(fill="both", expand=True)

    def _build_action_bar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=2, column=0, columnspan=2, sticky="ew")
        bar.grid_columnconfigure(0, weight=1)
        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.grid(row=0, column=0, sticky="ew", padx=(2, 12))
        self.status = ctk.CTkLabel(left, text="", font=theme.font(13), text_color=theme.TEXT, anchor="w")
        self.status.pack(fill="x")
        self.progress = ctk.CTkProgressBar(left, height=8, progress_color=theme.ACCENT, fg_color=theme.RAISED,
                                           corner_radius=4)
        self.progress.set(0)
        self.open_link = Link(bar, t("Open folder"))
        self.cancel_btn = ctk.CTkButton(bar, text=t("Cancel"), width=100, height=44, font=theme.font(14),
                                        fg_color=theme.RAISED, hover_color=theme.BORDER, text_color=theme.TEXT,
                                        command=self._cancel)
        self.go_btn = ctk.CTkButton(bar, text=t("Translate"), width=210, height=44, font=theme.font(15, "bold"),
                                    fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, text_color=theme.ON_ACCENT,
                                    text_color_disabled="#6B6450", command=self._start)
        self.go_btn.grid(row=0, column=3)

    # --------------------------------------------------------- provider UI
    def _provider(self) -> providers.Provider:
        return providers.get(self.settings.provider)

    def _apply_provider(self, initial: bool = False) -> None:
        prov = self._provider()
        cat_label = dict(CATEGORIES)[prov.category]
        self.category.set(t(cat_label))
        names = [t(p.name) for p in providers.by_category(prov.category)]
        self.provider_menu.configure(values=names)
        self.provider_menu.set(t(prov.name))
        self._fill_models(prov)

        self.key_entry.configure(show="•")
        self.key_entry.delete(0, "end")
        needs_url = prov.id in ("custom", "ollama", "lmstudio")
        if prov.kind == "ct2":
            self._show_key_row(False)
        elif needs_url and not prov.needs_key and prov.id != "custom":
            self._show_key_row(True, label=t("Server URL"), secret=False)
            self.key_entry.insert(0, self.settings.base_url_for(prov.id))
        elif prov.id == "custom":
            self._show_key_row(True, label=t("Server URL"), secret=False)
            self.key_entry.insert(0, self.settings.base_urls.get("custom", ""))
        else:
            self._show_key_row(True, label=t("API key"), secret=True)
            key = get_api_key(prov.id)
            if key:
                self.key_entry.insert(0, key)
        self.key_link.configure(text=t("Get a key") if prov.key_url else (t("Get Ollama") if prov.id == "ollama" else ""))
        self.key_link.set_url(prov.key_url or ("https://ollama.com/download" if prov.id == "ollama" else None))
        self._update_status_hint()
        if not initial:
            self.settings.save()

    def _show_key_row(self, show: bool, label: str = "", secret: bool = True) -> None:
        widgets = (self.key_label, self.key_entry, self.key_save)
        if not show:
            for w in widgets:
                w.grid_remove()
            return
        for w in widgets:
            w.grid()
        self.key_label.configure(text=label)
        self.key_entry.configure(show="•" if secret else "")

    def _fill_models(self, prov: providers.Provider) -> None:
        if prov.kind == "ct2":
            values = [m.id for m in catalog.OFFLINE_MODELS]
            self.model_box.configure(values=values, state="readonly")
            current = self.settings.model_for(prov.id)
            self.model_box.set(current if current in values else values[0])
            self.refresh_btn.grid_remove()
            return
        self.refresh_btn.grid()
        self.model_box.configure(state="normal")
        values = list(prov.models)
        current = self.settings.model_for(prov.id)
        if current and current not in values:
            values.insert(0, current)
        self.model_box.configure(values=values or [""])
        self.model_box.set(current or "")
        if prov.id == "deepl":
            self.model_box.set("")
            self.model_box.configure(values=[""], state="disabled")
            self.refresh_btn.grid_remove()

    def _update_status_hint(self) -> None:
        prov = self._provider()
        text = t(prov.note) if prov.note else ""
        if prov.kind == "ct2":
            model_id = self.model_box.get()
            if downloader.is_installed(model_id):
                text = t("Installed") + ". " + t("Downloaded once, then works without internet.")
            else:
                text = t("Not downloaded yet. It downloads automatically when you translate, or in Models.")
            try:
                m = catalog.get(model_id)
                text += "\n" + (m.description_pt if ui_lang() == "pt-BR" else m.description)
            except KeyError:
                pass
        elif prov.needs_key:
            text = (t("Key saved in the system credential store.") if get_api_key(prov.id) else t("No key yet."))
            if prov.note:
                text += " " + t(prov.note)
        self.status_hint.configure(text=text)
        if prov.id in ("ollama", "lmstudio"):
            self._check_local_server(prov)

    def _check_local_server(self, prov) -> None:
        url = self.settings.base_url_for(prov.id)

        def work():
            from ..models.ollama_client import OllamaClient

            if prov.id == "ollama":
                version = OllamaClient(url).version()
                msg = t("Ollama {version} is running.", version=version) if version else t("Ollama isn't running.")
            else:
                try:
                    names = list_models(self.settings.engine_settings("lmstudio"))
                    msg = t("{n} models found.", n=len(names))
                except Exception:
                    msg = t("LM Studio server not found at {url}.", url=url)
            self.after(0, lambda: self.status_hint.configure(text=msg + (" " + t(prov.note) if prov.note else "")))

        threading.Thread(target=work, daemon=True).start()

    def _on_category(self, label: str) -> None:
        cat = next(c for c, l in CATEGORIES if t(l) == label)
        if self._provider().category == cat:
            return
        last = self.settings.models.get(f"_last_{cat}")
        options = providers.by_category(cat)
        prov = next((p for p in options if p.id == last), options[0])
        self.settings.provider = prov.id
        self._apply_provider()

    def _on_provider_name(self, name: str) -> None:
        prov = next(p for p in providers.PROVIDERS if t(p.name) == name)
        self.settings.provider = prov.id
        self.settings.models[f"_last_{prov.category}"] = prov.id
        self._apply_provider()

    def _on_model(self, value: str) -> None:
        prov = self._provider()
        value = (value or "").strip()
        if prov.id == "deepl":
            return
        if value and self.settings.models.get(prov.id) != value:
            self.settings.models[prov.id] = value
            self.settings.save()
        if prov.kind == "ct2":
            self._update_status_hint()

    def _save_key(self) -> None:
        prov = self._provider()
        value = self.key_entry.get().strip()
        if prov.id in ("custom", "ollama", "lmstudio"):
            self.settings.base_urls[prov.id] = value
            self.settings.save()
            self._update_status_hint()
            return
        where = set_api_key(prov.id, value)
        msg = t("Key saved in the system credential store.") if where == "keyring" else \
            t("Key saved in the app folder (no credential store available).")
        self.status_hint.configure(text=msg if value else t("No key yet."))
        self.key_save.configure(text=t("Saved"))
        self.after(1500, lambda: self.key_save.configure(text=t("Save")))

    def _refresh_models(self) -> None:
        if self.key_entry.winfo_ismapped() and self.key_entry.get().strip():
            self._save_key()
        cfg = self.settings.engine_settings()
        self.refresh_btn.configure(state="disabled")

        def work():
            try:
                names = list_models(cfg)
                err = None
            except Exception as exc:
                names, err = [], str(exc)
            self.after(0, lambda: self._models_loaded(names, err))

        threading.Thread(target=work, daemon=True).start()

    def _models_loaded(self, names: list[str], err: str | None) -> None:
        self.refresh_btn.configure(state="normal")
        if err:
            self.status_hint.configure(text=t("Could not load models: {error}", error=err))
            return
        if names:
            current = self.model_box.get()
            self.model_box.configure(values=names)
            if current not in names and not current:
                self.model_box.set(names[0])
                self._on_model(names[0])
        self.status_hint.configure(text=t("{n} models found.", n=len(names)))

    # ------------------------------------------------------------ options
    def _on_src(self, code: str) -> None:
        self.settings.job.source_lang = code
        self.settings.save()

    def _on_tgt(self, code: str) -> None:
        self.settings.job.target_lang = code
        self.settings.save()

    def _swap(self) -> None:
        src, tgt = self.src_picker.get(), self.tgt_picker.get()
        if src == languages.AUTO:
            return
        self.src_picker.set(tgt)
        self.tgt_picker.set(src)
        self.settings.job.source_lang, self.settings.job.target_lang = tgt, src
        self.settings.save()

    def _browse_out(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.out_dir.get() or self.settings.last_dir or None)
        if folder:
            self.out_dir.delete(0, "end")
            self.out_dir.insert(0, folder)
            self._save_options()

    def _save_options(self) -> None:
        job = self.settings.job
        job.context_notes = self.notes.get("1.0", "end").strip()
        job.glossary = self.glossary.get("1.0", "end").strip()
        inv = {v: k for k, v in self._formality_values.items()}
        job.formality = inv.get(self.formality.get(), "default")
        try:
            job.max_line_length = max(0, min(200, int(self.max_line.get())))
        except ValueError:
            pass
        job.output_dir = self.out_dir.get().strip()
        job.filename_pattern = self.pattern.get().strip() or "{name}.{lang}"
        for key, sw in self.switches.items():
            setattr(job, key, bool(sw.get()))
        self.settings.save()

    # -------------------------------------------------------------- files
    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            initialdir=self.settings.last_dir or None,
            filetypes=[(t("Subtitle files"), "*.srt *.SRT"), (t("All files"), "*.*")])
        if paths:
            self.settings.last_dir = str(Path(paths[0]).parent)
            self.files.add_paths(list(paths))

    def _add_folder(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.settings.last_dir or None)
        if folder:
            self.settings.last_dir = folder
            self.files.add_paths([folder])

    def add_paths(self, paths: list[str]) -> None:
        if self._job_thread and self._job_thread.is_alive():
            return
        self.files.add_paths(paths)

    def _update_action(self) -> None:
        n = len(self.files.paths())
        busy = bool(self._job_thread and self._job_thread.is_alive())
        if busy:
            return
        self.go_btn.configure(text=plural(n, "Translate {n} file", "Translate {n} files") if n else t("Translate"),
                              state="normal" if n else "disabled")
        hint_text = t("Add .srt files to start.")
        if not n and not self.status.cget("text"):
            self.status.configure(text=hint_text, text_color=theme.MUTED)
        elif n and self.status.cget("text") == hint_text:
            self.status.configure(text="")

    def _switch_view(self, value: str) -> None:
        if value == t("Preview"):
            self.table.pack_forget()
            self.screen.pack(fill="both", expand=True)
        else:
            self.screen.pack_forget()
            self.table.pack(fill="both", expand=True)

    # ---------------------------------------------------------------- job
    def _start(self) -> None:
        paths = self.files.paths()
        if not paths:
            return
        self._save_options()
        if self.model_box.winfo_ismapped():
            self._on_model(self.model_box.get())
        if self.key_entry.winfo_ismapped() and self._provider().id in ("custom", "ollama", "lmstudio"):
            self._save_key()
        job = self.settings.job
        job.source_lang, job.target_lang = self.src_picker.get(), self.tgt_picker.get()
        if job.source_lang == job.target_lang:
            self._set_status(t("Choose a target language different from the source."), theme.ERROR)
            return
        try:
            engine = create_engine(self.settings.engine_settings())
        except (ConfigError, EngineError) as exc:
            self._set_status(str(exc), theme.ERROR)
            return
        self.settings.save()
        cache = TranslationCache(app_paths.cache_file()) if job.use_cache else None
        self.translator = SubtitleTranslator(engine, job, cache, self.events.put)
        self.screen.reset()
        self.table.clear()
        self.files.reset_statuses()
        self.files.set_busy(True)
        self.progress.set(0)
        self.progress.pack(fill="x", pady=(4, 0))
        self.open_link.grid_forget()
        self._results = []
        self._set_status(t("Starting..."), theme.TEXT)
        self.go_btn.grid_remove()
        self.cancel_btn.configure(text=t("Cancel"), state="normal")
        self.cancel_btn.grid(row=0, column=3)
        self._job_thread = threading.Thread(target=self._run_job, args=(paths,), daemon=True)
        self._job_thread.start()

    def _run_job(self, paths: list[str]) -> None:
        try:
            self.translator.run(paths)
        except Exception as exc:  # safety net; the pipeline reports per-file errors itself
            self.events.put(Event("done", data={"results": [], "cancelled": False, "error": str(exc)}))

    def _cancel(self) -> None:
        if self.translator:
            self.translator.cancel()
            self.cancel_btn.configure(text=t("Cancelling..."), state="disabled")

    def is_busy(self) -> bool:
        return bool(self._job_thread and self._job_thread.is_alive())

    def _set_status(self, text: str, color=None) -> None:
        self.status.configure(text=text, text_color=color or theme.TEXT)

    def _poll_events(self) -> None:
        try:
            for _ in range(400):
                self._handle(self.events.get_nowait())
        except queue.Empty:
            pass
        self.after(80, self._poll_events)

    def _handle(self, ev: Event) -> None:
        name = Path(ev.file).name if ev.file else ""
        if ev.kind == "status":
            msg = ev.data.get("message", "")
            frac = ev.data.get("fraction")
            m = re.match(r"Downloading model: (.+) / (.+) MB", msg)
            msg = t("Downloading {done} of {total} MB", done=m.group(1), total=m.group(2)) if m else t(msg)
            if msg.startswith("Detected language: "):
                lang = msg.split(": ", 1)[1]
                found = next((x for x in languages.LANGUAGES if x.name == lang), None)
                self.detected_label.configure(
                    text=t("Detected language: {name}", name=found.display(ui_lang()) if found else lang))
            else:
                self._set_status(msg)
            if isinstance(frac, (int, float)):
                self.progress.set(max(0.0, min(1.0, frac)))
        elif ev.kind == "file_start":
            self._progress_start[ev.file] = time.monotonic()
            self.files.set_status(ev.file, "0%", theme.TEXT)
            self.progress.set(0)
            self._set_status(name)
        elif ev.kind == "progress":
            done, total = ev.data["done"], ev.data["total"]
            frac = done / total if total else 1.0
            self.progress.set(frac)
            self.files.set_status(ev.file, f"{int(frac * 100)}%", theme.TEXT)
            elapsed = time.monotonic() - self._progress_start.get(ev.file, time.monotonic())
            if done and elapsed > 3 and done < total:
                eta = elapsed / done * (total - done)
                self._set_status(t("{name}: {done} of {total} lines, about {eta} left", name=name, done=done,
                                   total=total, eta=_fmt_eta(eta)))
            else:
                self._set_status(t("{name}: {done} of {total} lines", name=name, done=done, total=total))
        elif ev.kind == "preview":
            d = ev.data
            original, translation = strip_tags(d["original"]), strip_tags(d["translation"])
            self.screen.show(d["index"], d.get("start"), original, translation)
            self.table.add(d["index"], original, translation)
        elif ev.kind == "warning":
            self._set_status(ev.data.get("message", ""), theme.ERROR)
        elif ev.kind == "file_done":
            result = ev.data["result"]
            self._results.append(result)
            self.files.set_status(ev.file, t("Done"), theme.SUCCESS, output=str(result.output_path))
        elif ev.kind == "file_error":
            result = ev.data["result"]
            self._results.append(result)
            cancelled = result.error == "cancelled"
            self.files.set_status(ev.file, t("Cancelled") if cancelled else t("Failed"),
                                  theme.MUTED if cancelled else theme.ERROR)
            if not cancelled:
                self._set_status(f"{name}: {result.error}", theme.ERROR)
        elif ev.kind == "done":
            self._finish(ev.data)

    def _finish(self, data: dict) -> None:
        self.files.set_busy(False)
        self.cancel_btn.grid_remove()
        self.go_btn.grid(row=0, column=3)
        results = data.get("results") or self._results
        ok = [r for r in results if r.ok]
        if data.get("error"):
            self._set_status(data["error"], theme.ERROR)
        elif data.get("cancelled"):
            self._set_status(t("Translation cancelled."), theme.MUTED)
        elif results:
            failed = [r for r in results if not r.ok]
            text = t("{ok} of {total} files translated.", ok=len(ok), total=len(results))
            if failed and len(results) == 1:
                text = f"{Path(failed[0].input_path).name}: {failed[0].error}"
            self._set_status(text, theme.SUCCESS if not failed else theme.ERROR)
            if ok:
                self.progress.set(1)
        if ok:
            last = ok[-1].output_path
            self.open_link._command = lambda p=last: reveal_file(p)
            self.open_link.grid(row=0, column=2, padx=(0, 14))
        self._update_action()
        self.translator = None
