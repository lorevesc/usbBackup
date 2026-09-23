#!/usr/bin/env python3
"""Compila USB Backup in un eseguibile autonomo.

    python build.py

Windows: dist/USB Backup.exe      macOS: dist/USB Backup.app
Nessuna configurazione personale finisce dentro: l'eseguibile parte con i
valori di default e crea il suo config.json accanto a se' al primo salvataggio.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
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

    # Un eseguibile in esecuzione tiene il file bloccato: PyInstaller fallisce
    # a meta' e la vecchia versione resta li', identica, a far credere che sia
    # andato tutto bene.
    prodotto = HERE / "dist" / (NAME + (".exe" if sys.platform == "win32" else ""))
    if prodotto.exists():
        # Windows rilascia il file con qualche istante di ritardo dopo la
        # chiusura del programma: vale la pena riprovare prima di arrendersi.
        for tentativo in range(6):
            try:
                with prodotto.open("r+b"):
                    break
            except OSError:
                if tentativo == 0:
                    print(f"{prodotto.name} risulta in uso, aspetto che si liberi...")
                time.sleep(1)
        else:
            print(f"ERRORE: {prodotto.name} e' ancora in uso.")
            print("Chiudi l'applicazione del tutto - anche dall'icona vicino "
                  "all'orologio - e rilancia.")
            return 2

    for cartella in ("build", "dist"):
        shutil.rmtree(HERE / cartella, ignore_errors=True)
        if (HERE / cartella).exists():
            print(f"ERRORE: non riesco a svuotare {cartella}/: file in uso.")
            return 2

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
        print("",
              "ERRORE: PyInstaller e' uscito con codice",
              esito.returncode, "- niente eseguibile nuovo.")
        return esito.returncode

    # nessun file personale deve essere finito nella cartella consegnata
    for nome in PRIVATI:
        for trovato in (HERE / "dist").rglob(nome):
            trovato.unlink()
            print(f"rimosso dal pacchetto: {trovato}")

    prodotto = next((HERE / "dist").glob("*.exe"), None) or (HERE / "dist" / f"{NAME}.app")
    if prodotto is None or not prodotto.exists():
        print("ERRORE: la compilazione non ha prodotto nessun eseguibile.")
        return 3
    if prodotto.exists():
        peso = (sum(f.stat().st_size for f in prodotto.rglob("*") if f.is_file())
                if prodotto.is_dir() else prodotto.stat().st_size)
        print(f"\nPronto: {prodotto}  ({peso / 1024 / 1024:.1f} MB)")
        firma(prodotto)
    return 0


def firma(eseguibile: Path) -> bool:
    """Firma l'eseguibile, se e' stato indicato un certificato.

    Senza firma Windows mostra "Windows ha protetto il PC", e alcune policy
    aziendali bloccano del tutto il programma. Si usa Set-AuthenticodeSignature
    di PowerShell, che non richiede l'SDK di Windows.

    Il certificato si indica con variabili d'ambiente:
      USBBACKUP_SIGN_THUMBPRINT   impronta di un certificato gia' presente
                                  nell'archivio personale di Windows
      USBBACKUP_SIGN_PFX          oppure un file .pfx...
      USBBACKUP_SIGN_PASSWORD     ...con la sua password
    """
    if sys.platform != "win32":
        return False
    impronta = os.environ.get("USBBACKUP_SIGN_THUMBPRINT", "").strip()
    pfx = os.environ.get("USBBACKUP_SIGN_PFX", "").strip()
    if not impronta and not pfx:
        print("Eseguibile NON firmato: nessun certificato indicato (vedi README).")
        return False

    if pfx:
        carica = ("$c = New-Object System.Security.Cryptography.X509Certificates"
                  ".X509Certificate2($env:USBBACKUP_SIGN_PFX, $env:USBBACKUP_SIGN_PASSWORD)")
    else:
        carica = "$c = Get-Item ('Cert:/CurrentUser/My/' + $env:USBBACKUP_SIGN_THUMBPRINT)"
    script = (carica + "; "
              "$r = Set-AuthenticodeSignature -FilePath $env:USBBACKUP_EXE -Certificate $c "
              "-HashAlgorithm SHA256 -TimestampServer http://timestamp.digicert.com; "
              "$r.Status")
    ambiente = dict(os.environ, USBBACKUP_EXE=str(eseguibile))
    esito = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                           capture_output=True, text=True, env=ambiente,
                           creationflags=0x08000000)     # niente console
    ultima = (esito.stdout or "").strip().splitlines()[-1:] or [""]
    if esito.returncode == 0 and ultima[0] == "Valid":
        print("Eseguibile firmato.")
        return True
    print("ATTENZIONE: firma non riuscita, l'eseguibile resta non firmato.")
    print((esito.stderr or esito.stdout or "").strip()[-400:])
    return False


if __name__ == "__main__":
    sys.exit(main())
