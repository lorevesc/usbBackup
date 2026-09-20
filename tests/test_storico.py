"""Storico: il motore registra i giri, l'app li mostra."""
import json, os, shutil, sys, tempfile, time
from pathlib import Path
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub

tmp = Path(tempfile.mkdtemp(prefix="stor_"))
stick = tmp / "STICK"; dest = tmp / "Backup"
(stick / "Documenti").mkdir(parents=True)
for i in range(5):
    (stick / "Documenti" / f"f{i}.txt").write_text("x" * (i + 1), encoding="utf-8")
dest.mkdir()
(stick / "backup.json").write_text(json.dumps(
    {"name": "chiavetta", "folders": ["Documenti"]}), encoding="utf-8")
ub.CONFIG_PATH = tmp / "config.json"
ub.setup_log(str(tmp / "_logs" / "log.txt"))
ub.volume_label = lambda r: "STICK"
ub.list_volumes = lambda inc: [(stick, True)]
cfg = dict(ub.DEFAULT_CONFIG); cfg["dest_root"] = str(dest); cfg["notify"] = False

assert ub.read_history() == [], "storico non vuoto all'inizio"
ub.handle_volume(stick, cfg, True)
ub._last_run.clear()
ub.handle_volume(stick, cfg, True)          # secondo giro: tutto invariato

storia = ub.read_history()
assert len(storia) == 2, storia
recente, vecchio = storia
assert recente["invariati"] == 5 and recente["copiati"] == 0, recente
assert vecchio["copiati"] == 5, vecchio
assert recente["volume"] == "STICK" and recente["errori"] == 0
assert recente["quando"] >= vecchio["quando"], "ordine sbagliato"
assert "secondi" in recente and "byte" in recente
print("motore: 2 giri registrati, il piu' recente per primo")
print("  ", json.dumps(recente, ensure_ascii=False))

# --- la pagina dell'app ---
_orig = ub.load_config
ub.load_config = lambda: {**_orig(), "dest_root": str(dest), "notify": False,
                          "log_file": str(tmp / "_logs" / "log.txt")}
from PySide6.QtWidgets import QApplication
import usb_backup_qt as qt
app = QApplication(sys.argv)
win = qt.Window()
win.show_page(2)
app.processEvents()
tab = win.history_table
assert tab.rowCount() == 2, tab.rowCount()
assert tab.item(0, 1).text() == "STICK"
assert tab.item(0, 3).text() == "5"          # invariati
assert tab.item(1, 2).text() == "5"          # copiati nel primo giro
assert "2 giri registrati" in win.history_card.sub.text()
print("app: tabella con", tab.rowCount(), "righe,", 
      [tab.horizontalHeaderItem(i).text() for i in range(tab.columnCount())])
win.close()
shutil.rmtree(tmp, ignore_errors=True)
print("\nSTORICO OK")
