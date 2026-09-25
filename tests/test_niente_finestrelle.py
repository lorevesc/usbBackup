"""Avvio nella tray: nessuna finestra deve comparire, nemmeno per un attimo.

Un widget ancora senza genitore a cui si fa setVisible(True) diventa una
finestra a se': all'avvio automatico si vedevano dodici finestrelle comparire
e sparire, una per ogni sottotitolo delle schede.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub

tmp = Path(tempfile.mkdtemp(prefix="finestrelle_"))
disco = tmp / "DISCO"
disco.mkdir()
(disco / "backup.json").write_text(json.dumps({"folders": ["."]}), encoding="utf-8")
ub.CONFIG_PATH = tmp / "config.json"
ub.CONFIG_PATH.write_text(json.dumps({
    "dest_root": str(tmp / "Backup"), "log_file": str(tmp / "log.txt"),
    "autostart": False, "notify": False, "language": "it"}), encoding="utf-8")
ub.load_config()
ub.handle_volume = lambda *a, **k: False
volumi = []
ub.list_volumes = lambda inc: list(volumi)
ub.volume_label = lambda r: "DISCO"
ub.volume_serial = lambda r: "AB12-CD34"

from PySide6.QtCore import QEvent, QObject  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import usb_backup_qt as qt  # noqa: E402

app = QApplication(sys.argv)
mostrate = []


class Spia(QObject):
    def eventFilter(self, obj, ev):  # noqa: N802
        if ev.type() == QEvent.Show and obj.isWidgetType() and obj.isWindow():
            testo = obj.text() if hasattr(obj, "text") else ""
            mostrate.append(f"{type(obj).__name__} {obj.objectName()!r} {str(testo)[:40]!r}")
        return False


spia = Spia()
app.installEventFilter(spia)

win = qt.Window()                       # come main() con --tray: la finestra resta nascosta
app.processEvents()
assert not mostrate, "all'avvio compaiono finestre:\n" + "\n".join(mostrate)
print("avvio nella tray: nessuna finestra")

volumi.append((disco, True))            # disco collegato con la finestra nascosta
win.refresh_volumes()
win.load_history()
win.load_pc_plan()
for pagina in range(4):
    win.show_page(pagina)
volumi.clear()
win.refresh_volumes()
app.processEvents()
assert not mostrate, "con la finestra nascosta compaiono finestre:\n" + "\n".join(mostrate)
print("disco collegato e staccato, storico, pagine: nessuna finestra")

win.show()
app.processEvents()
assert [m for m in mostrate if m.startswith("Window")], "la finestra vera non si apre"
assert len(mostrate) == 1, "aprendo la finestra compaiono altre finestre:\n" + "\n".join(mostrate)
print("aperta a mano: compare solo la finestra dell'app")

print("\nNIENTE FINESTRELLE OK")
