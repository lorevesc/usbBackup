#!/usr/bin/env python3
"""USB Backup - applicazione desktop (PySide6 / Qt).

Configura i tre piani di backup e li esegue:
  chiavetta -> PC, PC -> chiavetta (push), chiavetta -> PC (pull).
La logica sta tutta in usb_backup.py: qui c'e' solo l'interfaccia.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from PySide6.QtCore import (Property, QAbstractNativeEventFilter, QEasingCurve,
                            QFileSystemWatcher, QObject, QPropertyAnimation, QSize,
                            Qt, QTimer, Signal)
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QPainter, QPainterPath,
                           QTextCursor)
from PySide6.QtWidgets import (QAbstractButton, QApplication, QButtonGroup,
                               QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
                               QPlainTextEdit, QPushButton, QScrollArea,
                               QSizePolicy, QSplitter, QStackedWidget,
                               QComboBox, QSystemTrayIcon, QTableWidget,
                               QTableWidgetItem,
                               QVBoxLayout, QWidget)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import appicon  # noqa: E402
import usb_backup as ub  # noqa: E402
from i18n import t, tf  # noqa: E402

# --------------------------------------------------------------------------
# palette
# --------------------------------------------------------------------------
C = {
    "bg": "#0b0e13", "side": "#0f131a", "panel": "#10141b",
    "card": "#161b24", "card_hi": "#1c2330", "input": "#0d1117",
    "line": "#232b38", "line_hi": "#313b4d",
    "text": "#e8ecf4", "muted": "#99a4b8", "dim": "#6a7488",
    "accent": "#5b9dff", "accent_dk": "#1d3358", "ok": "#3ecf8e",
    "warn": "#f2b45c", "danger": "#ff6b6b",
}

MONO = "Consolas" if sys.platform == "win32" else "SF Mono"
UIFONT = "Segoe UI" if sys.platform == "win32" else "SF Pro Text"

QSS = f"""
QWidget {{ color: {C['text']}; font-family: "{UIFONT}"; font-size: 14px; }}
QMainWindow, #root {{ background: {C['bg']}; }}

/* ---------- sidebar ---------- */
#sidebar {{ background: {C['side']}; border-right: 1px solid {C['line']}; }}
#brand {{ font-size: 16px; font-weight: 600; }}
#logo {{ background: transparent; }}
#nav {{ background: transparent; border: none; border-left: 3px solid transparent;
        color: {C['muted']}; text-align: left; padding: 11px 16px; font-size: 14px; }}
#nav:hover {{ color: {C['text']}; background: #141922; }}
#nav:checked {{ color: {C['text']}; background: {C['panel']};
                border-left: 3px solid {C['accent']}; font-weight: 600; }}
#sidehint {{ color: {C['dim']}; font-size: 12px; }}

/* ---------- testata ---------- */
#page {{ background: {C['panel']}; }}
#h1 {{ font-size: 24px; font-weight: 600; }}
#h2 {{ color: {C['dim']}; font-size: 13px; }}

/* ---------- schede ---------- */
#card {{ background: {C['card']}; border: 1px solid {C['line']}; border-radius: 14px; }}
#cardTitle {{ font-size: 15px; font-weight: 600; }}
#cardSub {{ color: {C['dim']}; font-size: 12px; }}
#label {{ color: {C['muted']}; font-size: 12px; }}
#hint {{ color: {C['dim']}; font-size: 12px; }}
#mono {{ font-family: "{MONO}"; font-size: 12px; }}

/* ---------- campi ---------- */
QLineEdit, QPlainTextEdit {{
    background: {C['input']}; border: 1px solid {C['line']}; border-radius: 9px;
    padding: 8px 10px; selection-background-color: {C['accent_dk']};
}}
QLineEdit:focus, QPlainTextEdit:focus {{ border: 1px solid {C['accent']}; }}
QLineEdit::placeholder {{ color: #4d566b; }}
QPlainTextEdit {{ font-family: "{MONO}"; font-size: 12px; }}

/* ---------- bottoni ---------- */
QPushButton {{
    background: {C['card_hi']}; border: 1px solid {C['line_hi']}; border-radius: 9px;
    padding: 8px 15px; font-size: 13px; font-weight: 500;
}}
QPushButton:hover {{ background: #232c3a; border-color: #3d4759; }}
QPushButton:pressed {{ background: #1a2130; }}
QPushButton:disabled {{ color: {C['dim']}; background: #171c25; border-color: {C['line']}; }}
QPushButton[kind="primary"] {{ background: {C['accent']}; border-color: {C['accent']}; color: #07101f;
                               font-weight: 600; }}
QPushButton[kind="primary"]:hover {{ background: #79b0ff; border-color: #79b0ff; }}
QPushButton[kind="ghost"] {{ background: transparent; border-color: {C['line']}; color: {C['muted']}; }}
QPushButton[kind="ghost"]:hover {{ background: {C['card_hi']}; color: {C['text']}; }}
QPushButton[kind="danger"] {{ background: transparent; border-color: #4a2b32; color: {C['danger']}; }}
QPushButton[kind="danger"]:hover {{ background: #2a1a1e; }}
QPushButton[kind="tiny"] {{ padding: 5px 10px; font-size: 12px; }}

/* ---------- menu a tendina ---------- */
QComboBox {{ background: {C['input']}; border: 1px solid {C['line']};
             border-radius: 9px; padding: 8px 10px; }}
QComboBox:hover {{ border-color: {C['line_hi']}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{ background: {C['card']}; border: 1px solid {C['line_hi']};
                               selection-background-color: {C['accent_dk']};
                               padding: 4px; }}

/* ---------- badge ---------- */
#badge {{ background: #1c232f; color: {C['muted']}; border-radius: 6px;
          padding: 3px 8px; font-size: 11px; }}
#badge[variant="ok"] {{ background: #16291f; color: {C['ok']}; }}
#badge[variant="accent"] {{ background: {C['accent_dk']}; color: #b9d4ff; }}
#badge[variant="dim"] {{ background: #171d27; color: {C['dim']}; }}
#tag {{ background: {C['accent_dk']}; color: #b9d4ff; border-radius: 6px;
        padding: 3px 9px; font-size: 11px; font-weight: 600; }}

/* ---------- card volume ---------- */
#volcard {{ background: #141a23; border: 1px solid {C['line']}; border-radius: 12px; }}
#volcard:hover {{ background: {C['card_hi']}; border-color: {C['line_hi']}; }}
#volcard[selected="true"] {{ background: {C['card_hi']}; border: 1px solid {C['accent']}; }}
#volname {{ font-size: 14px; font-weight: 600; }}
#volpath {{ font-family: "{MONO}"; font-size: 11px; color: {C['dim']}; }}
#volicon {{ background: #1e2635; border-radius: 9px; min-width: 34px; min-height: 34px;
            font-size: 15px; qproperty-alignment: AlignCenter; }}
#volcard[selected="true"] #volicon {{ background: {C['accent_dk']}; }}

/* ---------- riga cartella ---------- */
#frow {{ background: {C['input']}; border: 1px solid {C['line']}; border-radius: 10px; }}
#frow QLineEdit {{ background: {C['card']}; border-radius: 7px; padding: 6px 9px;
                   font-family: "{MONO}"; font-size: 12px; }}
#xbtn {{ background: transparent; border: none; color: {C['dim']}; font-size: 16px;
         padding: 2px 8px; border-radius: 6px; }}
#xbtn:hover {{ color: {C['danger']}; background: #2a1a1e; }}
#arrow {{ color: {C['dim']}; font-size: 13px; }}

/* ---------- vuoto ---------- */
#empty {{ background: #11161e; border: 1px dashed {C['line_hi']}; border-radius: 12px; }}
#emptyIcon {{ font-size: 30px; color: {C['dim']}; }}
#emptyTitle {{ font-size: 14px; font-weight: 600; color: {C['muted']}; }}

/* ---------- log ---------- */
#logpanel {{ background: #080b10; border-top: 1px solid {C['line']}; }}
#logview {{ background: #080b10; border: none; font-family: "{MONO}"; font-size: 12px;
            color: #9fb0c9; }}
#logtitle {{ font-size: 13px; font-weight: 600; color: {C['muted']}; }}
#logstate {{ color: {C['dim']}; font-size: 12px; }}

/* ---------- tabella dello storico ---------- */
QTableWidget {{ background: {C['input']}; border: 1px solid {C['line']};
                border-radius: 10px; gridline-color: {C['line']};
                selection-background-color: {C['accent_dk']}; }}
QTableWidget::item {{ padding: 7px 10px; border: none; }}
QHeaderView::section {{ background: {C['card_hi']}; color: {C['muted']};
                        border: none; border-bottom: 1px solid {C['line']};
                        padding: 8px 10px; font-size: 12px; font-weight: 600; }}
QTableCornerButton::section {{ background: {C['card_hi']}; border: none; }}

/* ---------- scroll ---------- */
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #333d4f; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #414d63; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---------- maniglia del log ---------- */
QSplitter#split::handle {{ background: {C['panel']}; }}
QSplitter#split::handle:vertical {{ height: 6px; image: none;
    border-top: 1px solid {C['line']}; }}
QSplitter#split::handle:vertical:hover {{ border-top: 1px solid {C['accent']};
    background: #141a24; }}

/* ---------- toast ---------- */
#toast {{ background: {C['card_hi']}; border: 1px solid {C['line_hi']};
          border-left: 3px solid {C['accent']}; border-radius: 10px; padding: 11px 15px;
          font-size: 13px; }}
#toast[variant="ok"] {{ border-left: 3px solid {C['ok']}; }}
#toast[variant="err"] {{ border-left: 3px solid {C['danger']}; }}

QMessageBox {{ background: {C['card']}; }}
QMessageBox QLabel {{ color: {C['text']}; }}
"""


# --------------------------------------------------------------------------
# widget su misura
# --------------------------------------------------------------------------

class Switch(QAbstractButton):
    """Interruttore animato."""

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self._offset = 0.0
        self._text = text
        self.setMinimumHeight(24)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)

    def get_offset(self) -> float:
        return self._offset

    def set_offset(self, value: float) -> None:
        self._offset = value
        self.update()

    offset = Property(float, get_offset, set_offset)

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def setText(self, text: str) -> None:  # noqa: N802
        self._text = text
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        width = 46 + QFontMetrics(self.font()).horizontalAdvance(self._text) + 12
        return QSize(width, 26)

    def paintEvent(self, _event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        height = 22
        top = (self.height() - height) / 2
        track = QColor("#1e4b38") if self.isChecked() else QColor("#222a37")
        painter.setPen(Qt.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(0, top, 42, height, height / 2, height / 2)
        knob = QColor(C["ok"]) if self.isChecked() else QColor("#5d6880")
        painter.setBrush(knob)
        cx = 11 + self._offset * 20
        painter.drawEllipse(cx - 8, top + 3, 16, 16)
        if self._text:
            painter.setPen(QColor(C["text"] if self.isChecked() else C["muted"]))
            painter.drawText(54, 0, self.width() - 54, self.height(),
                             Qt.AlignVCenter | Qt.AlignLeft, self._text)


class ElidedLabel(QLabel):
    """QLabel che taglia il testo con i puntini invece di allargare la finestra."""

    def __init__(self, text="", parent=None, mode=Qt.ElideMiddle):
        super().__init__(parent)
        self._full = text
        self._mode = mode
        self.setMinimumWidth(40)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setText(text)

    def setText(self, text):  # noqa: N802
        self._full = text
        super().setText(QFontMetrics(self.font()).elidedText(
            text, self._mode, max(40, self.width())))

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        super().setText(QFontMetrics(self.font()).elidedText(
            self._full, self._mode, max(40, self.width())))


def pixmap_glyph(size: int, color: str) -> QPixmap:
    """Glifo chiavetta nitido anche su schermi ad alta densita'."""
    app = QApplication.instance()
    ratio = max(1.0, app.devicePixelRatio() if app else 1.0)
    pixmap = appicon.glyph(int(size * ratio), color)
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def label(text, name="", parent=None) -> QLabel:
    widget = QLabel(text, parent)
    if name:
        widget.setObjectName(name)
    return widget


def button(text, kind="normal", on_click=None) -> QPushButton:
    btn = QPushButton(text)
    btn.setProperty("kind", kind)
    btn.setCursor(Qt.PointingHandCursor)
    if on_click:
        btn.clicked.connect(on_click)
    return btn


class Card(QFrame):
    """Scheda con titolo, sottotitolo e corpo verticale."""

    def __init__(self, title="", subtitle="", tag_text=""):
        super().__init__()
        self.setObjectName("card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(0)

        if title:
            head = QHBoxLayout()
            head.setSpacing(10)
            self.title = label(title, "cardTitle")
            head.addWidget(self.title)
            if tag_text:
                head.addWidget(label(tag_text, "tag"))
            head.addStretch(1)
            self.head = head
            outer.addLayout(head)

        self.sub = label(subtitle, "cardSub")
        self.sub.setVisible(bool(subtitle))
        outer.addWidget(self.sub)
        outer.addSpacing(10)

        self.body = QVBoxLayout()
        self.body.setSpacing(0)
        outer.addLayout(self.body)

    def field(self, text: str, widget: QWidget, hint_text: str = "") -> QWidget:
        self.body.addSpacing(12)
        self.body.addWidget(label(text, "label"))
        self.body.addSpacing(6)
        self.body.addWidget(widget)
        if hint_text:
            self.body.addSpacing(5)
            self.body.addWidget(label(hint_text, "hint"))
        return widget


class FolderList(QWidget):
    """Elenco di righe 'sorgente -> nome destinazione'."""

    changed = Signal()

    def __init__(self, add_text: str, picker):
        super().__init__()
        self.picker = picker
        self.rows: list[dict] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(7)
        self.holder = QVBoxLayout()
        self.holder.setSpacing(6)
        root.addLayout(self.holder)
        self.add_btn = button(add_text, "normal", self._add)
        self.add_btn.setProperty("kind", "normal")
        row = QHBoxLayout()
        row.addWidget(self.add_btn)
        row.addStretch(1)
        root.addLayout(row)

    def set_rows(self, rows):
        self.rows = [dict(r) for r in rows]
        self._render()

    def get_rows(self):
        return [r for r in self.rows if r.get("path")]

    def _clear(self):
        while self.holder.count():
            item = self.holder.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _render(self):
        self._clear()
        if not self.rows:
            self.holder.addWidget(label(t("Nessuna cartella impostata."), "hint"))
            return
        for index, row in enumerate(self.rows):
            self.holder.addWidget(self._row_widget(index, row))

    def _row_widget(self, index: int, row: dict) -> QWidget:
        frame = QFrame()
        frame.setObjectName("frow")
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(12, 7, 8, 7)
        lay.setSpacing(9)

        shown = "(tutta la chiavetta)" if row["path"] == "." else row["path"]
        src = ElidedLabel(shown)
        src.setObjectName("mono")
        lay.addWidget(src, 3)
        lay.addWidget(label("→", "arrow"))

        default = "root" if row["path"] == "." else Path(row["path"].rstrip("/\\")).name
        alias = QLineEdit(row.get("as", ""))
        alias.setPlaceholderText(default or "root")
        alias.setMinimumWidth(130)
        alias.textChanged.connect(lambda value, r=row: (r.update(**{"as": value.strip()}),
                                                        self.changed.emit()))
        lay.addWidget(alias, 2)

        remove = QPushButton("✕")
        remove.setObjectName("xbtn")
        remove.setCursor(Qt.PointingHandCursor)
        remove.setToolTip(t("Rimuovi"))
        remove.clicked.connect(lambda _=False, i=index: self._remove(i))
        lay.addWidget(remove)
        return frame

    def _remove(self, index: int):
        del self.rows[index]
        self._render()
        self.changed.emit()

    def _add(self):
        path = self.picker()
        if not path or any(r["path"] == path for r in self.rows):
            return
        self.rows.append({"path": path, "as": ""})
        self._render()
        self.changed.emit()


class VolumeCard(QFrame):
    clicked = Signal(str)

    def __init__(self, volume: dict, selected: bool):
        super().__init__()
        self.setObjectName("volcard")
        self.setProperty("selected", "true" if selected else "false")
        self.setCursor(Qt.PointingHandCursor)
        self.path = volume["path"]

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 13, 14, 13)
        lay.setSpacing(11)

        top = QHBoxLayout()
        top.setSpacing(11)
        icon = label("", "volicon")
        icon.setFixedSize(36, 36)
        icon.setAlignment(Qt.AlignCenter)
        icon.setPixmap(pixmap_glyph(22, C["accent"] if volume["removable"] else C["dim"]))
        top.addWidget(icon)
        names = QVBoxLayout()
        names.setSpacing(2)
        names.addWidget(label(volume["label"], "volname"))
        path_label = ElidedLabel(volume["path"])
        path_label.setObjectName("volpath")
        names.addWidget(path_label)
        top.addLayout(names, 1)
        lay.addLayout(top)

        badges = QHBoxLayout()
        badges.setSpacing(6)
        badges.addWidget(self._badge(t("rimovibile") if volume["removable"] else t("disco fisso"),
                                     "" if volume["removable"] else "dim"))
        badges.addWidget(self._badge(t("backup.json") if volume["has_plan"] else t("nessun piano"),
                                     "ok" if volume["has_plan"] else "dim"))
        if volume["pc_plan"]:
            badges.addWidget(self._badge(t("piano PC"), "accent"))
        if volume.get("serial"):
            badges.addWidget(self._badge("n. " + volume["serial"], "dim"))
        badges.addStretch(1)
        lay.addLayout(badges)

    @staticmethod
    def _badge(text: str, variant: str) -> QLabel:
        widget = label(text, "badge")
        if variant:
            widget.setProperty("variant", variant)
        return widget

    def mousePressEvent(self, event):  # noqa: N802
        self.clicked.emit(self.path)
        super().mousePressEvent(event)


class Toast(QFrame):
    def __init__(self, parent, text: str, variant: str = ""):
        super().__init__(parent)
        self.setObjectName("toast")
        if variant:
            self.setProperty("variant", variant)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QLabel(text))
        self.adjustSize()


# --------------------------------------------------------------------------
# ponte fra thread di lavoro e interfaccia
# --------------------------------------------------------------------------

class Bus(QObject):
    line = Signal(str)
    backup_done = Signal()
    device_changed = Signal()


class DeviceEvents(QAbstractNativeEventFilter):
    """Ascolta WM_DEVICECHANGE: Windows avvisa quando un disco arriva o se ne va,
    cosi' non serve nessun controllo periodico."""

    WM_DEVICECHANGE = 0x0219
    DBT_DEVICEARRIVAL = 0x8000
    DBT_DEVICEREMOVECOMPLETE = 0x8004
    DBT_DEVNODES_CHANGED = 0x0007

    def __init__(self, bus: Bus):
        super().__init__()
        self.bus = bus

    def nativeEventFilter(self, event_type, message):  # noqa: N802
        if event_type == b"windows_generic_MSG":
            try:
                import ctypes.wintypes
                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == self.WM_DEVICECHANGE and msg.wParam in (
                        self.DBT_DEVICEARRIVAL, self.DBT_DEVICEREMOVECOMPLETE,
                        self.DBT_DEVNODES_CHANGED):
                    self.bus.device_changed.emit()
            except Exception:
                pass
        return False, 0


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
            rows.append({"path": str(item.get("path", "")), "as": str(item.get("as", "") or "")})
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
            ub.run_hidden(["open", str(path)], check=False)
        else:
            ub.run_hidden(["xdg-open", str(path)], check=False)
    except Exception as exc:
        ub.log(f"[errore] apertura {path}: {exc}")


# --------------------------------------------------------------------------
# finestra
# --------------------------------------------------------------------------

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(t("USB Backup"))
        self.resize(1240, 860)
        self.setMinimumSize(1060, 720)

        self.cfg = ub.load_config()
        ub.setup_log(self.cfg.get("log_file"))
        self.volumes: list[dict] = []
        self.volume: dict | None = None
        self.busy = False
        self.stop_event = threading.Event()
        self.watcher: threading.Thread | None = None
        self.toasts: list[Toast] = []
        self._last_progress = False
        self._device_filter = None
        self._fs_watcher = None
        self._only_serials: list[str] = []
        self._restoring = False
        self.tray = None
        self._quitting = False
        self._titlebar_done = False
        self._known: set[str] = set()
        self._scanning = False
        self._device_timer = QTimer(self)      # raggruppa piu' eventi vicini
        self._device_timer.setSingleShot(True)
        self._device_timer.timeout.connect(self.scan_devices)

        self.bus = Bus()
        self.bus.line.connect(self.append_log)
        self.bus.backup_done.connect(self.on_backup_done)
        self.bus.device_changed.connect(self.on_device_changed)
        ub.add_log_sink(self.bus.line.emit)

        self._build()
        self._build_tray()
        self.refresh_volumes()
        self.load_pc_plan()
        self.load_cfg()
        if self.cfg.get("watch_enabled"):
            self._restoring = True
            self.sw_watch.setChecked(True)    # riaccende com'era alla chiusura
            self._restoring = False

    # ---------------------------------------------------------------- layout
    def _build(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._sidebar())

        right = QWidget()
        right.setObjectName("page")
        outer.addWidget(right, 1)
        col = QVBoxLayout(right)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        head = QWidget()
        head_lay = QHBoxLayout(head)
        head_lay.setContentsMargins(30, 24, 30, 12)
        head_lay.setSpacing(14)
        self.h1 = label(t("Chiavette"), "h1")
        self.h2 = label("", "h2")
        head_lay.addWidget(self.h1)
        head_lay.addWidget(self.h2)
        head_lay.addStretch(1)
        self.pc_chip = label("", "badge")
        self.pc_chip.setProperty("variant", "accent")
        head_lay.addWidget(self.pc_chip)
        col.addWidget(head)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._scroll(self._page_stick()))
        self.pages.addWidget(self._scroll(self._page_pc()))
        self.pages.addWidget(self._scroll(self._page_history()))
        self.pages.addWidget(self._scroll(self._page_cfg()))

        # pagine e log divisi da una maniglia trascinabile
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.setObjectName("split")
        self.splitter.setHandleWidth(6)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.pages)
        self.splitter.addWidget(self._log_panel())
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([640, 210])
        col.addWidget(self.splitter, 1)
        self.show_page(0)

    def _scroll(self, inner: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        holder = QWidget()
        holder.setObjectName("page")
        lay = QVBoxLayout(holder)
        lay.setContentsMargins(30, 6, 30, 24)
        lay.setSpacing(16)
        lay.addWidget(inner)
        lay.addStretch(1)
        area.setWidget(holder)
        return area

    def _sidebar(self) -> QWidget:
        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(236)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(0, 22, 0, 20)
        lay.setSpacing(0)

        brand = QHBoxLayout()
        brand.setContentsMargins(18, 0, 18, 26)
        brand.setSpacing(11)
        logo = label("", "logo")
        ratio = max(1.0, self.devicePixelRatioF())
        mark = appicon.paint(int(32 * ratio))
        mark.setDevicePixelRatio(ratio)
        logo.setPixmap(mark)
        logo.setFixedSize(32, 32)
        brand.addWidget(logo)
        brand.addWidget(label(t("USB Backup"), "brand"))
        brand.addStretch(1)
        lay.addLayout(brand)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for index, text in enumerate((t("Chiavette"), t("Questo PC"), t("Storico"),
                                      t("Impostazioni"))):
            btn = QPushButton(text)
            btn.setObjectName("nav")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, i=index: self.show_page(i))
            self.nav_group.addButton(btn, index)
            lay.addWidget(btn)

        lay.addStretch(1)

        box = QVBoxLayout()
        box.setContentsMargins(18, 0, 18, 0)
        box.setSpacing(9)
        self.sw_watch = Switch(t("sorveglianza spenta"))
        self.sw_watch.toggled.connect(self.toggle_watch)
        box.addWidget(self.sw_watch)
        hint = label(t("Copia da sola a ogni chiavetta collegata."), "sidehint")
        hint.setWordWrap(True)
        box.addWidget(hint)
        lay.addLayout(box)
        return side

    # ------------------------------------------------------------ pagina 1
    def _page_stick(self) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        self.avviso_box = QFrame()
        self.avviso_box.setStyleSheet("QFrame { background:#2a2417; border:1px solid #4a3f24;"
                                      " border-radius:10px; }")
        riga_avviso = QHBoxLayout(self.avviso_box)
        riga_avviso.setContentsMargins(14, 9, 9, 9)
        riga_avviso.setSpacing(12)
        self.avviso = label("", "hint")
        self.avviso.setWordWrap(True)
        self.avviso.setStyleSheet(f"color:{C['warn']}; background:transparent; border:none;")
        riga_avviso.addWidget(self.avviso, 1)
        dimentica = button(t("Dimentica"), "ghost", self.forget_stale)
        dimentica.setToolTip(t("Non segnalare piu' questi dischi. Se li ricolleghi, tornano."))
        riga_avviso.addWidget(dimentica)
        self.avviso_box.setVisible(False)
        self._fermi: list[dict] = []
        lay.addWidget(self.avviso_box)

        vols = Card(t("Volumi collegati"), t("Seleziona una chiavetta per configurarla."))
        vols.head.addWidget(button(t("Aggiorna"), "ghost", self.refresh_volumes))
        self.vol_grid = QGridLayout()
        self.vol_grid.setSpacing(11)
        vols.body.addLayout(self.vol_grid)
        lay.addWidget(vols)

        card = Card(t("backup.json della chiavetta"), "—", t("CHIAVETTA → PC"))
        self.stick_card = card

        self.st_name = QLineEdit()
        self.st_name.textChanged.connect(self.update_stick_dest)
        card.field(t("Nome della cartella di destinazione"), self.st_name,
                   t("Vuoto = etichetta del volume."))

        self.st_folders = FolderList(t("+  Aggiungi cartella"), self.pick_stick_folder)
        card.field(t("Cartelle della chiavetta da copiare sul PC"), self.st_folders)

        cols = QHBoxLayout()
        cols.setSpacing(24)
        left = QVBoxLayout()
        left.setSpacing(6)
        left.addWidget(label(t("Esclusioni (una per riga, glob)"), "label"))
        self.st_exclude = QPlainTextEdit()
        self.st_exclude.setFixedHeight(88)
        self.st_exclude.setPlaceholderText("*.tmp\nnode_modules")
        left.addWidget(self.st_exclude)
        right = QVBoxLayout()
        right.setSpacing(6)
        right.addWidget(label(t("Opzioni"), "label"))
        self.st_delete = Switch(t("Sposta in __deleted i file spariti dalla chiavetta"))
        right.addWidget(self.st_delete)
        note = label(t("Niente viene mai cancellato: finisce in __deleted, accanto alla copia."), "hint")
        note.setWordWrap(True)
        right.addWidget(note)
        right.addStretch(1)
        cols.addLayout(left, 1)
        cols.addLayout(right, 1)
        card.body.addSpacing(16)
        card.body.addLayout(cols)

        bar = QHBoxLayout()
        bar.setSpacing(9)
        bar.addWidget(button(t("Salva sulla chiavetta"), "primary", self.save_stick_plan))
        self.btn_backup = button(t("Backup adesso"), "normal", self.backup_now)
        bar.addWidget(self.btn_backup)
        self.btn_stop = button(t("Ferma"), "danger", self.stop_now)
        self.btn_stop.setVisible(False)
        bar.addWidget(self.btn_stop)
        bar.addWidget(button(t("Apri chiavetta"), "ghost",
                             lambda: self.volume and reveal(Path(self.volume["path"]))))
        bar.addStretch(1)
        bar.addWidget(button(t("Elimina backup.json"), "danger", self.delete_stick_plan))
        card.body.addSpacing(20)
        card.body.addLayout(bar)

        lay.addWidget(card)
        return page

    # ------------------------------------------------------------ pagina 2
    def _page_pc(self) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        ident = Card(t("Identità e filtro"), "—")
        self.pc_card = ident
        self.pc_name = QLineEdit()
        self.pc_name.setPlaceholderText(ub.machine_name())
        self.pc_name.textChanged.connect(self.update_pc_dest)
        ident.field(t("Nome di questo PC"), self.pc_name,
                    t("Vuoto = hostname. È il nome della cartella creata sulla chiavetta."))
        self.pc_only = QPlainTextEdit()
        self.pc_only.setFixedHeight(72)
        self.pc_only.setPlaceholderText("chiavetta-lavoro\nKINGSTON*")
        ident.field(t("Applica solo a queste chiavette (una per riga, glob)"), self.pc_only,
                    t("Vuoto = tutte le chiavette rimovibili, mai i dischi fissi."))

        riga = QWidget()
        lega = QHBoxLayout(riga)
        lega.setContentsMargins(0, 0, 0, 0)
        lega.setSpacing(9)
        self.lbl_serial = label("", "mono")
        lega.addWidget(self.lbl_serial, 1)
        lega.addWidget(button(t("Lega al disco selezionato"), "normal", self.bind_serial))
        lega.addWidget(button(t("Togli il vincolo"), "ghost", self.unbind_serial))
        ident.field(t("Vincolo al disco (numero di serie)"), riga,
                    t("Il piu' solido: la lettera di unita' cambia e l'etichetta la "
                      "cambia chiunque, il numero di serie no. Se impostato vale solo "
                      "questo, e le regole qui sopra vengono ignorate."))
        lay.addWidget(ident)

        push = Card(t("Push"), "—", t("PC → CHIAVETTA"))
        self.push_card = push
        self.push_folders = FolderList(t("+  Aggiungi cartella del PC"), self.pick_pc_folder)
        push.field(t("Cartelle del PC da spedire sulla chiavetta"), self.push_folders)
        cols = QHBoxLayout()
        cols.setSpacing(24)
        left = QVBoxLayout()
        left.setSpacing(6)
        left.addWidget(label(t("Cartella radice sulla chiavetta"), "label"))
        self.push_subdir = QLineEdit()
        self.push_subdir.setPlaceholderText("backup")
        self.push_subdir.textChanged.connect(self.update_pc_dest)
        left.addWidget(self.push_subdir)
        left.addSpacing(8)
        left.addWidget(label(t("Esclusioni"), "label"))
        self.push_exclude = QPlainTextEdit()
        self.push_exclude.setFixedHeight(72)
        self.push_exclude.setPlaceholderText("node_modules\n.git")
        left.addWidget(self.push_exclude)
        right = QVBoxLayout()
        right.setSpacing(6)
        right.addWidget(label(t("Opzioni"), "label"))
        self.push_delete = Switch(t("Sposta in __deleted sulla chiavetta ciò che non c'è più sul PC"))
        right.addWidget(self.push_delete)
        right.addStretch(1)
        cols.addLayout(left, 1)
        cols.addLayout(right, 1)
        push.body.addSpacing(16)
        push.body.addLayout(cols)
        lay.addWidget(push)

        pull = Card(t("Pull"), "—", t("CHIAVETTA → PC"))
        self.pull_card = pull
        self.pull_folders = FolderList(t("+  Aggiungi cartella della chiavetta"),
                                       self.pick_stick_folder)
        pull.field(t("Cartelle della chiavetta da prendere"), self.pull_folders)

        dest_row = QWidget()
        dest_lay = QHBoxLayout(dest_row)
        dest_lay.setContentsMargins(0, 0, 0, 0)
        dest_lay.setSpacing(9)
        self.pull_dest = QLineEdit()
        self.pull_dest.textChanged.connect(self.update_pc_dest)
        dest_lay.addWidget(self.pull_dest, 1)
        dest_lay.addWidget(button(t("Sfoglia"), "normal", self.pick_pull_dest))
        pull.field(t("Cartella di destinazione sul PC"), dest_row,
                   t("Vuoto = ~/Backup/<nome del disco>. Mettici una cartella di staging se "
                     "vuoi confrontare e unire a mano, senza toccare il progetto vero."))
        cols2 = QHBoxLayout()
        cols2.setSpacing(24)
        left2 = QVBoxLayout()
        left2.setSpacing(6)
        left2.addWidget(label(t("Esclusioni"), "label"))
        self.pull_exclude = QPlainTextEdit()
        self.pull_exclude.setFixedHeight(72)
        self.pull_exclude.setPlaceholderText("*.tmp")
        left2.addWidget(self.pull_exclude)
        right2 = QVBoxLayout()
        right2.setSpacing(6)
        right2.addWidget(label(t("Opzioni"), "label"))
        self.pull_delete = Switch(t("Sposta in __deleted sul PC ciò che non c'è più sulla chiavetta"))
        right2.addWidget(self.pull_delete)
        right2.addStretch(1)
        cols2.addLayout(left2, 1)
        cols2.addLayout(right2, 1)
        pull.body.addSpacing(16)
        pull.body.addLayout(cols2)

        bar = QHBoxLayout()
        bar.setSpacing(9)
        bar.addWidget(button(t("Salva piano del PC"), "primary", self.save_pc_plan))
        bar.addWidget(button(t("Ricarica"), "ghost", self.load_pc_plan))
        bar.addStretch(1)
        bar.addWidget(button(t("Elimina piano del PC"), "danger", self.delete_pc_plan))
        pull.body.addSpacing(20)
        pull.body.addLayout(bar)
        lay.addWidget(pull)
        return page

    # ------------------------------------------------------- pagina storico
    COLONNE = (t("Quando"), t("Volume"), t("Copiati"), t("Invariati"), t("In __deleted"),
               t("Errori"), t("Dati"), t("Durata"))

    def _page_history(self) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        card = Card(t("Ultimi backup"), "—")
        self.history_card = card
        card.head.addWidget(button(t("Aggiorna"), "ghost", self.load_history))
        self.history_table = QTableWidget(0, len(self.COLONNE))
        self.history_table.setHorizontalHeaderLabels(self.COLONNE)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setAlternatingRowColors(False)
        self.history_table.setMinimumHeight(360)
        header = self.history_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(1, header.ResizeMode.Stretch)
        card.body.addWidget(self.history_table)

        riga = QHBoxLayout()
        riga.setSpacing(9)
        riga.addWidget(button(t("Apri la cartella dei log"), "ghost",
                              lambda: reveal(Path(str(self.cfg.get("log_file") or
                                                      ub.APP_DIR)).expanduser().parent)))
        riga.addStretch(1)
        card.body.addSpacing(14)
        card.body.addLayout(riga)
        lay.addWidget(card)
        return page

    def load_history(self):
        storia = ub.read_history()
        self.history_table.setRowCount(len(storia))
        for riga, voce in enumerate(storia):
            quando = str(voce.get("quando", "")).replace("T", "  ")
            errori = int(voce.get("errori", 0))
            valori = [
                quando,
                str(voce.get("volume", "")),
                str(voce.get("copiati", 0)),
                str(voce.get("invariati", 0)),
                str(voce.get("cestinati", 0)),
                str(errori),
                ub.human_bytes(voce.get("byte", 0)),
                ub.human_time(voce.get("secondi", 0)),
            ]
            for colonna, testo in enumerate(valori):
                item = QTableWidgetItem(testo)
                if colonna >= 2:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if colonna == 5 and errori:
                    item.setForeground(QColor(C["danger"]))
                elif colonna == 2 and voce.get("copiati"):
                    item.setForeground(QColor(C["ok"]))
                self.history_table.setItem(riga, colonna, item)
        self.history_table.resizeColumnsToContents()
        if storia:
            ultimo = storia[0]
            self.history_card.sub.setText(
                f"{len(storia)} giri registrati - l'ultimo "
                f"{str(ultimo.get('quando', '')).replace('T', t(' alle '))}")
        else:
            self.history_card.sub.setText(
                t("Ancora nessun giro: appena ne parte uno compare qui."))
        self.history_card.sub.setVisible(True)

    # ------------------------------------------------------------ pagina 3
    def _page_cfg(self) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        card = Card(t("Generali"), "—")
        self.cfg_card = card
        dest_row = QWidget()
        dest_lay = QHBoxLayout(dest_row)
        dest_lay.setContentsMargins(0, 0, 0, 0)
        dest_lay.setSpacing(9)
        self.cfg_dest = QLineEdit()
        dest_lay.addWidget(self.cfg_dest, 1)
        dest_lay.addWidget(button(t("Sfoglia"), "normal", self.pick_dest))
        card.field(t("Cartella dei backup sul PC"), dest_row,
                   t("Qui dentro vive anche il backup.json del PC."))

        cols = QHBoxLayout()
        cols.setSpacing(24)
        left = QVBoxLayout()
        left.setSpacing(6)
        left.addWidget(label(t("File di log"), "label"))
        self.cfg_log = QLineEdit()
        left.addWidget(self.cfg_log)
        right = QVBoxLayout()
        right.setSpacing(6)
        right.addWidget(label(t("Controlla i volumi ogni (secondi)"), "label"))
        self.cfg_poll = QLineEdit()
        self.cfg_poll.setFixedWidth(90)
        right.addWidget(self.cfg_poll)
        right.addStretch(1)
        cols.addLayout(left, 2)
        cols.addLayout(right, 1)
        card.body.addSpacing(14)
        card.body.addLayout(cols)

        card.body.addSpacing(18)
        self.cfg_fixed = Switch("Considera anche i dischi \"fissi\" non di sistema")
        card.body.addWidget(self.cfg_fixed)
        card.body.addSpacing(4)
        card.body.addWidget(label(t("Molti SSD USB su Windows si presentano come disco fisso."), "hint"))
        card.body.addSpacing(12)
        self.cfg_notify = Switch(t("Notifica di sistema a fine backup"))
        card.body.addWidget(self.cfg_notify)
        card.body.addSpacing(12)
        self.cfg_tray = Switch(t("Chiudendo la finestra resta nella tray"))
        card.body.addWidget(self.cfg_tray)
        card.body.addSpacing(12)
        self.cfg_minimized = Switch(t("All'avvio parti direttamente nella tray"))
        card.body.addWidget(self.cfg_minimized)
        card.body.addSpacing(4)
        card.body.addWidget(label(t("Comodo con l'avvio automatico: il programma si "
                                    "accende da solo senza aprirti la finestra in faccia."),
                                  "hint"))

        lingua_riga = QWidget()
        lay_lingua = QHBoxLayout(lingua_riga)
        lay_lingua.setContentsMargins(0, 0, 0, 0)
        self.cfg_lingua = QComboBox()
        for codice, nome in (("auto", t("Come il sistema")),
                             ("it", t("Italiano")), ("en", t("Inglese"))):
            self.cfg_lingua.addItem(nome, codice)
        self.cfg_lingua.setFixedWidth(200)
        lay_lingua.addWidget(self.cfg_lingua)
        lay_lingua.addStretch(1)
        card.field(t("Lingua"), lingua_riga, t("La lingua cambia alla prossima apertura."))

        card.body.addSpacing(12)
        self.cfg_gitignore = Switch(t("Rispetta i .gitignore dei progetti"))
        card.body.addWidget(self.cfg_gitignore)
        card.body.addSpacing(4)
        card.body.addWidget(label(t("Salta quello che git gia' ignora: node_modules, "
                                    ".venv, build. Niente liste da mantenere a mano."),
                                  "hint"))
        card.body.addSpacing(12)
        riga_ver = QWidget()
        lay_ver = QHBoxLayout(riga_ver)
        lay_ver.setContentsMargins(0, 0, 0, 0)
        lay_ver.setSpacing(9)
        self.cfg_verify = QLineEdit()
        self.cfg_verify.setFixedWidth(90)
        lay_ver.addWidget(self.cfg_verify)
        lay_ver.addWidget(label(t("% dei file copiati, 0 per non verificare"), "hint"), 1)
        card.field(t("Verifica a campione dopo la copia"), riga_ver,
                   t("Confronta l'impronta del file copiato con l'originale: le "
                     "chiavette si guastano in silenzio."))

        self.cfg_exclude = QPlainTextEdit()
        self.cfg_exclude.setFixedHeight(120)
        card.field(t("Esclusioni globali (una per riga)"), self.cfg_exclude)

        bar = QHBoxLayout()
        bar.setSpacing(9)
        bar.addWidget(button(t("Salva impostazioni"), "primary", self.save_cfg))
        bar.addWidget(button(t("Apri cartella backup"), "ghost",
                             lambda: reveal(ub.dest_root_of(self.cfg))))
        bar.addWidget(button(t("Apri il log"), "ghost", self.open_log))
        bar.addStretch(1)
        bar.addWidget(button(t("Esporta sul disco"), "ghost", self.export_settings))
        bar.addWidget(button(t("Importa da file"), "ghost", self.import_settings))
        card.body.addSpacing(20)
        card.body.addLayout(bar)
        lay.addWidget(card)

        auto = Card(t("Avvio automatico al login"),
                    "Windows: attività pianificata ONLOGON, senza finestra.  "
                    "macOS: LaunchAgent caricato con launchctl.")
        row = QHBoxLayout()
        row.setSpacing(9)
        row.addWidget(button(t("Installa"), "normal", lambda: self.autostart(True)))
        row.addWidget(button(t("Rimuovi"), "ghost", lambda: self.autostart(False)))
        row.addStretch(1)
        auto.body.addLayout(row)
        lay.addWidget(auto)
        return page

    # ---------------------------------------------------------------- log
    def _log_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("logpanel")
        panel.setMinimumHeight(120)
        self.log_panel = panel
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(30, 10, 30, 14)
        lay.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(9)
        self.dot = QLabel("●")
        self.dot.setStyleSheet(f"color:{C['dim']};font-size:12px")
        head.addWidget(self.dot)
        head.addWidget(label(t("Log"), "logtitle"))
        self.log_state = label(t("in attesa"), "logstate")
        head.addWidget(self.log_state)
        head.addStretch(1)
        self.btn_log = button(t("Nascondi"), "ghost", self.toggle_log)
        self.btn_log.setProperty("kind", "tiny")
        head.addWidget(self.btn_log)
        head.addWidget(button(t("Pulisci"), "ghost", lambda: self.logview.clear()))
        lay.addLayout(head)

        self.logview = QPlainTextEdit()
        self.logview.setObjectName("logview")
        self.logview.setReadOnly(True)
        self.logview.setMaximumBlockCount(4000)
        self.logview.setPlaceholderText("Nessuna attività finora.")
        lay.addWidget(self.logview, 1)
        return panel

    def toggle_log(self):
        """Riduce il log alla sola barra del titolo, o lo riapre com'era."""
        if self.logview.isVisible():
            self._log_height = max(140, self.log_panel.height())
            self.logview.setVisible(False)
            collapsed = self.log_panel.layout().contentsMargins().top() + \
                self.btn_log.sizeHint().height() + 18
            self.log_panel.setMinimumHeight(collapsed)
            self.log_panel.setMaximumHeight(collapsed)
            self.btn_log.setText("Mostra")
        else:
            self.logview.setVisible(True)
            self.log_panel.setMaximumHeight(16777215)
            self.log_panel.setMinimumHeight(120)
            total = sum(self.splitter.sizes())
            height = getattr(self, "_log_height", 210)
            self.splitter.setSizes([max(200, total - height), height])
            self.btn_log.setText("Nascondi")

    def append_log(self, line: str):
        # le righe di avanzamento iniziano con \r e sostituiscono la precedente,
        # come fa una barra di progresso in un terminale
        progress = line.startswith(ub.PROGRESS_MARK)
        if progress:
            line = line[len(ub.PROGRESS_MARK):]

        color = "#9fb0c9"
        if progress:
            color = "#7fd7ff"
        elif "[errore]" in line:
            color = "#ff8e8e"
        elif "[fine" in line or "[salvato]" in line:
            color = "#5fdca9"
        elif "[attenzione]" in line or "[salto]" in line or "[eliminato]" in line:
            color = C["warn"]
        elif "->" in line or "[watcher]" in line:
            color = "#8fbcff"

        if self._last_progress:
            cursor = self.logview.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.select(QTextCursor.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.deletePreviousChar()
        self._last_progress = progress

        safe = (line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    .replace(" ", "&nbsp;"))
        self.logview.appendHtml(f'<span style="color:{color}">{safe}</span>')
        bar = self.logview.verticalScrollBar()
        bar.setValue(bar.maximum())

    # ---------------------------------------------------------------- toast
    def toast(self, text: str, variant: str = ""):
        widget = Toast(self, text, variant)
        widget.show()
        self.toasts.append(widget)
        self._place_toasts()
        QTimer.singleShot(2600, lambda: self._drop_toast(widget))

    def _drop_toast(self, widget: Toast):
        if widget in self.toasts:
            self.toasts.remove(widget)
        widget.deleteLater()
        self._place_toasts()

    def _place_toasts(self):
        y = self.height() - 28
        for widget in reversed(self.toasts):
            widget.adjustSize()
            y -= widget.height() + 9
            widget.move(self.width() - widget.width() - 28, y)
            widget.raise_()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._place_toasts()

    # ------------------------------------------------------------- pagine
    def show_page(self, index: int):
        self.pages.setCurrentIndex(index)
        self.nav_group.button(index).setChecked(True)
        titles = [(t("Chiavette"), t("cosa copiare da ogni chiavetta")),
                  (t("Questo PC"), t("cosa scambiare tra PC e chiavetta")),
                  (t("Storico"), t("come sono andati gli ultimi giri")),
                  (t("Impostazioni"), t("destinazione, notifiche, avvio automatico"))]
        self.h1.setText(titles[index][0])
        self.h2.setText(titles[index][1])
        if index == 2:
            self.load_history()

    # ------------------------------------------------------------- volumi
    def refresh_volumes(self):
        plan = ub.read_pc_plan(self.cfg)
        self.volumes = []
        for root, removable in ub.list_volumes(bool(self.cfg.get("include_fixed_drives", True))):
            name = ub.volume_label(root)
            self.volumes.append({
                "path": str(root), "label": name, "removable": removable,
                "serial": ub.volume_serial(root),
                "has_plan": (root / ub.MARKER_NAME).is_file(),
                "pc_plan": bool(plan and ub.volume_matches(plan, root, name, removable)),
            })

        while self.vol_grid.count():
            item = self.vol_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.volumes:
            self.volume = None
            self.stick_card.setVisible(False)
            box = QFrame()
            box.setObjectName("empty")
            lay = QVBoxLayout(box)
            lay.setContentsMargins(20, 30, 20, 30)
            lay.setSpacing(6)
            mark = label("", "emptyIcon")
            mark.setPixmap(pixmap_glyph(38, C["line_hi"]))
            mark.setAlignment(Qt.AlignCenter)
            lay.addWidget(mark)
            lay.addSpacing(4)
            for text, name in ((t("Nessun volume collegato"), "emptyTitle"),
                               (t("Infila una chiavetta: compare qui appena il sistema la monta."),
                                "hint")):
                widget = label(text, name)
                widget.setAlignment(Qt.AlignCenter)
                lay.addWidget(widget)
            self.vol_grid.addWidget(box, 0, 0, 1, 3)
            self.update_pc_dest()
            self.check_stale()      # a maggior ragione quando non c'e' niente collegato
            return

        known = [v["path"] for v in self.volumes]
        if self.volume is None or self.volume["path"] not in known:
            self.volume = self.volumes[0]
            self.load_stick_plan()
        else:
            self.volume = next(v for v in self.volumes if v["path"] == self.volume["path"])

        for index, volume in enumerate(self.volumes):
            widget = VolumeCard(volume, volume["path"] == self.volume["path"])
            widget.clicked.connect(self.select_volume)
            self.vol_grid.addWidget(widget, index // 3, index % 3)
        for col in range(3):
            self.vol_grid.setColumnStretch(col, 1)
        self.stick_card.setVisible(True)
        self.update_pc_dest()
        self.check_stale()

    def check_stale(self):
        """Avvisa se un disco visto in passato non viene collegato da troppo."""
        soglia = float(self.cfg.get("stale_days", 7))
        if soglia <= 0:
            self.avviso_box.setVisible(False)
            return
        collegati = set()
        for v in self.volumes:
            collegati.add(ub.chiave_disco(v.get("serial", ""), v["label"]))
            collegati.add(ub.chiave_disco("", v["label"]))
        self._fermi = ub.dischi_fermi(soglia, collegati, self.cfg)
        if not self._fermi:
            self.avviso_box.setVisible(False)
            return
        pezzi = [tf("stale.item", nome=d["nome"], giorni=int(d["giorni"]))
                 for d in self._fermi[:3]]
        self.avviso.setText(t("Non colleghi da un po': ") + ", ".join(pezzi)
                            + t(".  Il backup di quei dischi e' fermo a quella data."))
        self.avviso_box.setVisible(True)

    def forget_stale(self):
        if not self._fermi:
            return
        self.cfg = ub.dimentica_dischi([d["chiave"] for d in self._fermi], self.cfg)
        self.check_stale()

    def select_volume(self, path: str):
        if self.volume and self.volume["path"] == path:
            return
        self.volume = next((v for v in self.volumes if v["path"] == path), None)
        self.load_stick_plan()
        self.refresh_volumes()

    # -------------------------------------------------- piano della chiavetta
    def pick_stick_folder(self) -> str | None:
        if not self.volume:
            self.toast("Seleziona prima una chiavetta", "err")
            return None
        chosen = QFileDialog.getExistingDirectory(
            self, f"Cartella dentro {self.volume['label']}", self.volume["path"])
        if not chosen:
            return None
        rel = relative_to_volume(chosen, Path(self.volume["path"]))
        if rel is None:
            self.toast("Quella cartella non è sulla chiavetta", "err")
            return None
        return rel

    def pick_pc_folder(self) -> str | None:
        chosen = QFileDialog.getExistingDirectory(
            self, t("Cartella del PC da spedire sulla chiavetta"), str(Path.home()))
        return chosen or None

    def pick_pull_dest(self):
        start = self.pull_dest.text().strip() or str(ub.dest_root_of(self.cfg))
        chosen = QFileDialog.getExistingDirectory(
            self, t("Dove far atterrare la roba presa dalla chiavetta"), start)
        if chosen:
            self.pull_dest.setText(chosen)

    def load_stick_plan(self):
        if not self.volume:
            return
        plan = ub.read_stick_plan(Path(self.volume["path"])) or {}
        self.st_name.setText(str(plan.get("name") or ""))
        self.st_name.setPlaceholderText(self.volume["label"])
        self.st_folders.set_rows(folders_from_json(plan.get("folders")))
        self.st_exclude.setPlainText("\n".join(plan.get("exclude") or []))
        self.st_delete.setChecked(bool(plan.get("delete_extra", False)))
        self.update_stick_dest()

    def update_stick_dest(self):
        if not self.volume:
            return
        name = ub.safe_name(self.st_name.text().strip() or self.volume["label"])
        self.stick_card.sub.setText(
            f"{self.volume['path']}   →   {ub.dest_root_of(self.cfg) / name}")
        self.stick_card.sub.setVisible(True)

    def save_stick_plan(self) -> bool:
        if not self.volume:
            return False
        rows = self.st_folders.get_rows()
        if not rows:
            self.toast("Aggiungi almeno una cartella", "err")
            return False
        plan = {"folders": folders_to_json(rows)}
        name = self.st_name.text().strip()
        if name:
            plan["name"] = name
        exclude = lines_of(self.st_exclude.toPlainText())
        if exclude:
            plan["exclude"] = exclude
        plan["delete_extra"] = self.st_delete.isChecked()
        target = Path(self.volume["path"]) / ub.MARKER_NAME
        try:
            target.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            self.toast(f"Scrittura fallita: {exc}", "err")
            return False
        ub.log(tf("saved", path=target))
        self.toast("Salvato sulla chiavetta", "ok")
        self.refresh_volumes()
        return True

    def delete_stick_plan(self):
        if not self.volume:
            return
        target = Path(self.volume["path"]) / ub.MARKER_NAME
        if not target.is_file():
            return
        answer = QMessageBox.question(
            self, t("Conferma"),
            f"Eliminare {target}?\n\nLa chiavetta non verrà più copiata in automatico.\n"
            "I backup già fatti sul PC restano dove sono.")
        if answer != QMessageBox.Yes:
            return
        try:
            target.unlink()
        except OSError as exc:
            self.toast(str(exc), "err")
            return
        ub.log(tf("deleted", path=target))
        self.load_stick_plan()
        self.refresh_volumes()

    # -------------------------------------------------------- piano del PC
    def update_pc_dest(self):
        pc = ub.safe_name(self.pc_name.text().strip() or ub.machine_name())
        sub = self.push_subdir.text().strip() or "backup"
        vol = self.volume["path"] if self.volume else "<chiavetta>"
        self.pc_chip.setText(f"PC: {pc}")
        self.pc_card.sub.setText(f"File: {ub.dest_root_of(self.cfg) / ub.MARKER_NAME}")
        self.push_card.sub.setText(f"Destinazione:   {Path(vol) / sub / pc}")
        landing = self.pull_dest.text().strip()
        stick_name = ub.safe_name(self.volume["label"]) if self.volume else "<chiavetta>"
        default_landing = ub.dest_root_of(self.cfg) / stick_name
        self.pull_dest.setPlaceholderText(str(default_landing))
        self.pull_card.sub.setText(
            f"Destinazione:   {Path(landing) if landing else default_landing}")
        for card in (self.pc_card, self.push_card, self.pull_card):
            card.sub.setVisible(True)

    def bind_serial(self):
        if not self.volume:
            self.toast("Seleziona prima un disco nella scheda Chiavette", "err")
            return
        serial = self.volume.get("serial")
        if not serial:
            self.toast("Questo disco non espone un numero di serie", "err")
            return
        self._only_serials = [serial]
        self.update_serial_label()
        self.toast(f"Piano legato a {self.volume['label']} ({serial})", "ok")

    def unbind_serial(self):
        self._only_serials = []
        self.update_serial_label()

    def update_serial_label(self):
        if self._only_serials:
            quale = self._only_serials[0]
            nome = next((v["label"] for v in self.volumes
                         if v.get("serial") == quale), t("disco non collegato"))
            self.lbl_serial.setText(f"legato a {quale}  ({nome})")
            self.lbl_serial.setStyleSheet(f"color:{C['ok']}")
        else:
            self.lbl_serial.setText(t("nessun vincolo"))
            self.lbl_serial.setStyleSheet(f"color:{C['dim']}")

    def load_pc_plan(self):
        plan = ub.read_pc_plan(self.cfg) or {}
        push = plan.get("push") or {}
        pull = plan.get("pull") or {}
        self.pc_name.setText(str(plan.get("pc_name") or ""))
        only = plan.get("only_volumes") or []
        if isinstance(only, str):
            only = [only]
        self.pc_only.setPlainText("\n".join(str(o) for o in only))
        serials = plan.get("only_serials") or []
        if isinstance(serials, str):
            serials = [serials]
        self._only_serials = [str(x) for x in serials]
        self.update_serial_label()

        self.push_subdir.setText(str(push.get("target_subdir", "") or ""))
        self.push_folders.set_rows(folders_from_json(push.get("folders")))
        self.push_exclude.setPlainText("\n".join(push.get("exclude") or []))
        self.push_delete.setChecked(bool(push.get("delete_extra", False)))

        self.pull_folders.set_rows(folders_from_json(pull.get("folders")))
        self.pull_dest.setText(str(pull.get("dest") or ""))
        self.pull_exclude.setPlainText("\n".join(pull.get("exclude") or []))
        self.pull_delete.setChecked(bool(pull.get("delete_extra", False)))
        self.update_pc_dest()

    def save_pc_plan(self) -> bool:
        plan: dict = {}
        name = self.pc_name.text().strip()
        if name:
            plan["pc_name"] = name
        only = lines_of(self.pc_only.toPlainText())
        if only:
            plan["only_volumes"] = only
        if self._only_serials:
            plan["only_serials"] = self._only_serials

        push_rows = folders_to_json(self.push_folders.get_rows())
        if push_rows:
            push = {"folders": push_rows,
                    "target_subdir": self.push_subdir.text().strip() or "backup",
                    "delete_extra": self.push_delete.isChecked()}
            exclude = lines_of(self.push_exclude.toPlainText())
            if exclude:
                push["exclude"] = exclude
            plan["push"] = push

        pull_rows = folders_to_json(self.pull_folders.get_rows())
        if pull_rows:
            pull = {"folders": pull_rows, "delete_extra": self.pull_delete.isChecked()}
            dest = self.pull_dest.text().strip()
            if dest:
                pull["dest"] = dest
            exclude = lines_of(self.pull_exclude.toPlainText())
            if exclude:
                pull["exclude"] = exclude
            plan["pull"] = pull

        if not push_rows and not pull_rows:
            self.toast("Aggiungi almeno una cartella in Push o in Pull", "err")
            return False

        target = ub.dest_root_of(self.cfg) / ub.MARKER_NAME
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            self.toast(f"Scrittura fallita: {exc}", "err")
            return False
        ub.log(tf("saved", path=target))
        self.toast("Piano del PC salvato", "ok")
        self.refresh_volumes()
        return True

    def delete_pc_plan(self):
        target = ub.dest_root_of(self.cfg) / ub.MARKER_NAME
        if not target.is_file():
            return
        if QMessageBox.question(self, t("Conferma"), f"Eliminare {target}?") != QMessageBox.Yes:
            return
        try:
            target.unlink()
        except OSError as exc:
            self.toast(str(exc), "err")
            return
        ub.log(tf("deleted", path=target))
        self.load_pc_plan()
        self.refresh_volumes()

    # ------------------------------------------------------------ impostazioni
    def pick_dest(self):
        chosen = QFileDialog.getExistingDirectory(self, t("Cartella dei backup"),
                                                  str(ub.dest_root_of(self.cfg)))
        if chosen:
            self.cfg_dest.setText(chosen)

    def open_log(self):
        path = self.cfg.get("log_file")
        if not path:
            self.toast("Log su file disattivato")
            return
        reveal(Path(path).expanduser().parent)

    def load_cfg(self):
        self.cfg_card.sub.setText(f"File: {ub.CONFIG_PATH}")
        self.cfg_card.sub.setVisible(True)
        self.cfg_dest.setText(str(self.cfg.get("dest_root", "")))
        self.cfg_log.setText(str(self.cfg.get("log_file") or ""))
        self.cfg_poll.setText(str(self.cfg.get("poll_seconds", 3)))
        self.cfg_fixed.setChecked(bool(self.cfg.get("include_fixed_drives", True)))
        self.cfg_notify.setChecked(bool(self.cfg.get("notify", True)))
        self.cfg_tray.setChecked(bool(self.cfg.get("close_to_tray", True)))
        self.cfg_minimized.setChecked(bool(self.cfg.get("start_minimized", False)))
        self.cfg_gitignore.setChecked(bool(self.cfg.get("use_gitignore", False)))
        self.cfg_verify.setText(str(self.cfg.get("verify_percent", 1)))
        indice = self.cfg_lingua.findData(str(self.cfg.get("language", "auto")))
        self.cfg_lingua.setCurrentIndex(max(0, indice))
        self.cfg_exclude.setPlainText("\n".join(self.cfg.get("default_exclude", [])))

    def save_cfg(self):
        try:
            poll = max(1, int(self.cfg_poll.text().strip() or "3"))
        except ValueError:
            self.toast("L'intervallo deve essere un numero", "err")
            return
        cfg = dict(self.cfg)
        cfg["dest_root"] = self.cfg_dest.text().strip() or str(Path.home() / "Backup")
        cfg["log_file"] = self.cfg_log.text().strip() or None
        cfg["poll_seconds"] = poll
        cfg["include_fixed_drives"] = self.cfg_fixed.isChecked()
        cfg["notify"] = self.cfg_notify.isChecked()
        cfg["close_to_tray"] = self.cfg_tray.isChecked()
        cfg["start_minimized"] = self.cfg_minimized.isChecked()
        cfg["use_gitignore"] = self.cfg_gitignore.isChecked()
        cfg["language"] = self.cfg_lingua.currentData()
        try:
            cfg["verify_percent"] = max(0.0, min(100.0, float(self.cfg_verify.text())))
        except ValueError:
            self.toast("La percentuale di verifica dev'essere un numero", "err")
            return
        cfg["default_exclude"] = lines_of(self.cfg_exclude.toPlainText())
        try:
            ub.CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
        except OSError as exc:
            self.toast(f"Scrittura fallita: {exc}", "err")
            return
        self.cfg = ub.load_config()
        ub.setup_log(self.cfg.get("log_file"))
        ub.log(tf("saved", path=ub.CONFIG_PATH))
        self.toast("Impostazioni salvate", "ok")
        self.refresh_volumes()
        self.load_pc_plan()
        self.load_cfg()

    def export_settings(self):
        """Mette impostazioni e piano sul disco selezionato, per l'altro PC."""
        if not self.volume:
            self.toast("Seleziona prima un disco nella scheda Chiavette", "err")
            return
        try:
            dove = ub.export_settings(Path(self.volume["path"]), self.cfg)
        except OSError as exc:
            self.toast(f"Non riesco a scrivere: {exc}", "err")
            return
        self.toast(f"Esportato in {dove.name}", "ok")

    def import_settings(self):
        inizio = self.volume["path"] if self.volume else str(Path.home())
        scelto, _ = QFileDialog.getOpenFileName(
            self, t("File di impostazioni da importare"), inizio, "JSON (*.json)")
        if not scelto:
            return
        try:
            nuova, piano = ub.import_settings(Path(scelto), self.cfg)
        except Exception as exc:
            self.toast(f"File non valido: {exc}", "err")
            return
        risposta = QMessageBox.question(
            self, t("Importare?"),
            t("Arrivano impostazioni e piano da un'altra macchina.") + chr(10) * 2
            + t("Restano com'erano: cartella dei backup, file di log e vincoli ")
            + t("ai dischi.") + chr(10)
            + t("I percorsi locali del piano (push) andranno adattati a mano.")
            + chr(10) * 2 + t("Procedo?"))
        if risposta != QMessageBox.Yes:
            return
        try:
            ub.CONFIG_PATH.write_text(json.dumps(nuova, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
            if piano:
                bersaglio = ub.dest_root_of(nuova) / ub.MARKER_NAME
                bersaglio.parent.mkdir(parents=True, exist_ok=True)
                bersaglio.write_text(json.dumps(piano, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
        except OSError as exc:
            self.toast(f"Scrittura fallita: {exc}", "err")
            return
        self.cfg = ub.load_config()
        ub.setup_log(self.cfg.get("log_file"))
        self.load_cfg()
        self.load_pc_plan()
        self.refresh_volumes()
        self.toast("Importato: controlla i percorsi nella scheda Questo PC", "ok")

    def autostart(self, install: bool):
        rc = ub.install_autostart(gui=True) if install else ub.uninstall_autostart()
        ub.log(f"[avvio automatico] {t('installato') if install else t('rimosso')} (codice {rc})")
        self.toast("Avvio automatico " + (t("installato") if install else t("rimosso"))
                   if rc == 0 else f"Operazione fallita (codice {rc})",
                   "ok" if rc == 0 else "err")

    # ------------------------------------------------------------------ run
    def backup_now(self):
        if self.busy or not self.volume:
            return
        answer = QMessageBox.question(
            self, t("Backup adesso"),
            "Il backup usa i file già salvati.\n\nSalvare prima le modifiche aperte?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        if answer == QMessageBox.Cancel:
            return
        if answer == QMessageBox.Yes:
            if self.st_folders.get_rows():
                self.save_stick_plan()
            if self.push_folders.get_rows() or self.pull_folders.get_rows():
                self.save_pc_plan()

        volume = Path(self.volume["path"])
        removable = self.volume["removable"]
        self.busy = True
        ub.clear_stop()
        self.btn_backup.setEnabled(False)
        self.btn_stop.setVisible(True)
        self.log_state.setText("backup in corso…")

        def job():
            try:
                if not ub.handle_volume(volume, self.cfg, removable):
                    ub.log(f"[attenzione] {volume}: niente da fare - nessun backup.json "
                           "sulla chiavetta e il piano del PC non si applica")
            except Exception as exc:
                ub.log(f"[errore] {exc}")
            finally:
                self.bus.backup_done.emit()

        threading.Thread(target=job, daemon=True).start()

    def stop_now(self):
        """Chiede al giro in corso di fermarsi: finisce il file che sta
        copiando e si ferma li'."""
        ub.request_stop()
        self.btn_stop.setEnabled(False)
        self.log_state.setText("mi fermo appena finisce il file…")

    def on_backup_done(self):
        if self._scanning:
            return
        self.busy = False
        self.btn_backup.setEnabled(True)
        self.btn_stop.setVisible(False)
        self.btn_stop.setEnabled(True)
        ub.clear_stop()
        self.log_state.setText("in ascolto" if self.watching() else t("backup terminato"))
        self.refresh_volumes()

    def watching(self) -> bool:
        if self._device_filter is not None or self._fs_watcher is not None:
            return True
        return self.watcher is not None and self.watcher.is_alive()

    def remember_watch(self, on: bool) -> None:
        """Ricorda lo stato dell'interruttore, cosi' alla riapertura riparte
        come l'hai lasciato."""
        if self._restoring:
            return
        cfg = dict(self.cfg)
        cfg["watch_enabled"] = bool(on)
        try:
            ub.CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
            self.cfg = ub.load_config()
        except OSError as exc:
            ub.log(f"[errore] non riesco a ricordare la sorveglianza: {exc}")

    def toggle_watch(self, on: bool):
        self.remember_watch(on)
        if on:
            if sys.platform == "win32":
                # niente controllo periodico: ci pensa Windows ad avvisare
                self._device_filter = DeviceEvents(self.bus)
                QApplication.instance().installNativeEventFilter(self._device_filter)
                ub.log(tf("watch.events", sistema="Windows"))
                self.scan_devices(first=True)
            elif sys.platform == "darwin" and Path("/Volumes").is_dir():
                # su macOS un disco montato compare come voce in /Volumes:
                # basta farsi avvisare quando quella cartella cambia
                self._fs_watcher = QFileSystemWatcher(["/Volumes"], self)
                self._fs_watcher.directoryChanged.connect(
                    lambda _p: self.bus.device_changed.emit())
                ub.log(tf("watch.events", sistema="/Volumes"))
                self.scan_devices(first=True)
            else:
                self.stop_event = threading.Event()
                self.watcher = threading.Thread(target=ub.watch,
                                                args=(self.cfg, self.stop_event),
                                                daemon=True)
                self.watcher.start()
            self.sw_watch.setText("sorveglianza attiva")
            self.log_state.setText("in ascolto")
            self.dot.setStyleSheet(f"color:{C['ok']};font-size:12px")
            self.update_tray()
        else:
            if self._device_filter is not None:
                QApplication.instance().removeNativeEventFilter(self._device_filter)
                self._device_filter = None
                ub.log(tf("watch.stop"))
            if self._fs_watcher is not None:
                self._fs_watcher.deleteLater()
                self._fs_watcher = None
                ub.log(tf("watch.stop"))
            self.stop_event.set()
            self.sw_watch.setText("sorveglianza spenta")
            self.log_state.setText("in attesa")
            self.dot.setStyleSheet(f"color:{C['dim']};font-size:12px")
            self.update_tray()

    def on_device_changed(self):
        """Windows ha segnalato un cambio: aspetto che il volume sia montato
        davvero, poi guardo una volta sola."""
        self._device_timer.start(1500)

    def scan_devices(self, first: bool = False):
        if self.busy or self._scanning:
            self._device_timer.start(3000)      # ci riprovo fra poco
            return
        self._scanning = True

        def job():
            try:
                if first:
                    presenti = ub.list_volumes(bool(self.cfg.get("include_fixed_drives", True)))
                    if presenti:
                        ub.log("[watcher] gia' collegati: " + ", ".join(
                            f"{p} ({ub.volume_label(p)})" for p, _ in presenti))
                    else:
                        ub.log("[watcher] nessun volume collegato, aspetto")
                self._known = ub.scan_once(self.cfg, self._known)
            except Exception as exc:
                ub.log(f"[errore] controllo volumi: {exc}")
            finally:
                self._scanning = False
                self.bus.backup_done.emit()

        threading.Thread(target=job, daemon=True).start()

    def _build_tray(self):
        """Icona vicino all'orologio: chiudendo la finestra il programma resta
        li' a sorvegliare."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(appicon.app_icon(), self)

        menu = QMenu()
        self.act_open = menu.addAction(t("Apri USB Backup"))
        self.act_open.triggered.connect(self.show_from_tray)
        self.act_backup = menu.addAction(t("Backup adesso"))
        self.act_backup.triggered.connect(self.backup_now)
        menu.addSeparator()
        self.act_watch = menu.addAction(t("Sorveglianza"))
        self.act_watch.setCheckable(True)
        self.act_watch.toggled.connect(self.sw_watch.setChecked)
        menu.addSeparator()
        act_quit = menu.addAction(t("Esci"))
        act_quit.triggered.connect(self.quit_app)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_clicked)
        self.update_tray()
        self.tray.show()

    def _tray_clicked(self, reason):
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.show_from_tray()

    def show_from_tray(self):
        primo = not self.isVisible() and not self._titlebar_done
        self.showNormal()
        if primo:
            self._titlebar_done = True
            dark_titlebar(self)
        self.raise_()
        self.activateWindow()

    def update_tray(self):
        if self.tray is None:
            return
        attiva = self.watching()
        self.tray.setToolTip(t("USB Backup - sorveglianza ")
                             + (t("attiva") if attiva else t("spenta")))
        if self.act_watch.isChecked() != attiva:
            self.act_watch.blockSignals(True)
            self.act_watch.setChecked(attiva)
            self.act_watch.blockSignals(False)

    def quit_app(self):
        self._quitting = True
        self.close()

    def closeEvent(self, event):  # noqa: N802
        if self.tray is not None and not self._quitting                 and self.cfg.get("close_to_tray", True):
            event.ignore()
            self.hide()            # in silenzio, senza messaggini
            return
        self.stop_event.set()
        if self.tray is not None:
            self.tray.hide()
        super().closeEvent(event)
        QApplication.instance().quit()


def dark_titlebar(widget: QWidget) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            int(widget.winId()), 20, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass


def main() -> int:
    if sys.platform == "win32":
        try:  # senza questo la barra delle applicazioni mostra l'icona di Python
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("usbbackup.app")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName(t("USB Backup"))
    app.setStyleSheet(QSS)
    app.setFont(QFont(UIFONT, 10 if sys.platform == "win32" else 13))
    app.setWindowIcon(appicon.app_icon())
    app.setQuitOnLastWindowClosed(False)   # la tray tiene vivo il programma
    window = Window()
    in_tray = bool(window.cfg.get("start_minimized")) and window.tray is not None
    if not in_tray:
        window.show()
        dark_titlebar(window)
    else:
        ub.log(tf("start.tray"))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
