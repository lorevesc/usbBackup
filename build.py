#!/usr/bin/env python3
"""Compila USB Backup in un eseguibile autonomo.

    python build.py

Windows: dist/USB Backup.exe      macOS: dist/USB Backup.app
Nessuna configurazione personale finisce dentro: l'eseguibile parte con i
valori di default e crea il suo config.json accanto a se' al primo salvataggio.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = "USB Backup"
PRIVATI = ("config.json", "backup.json", "scan-totals.json")


def main() -> int:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("Manca PyInstaller:  pip install pyinstaller")
        return 1

    # l'icona serve come file solo per la barra del titolo di Windows;
    # dentro l'app viene comunque ridisegnata a vettori
    icona = HERE / "assets" / "icon.ico" if sys.platform == "win32" else \
        HERE / "assets" / "icon.png"
    if not icona.exists():
        print("Genero l'icona...")
        subprocess.run([sys.executable, str(HERE / "appicon.py")], check=True)

    for cartella in ("build", "dist"):
        shutil.rmtree(HERE / cartella, ignore_errors=True)

    comando = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--name", NAME,
        "--windowed",                       # niente finestra console
        "--onefile",
        "--icon", str(icona),
        # i moduli non importati direttamente dall'entry point
        "--hidden-import", "usb_backup",
        "--hidden-import", "appicon",
        "--paths", str(HERE),
        # fuori tutto cio' che non serve: l'eseguibile dimagrisce parecchio
        "--exclude-module", "tkinter",
        "--exclude-module", "PySide6.QtNetwork",
        "--exclude-module", "PySide6.QtQml",
        "--exclude-module", "PySide6.QtQuick",
        "--exclude-module", "PySide6.Qt3DCore",
        "--exclude-module", "PySide6.QtMultimedia",
        "--exclude-module", "PySide6.QtWebEngineCore",
        "--exclude-module", "PySide6.QtPdf",
        "--exclude-module", "numpy",
        "--exclude-module", "pytest",
        str(HERE / "usb_backup_qt.py"),
    ]
    print(" ".join(comando), "\n")
    esito = subprocess.run(comando, cwd=HERE)
    if esito.returncode != 0:
        return esito.returncode

    # nessun file personale deve essere finito nella cartella consegnata
    for nome in PRIVATI:
        for trovato in (HERE / "dist").rglob(nome):
            trovato.unlink()
            print(f"rimosso dal pacchetto: {trovato}")

    prodotto = next((HERE / "dist").glob("*.exe"), None) or (HERE / "dist" / f"{NAME}.app")
    if prodotto.exists():
        peso = (sum(f.stat().st_size for f in prodotto.rglob("*") if f.is_file())
                if prodotto.is_dir() else prodotto.stat().st_size)
        print(f"\nPronto: {prodotto}  ({peso / 1024 / 1024:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
