#!/usr/bin/env python3
"""Icona dell'applicazione, disegnata a vettori con QPainter.

Nessun file immagine da tenere dietro: l'icona viene generata alla dimensione
richiesta, quindi resta nitida a 16 px come a 512 px. Eseguito da solo, scrive
assets/icon.ico (Windows), assets/icon.png (macOS/Linux) e un provino.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QIcon, QLinearGradient, QPainter,
                           QRadialGradient,
                           QPainterPath, QPen, QPixmap)

ASSETS = Path(__file__).resolve().parent / "assets"
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)

BLUE = "#4f93ff"
VIOLET = "#7b5bff"
WHITE = "#ffffff"


def draw_trident(painter: QPainter, s: float, color: str, detailed: bool = True) -> None:
    """Il simbolo USB: asse orizzontale, disco a sinistra, punta a destra,
    ramo alto che finisce in quadrato e ramo basso che finisce in disco.

    Geometria costruita su un asse ottico unico, cosi' i due rami sono
    simmetrici e lunghi uguale. `detailed=False` toglie i rami: sotto i 24 px
    diventano tre macchie.
    """
    # il simbolo vive in un quadrato normalizzato e viene rimpicciolito dentro
    # la pastiglia, con un margine d'aria attorno
    span = 0.68
    painter.save()
    painter.translate(s * (1 - span) / 2, s * (1 - span) / 2 + s * 0.015)
    painter.scale(span, span)

    axis = s * 0.50
    pen = QPen(QColor(color))
    pen.setWidthF(s * 0.115)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    painter.drawLine(QPointF(s * 0.115, axis), QPointF(s * 0.77, axis))

    fork = QPointF(s * 0.32, axis)      # i due rami partono dallo stesso nodo
    up_to = QPointF(s * 0.58, s * 0.26)
    down_to = QPointF(s * 0.58, s * 0.74)
    if detailed:
        painter.drawLine(fork, up_to)
        painter.drawLine(fork, down_to)

    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    painter.drawEllipse(QPointF(s * 0.115, axis), s * 0.115, s * 0.115)

    head = QPainterPath()       # punta a freccia, triangolo isoscele
    head.moveTo(QPointF(s * 0.755, axis - s * 0.155))
    head.lineTo(QPointF(s * 0.755, axis + s * 0.155))
    head.lineTo(QPointF(s * 1.00, axis))
    head.closeSubpath()
    painter.drawPath(head)

    if detailed:
        side = s * 0.155        # quadrato in punta al ramo alto
        painter.drawRoundedRect(
            QRectF(up_to.x() - side / 2, up_to.y() - side / 2, side, side),
            s * 0.018, s * 0.018)
        painter.drawEllipse(down_to, s * 0.105, s * 0.105)

    painter.restore()


def paint(size: int) -> QPixmap:
    """Icona: simbolo USB bianco su pastiglia blu/viola con un po' di rilievo."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    s = float(size)

    shape = QPainterPath()
    shape.addRoundedRect(QRectF(0, 0, s, s), s * 0.225, s * 0.225)
    painter.setClipPath(shape)

    gradient = QLinearGradient(0, 0, s * 0.35, s)
    gradient.setColorAt(0.0, QColor("#63a5ff"))
    gradient.setColorAt(1.0, QColor("#6a53ff"))
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(gradient))
    painter.drawPath(shape)

    # un filo di luce in alto e un velo d'ombra in basso: volume, senza plastica
    glow = QRadialGradient(QPointF(s * 0.30, s * 0.06), s * 0.72)
    glow.setColorAt(0.0, QColor(255, 255, 255, 46))
    glow.setColorAt(1.0, QColor(255, 255, 255, 0))
    painter.setBrush(QBrush(glow))
    painter.drawPath(shape)

    shade = QLinearGradient(0, s * 0.55, 0, s)
    shade.setColorAt(0.0, QColor(12, 10, 45, 0))
    shade.setColorAt(1.0, QColor(12, 10, 45, 55))
    painter.setBrush(QBrush(shade))
    painter.drawPath(shape)

    if size >= 40:
        edge = QPen(QColor(255, 255, 255, 40))
        edge.setWidthF(max(1.0, s * 0.01))
        painter.setPen(edge)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(shape)

    # ombra appena accennata sotto il simbolo
    if size >= 64:
        painter.save()
        painter.setOpacity(0.22)
        painter.translate(0, s * 0.018)
        draw_trident(painter, s, "#141d52", detailed=True)
        painter.restore()

    draw_trident(painter, s, WHITE, detailed=size >= 24)
    painter.end()
    return pixmap


def glyph(size: int, color: str = WHITE) -> QPixmap:
    """Solo il simbolo, tinta unita su fondo trasparente: serve nell'interfaccia
    al posto delle emoji."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    draw_trident(painter, float(size), color, detailed=size >= 18)
    painter.end()
    return pixmap


def paint_alert(size: int) -> QPixmap:
    """L'icona con un pallino rosso in alto a destra: l'ultimo giro ha avuto errori."""
    pixmap = paint(size)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    s = float(size)
    raggio = s * 0.21
    centro = QPointF(s - raggio - s * 0.02, raggio + s * 0.02)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#0b0e13"))              # anello scuro: si stacca da ogni sfondo
    painter.drawEllipse(centro, raggio + s * 0.05, raggio + s * 0.05)
    painter.setBrush(QColor("#ff4d4f"))
    painter.drawEllipse(centro, raggio, raggio)
    painter.end()
    return pixmap


def app_icon(avviso: bool = False) -> QIcon:
    icon = QIcon()
    for size in SIZES:
        icon.addPixmap(paint_alert(size) if avviso else paint(size))
    return icon


def _png_bytes(size: int) -> bytes:
    store = QByteArray()          # va tenuto vivo: QBuffer non ne prende possesso
    buffer = QBuffer(store)
    buffer.open(QBuffer.WriteOnly)
    paint(size).save(buffer, "PNG")
    buffer.close()
    return bytes(store)


def write_ico(path: Path, sizes=SIZES) -> Path:
    """Scrive un .ico con dentro i PNG (formato supportato da Windows Vista+)."""
    images = [(size, _png_bytes(size)) for size in sizes]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, blobs = b"", b""
    for size, data in images:
        entries += struct.pack("<BBBBHHII", size if size < 256 else 0,
                               size if size < 256 else 0, 0, 0, 1, 32,
                               len(data), offset)
        blobs += data
        offset += len(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + entries + blobs)
    return path


def write_png(path: Path, size: int = 512) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    paint(size).save(str(path), "PNG")
    return path


def _preview(path: Path) -> Path:
    """Provino con tutte le misure in fila, su fondo chiaro e scuro."""
    shown = (16, 24, 32, 48, 64, 128, 256)
    width = sum(s + 16 for s in shown) + 16
    height = 256 * 2 + 60
    sheet = QPixmap(width, height)
    sheet.fill(QColor("#0e1116"))
    painter = QPainter(sheet)
    painter.fillRect(QRectF(0, 0, width, height / 2), QColor("#f2f3f5"))
    x = 16
    for size in shown:
        painter.drawPixmap(x, int(height / 4 - size / 2), paint(size))
        painter.drawPixmap(x, int(height * 3 / 4 - size / 2), paint(size))
        x += size + 16
    painter.end()
    sheet.save(str(path), "PNG")
    return path


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication

    QApplication(sys.argv)
    print(write_ico(ASSETS / "icon.ico"))
    print(write_png(ASSETS / "icon.png", 512))
    if "--preview" in sys.argv:
        print(_preview(ASSETS / "preview.png"))
