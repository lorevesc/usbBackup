"""Avvio automatico di default: si registra da solo, una volta, e si toglie.

Il registro di Windows qui e' finto: i test non devono registrare niente di
vero sul PC su cui girano.
"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub

tmp = Path(tempfile.mkdtemp(prefix="auto_"))
ub.CONFIG_PATH = tmp / "config.json"
ub.CONFIG_PATH.write_text(json.dumps({"notify": False, "dest_root": str(tmp / "B"),
                                      "log_file": str(tmp / "log.txt")}), encoding="utf-8")
cfg = ub.load_config()
ub.setup_log(None)

# ---------------- registro finto ----------------
# la chiave Run vera non va toccata dai test
registro = {"attivita": None}
comandi = []


def scrivi(valore):
    comandi.append(("scrivi", valore))
    registro["attivita"] = valore


def cancella():
    comandi.append(("cancella",))
    registro["attivita"] = None


ub._run_leggi = lambda: registro["attivita"]
ub._run_scrivi = scrivi
ub._run_cancella = cancella
if not ub.IS_WIN:
    print("fuori da Windows: il registro finto vale solo li', salto")
    print()
    print("AVVIO AUTOMATICO OK")
    sys.exit(0)

# ---------------- acceso di default ----------------
assert ub.DEFAULT_CONFIG["autostart"] is True
assert cfg["autostart"] is True, "la config senza la chiave deve valere acceso"

atteso = ub.launch_command(gui=True)
assert "--tray" in atteso, "all'accensione deve partire nella tray"
assert "usb_backup_qt.py" in atteso or getattr(sys, "frozen", False)
print("comando registrato:", atteso)

# primo avvio: si registra da solo
assert ub.sync_autostart(cfg) == "installato"
assert registro["attivita"] == atteso
assert sum(1 for c in comandi if c[0] == "scrivi") == 1

# avvii successivi: gia' a posto, nessuna nuova registrazione
assert ub.sync_autostart(cfg) == "a posto"
assert ub.sync_autostart(cfg) == "a posto"
assert sum(1 for c in comandi if c[0] == "scrivi") == 1, \
    "ha riscritto la chiave a ogni avvio"
print("primo avvio: registrato; avvii successivi: nessuna riscrittura")

# programma spostato: la registrazione vecchia punta altrove, si rifa'
registro["attivita"] = '"C:\\vecchio\\pythonw.exe" "C:\\vecchio\\usb_backup_qt.py" --tray'
assert ub.sync_autostart(cfg) == "installato"
assert registro["attivita"] == atteso
print("programma spostato: registrazione rifatta col percorso nuovo")

# spento dall'utente: si toglie, e resta tolto
cfg_spento = dict(cfg, autostart=False)
assert ub.sync_autostart(cfg_spento) == "rimosso"
assert registro["attivita"] is None
assert ub.sync_autostart(cfg_spento) == "spento"
print("spento: attivita' rimossa, e non ricompare")

# ---------------- app: interruttore e partenza nella tray ----------------
ub.list_volumes = lambda inc: []
from PySide6.QtWidgets import QApplication  # noqa: E402
import usb_backup_qt as qt  # noqa: E402

app = QApplication(sys.argv)
win = qt.Window()
assert win.cfg_autostart.isChecked() is True, "l'interruttore deve partire acceso"
win.toast = lambda *a, **k: None
win.set_autostart(False)
assert json.loads(ub.CONFIG_PATH.read_text(encoding="utf-8"))["autostart"] is False
assert registro["attivita"] is None
win.set_autostart(True)
assert registro["attivita"] == atteso
print("app: l'interruttore salva la scelta e registra/toglie davvero")

# il caricamento dei valori non deve scatenare registrazioni
prima = len(comandi)
win.load_cfg()
assert len(comandi) == prima, "caricare le impostazioni ha toccato il registro"
print("app: caricare le impostazioni non tocca il registro")

win.close()
shutil.rmtree(tmp, ignore_errors=True)
print("\nAVVIO AUTOMATICO OK")
