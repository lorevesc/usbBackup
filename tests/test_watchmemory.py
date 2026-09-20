"""L'interruttore della sorveglianza deve sopravvivere alla chiusura dell'app."""
import json, os, shutil, sys, tempfile, time
from pathlib import Path
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub

tmp = Path(tempfile.mkdtemp(prefix="mem_"))
dest = tmp / "Backup"; dest.mkdir()
ub.CONFIG_PATH = tmp / "config.json"
ub.CONFIG_PATH.write_text(json.dumps({"dest_root": str(dest), "notify": False}), encoding="utf-8")
ub.list_volumes = lambda inc: []
ub.volume_label = lambda r: "X"

from PySide6.QtWidgets import QApplication
import usb_backup_qt as qt
app = QApplication(sys.argv)

win = qt.Window()
assert win.sw_watch.isChecked() is False, "parte accesa senza averglielo detto"
win.sw_watch.setChecked(True)                      # l'utente accende
for _ in range(10):
    app.processEvents(); time.sleep(0.02)
salvato = json.loads(ub.CONFIG_PATH.read_text(encoding="utf-8"))
assert salvato.get("watch_enabled") is True, salvato
print("acceso -> scritto nel config")
win.close()

win2 = qt.Window()                                  # riapro l'app
for _ in range(10):
    app.processEvents(); time.sleep(0.02)
assert win2.sw_watch.isChecked() is True, "riaperta spenta"
assert win2.watching() is True, "interruttore acceso ma non sorveglia"
print("riapertura -> riaccesa da sola e in ascolto")

win2.sw_watch.setChecked(False)                     # l'utente spegne
for _ in range(10):
    app.processEvents(); time.sleep(0.02)
assert json.loads(ub.CONFIG_PATH.read_text(encoding="utf-8"))["watch_enabled"] is False
win2.close()
win3 = qt.Window()
assert win3.sw_watch.isChecked() is False, "riaperta accesa dopo averla spenta"
print("spento -> resta spenta anche alla riapertura")
win3.close()

shutil.rmtree(tmp, ignore_errors=True)
print("\nWATCH MEMORY OK")
