"""Chiudendo la finestra il programma deve restare vivo nella tray."""
import json, os, shutil, sys, tempfile, time
from pathlib import Path
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub

tmp = Path(tempfile.mkdtemp(prefix="tray_")); dest = tmp / "Backup"; dest.mkdir()
ub.CONFIG_PATH = tmp / "config.json"
ub.CONFIG_PATH.write_text(json.dumps({"dest_root": str(dest), "notify": False}), encoding="utf-8")
ub.list_volumes = lambda inc: []
ub.volume_label = lambda r: "X"

from PySide6.QtWidgets import QApplication, QSystemTrayIcon
from PySide6.QtGui import QCloseEvent
import usb_backup_qt as qt

app = QApplication(sys.argv)
disponibile = QSystemTrayIcon.isSystemTrayAvailable()
print("tray disponibile in questo ambiente:", disponibile)
win = qt.Window()
win.show()
app.processEvents()

if disponibile:
    assert win.tray is not None, "tray non creata"
    assert win.tray.contextMenu() is not None
    voci = [a.text() for a in win.tray.contextMenu().actions() if a.text()]
    assert voci == ["Apri USB Backup", "Backup adesso", "Sorveglianza", "Esci"], voci
    print("voci del menu:", voci)

    # chiusura: la finestra sparisce ma il programma resta
    win.close()
    app.processEvents()
    assert win.isHidden(), "la finestra non si e' nascosta"
    assert win.isVisible() is False
    print("chiusa: finestra nascosta, programma vivo")

    win.show_from_tray()
    app.processEvents()
    assert win.isVisible(), "non si riapre dalla tray"
    print("riaperta dalla tray")

    # l'interruttore e la voce di menu restano allineati
    win.act_watch.setChecked(True)
    app.processEvents()
    assert win.sw_watch.isChecked(), "menu -> interruttore non funziona"
    win.sw_watch.setChecked(False)
    app.processEvents()
    assert win.act_watch.isChecked() is False, "interruttore -> menu non funziona"
    print("menu e interruttore allineati nei due versi")

    # Esci chiude davvero
    win._quitting = True
    win.close()
    app.processEvents()
    assert win.isHidden()
    print("Esci: chiude davvero")
else:
    win.close()
    print("ambiente senza tray: chiusura normale, nessun errore")

shutil.rmtree(tmp, ignore_errors=True)
print("\nTRAY OK")
