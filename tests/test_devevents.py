"""La sorveglianza su Windows deve funzionare a eventi, senza controlli periodici."""
import os, shutil, sys, tempfile, time
from pathlib import Path
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub

tmp = Path(tempfile.mkdtemp(prefix="dev_"))
disco = tmp / "SSD"; disco.mkdir()
dest = tmp / "Backup"; dest.mkdir()
letture = {"n": 0}
_orig_list = ub.list_volumes
presente = [True]
def finto_list(inc):
    letture["n"] += 1
    return [(disco, True)] if presente[0] else []
ub.list_volumes = finto_list
ub.volume_label = lambda r: "SSD"
ub.CONFIG_PATH = tmp / "config.json"
_orig_cfg = ub.load_config
ub.load_config = lambda: {**_orig_cfg(), "dest_root": str(dest), "notify": False}
giri = {"n": 0}
ub.handle_volume = lambda root, cfg, rem: (giri.__setitem__("n", giri["n"] + 1), True)[-1]

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication
import usb_backup_qt as qt

app = QApplication(sys.argv)
win = qt.Window()

# accendo la sorveglianza: deve lavorare subito su quello che c'e' gia'
win.sw_watch.setChecked(True)
for _ in range(40):
    app.processEvents(); time.sleep(0.05)
assert giri["n"] == 1, f"non ha guardato all'avvio (giri={giri['n']})"
assert win._device_filter is not None, "filtro eventi non installato"
assert win.watcher is None, "ha avviato lo scandaglio periodico invece degli eventi"
letture_dopo_avvio = letture["n"]
print(f"avvio: {giri['n']} giro, {letture_dopo_avvio} letture dell'elenco unita'")

# aspetto: senza eventi non deve toccare niente
time.sleep(3)
for _ in range(20):
    app.processEvents(); time.sleep(0.02)
assert letture["n"] == letture_dopo_avvio, (
    f"ha continuato a guardare da solo: {letture['n'] - letture_dopo_avvio} letture in 3s")
assert giri["n"] == 1
print("3 secondi di attesa: nessuna lettura in piu'")

# simulo l'evento di Windows: disco nuovo
ub._last_run.clear()
win._known = set()
win.bus.device_changed.emit()
for _ in range(80):
    app.processEvents(); time.sleep(0.05)
assert giri["n"] == 2, f"evento ignorato (giri={giri['n']})"
print("evento di collegamento: un giro, subito")

win.sw_watch.setChecked(False)
for _ in range(10):
    app.processEvents(); time.sleep(0.02)
assert win._device_filter is None, "filtro non rimosso allo spegnimento"
print("spegnimento: filtro rimosso")

win.close()
ub.list_volumes = _orig_list
shutil.rmtree(tmp, ignore_errors=True)
print("\nDEVICE EVENTS OK")
