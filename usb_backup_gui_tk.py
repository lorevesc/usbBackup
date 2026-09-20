#!/usr/bin/env python3
"""USB Backup - applicazione desktop (Tkinter, nessuna dipendenza).

Finestra nativa con tema scuro disegnato a mano: niente widget di sistema
grigi, niente browser. Configura i tre piani di backup e li lancia.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

sys.path.insert(0, str(Path(__file__).resolve().parent))
import usb_backup as ub  # noqa: E402

# --------------------------------------------------------------------------
# palette e font
# --------------------------------------------------------------------------
BG = "#0e1116"        # sfondo finestra
SIDE = "#12161e"      # barra laterale
PANEL = "#151a23"     # sfondo contenuto
CARD = "#1a2029"      # scheda
CARD_HI = "#202834"   # scheda in hover
INPUT = "#0f1319"     # campi
LINE = "#252d3a"      # bordi
LINE_HI = "#36415420"
TEXT = "#e7eaf0"
MUTED = "#98a3b8"
DIM = "#69738a"
ACCENT = "#5b9dff"
ACCENT_DK = "#24395e"
OK = "#3ecf8e"
WARN = "#f2b45c"
DANGER = "#ff6b6b"

if sys.platform == "darwin":
    F_UI = ("SF Pro Text", 13)
    F_UI_B = ("SF Pro Text", 13, "bold")
    F_SM = ("SF Pro Text", 11)
    F_H = ("SF Pro Display", 15, "bold")
    F_MONO = ("SF Mono", 11)
else:
    F_UI = ("Segoe UI", 10)
    F_UI_B = ("Segoe UI Semibold", 10)
    F_SM = ("Segoe UI", 8)
    F_H = ("Segoe UI Semibold", 12)
    F_MONO = ("Consolas", 9)


# --------------------------------------------------------------------------
# widget disegnati a mano
# --------------------------------------------------------------------------

class Btn(tk.Frame):
    """Bottone piatto: Frame + Label, cosi' i colori valgono anche su macOS."""

    STYLES = {
        "primary": (ACCENT, "#0a1220", "#7ab0ff", ACCENT),
        "normal":  (CARD, TEXT, CARD_HI, LINE),
        "ghost":   (PANEL, MUTED, CARD, LINE),
        "danger":  (PANEL, DANGER, "#2a1a1e", "#4a2a30"),
    }

    def __init__(self, master, text, command=None, kind="normal", pad=(14, 7), **kw):
        bg, fg, hover, border = self.STYLES[kind]
        super().__init__(master, bg=bg, highlightthickness=1,
                         highlightbackground=border, highlightcolor=border,
                         cursor="hand2", **kw)
        self.command = command
        self.bg, self.hover, self.enabled = bg, hover, True
        self.label = tk.Label(self, text=text, bg=bg, fg=fg, font=F_UI,
                              padx=pad[0], pady=pad[1])
        self.label.pack()
        for widget in (self, self.label):
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)
            widget.bind("<Button-1>", self._on_click)

    def _paint(self, color):
        self.configure(bg=color)
        self.label.configure(bg=color)

    def _on_enter(self, _e=None):
        if self.enabled:
            self._paint(self.hover)

    def _on_leave(self, _e=None):
        self._paint(self.bg)

    def _on_click(self, _e=None):
        if self.enabled and self.command:
            self.command()

    def set_text(self, text):
        self.label.configure(text=text)

    def set_enabled(self, value: bool):
        self.enabled = value
        self.label.configure(fg=DIM if not value else self.STYLES["normal"][1])
        self.configure(cursor="arrow" if not value else "hand2")


class Switch(tk.Frame):
    """Interruttore disegnato su Canvas, con etichetta a fianco."""

    def __init__(self, master, text="", value=False, command=None, bg=CARD, wrap=0):
        super().__init__(master, bg=bg)
        self.value = bool(value)
        self.command = command
        self.canvas = tk.Canvas(self, width=40, height=22, bg=bg,
                                highlightthickness=0, cursor="hand2")
        self.canvas.pack(side="left")
        self.label = tk.Label(self, text=text, bg=bg, fg=MUTED, font=F_UI,
                              anchor="w", justify="left", wraplength=wrap or 0)
        self.label.pack(side="left", padx=(9, 0))
        for widget in (self.canvas, self.label):
            widget.bind("<Button-1>", self._toggle)
        self._draw()

    def _rounded(self, x0, y0, x1, y1, r, color):
        self.canvas.create_oval(x0, y0, x0 + 2 * r, y1, fill=color, outline=color)
        self.canvas.create_oval(x1 - 2 * r, y0, x1, y1, fill=color, outline=color)
        self.canvas.create_rectangle(x0 + r, y0, x1 - r, y1, fill=color, outline=color)

    def _draw(self):
        self.canvas.delete("all")
        track = "#1d4a39" if self.value else "#232a37"
        knob = OK if self.value else "#5d6880"
        self._rounded(1, 2, 39, 20, 9, track)
        cx = 30 if self.value else 11
        self.canvas.create_oval(cx - 7, 4, cx + 7, 18, fill=knob, outline=knob)
        self.label.configure(fg=TEXT if self.value else MUTED)

    def _toggle(self, _e=None):
        self.set(not self.value)
        if self.command:
            self.command(self.value)

    def get(self) -> bool:
        return self.value

    def set(self, value: bool):
        self.value = bool(value)
        self._draw()

    def set_text(self, text):
        self.label.configure(text=text)


def card(master, title=None, subtitle=None, pad=16) -> tk.Frame:
    """Scheda: contenitore con bordo sottile e titolo."""
    outer = tk.Frame(master, bg=CARD, highlightthickness=1,
                     highlightbackground=LINE, highlightcolor=LINE)
    outer.pack(fill="x", pady=(0, 14))
    inner = tk.Frame(outer, bg=CARD)
    inner.pack(fill="both", expand=True, padx=pad, pady=pad)
    if title:
        head = tk.Frame(inner, bg=CARD)
        head.pack(fill="x")
        tk.Label(head, text=title, bg=CARD, fg=TEXT, font=F_H).pack(side="left")
        outer.title_extra = head
    if subtitle is not None:
        outer.sub = tk.Label(inner, text=subtitle, bg=CARD, fg=DIM, font=F_SM,
                             anchor="w", justify="left")
        outer.sub.pack(fill="x", pady=(3, 0))
    outer.body = inner
    return outer


def tag(master, text, color=ACCENT, bgc=ACCENT_DK) -> tk.Label:
    lbl = tk.Label(master, text=text, bg=bgc, fg=color, font=F_SM, padx=7, pady=2)
    lbl.pack(side="left", padx=(9, 0))
    return lbl


def field_label(master, text) -> tk.Label:
    lbl = tk.Label(master, text=text, bg=CARD, fg=MUTED, font=F_SM, anchor="w")
    lbl.pack(fill="x", pady=(14, 5))
    return lbl


def hint(master, text) -> tk.Label:
    lbl = tk.Label(master, text=text, bg=CARD, fg=DIM, font=F_SM, anchor="w",
                   justify="left")
    lbl.pack(fill="x", pady=(5, 0))
    return lbl


def entry(master, **kw) -> tk.Entry:
    widget = tk.Entry(master, bg=INPUT, fg=TEXT, font=F_UI, relief="flat",
                      insertbackground=TEXT, highlightthickness=1,
                      highlightbackground=LINE, highlightcolor=ACCENT, **kw)
    widget.configure(borderwidth=6)
    return widget


def textbox(master, height=4) -> tk.Text:
    widget = tk.Text(master, height=height, bg=INPUT, fg=TEXT, font=F_MONO,
                     relief="flat", insertbackground=TEXT, highlightthickness=1,
                     highlightbackground=LINE, highlightcolor=ACCENT, wrap="none",
                     borderwidth=6)
    return widget


class SlimScroll(tk.Canvas):
    """Scrollbar sottile disegnata a mano: niente frecce, sparisce se inutile."""

    WIDTH = 9

    def __init__(self, master, yview, bg=PANEL):
        super().__init__(master, width=self.WIDTH, bg=bg, highlightthickness=0,
                         borderwidth=0)
        self.yview = yview
        self.first, self.last = 0.0, 1.0
        self.bind("<Button-1>", self._grab)
        self.bind("<B1-Motion>", self._grab)
        self.bind("<Configure>", lambda _e: self._draw())

    def set(self, first, last):
        self.first, self.last = float(first), float(last)
        self._draw()

    def _draw(self):
        self.delete("all")
        height = self.winfo_height()
        if height <= 1 or (self.first <= 0.001 and self.last >= 0.999):
            return
        top = self.first * height
        bottom = max(self.last * height, top + 30)
        self.create_rectangle(2, top + 2, self.WIDTH - 1, bottom - 2,
                              fill="#3a4559", outline="")

    def _grab(self, event):
        height = max(1, self.winfo_height())
        span = max(0.02, self.last - self.first)
        frac = (event.y - span * height / 2) / height
        self.yview("moveto", min(max(frac, 0.0), 1.0 - span))


class ScrollArea(tk.Frame):
    """Area scorrevole verticale con il contenuto in `.inner`."""

    def __init__(self, master, bg=PANEL):
        super().__init__(master, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.bar = SlimScroll(self, self.canvas.yview, bg=bg)
        self.bar.pack(side="right", fill="y", padx=(4, 0))
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda _e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(
            self.window, width=e.width))
        self.canvas.bind_all("<MouseWheel>", self._wheel, add="+")

    def _wheel(self, event):
        if not self.winfo_ismapped():
            return
        widget = self.winfo_toplevel().winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget is self:
                step = -1 if event.delta > 0 else 1
                self.canvas.yview_scroll(step, "units")
                return
            widget = getattr(widget, "master", None)


class FolderList(tk.Frame):
    """Righe 'cartella -> nome destinazione' con campo per il nome e rimozione."""

    def __init__(self, master, on_pick, on_change=None, bg=CARD):
        super().__init__(master, bg=bg)
        self.on_pick = on_pick
        self.on_change = on_change
        self.bgc = bg
        self.rows: list[dict] = []
        self.holder = tk.Frame(self, bg=bg)
        self.holder.pack(fill="x")
        self.add_btn = Btn(self, "+  Aggiungi cartella", self._add, "normal", pad=(12, 6))
        self.add_btn.pack(anchor="w", pady=(9, 0))

    # -- dati --
    def set_rows(self, rows):
        self.rows = [dict(r) for r in rows]
        self.render()

    def get_rows(self):
        return [r for r in self.rows if r.get("path")]

    def set_add_text(self, text):
        self.add_btn.set_text(text)

    # -- disegno --
    def render(self):
        for child in self.holder.winfo_children():
            child.destroy()
        if not self.rows:
            tk.Label(self.holder, text="Nessuna cartella impostata.", bg=self.bgc,
                     fg=DIM, font=F_SM, anchor="w").pack(fill="x", pady=(2, 0))
            return
        for index, row in enumerate(self.rows):
            line = tk.Frame(self.holder, bg=INPUT, highlightthickness=1,
                            highlightbackground=LINE)
            line.pack(fill="x", pady=3)
            src = row["path"] if row["path"] != "." else "(tutta la chiavetta)"
            tk.Label(line, text=src, bg=INPUT, fg=TEXT, font=F_MONO, anchor="w",
                     padx=10, pady=7).pack(side="left", fill="x", expand=True)
            tk.Label(line, text="→", bg=INPUT, fg=DIM, font=F_UI).pack(side="left", padx=4)
            alias = tk.Entry(line, bg=CARD, fg=TEXT, font=F_MONO, relief="flat",
                             insertbackground=TEXT, highlightthickness=1,
                             highlightbackground=LINE, highlightcolor=ACCENT,
                             borderwidth=5, width=18)
            alias.insert(0, row.get("as", ""))
            alias.pack(side="left", padx=(0, 6), pady=5)
            default = "root" if row["path"] == "." else Path(row["path"].rstrip("/\\")).name
            if not row.get("as"):
                alias.insert(0, "")
                alias.configure(fg=DIM)
                alias.insert(0, default)
                alias.bind("<FocusIn>", lambda _e, a=alias, d=default: self._clear_ph(a, d))
            alias.bind("<KeyRelease>", lambda _e, r=row, a=alias, d=default:
                       self._alias_changed(r, a, d))
            row["_entry"], row["_default"] = alias, default
            remove = tk.Label(line, text="✕", bg=INPUT, fg=DIM, font=F_UI,
                              padx=10, cursor="hand2")
            remove.pack(side="left")
            remove.bind("<Button-1>", lambda _e, i=index: self._remove(i))
            remove.bind("<Enter>", lambda e: e.widget.configure(fg=DANGER))
            remove.bind("<Leave>", lambda e: e.widget.configure(fg=DIM))

    def _clear_ph(self, widget, default):
        if widget.get() == default and str(widget.cget("fg")) == DIM:
            widget.delete(0, tk.END)
            widget.configure(fg=TEXT)

    def _alias_changed(self, row, widget, default):
        value = widget.get().strip()
        row["as"] = "" if value == default else value
        widget.configure(fg=TEXT if value else DIM)
        if self.on_change:
            self.on_change()

    def _remove(self, index):
        del self.rows[index]
        self.render()
        if self.on_change:
            self.on_change()

    def _add(self):
        path = self.on_pick()
        if not path or any(r["path"] == path for r in self.rows):
            return
        self.rows.append({"path": path, "as": ""})
        self.render()
        if self.on_change:
            self.on_change()


# --------------------------------------------------------------------------
# utilita'
# --------------------------------------------------------------------------

def lines_of(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def folders_from_json(raw) -> list[dict]:
    if isinstance(raw, str):
        raw = [raw]
    rows = []
    for item in raw or []:
        if isinstance(item, str):
            rows.append({"path": item, "as": ""})
        elif isinstance(item, dict):
            rows.append({"path": str(item.get("path", "")),
                         "as": str(item.get("as", "") or "")})
    return [r for r in rows if r["path"]]


def folders_to_json(rows: list[dict]) -> list:
    out = []
    for row in rows:
        alias = (row.get("as") or "").strip()
        out.append({"path": row["path"], "as": alias} if alias else row["path"])
    return out


def relative_to_volume(chosen: str, volume: Path) -> str | None:
    try:
        rel = Path(chosen).resolve().relative_to(Path(volume).resolve())
    except (ValueError, OSError):
        return None
    return rel.as_posix() or "."


def reveal(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
        if ub.IS_WIN:
            os.startfile(str(path))  # noqa: S606
        elif ub.IS_MAC:
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception as exc:
        messagebox.showerror("Errore", f"{path}\n{exc}")


# --------------------------------------------------------------------------
# applicazione
# --------------------------------------------------------------------------

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("USB Backup")
        root.configure(bg=BG)
        width = min(1500, max(1040, int(root.winfo_screenwidth() * 0.72)))
        height = min(1020, max(720, int(root.winfo_screenheight() * 0.78)))
        root.geometry(f"{width}x{height}+{(root.winfo_screenwidth() - width) // 2}+60")
        root.minsize(1000, 700)

        self.cfg = ub.load_config()
        ub.setup_log(self.cfg.get("log_file"))
        self.volumes: list[tuple[Path, bool]] = []
        self.volume: Path | None = None
        self.volume_label = ""
        self.removable = True
        self.busy = False
        self.stop_event = threading.Event()
        self.watcher: threading.Thread | None = None
        self.log_queue: list[str] = []
        ub.add_log_sink(self.log_queue.append)

        self._build()
        self.refresh_volumes()
        self.load_pc_plan()
        self.load_cfg()
        self.root.after(150, self._drain)

    # ------------------------------------------------------------- struttura
    def _build(self):
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True)

        self._build_sidebar(body)

        right = tk.Frame(body, bg=PANEL)
        right.pack(side="left", fill="both", expand=True)

        self.header = tk.Frame(right, bg=PANEL)
        self.header.pack(fill="x", padx=26, pady=(22, 10))
        self.h_title = tk.Label(self.header, text="Chiavette", bg=PANEL, fg=TEXT,
                                font=("Segoe UI Semibold", 17) if not ub.IS_MAC
                                else ("SF Pro Display", 20, "bold"), anchor="w")
        self.h_title.pack(side="left")
        self.h_sub = tk.Label(self.header, text="", bg=PANEL, fg=DIM, font=F_SM, anchor="w")
        self.h_sub.pack(side="left", padx=(12, 0), pady=(6, 0))

        self.panes = {}
        holder = tk.Frame(right, bg=PANEL)
        holder.pack(fill="both", expand=True, padx=26)
        for key in ("stick", "pc", "cfg"):
            area = ScrollArea(holder)
            self.panes[key] = area
        self._build_stick(self.panes["stick"].inner)
        self._build_pc(self.panes["pc"].inner)
        self._build_cfg(self.panes["cfg"].inner)
        self.show_pane("stick")

        self._build_log(right)

    def _build_sidebar(self, parent):
        side = tk.Frame(parent, bg=SIDE, width=252)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)

        brand = tk.Frame(side, bg=SIDE)
        brand.pack(fill="x", padx=18, pady=(22, 26))
        mark = tk.Label(brand, text="⛁", bg=ACCENT, fg="#0a1220",
                        font=F_UI_B, width=2, pady=4)
        mark.pack(side="left")
        tk.Label(brand, text="USB Backup", bg=SIDE, fg=TEXT,
                 font=F_UI_B, anchor="w").pack(side="left", padx=10)

        self.nav = {}
        for key, text in (("stick", "Chiavette"), ("pc", "Questo PC"),
                          ("cfg", "Impostazioni")):
            item = tk.Frame(side, bg=SIDE, cursor="hand2")
            item.pack(fill="x")
            bar = tk.Frame(item, bg=SIDE, width=3)
            bar.pack(side="left", fill="y")
            label = tk.Label(item, text=text, bg=SIDE, fg=MUTED, font=F_UI,
                             anchor="w", padx=15, pady=11)
            label.pack(side="left", fill="x", expand=True)
            for widget in (item, label):
                widget.bind("<Button-1>", lambda _e, k=key: self.show_pane(k))
                widget.bind("<Enter>", lambda _e, k=key: self._nav_hover(k, True))
                widget.bind("<Leave>", lambda _e, k=key: self._nav_hover(k, False))
            self.nav[key] = (item, bar, label)

        bottom = tk.Frame(side, bg=SIDE)
        bottom.pack(side="bottom", fill="x", padx=18, pady=20)
        self.sw_watch = Switch(bottom, "sorveglianza spenta", False,
                               command=self.toggle_watch, bg=SIDE, wrap=110)
        self.sw_watch.pack(anchor="w")
        tk.Label(bottom, text="Copia da sola a ogni\nchiavetta collegata.", bg=SIDE,
                 fg=DIM, font=F_SM, justify="left").pack(anchor="w", pady=(9, 0))

    def _nav_hover(self, key, on):
        item, bar, label = self.nav[key]
        if getattr(self, "current_pane", None) == key:
            return
        color = "#171c25" if on else SIDE
        item.configure(bg=color)
        bar.configure(bg=color)
        label.configure(bg=color, fg=TEXT if on else MUTED)

    def show_pane(self, key):
        self.current_pane = key
        for name, (item, bar, label) in self.nav.items():
            active = name == key
            item.configure(bg=PANEL if active else SIDE)
            bar.configure(bg=ACCENT if active else (PANEL if active else SIDE))
            label.configure(bg=PANEL if active else SIDE, fg=TEXT if active else MUTED)
        for name, area in self.panes.items():
            area.pack_forget()
        self.panes[key].pack(fill="both", expand=True)
        titles = {"stick": ("Chiavette", "cosa copiare da ogni chiavetta"),
                  "pc": ("Questo PC", "cosa scambiare tra PC e chiavetta"),
                  "cfg": ("Impostazioni", "destinazione, notifiche, avvio automatico")}
        self.h_title.configure(text=titles[key][0])
        self.h_sub.configure(text=titles[key][1])

    # ---------------------------------------------------------- pane chiavette
    def _build_stick(self, parent):
        box = card(parent, "Volumi collegati", "Seleziona una chiavetta per configurarla.")
        Btn(box.title_extra, "Aggiorna", self.refresh_volumes, "ghost",
            pad=(11, 4)).pack(side="right")
        self.vol_holder = tk.Frame(box.body, bg=CARD)
        self.vol_holder.pack(fill="x", pady=(14, 0))

        self.stick_card = card(parent, "backup.json della chiavetta", "—")
        tag(self.stick_card.title_extra, "CHIAVETTA → PC", "#b9d4ff", ACCENT_DK)
        body = self.stick_card.body

        field_label(body, "Nome della cartella di destinazione")
        self.st_name = entry(body)
        self.st_name.pack(fill="x")
        self.st_name.bind("<KeyRelease>", lambda _e: self.update_stick_dest())
        hint(body, "Vuoto = etichetta del volume.")

        field_label(body, "Cartelle della chiavetta da copiare sul PC")
        self.st_folders = FolderList(body, self._pick_stick_folder, self.update_stick_dest)
        self.st_folders.pack(fill="x")

        cols = tk.Frame(body, bg=CARD)
        cols.pack(fill="x", pady=(4, 0))
        left = tk.Frame(cols, bg=CARD)
        left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(cols, bg=CARD)
        right.pack(side="left", fill="both", expand=True, padx=(22, 0))

        tk.Label(left, text="Esclusioni (una per riga, glob)", bg=CARD, fg=MUTED,
                 font=F_SM, anchor="w").pack(fill="x", pady=(14, 5))
        self.st_exclude = textbox(left, 4)
        self.st_exclude.pack(fill="x")

        tk.Label(right, text="Opzioni", bg=CARD, fg=MUTED, font=F_SM,
                 anchor="w").pack(fill="x", pady=(14, 5))
        self.st_delete = Switch(right, "Cancella dalla copia i file spariti\ndalla chiavetta",
                                False, bg=CARD)
        self.st_delete.pack(anchor="w", pady=(4, 0))
        tk.Label(right, text="Spento: sul PC non viene cancellato niente.", bg=CARD,
                 fg=DIM, font=F_SM, anchor="w").pack(fill="x", pady=(8, 0))

        bar = tk.Frame(body, bg=CARD)
        bar.pack(fill="x", pady=(20, 0))
        Btn(bar, "Salva sulla chiavetta", self.save_stick_plan, "primary").pack(side="left")
        self.btn_backup = Btn(bar, "Backup adesso", self.backup_now, "normal")
        self.btn_backup.pack(side="left", padx=8)
        Btn(bar, "Apri chiavetta", self.open_volume, "ghost").pack(side="left")
        Btn(bar, "Elimina backup.json", self.delete_stick_plan, "danger").pack(side="right")

    def _vol_card(self, parent, root: Path, label: str, removable: bool,
                  has_plan: bool, pc_plan: bool):
        selected = self.volume is not None and str(self.volume) == str(root)
        bgc = CARD_HI if selected else "#171d26"
        box = tk.Frame(parent, bg=bgc, highlightthickness=1, cursor="hand2",
                       highlightbackground=ACCENT if selected else LINE)
        inner = tk.Frame(box, bg=bgc)
        inner.pack(fill="both", expand=True, padx=13, pady=12)

        top = tk.Frame(inner, bg=bgc)
        top.pack(fill="x")
        icon = tk.Label(top, text="🔑" if removable else "🖴", bg=ACCENT_DK if selected else "#1e2632",
                        fg=TEXT, font=("Segoe UI", 12), width=3, pady=4)
        icon.pack(side="left")
        names = tk.Frame(top, bg=bgc)
        names.pack(side="left", padx=10, fill="x", expand=True)
        tk.Label(names, text=label, bg=bgc, fg=TEXT, font=F_UI_B, anchor="w").pack(fill="x")
        tk.Label(names, text=str(root), bg=bgc, fg=DIM, font=F_MONO, anchor="w").pack(fill="x")

        badges = tk.Frame(inner, bg=bgc)
        badges.pack(fill="x", pady=(10, 0))
        def badge(text, fg, bgb):
            tk.Label(badges, text=text, bg=bgb, fg=fg, font=F_SM,
                     padx=7, pady=2).pack(side="left", padx=(0, 6))
        badge("rimovibile" if removable else "disco fisso",
              MUTED if removable else DIM, "#1e2632")
        badge("backup.json" if has_plan else "nessun piano",
              OK if has_plan else DIM, "#16281f" if has_plan else "#1e2632")
        if pc_plan:
            badge("piano PC", "#b9d4ff", ACCENT_DK)

        for widget in (box, inner, top, names, badges, icon):
            widget.bind("<Button-1>", lambda _e, r=root: self.select_volume(r))
        for child in names.winfo_children():
            child.bind("<Button-1>", lambda _e, r=root: self.select_volume(r))
        return box

    def refresh_volumes(self):
        for child in self.vol_holder.winfo_children():
            child.destroy()
        self.volumes = ub.list_volumes(bool(self.cfg.get("include_fixed_drives", True)))
        plan = ub.read_pc_plan(self.cfg)

        if not self.volumes:
            empty = tk.Frame(self.vol_holder, bg="#141920", highlightthickness=1,
                             highlightbackground=LINE)
            empty.pack(fill="x")
            tk.Label(empty, text="🔌", bg="#141920", fg=DIM,
                     font=("Segoe UI", 22)).pack(pady=(24, 6))
            tk.Label(empty, text="Nessun volume collegato", bg="#141920", fg=MUTED,
                     font=F_UI_B).pack()
            tk.Label(empty, text="Infila una chiavetta: compare qui appena Windows la monta.",
                     bg="#141920", fg=DIM, font=F_SM).pack(pady=(4, 26))
            self.volume = None
            self.stick_card.pack_forget()
            return

        grid = tk.Frame(self.vol_holder, bg=CARD)
        grid.pack(fill="x")
        for index, (root, removable) in enumerate(self.volumes):
            label = ub.volume_label(root)
            applies = bool(plan and ub.volume_matches(plan, root, label, removable))
            widget = self._vol_card(grid, root, label, removable,
                                    (root / ub.MARKER_NAME).is_file(), applies)
            widget.grid(row=index // 3, column=index % 3, sticky="ew", padx=(0, 10), pady=5)
        for col in range(3):
            grid.columnconfigure(col, weight=1, uniform="v")

        known = [str(p) for p, _ in self.volumes]
        if self.volume is None or str(self.volume) not in known:
            self.select_volume(self.volumes[0][0])
        else:
            self.stick_card.pack(fill="x", pady=(0, 14))

    def select_volume(self, root: Path):
        self.volume = Path(root)
        self.removable = next((r for p, r in self.volumes if str(p) == str(root)), True)
        self.volume_label = ub.volume_label(self.volume)
        self.refresh_volumes()
        self.load_stick_plan()
        self.update_pc_dest()

    def _pick_stick_folder(self) -> str | None:
        if not self.volume:
            messagebox.showinfo("Nessuna chiavetta", "Seleziona prima un volume.")
            return None
        chosen = filedialog.askdirectory(title=f"Cartella dentro {self.volume_label}",
                                         initialdir=str(self.volume), mustexist=True)
        if not chosen:
            return None
        rel = relative_to_volume(chosen, self.volume)
        if rel is None:
            messagebox.showwarning("Fuori dalla chiavetta",
                                   "Scegli una cartella che sta dentro la chiavetta selezionata.")
            return None
        return rel

    def load_stick_plan(self):
        if not self.volume:
            return
        plan = ub.read_stick_plan(self.volume) or {}
        self.stick_card.pack(fill="x", pady=(0, 14))
        self.st_name.delete(0, tk.END)
        self.st_name.insert(0, str(plan.get("name") or ""))
        self.st_folders.set_rows(folders_from_json(plan.get("folders")))
        self.st_exclude.delete("1.0", tk.END)
        self.st_exclude.insert("1.0", "\n".join(plan.get("exclude") or []))
        self.st_delete.set(bool(plan.get("delete_extra", False)))
        self.update_stick_dest()

    def update_stick_dest(self):
        if not self.volume:
            return
        name = ub.safe_name(self.st_name.get().strip() or self.volume_label)
        self.stick_card.sub.configure(
            text=f"{self.volume}  →  {ub.dest_root_of(self.cfg) / name}")

    def save_stick_plan(self) -> bool:
        if not self.volume:
            return False
        rows = self.st_folders.get_rows()
        if not rows:
            messagebox.showwarning("Nessuna cartella", "Aggiungi almeno una cartella da copiare.")
            return False
        plan = {"folders": folders_to_json(rows)}
        name = self.st_name.get().strip()
        if name:
            plan["name"] = name
        exclude = lines_of(self.st_exclude.get("1.0", tk.END))
        if exclude:
            plan["exclude"] = exclude
        plan["delete_extra"] = self.st_delete.get()
        target = self.volume / ub.MARKER_NAME
        try:
            target.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Errore di scrittura", f"{target}\n{exc}")
            return False
        ub.log(f"[salvato] {target}")
        self.refresh_volumes()
        return True

    def delete_stick_plan(self):
        if not self.volume:
            return
        target = self.volume / ub.MARKER_NAME
        if not target.is_file():
            return
        if not messagebox.askyesno("Conferma", f"Eliminare {target}?\n\n"
                                   "La chiavetta non verra' piu' copiata in automatico.\n"
                                   "I backup gia' fatti sul PC restano dove sono."):
            return
        try:
            target.unlink()
        except OSError as exc:
            messagebox.showerror("Errore", str(exc))
            return
        ub.log(f"[eliminato] {target}")
        self.load_stick_plan()
        self.refresh_volumes()

    def open_volume(self):
        if self.volume:
            reveal(self.volume)

    # --------------------------------------------------------------- pane PC
    def _build_pc(self, parent):
        box = card(parent, "Identita' e filtro", "—")
        self.pc_card = box
        body = box.body

        field_label(body, "Nome di questo PC")
        self.pc_name = entry(body)
        self.pc_name.pack(fill="x")
        self.pc_name.bind("<KeyRelease>", lambda _e: self.update_pc_dest())
        hint(body, f"Vuoto = hostname ({ub.machine_name()}). E' il nome della cartella "
                   "creata sulla chiavetta.")

        field_label(body, "Applica solo a queste chiavette (una per riga, glob)")
        self.pc_only = textbox(body, 3)
        self.pc_only.pack(fill="x")
        hint(body, "Vuoto = tutte le chiavette rimovibili, mai i dischi fissi.")

        push = card(parent, "Push", "—")
        tag(push.title_extra, "PC → CHIAVETTA", "#b9d4ff", ACCENT_DK)
        self.push_card = push
        pbody = push.body
        field_label(pbody, "Cartelle del PC da spedire sulla chiavetta")
        self.push_folders = FolderList(pbody, self._pick_pc_folder, self.update_pc_dest)
        self.push_folders.set_add_text("+  Aggiungi cartella del PC")
        self.push_folders.pack(fill="x")

        cols = tk.Frame(pbody, bg=CARD)
        cols.pack(fill="x")
        left = tk.Frame(cols, bg=CARD)
        left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(cols, bg=CARD)
        right.pack(side="left", fill="both", expand=True, padx=(22, 0))
        tk.Label(left, text="Cartella radice sulla chiavetta", bg=CARD, fg=MUTED,
                 font=F_SM, anchor="w").pack(fill="x", pady=(14, 5))
        self.push_subdir = entry(left)
        self.push_subdir.pack(fill="x")
        self.push_subdir.bind("<KeyRelease>", lambda _e: self.update_pc_dest())
        tk.Label(left, text="Esclusioni", bg=CARD, fg=MUTED, font=F_SM,
                 anchor="w").pack(fill="x", pady=(14, 5))
        self.push_exclude = textbox(left, 3)
        self.push_exclude.pack(fill="x")
        tk.Label(right, text="Opzioni", bg=CARD, fg=MUTED, font=F_SM,
                 anchor="w").pack(fill="x", pady=(14, 5))
        self.push_delete = Switch(right, "Cancella sulla chiavetta cio' che\nnon c'e' piu' sul PC",
                                  False, bg=CARD)
        self.push_delete.pack(anchor="w", pady=(4, 0))

        pull = card(parent, "Pull", "—")
        tag(pull.title_extra, "CHIAVETTA → PC", "#b9d4ff", ACCENT_DK)
        self.pull_card = pull
        lbody = pull.body
        field_label(lbody, "Cartelle della chiavetta da prendere")
        self.pull_folders = FolderList(lbody, self._pick_stick_folder, self.update_pc_dest)
        self.pull_folders.set_add_text("+  Aggiungi cartella della chiavetta")
        self.pull_folders.pack(fill="x")

        cols2 = tk.Frame(lbody, bg=CARD)
        cols2.pack(fill="x")
        left2 = tk.Frame(cols2, bg=CARD)
        left2.pack(side="left", fill="both", expand=True)
        right2 = tk.Frame(cols2, bg=CARD)
        right2.pack(side="left", fill="both", expand=True, padx=(22, 0))
        tk.Label(left2, text="Esclusioni", bg=CARD, fg=MUTED, font=F_SM,
                 anchor="w").pack(fill="x", pady=(14, 5))
        self.pull_exclude = textbox(left2, 3)
        self.pull_exclude.pack(fill="x")
        tk.Label(right2, text="Opzioni", bg=CARD, fg=MUTED, font=F_SM,
                 anchor="w").pack(fill="x", pady=(14, 5))
        self.pull_delete = Switch(right2, "Cancella sul PC cio' che non\nc'e' piu' sulla chiavetta",
                                  False, bg=CARD)
        self.pull_delete.pack(anchor="w", pady=(4, 0))

        bar = tk.Frame(lbody, bg=CARD)
        bar.pack(fill="x", pady=(20, 0))
        Btn(bar, "Salva piano del PC", self.save_pc_plan, "primary").pack(side="left")
        Btn(bar, "Ricarica", self.load_pc_plan, "ghost").pack(side="left", padx=8)
        Btn(bar, "Elimina piano del PC", self.delete_pc_plan, "danger").pack(side="right")

    def _pick_pc_folder(self) -> str | None:
        chosen = filedialog.askdirectory(title="Cartella del PC da spedire sulla chiavetta",
                                         initialdir=str(Path.home()), mustexist=True)
        return chosen or None

    def update_pc_dest(self):
        pc = ub.safe_name(self.pc_name.get().strip() or ub.machine_name())
        sub = self.push_subdir.get().strip() or "backup"
        vol = str(self.volume) if self.volume else "<chiavetta>"
        self.pc_card.sub.configure(text=f"File: {ub.dest_root_of(self.cfg) / ub.MARKER_NAME}")
        self.push_card.sub.configure(text=f"Destinazione: {Path(vol) / sub / pc}")
        self.pull_card.sub.configure(text=f"Destinazione: {ub.dest_root_of(self.cfg) / pc}")

    def load_pc_plan(self):
        plan = ub.read_pc_plan(self.cfg) or {}
        push = plan.get("push") or {}
        pull = plan.get("pull") or {}
        self.pc_name.delete(0, tk.END)
        self.pc_name.insert(0, str(plan.get("pc_name") or ""))
        only = plan.get("only_volumes") or []
        if isinstance(only, str):
            only = [only]
        self.pc_only.delete("1.0", tk.END)
        self.pc_only.insert("1.0", "\n".join(str(o) for o in only))

        self.push_subdir.delete(0, tk.END)
        self.push_subdir.insert(0, str(push.get("target_subdir", "backup")))
        self.push_folders.set_rows(folders_from_json(push.get("folders")))
        self.push_exclude.delete("1.0", tk.END)
        self.push_exclude.insert("1.0", "\n".join(push.get("exclude") or []))
        self.push_delete.set(bool(push.get("delete_extra", False)))

        self.pull_folders.set_rows(folders_from_json(pull.get("folders")))
        self.pull_exclude.delete("1.0", tk.END)
        self.pull_exclude.insert("1.0", "\n".join(pull.get("exclude") or []))
        self.pull_delete.set(bool(pull.get("delete_extra", False)))
        self.update_pc_dest()

    def save_pc_plan(self) -> bool:
        plan: dict = {}
        name = self.pc_name.get().strip()
        if name:
            plan["pc_name"] = name
        only = lines_of(self.pc_only.get("1.0", tk.END))
        if only:
            plan["only_volumes"] = only

        push_rows = folders_to_json(self.push_folders.get_rows())
        if push_rows:
            push = {"folders": push_rows,
                    "target_subdir": self.push_subdir.get().strip() or "backup",
                    "delete_extra": self.push_delete.get()}
            exclude = lines_of(self.push_exclude.get("1.0", tk.END))
            if exclude:
                push["exclude"] = exclude
            plan["push"] = push

        pull_rows = folders_to_json(self.pull_folders.get_rows())
        if pull_rows:
            pull = {"folders": pull_rows, "delete_extra": self.pull_delete.get()}
            exclude = lines_of(self.pull_exclude.get("1.0", tk.END))
            if exclude:
                pull["exclude"] = exclude
            plan["pull"] = pull

        if not push_rows and not pull_rows:
            messagebox.showwarning("Piano vuoto",
                                   "Aggiungi almeno una cartella in Push o in Pull.")
            return False

        target = ub.dest_root_of(self.cfg) / ub.MARKER_NAME
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Errore di scrittura", f"{target}\n{exc}")
            return False
        ub.log(f"[salvato] {target}")
        self.refresh_volumes()
        return True

    def delete_pc_plan(self):
        target = ub.dest_root_of(self.cfg) / ub.MARKER_NAME
        if not target.is_file():
            return
        if not messagebox.askyesno("Conferma", f"Eliminare {target}?"):
            return
        try:
            target.unlink()
        except OSError as exc:
            messagebox.showerror("Errore", str(exc))
            return
        ub.log(f"[eliminato] {target}")
        self.load_pc_plan()
        self.refresh_volumes()

    # -------------------------------------------------------- pane impostazioni
    def _build_cfg(self, parent):
        box = card(parent, "Generali", "—")
        self.cfg_card = box
        body = box.body

        field_label(body, "Cartella dei backup sul PC")
        row = tk.Frame(body, bg=CARD)
        row.pack(fill="x")
        self.cfg_dest = entry(row)
        self.cfg_dest.pack(side="left", fill="x", expand=True)
        Btn(row, "Sfoglia", self._pick_dest, "normal", pad=(12, 5)).pack(side="left", padx=(8, 0))
        hint(body, "Qui dentro vive anche il backup.json del PC.")

        cols = tk.Frame(body, bg=CARD)
        cols.pack(fill="x")
        left = tk.Frame(cols, bg=CARD)
        left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(cols, bg=CARD)
        right.pack(side="left", fill="both", expand=True, padx=(22, 0))
        tk.Label(left, text="File di log", bg=CARD, fg=MUTED, font=F_SM,
                 anchor="w").pack(fill="x", pady=(14, 5))
        self.cfg_log = entry(left)
        self.cfg_log.pack(fill="x")
        tk.Label(right, text="Controlla i volumi ogni (secondi)", bg=CARD, fg=MUTED,
                 font=F_SM, anchor="w").pack(fill="x", pady=(14, 5))
        self.cfg_poll = entry(right, width=8)
        self.cfg_poll.pack(anchor="w")

        self.cfg_fixed = Switch(body, "Considera anche i dischi \"fissi\" non di sistema",
                                True, bg=CARD)
        self.cfg_fixed.pack(anchor="w", pady=(18, 0))
        hint(body, "Molti SSD USB su Windows si presentano come disco fisso.")
        self.cfg_notify = Switch(body, "Notifica di sistema a fine backup", True, bg=CARD)
        self.cfg_notify.pack(anchor="w", pady=(14, 0))

        field_label(body, "Esclusioni globali (una per riga)")
        self.cfg_exclude = textbox(body, 6)
        self.cfg_exclude.pack(fill="x")

        bar = tk.Frame(body, bg=CARD)
        bar.pack(fill="x", pady=(20, 0))
        Btn(bar, "Salva impostazioni", self.save_cfg, "primary").pack(side="left")
        Btn(bar, "Apri cartella backup",
            lambda: reveal(ub.dest_root_of(self.cfg)), "ghost").pack(side="left", padx=8)
        Btn(bar, "Apri il log", self._open_log, "ghost").pack(side="left")

        auto = card(parent, "Avvio automatico al login",
                    "Windows: attivita' pianificata ONLOGON, senza finestra.  "
                    "macOS: LaunchAgent." if ub.IS_WIN else
                    "macOS: LaunchAgent caricato con launchctl.")
        abar = tk.Frame(auto.body, bg=CARD)
        abar.pack(fill="x", pady=(14, 0))
        Btn(abar, "Installa", lambda: self._autostart(True), "normal").pack(side="left")
        Btn(abar, "Rimuovi", lambda: self._autostart(False), "ghost").pack(side="left", padx=8)

    def _pick_dest(self):
        chosen = filedialog.askdirectory(title="Cartella dei backup",
                                         initialdir=str(ub.dest_root_of(self.cfg)))
        if chosen:
            self.cfg_dest.delete(0, tk.END)
            self.cfg_dest.insert(0, chosen)

    def _open_log(self):
        path = self.cfg.get("log_file")
        if not path:
            messagebox.showinfo("Log", "Log su file disattivato.")
            return
        reveal(Path(path).expanduser().parent)

    def _autostart(self, install: bool):
        rc = ub.install_autostart() if install else ub.uninstall_autostart()
        ub.log(f"[avvio automatico] {'installato' if install else 'rimosso'} (codice {rc})")
        if rc != 0:
            messagebox.showerror("Avvio automatico", f"Operazione fallita (codice {rc}).")

    def load_cfg(self):
        self.cfg_card.sub.configure(text=f"File: {ub.CONFIG_PATH}")
        self.cfg_dest.delete(0, tk.END)
        self.cfg_dest.insert(0, str(self.cfg.get("dest_root", "")))
        self.cfg_log.delete(0, tk.END)
        self.cfg_log.insert(0, str(self.cfg.get("log_file") or ""))
        self.cfg_poll.delete(0, tk.END)
        self.cfg_poll.insert(0, str(self.cfg.get("poll_seconds", 3)))
        self.cfg_fixed.set(bool(self.cfg.get("include_fixed_drives", True)))
        self.cfg_notify.set(bool(self.cfg.get("notify", True)))
        self.cfg_exclude.delete("1.0", tk.END)
        self.cfg_exclude.insert("1.0", "\n".join(self.cfg.get("default_exclude", [])))

    def save_cfg(self):
        try:
            poll = max(1, int(self.cfg_poll.get()))
        except ValueError:
            messagebox.showwarning("Valore non valido", "L'intervallo deve essere un numero.")
            return
        cfg = dict(self.cfg)
        cfg["dest_root"] = self.cfg_dest.get().strip() or str(Path.home() / "Backup")
        cfg["log_file"] = self.cfg_log.get().strip() or None
        cfg["poll_seconds"] = poll
        cfg["include_fixed_drives"] = self.cfg_fixed.get()
        cfg["notify"] = self.cfg_notify.get()
        cfg["default_exclude"] = lines_of(self.cfg_exclude.get("1.0", tk.END))
        try:
            ub.CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Errore di scrittura", f"{ub.CONFIG_PATH}\n{exc}")
            return
        self.cfg = ub.load_config()
        ub.setup_log(self.cfg.get("log_file"))
        ub.log(f"[salvato] {ub.CONFIG_PATH}")
        self.refresh_volumes()
        self.load_pc_plan()
        self.load_cfg()

    # ------------------------------------------------------------------- log
    def _build_log(self, parent):
        wrap = tk.Frame(parent, bg="#0a0d12", height=200)
        wrap.pack(fill="x", side="bottom")
        wrap.pack_propagate(False)

        head = tk.Frame(wrap, bg="#0a0d12")
        head.pack(fill="x", padx=26, pady=(9, 4))
        self.pulse = tk.Canvas(head, width=9, height=9, bg="#0a0d12", highlightthickness=0)
        self.pulse.pack(side="left", pady=(1, 0))
        self._draw_pulse(False)
        tk.Label(head, text="Log", bg="#0a0d12", fg=MUTED, font=F_UI_B).pack(side="left", padx=8)
        self.status = tk.Label(head, text="in attesa", bg="#0a0d12", fg=DIM, font=F_SM)
        self.status.pack(side="left")
        Btn(head, "Pulisci", self._clear_log, "ghost", pad=(10, 3)).pack(side="right")

        body = tk.Frame(wrap, bg="#0a0d12")
        body.pack(fill="both", expand=True, padx=26, pady=(0, 12))
        self.logbox = tk.Text(body, bg="#0a0d12", fg="#9fb0c9", font=F_MONO,
                              relief="flat", highlightthickness=0, wrap="none",
                              state="disabled", borderwidth=0)
        self.logbox.pack(side="left", fill="both", expand=True)
        bar = SlimScroll(body, self.logbox.yview, bg="#0a0d12")
        bar.pack(side="right", fill="y", padx=(4, 0))
        self.logbox.configure(yscrollcommand=bar.set)
        self.logbox.bind("<MouseWheel>", lambda e: self.logbox.yview_scroll(
            -1 if e.delta > 0 else 1, "units"))
        self.logbox.tag_configure("err", foreground="#ff8e8e")
        self.logbox.tag_configure("ok", foreground="#5fdca9")
        self.logbox.tag_configure("acc", foreground="#8fbcff")
        self.logbox.tag_configure("warn", foreground=WARN)

    def _draw_pulse(self, on: bool):
        self.pulse.delete("all")
        color = OK if on else "#39415a"
        self.pulse.create_oval(0, 0, 9, 9, fill=color, outline=color)

    def _clear_log(self):
        self.logbox.configure(state="normal")
        self.logbox.delete("1.0", tk.END)
        self.logbox.configure(state="disabled")

    def _drain(self):
        if self.log_queue:
            self.logbox.configure(state="normal")
            at_end = self.logbox.yview()[1] > 0.98
            while self.log_queue:
                line = self.log_queue.pop(0)
                tag_name = ""
                if "[errore]" in line:
                    tag_name = "err"
                elif "[fine" in line or "[salvato]" in line:
                    tag_name = "ok"
                elif "[attenzione]" in line or "[salto]" in line or "[eliminato]" in line:
                    tag_name = "warn"
                elif "->" in line or "[watcher]" in line:
                    tag_name = "acc"
                self.logbox.insert(tk.END, line + "\n", tag_name)
            if at_end:
                self.logbox.see(tk.END)
            self.logbox.configure(state="disabled")
        self.root.after(150, self._drain)

    # --------------------------------------------------------------- azioni
    def backup_now(self):
        if self.busy or not self.volume:
            return
        answer = messagebox.askyesnocancel(
            "Backup adesso",
            "Il backup usa i file gia' salvati.\n\nSalvare prima le modifiche aperte?")
        if answer is None:
            return
        if answer:
            if self.st_folders.get_rows():
                self.save_stick_plan()
            if self.push_folders.get_rows() or self.pull_folders.get_rows():
                self.save_pc_plan()

        volume, removable = self.volume, self.removable
        self.busy = True
        self.btn_backup.set_enabled(False)
        self.status.configure(text="backup in corso...", fg=ACCENT)

        def job():
            try:
                if not ub.handle_volume(volume, self.cfg, removable):
                    ub.log(f"[attenzione] {volume}: niente da fare - nessun backup.json "
                           "sulla chiavetta e il piano del PC non si applica")
            except Exception as exc:
                ub.log(f"[errore] {exc}")
            finally:
                self.root.after(0, self._backup_done)

        threading.Thread(target=job, daemon=True).start()

    def _backup_done(self):
        self.busy = False
        self.btn_backup.set_enabled(True)
        self.status.configure(text="backup terminato", fg=OK)
        self.refresh_volumes()

    def toggle_watch(self, value: bool):
        if value:
            self.stop_event = threading.Event()
            self.watcher = threading.Thread(target=ub.watch,
                                            args=(self.cfg, self.stop_event), daemon=True)
            self.watcher.start()
            self.sw_watch.set_text("sorveglianza attiva")
            self.status.configure(text="in ascolto", fg=OK)
            self._draw_pulse(True)
        else:
            self.stop_event.set()
            self.sw_watch.set_text("sorveglianza spenta")
            self.status.configure(text="in attesa", fg=DIM)
            self._draw_pulse(False)

    def on_close(self):
        self.stop_event.set()
        self.root.destroy()


def setup_dpi() -> None:
    """Su Windows senza questo le scritte sono sfocate sugli schermi scalati."""
    if ub.IS_WIN:
        import ctypes
        for call in (lambda: ctypes.windll.shcore.SetProcessDpiAwareness(1),
                     lambda: ctypes.windll.user32.SetProcessDPIAware()):
            try:
                call()
                break
            except Exception:
                continue


def main() -> int:
    setup_dpi()
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", root.winfo_fpixels("1i") / 72.0)
    except tk.TclError:
        pass
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
