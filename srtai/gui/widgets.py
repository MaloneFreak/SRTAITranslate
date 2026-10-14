"""Reusable widgets: language picker, file queue, preview screen, lines table."""
from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
import webbrowser
from datetime import timedelta
from pathlib import Path
from tkinter import ttk
from typing import Callable, Optional

import customtkinter as ctk

from .. import languages
from . import theme
from .i18n import current as ui_lang
from .i18n import plural, t


def open_path(path: str | Path) -> None:
    path = str(path)
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except OSError:
        pass


def reveal_file(path: str | Path) -> None:
    path = Path(path)
    if sys.platform == "win32" and path.exists():
        subprocess.Popen(["explorer", "/select,", str(path)])
    else:
        open_path(path.parent)


class Link(ctk.CTkLabel):
    def __init__(self, master, text: str, url: str | None = None, command: Callable | None = None, **kw):
        super().__init__(master, text=text, text_color=theme.LINK, cursor="hand2",
                         font=kw.pop("font", theme.font(12)), **kw)
        self._url, self._command = url, command
        self.bind("<Button-1>", self._click)

    def _click(self, _event=None):
        if self._command:
            self._command()
        elif self._url:
            webbrowser.open(self._url)

    def set_url(self, url: str | None) -> None:
        self._url = url


def section_title(master, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(master, text=text, font=theme.font(15, "bold"), text_color=theme.TEXT, anchor="w")


def hint(master, text: str, wrap: int = 420) -> ctk.CTkLabel:
    return ctk.CTkLabel(master, text=text, font=theme.font(12), text_color=theme.MUTED, anchor="w",
                        justify="left", wraplength=wrap)


# --- Language picker -----------------------------------------------------

class LanguagePicker(ctk.CTkButton):
    """A button that opens a searchable language list."""

    def __init__(self, master, code: str, allow_auto: bool = False,
                 on_change: Optional[Callable[[str], None]] = None, **kw):
        super().__init__(master, text="", command=self._open, anchor="w", height=34,
                         fg_color=theme.RAISED, hover_color=theme.BORDER, text_color=theme.TEXT,
                         border_width=1, border_color=theme.BORDER, corner_radius=6, font=theme.font(13), **kw)
        self.allow_auto = allow_auto
        self.on_change = on_change
        self._popup: Optional[ctk.CTkToplevel] = None
        self.set(code)

    def get(self) -> str:
        return self._code

    def set(self, code: str) -> None:
        if code == languages.AUTO and self.allow_auto:
            self._code = languages.AUTO
            label = t("Auto-detect")
        else:
            lang = languages.get(code) or languages.require("pt-BR")
            self._code = lang.code
            label = lang.display(ui_lang())
        self.configure(text=f"{label}  ▾")

    def _items(self) -> list[tuple[str, str]]:
        items = [(lang.code, lang.display(ui_lang())) for lang in languages.sorted_for_ui(ui_lang())]
        if self.allow_auto:
            items.insert(0, (languages.AUTO, t("Auto-detect")))
        return items

    def _open(self) -> None:
        if self._popup is not None and self._popup.winfo_exists():
            self._popup.destroy()
            return
        popup = ctk.CTkToplevel(self)
        popup.withdraw()
        popup.overrideredirect(True)
        popup.configure(fg_color=theme.SURFACE)
        frame = ctk.CTkFrame(popup, fg_color=theme.SURFACE, border_width=1, border_color=theme.BORDER,
                             corner_radius=0)
        frame.pack(fill="both", expand=True)
        search = ctk.CTkEntry(frame, placeholder_text=t("Search languages"), font=theme.font(13))
        search.pack(fill="x", padx=8, pady=(8, 4))
        box = tk.Listbox(frame, activestyle="none", exportselection=False, height=12, borderwidth=0,
                         highlightthickness=0, font=(theme.UI_FAMILY, 12),
                         bg=theme.pick(theme.SURFACE), fg=theme.pick(theme.TEXT),
                         selectbackground=theme.ACCENT, selectforeground=theme.ON_ACCENT)
        box.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        items = self._items()
        shown: list[tuple[str, str]] = []

        def refill(_e=None):
            query = search.get().strip().casefold()
            shown.clear()
            box.delete(0, "end")
            for code, label in items:
                if not query or query in label.casefold() or query == code.casefold():
                    shown.append((code, label))
                    box.insert("end", label)
            if shown:
                idx = next((i for i, (c, _) in enumerate(shown) if c == self._code), 0)
                box.selection_set(idx)
                box.see(idx)

        def choose(_e=None):
            sel = box.curselection()
            if sel:
                code = shown[sel[0]][0]
                self.set(code)
                if self.on_change:
                    self.on_change(code)
            popup.destroy()

        def move(delta):
            sel = box.curselection()
            idx = (sel[0] if sel else -1) + delta
            idx = max(0, min(len(shown) - 1, idx))
            box.selection_clear(0, "end")
            box.selection_set(idx)
            box.see(idx)
            return "break"

        search.bind("<KeyRelease>", lambda e: refill() if e.keysym not in ("Up", "Down", "Return", "Escape") else None)
        search.bind("<Down>", lambda e: move(1))
        search.bind("<Up>", lambda e: move(-1))
        search.bind("<Return>", choose)
        popup.bind("<Escape>", lambda e: popup.destroy())
        box.bind("<ButtonRelease-1>", choose)
        box.bind("<Return>", choose)
        refill()
        x, y = self.winfo_rootx(), self.winfo_rooty() + self.winfo_height() + 2
        width = max(260, self.winfo_width())
        popup.geometry(f"{width}x330+{x}+{y}")
        popup.deiconify()
        popup.lift()
        popup.after(30, lambda: (search.focus_force()))
        popup.bind("<FocusOut>", lambda e: popup.after(150, lambda: _close_if_unfocused(popup)))
        self._popup = popup


def _close_if_unfocused(popup) -> None:
    try:
        focused = popup.focus_get()
    except (KeyError, tk.TclError):
        focused = None
    if popup.winfo_exists() and (focused is None or not str(focused).startswith(str(popup))):
        popup.destroy()


# --- File queue ----------------------------------------------------------

class FileQueue(ctk.CTkFrame):
    def __init__(self, master, on_change: Optional[Callable[[], None]] = None, on_add: Optional[Callable] = None,
                 on_add_folder: Optional[Callable] = None):
        super().__init__(master, fg_color=theme.SURFACE, corner_radius=theme.RADIUS)
        self.on_change = on_change
        self._rows: dict[str, dict] = {}
        self._outputs: dict[str, str] = {}

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 4))
        section_title(header, t("Files")).pack(side="left")
        self.count_label = ctk.CTkLabel(header, text="", font=theme.font(12), text_color=theme.MUTED)
        self.count_label.pack(side="right")

        self.list = ctk.CTkScrollableFrame(self, fg_color=theme.RAISED, corner_radius=6)
        self.list.pack(fill="both", expand=True, padx=14, pady=4)
        self.empty = ctk.CTkLabel(self.list, text=t("Drop .srt files here, or use the buttons below."),
                                  font=theme.font(13), text_color=theme.MUTED, wraplength=260, justify="center")
        self.empty.pack(fill="x", pady=40, padx=10)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=14, pady=(6, 14))
        kw = dict(height=32, font=theme.font(13), fg_color=theme.RAISED, hover_color=theme.BORDER,
                  text_color=theme.TEXT, border_width=1, border_color=theme.BORDER)
        ctk.CTkButton(buttons, text=t("Add files"), command=on_add, width=110, **kw).pack(side="left")
        ctk.CTkButton(buttons, text=t("Add folder"), command=on_add_folder, width=110, **kw).pack(side="left", padx=6)
        self.clear_btn = ctk.CTkButton(buttons, text=t("Clear"), command=self.clear, width=70, **kw)
        self.clear_btn.pack(side="right")
        self._update_count()

    def drop_widgets(self) -> list:
        return [self, self.list, self.empty]

    def paths(self) -> list[str]:
        return list(self._rows)

    def add_paths(self, paths: list[str]) -> int:
        added = 0
        for raw in paths:
            path = Path(raw)
            candidates = sorted(p for p in path.iterdir() if p.suffix.lower() == ".srt") if path.is_dir() else [path]
            for p in candidates:
                key = str(p.resolve())
                if p.suffix.lower() != ".srt" or key in self._rows or not p.exists():
                    continue
                self._add_row(key)
                added += 1
        self._update_count()
        if added and self.on_change:
            self.on_change()
        return added

    def _add_row(self, key: str) -> None:
        self.empty.pack_forget()
        row = ctk.CTkFrame(self.list, fg_color="transparent")
        row.pack(fill="x", pady=1)
        name = ctk.CTkLabel(row, text=Path(key).name, font=theme.font(13), text_color=theme.TEXT, anchor="w")
        name.pack(side="left", fill="x", expand=True, padx=(8, 4))
        status = ctk.CTkLabel(row, text=t("Ready"), font=theme.font(12), text_color=theme.MUTED, width=90,
                              anchor="e")
        status.pack(side="left", padx=4)
        remove = ctk.CTkButton(row, text="✕", width=26, height=24, font=theme.font(12),
                               fg_color="transparent", hover_color=theme.BORDER, text_color=theme.MUTED,
                               command=lambda k=key: self.remove(k))
        remove.pack(side="left", padx=(0, 4))
        self._rows[key] = {"frame": row, "status": status, "remove": remove, "name": name}

    def remove(self, key: str) -> None:
        row = self._rows.pop(key, None)
        if row:
            row["frame"].destroy()
        self._outputs.pop(key, None)
        if not self._rows:
            self.empty.pack(fill="x", pady=40, padx=10)
        self._update_count()
        if self.on_change:
            self.on_change()

    def clear(self) -> None:
        for key in list(self._rows):
            self._rows.pop(key)["frame"].destroy()
        self._outputs.clear()
        self.empty.pack(fill="x", pady=40, padx=10)
        self._update_count()
        if self.on_change:
            self.on_change()

    def set_status(self, key: str, text: str, color=None, output: Optional[str] = None) -> None:
        row = self._rows.get(str(Path(key).resolve())) or self._rows.get(key)
        if not row:
            return
        row["status"].configure(text=text, text_color=color or theme.MUTED, cursor="hand2" if output else "")
        if output:
            self._outputs[key] = output
            row["status"].bind("<Button-1>", lambda e, o=output: reveal_file(o))
            row["name"].bind("<Button-1>", lambda e, o=output: reveal_file(o))

    def reset_statuses(self) -> None:
        for key, row in self._rows.items():
            row["status"].configure(text=t("Waiting"), text_color=theme.MUTED)

    def set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.clear_btn.configure(state=state)
        for row in self._rows.values():
            row["remove"].configure(state=state)

    def _update_count(self) -> None:
        n = len(self._rows)
        self.count_label.configure(text=plural(n, "{n} file", "{n} files") if n else "")


# --- Preview screen ------------------------------------------------------

def format_timecode(td: timedelta) -> str:
    total = int(td.total_seconds())
    ms = int(td.microseconds / 1000)
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d},{ms:03d}"


class SubtitleScreen(tk.Canvas):
    """A small 'cinema screen' that shows the line being translated, styled like a subtitle."""

    def __init__(self, master, height: int = 170):
        super().__init__(master, height=height, bg=theme.SCREEN, highlightthickness=0, borderwidth=0)
        self._data: Optional[dict] = None
        self.bind("<Configure>", lambda e: self._draw())

    def show(self, index: int, start: Optional[timedelta], original: str, translation: str) -> None:
        self._data = {"index": index, "start": start, "original": original, "translation": translation}
        self._draw()

    def reset(self) -> None:
        self._data = None
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        w, h = max(self.winfo_width(), 200), max(self.winfo_height(), 120)
        ui = theme.UI_FAMILY
        if not self._data:
            self.create_text(w / 2, h / 2, text=t("Translated lines appear here as they're ready."),
                             fill="#5A6172", font=(ui, 13), width=w - 60, justify="center")
            return
        d = self._data
        if d["start"] is not None:
            self.create_text(16, 14, text=format_timecode(d["start"]), anchor="nw", fill="#6B7385",
                             font=(theme.MONO_FAMILY, 10))
        self.create_text(w - 16, 14, text=f"#{d['index']}", anchor="ne", fill="#6B7385",
                         font=(theme.MONO_FAMILY, 10))
        self.create_text(w / 2, h * 0.36, text=d["original"], fill=theme.SCREEN_ORIGINAL, font=(ui, 12),
                         width=w - 80, justify="center")
        y = h * 0.72
        size = 20 if len(d["translation"]) < 90 else 16
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (2, 2)):
            self.create_text(w / 2 + dx, y + dy, text=d["translation"], fill="#000000",
                             font=(ui, size, "bold"), width=w - 80, justify="center")
        self.create_text(w / 2, y, text=d["translation"], fill=theme.ACCENT, font=(ui, size, "bold"),
                         width=w - 80, justify="center")


class LinesTable(ctk.CTkFrame):
    MAX_ROWS = 20000

    def __init__(self, master):
        super().__init__(master, fg_color=theme.SCREEN, corner_radius=0)
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("Lines.Treeview", background="#141822", fieldbackground="#141822", foreground="#D9DCE4",
                        rowheight=24, borderwidth=0, font=(theme.UI_FAMILY, 11))
        style.configure("Lines.Treeview.Heading", background="#1D2230", foreground="#9AA3B8", relief="flat",
                        font=(theme.UI_FAMILY, 11, "bold"))
        style.map("Lines.Treeview", background=[("selected", "#2C3346")], foreground=[("selected", "#FFFFFF")])
        self.tree = ttk.Treeview(self, columns=("n", "orig", "tr"), show="headings", style="Lines.Treeview")
        self.tree.heading("n", text="#")
        self.tree.heading("orig", text=t("Original"), anchor="w")
        self.tree.heading("tr", text=t("Translation"), anchor="w")
        self.tree.column("n", width=56, stretch=False, anchor="e")
        self.tree.column("orig", width=360, anchor="w")
        self.tree.column("tr", width=360, anchor="w")
        scroll = ctk.CTkScrollbar(self, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self._count = 0

    def add(self, index: int, original: str, translation: str) -> None:
        if self._count >= self.MAX_ROWS:
            return
        item = self.tree.insert("", "end", values=(index, original.replace("\n", " / "),
                                                   translation.replace("\n", " / ")))
        self._count += 1
        first, last = self.tree.yview()
        if last > 0.97:
            self.tree.see(item)

    def clear(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._count = 0


class Collapsible(ctk.CTkFrame):
    def __init__(self, master, title: str, opened: bool = False, on_toggle: Optional[Callable[[bool], None]] = None):
        super().__init__(master, fg_color="transparent")
        self._title = title
        self._open = opened
        self.on_toggle = on_toggle
        self.button = ctk.CTkButton(self, text="", anchor="w", fg_color="transparent", hover_color=theme.RAISED,
                                    text_color=theme.TEXT, font=theme.font(13, "bold"), height=30,
                                    command=self.toggle)
        self.button.pack(fill="x")
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self._refresh()

    def toggle(self) -> None:
        self._open = not self._open
        self._refresh()
        if self.on_toggle:
            self.on_toggle(self._open)

    def _refresh(self) -> None:
        self.button.configure(text=f"{'▾' if self._open else '▸'}  {self._title}")
        if self._open:
            self.body.pack(fill="x", pady=(4, 0))
        else:
            self.body.pack_forget()
