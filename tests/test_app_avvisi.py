"""App: avviso errori, dettaglio dei giri con ripristino, nuove opzioni."""
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub

tmp = Path(tempfile.mkdtemp(prefix="avvisi_"))
ub.CONFIG_PATH = tmp / "config.json"
ub.CONFIG_PATH.write_text(json.dumps({
    "notify": False, "dest_root": str(tmp / "Backup"),
    "log_file": str(tmp / "log.txt"), "language": "en",
}), encoding="utf-8")
ub.load_config()
ub.list_volumes = lambda inc: []

from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402
import usb_backup_qt as qt  # noqa: E402

app = QApplication(sys.argv)
win = qt.Window()

# ---------------- intestazioni tradotte anche se la lingua arriva dopo l'import ----------------
intestazioni = [win.history_table.horizontalHeaderItem(i).text()
                for i in range(win.history_table.columnCount())]
assert intestazioni[0] == "When" and intestazioni[2] == "Copied", intestazioni
print("storico: intestazioni in inglese", intestazioni[:3])

# ---------------- nuove opzioni: lette e salvate ----------------
assert win.cfg_versions.isChecked() is False
assert win.cfg_low.isChecked() is True
assert win.cfg_notify_err.isChecked() is True
win.cfg_versions.setChecked(True)
win.save_cfg()
assert json.loads(ub.CONFIG_PATH.read_text(encoding="utf-8"))["keep_versions"] is True
print("opzioni: versioni, secondo piano e avviso errori salvate")

# ---------------- avviso errori ----------------
notifiche = []
if win.tray is not None:
    win.tray.showMessage = lambda *a, **k: notifiche.append(a)
else:
    ub.notify = lambda *a, **k: notifiche.append(a)
win.hide()
win.on_run_finished({"errori": 0, "volume": "SSD"})
assert win._errori_da_vedere == 0 and not notifiche, "avvisa anche senza errori"
win.on_run_finished({"errori": 3, "volume": "SSD"})
assert win._errori_da_vedere == 3, win._errori_da_vedere
assert notifiche, "nessuna notifica sugli errori"
assert "3" in str(notifiche[-1]) and "SSD" in str(notifiche[-1]), notifiche[-1]
win.show()
app.processEvents()
assert win._errori_da_vedere == 0, "aprire l'app deve spegnere l'avviso"
print("errori: notifica inviata, avviso spento all'apertura")

# senza notifica, se l'opzione e' spenta
notifiche.clear()
win.cfg["notify_errors"] = False
win.hide()
win.on_run_finished({"errori": 1, "volume": "SSD"})
assert win._errori_da_vedere == 1 and not notifiche
win.show(); app.processEvents()
print("opzione spenta: niente notifica, ma l'icona segnala lo stesso")

# ---------------- dettaglio del giro e ripristino ----------------
dst = tmp / "dest"
dst.mkdir()
(dst / "doc.txt").write_text("attuale", encoding="utf-8")
(dst / ub.VERSIONS_DIR).mkdir()
salvata = dst / ub.VERSIONS_DIR / "doc.20260101-120000.txt"
salvata.write_text("vecchia buona", encoding="utf-8")
eventi = [
    {"tipo": "errore", "path": "C:/x/rotto.bin", "msg": "Accesso negato"},
    {"tipo": "versione", "originale": str(dst / "doc.txt"), "salvato": str(salvata)},
]
dialogo = qt.EventiDialog(win, "prova", list(eventi), 0)
assert dialogo.albero.topLevelItemCount() == 2
assert dialogo.btn_ripristina.isEnabled()
tipi = [dialogo.albero.topLevelItem(i).text(0) for i in range(2)]
assert tipi == ["Error", "Saved version"], tipi
QMessageBox = qt.QMessageBox
QMessageBox.information = lambda *a, **k: None       # niente finestre modali nel test
dialogo.albero.topLevelItem(1).setSelected(True)
dialogo.ripristina()
assert (dst / "doc.txt").read_text(encoding="utf-8") == "vecchia buona", "non ripristinato"
messa_da_parte = [p.read_text(encoding="utf-8") for p in (dst / ub.VERSIONS_DIR).iterdir()]
assert "attuale" in messa_da_parte, "il file che c'era e' andato perso"
assert dialogo.albero.topLevelItemCount() == 1, "la riga ripristinata deve sparire"
print("dettaglio: tipi in inglese, ripristino fatto, niente perso")

# ---------------- ripristino da una cartella ----------------
trovati = ub.elenca_recuperabili(dst)
assert trovati and trovati[0]["tipo"] == "versione", trovati
dialogo2 = qt.EventiDialog(win, "cartella", trovati, 0, solo_recuperabili=True)
assert dialogo2.albero.topLevelItemCount() == len(trovati)
print("ripristino da cartella:", len(trovati), "file trovati in", ub.VERSIONS_DIR)

# ---------------- icona di avviso ----------------
import appicon  # noqa: E402
normale, allarme = appicon.paint(32), appicon.paint_alert(32)
assert normale.toImage() != allarme.toImage(), "l'icona di avviso e' identica a quella normale"
print("icona: la versione con il pallino rosso e' diversa")

win.close()
shutil.rmtree(tmp, ignore_errors=True)
print("\nAVVISI E DETTAGLI OK")
