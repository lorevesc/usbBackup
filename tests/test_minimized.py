"""Avvio diretto nella tray, senza aprire la finestra."""
import json, os, shutil, sys, tempfile
from pathlib import Path
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub
tmp = Path(tempfile.mkdtemp(prefix="min_")); dest = tmp / "Backup"; dest.mkdir()
ub.CONFIG_PATH = tmp / "config.json"
ub.CONFIG_PATH.write_text(json.dumps({"dest_root": str(dest), "notify": False,
                                      "start_minimized": True}), encoding="utf-8")
ub.list_volumes = lambda inc: []
from PySide6.QtWidgets import QApplication
import usb_backup_qt as qt
app = QApplication(sys.argv)
win = qt.Window()
assert win.cfg.get("start_minimized") is True
assert win.isVisible() is False, "la finestra si e' aperta lo stesso"
# gli interruttori nuovi esistono e leggono il config
assert win.cfg_minimized.isChecked() is True
assert win.cfg_tray.isChecked() is True
win.cfg_minimized.setChecked(False)
win.save_cfg()
assert json.loads(ub.CONFIG_PATH.read_text(encoding="utf-8"))["start_minimized"] is False
print("avvio in tray: rispettato, e l'interruttore lo salva")
shutil.rmtree(tmp, ignore_errors=True)
print("\nMINIMIZED OK")
