"""App: freno con domanda, uscita durante un giro, verifica completa dal pulsante,
configurazione guidata, disinstalla, disco staccato durante la verifica."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub

tmp = Path(tempfile.mkdtemp(prefix="nuove_"))
disco = tmp / "DISCO"
(disco / "Documenti").mkdir(parents=True)
for i in range(5):
    (disco / "Documenti" / f"d{i}.txt").write_text(f"doc {i}", encoding="utf-8")
(disco / "backup.json").write_text(json.dumps({"folders": ["Documenti"]}), encoding="utf-8")
ub.CONFIG_PATH = tmp / "config.json"
ub.CONFIG_PATH.write_text(json.dumps({
    "notify": False, "dest_root": str(tmp / "Backup"), "log_file": str(tmp / "log.txt"),
    "language": "it", "autostart": False, "verify_percent": 0,
}), encoding="utf-8")
ub.load_config()
ub.list_volumes = lambda inc: [(disco, True)]
ub.volume_label = lambda r: "DISCO"
ub.volume_serial = lambda r: "AB12-CD34"

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402
import usb_backup_qt as qt  # noqa: E402

app = QApplication(sys.argv)
win = qt.Window()
win.refresh_volumes()
assert win.volume and win.volume["label"] == "DISCO", win.volume


def aspetta_fine(secondi=20):
    fine = time.time() + secondi
    while win.busy and time.time() < fine:
        app.processEvents()
        time.sleep(0.02)
    app.processEvents()
    assert not win.busy, "il giro non finisce"


class Finta(QMessageBox):
    """QMessageBox che non si apre: 'premi' il pulsante con il testo scelto."""
    premi = ""
    risposta = QMessageBox.Ok
    viste = []

    def exec(self):
        Finta.viste.append(self.text())
        self._premuto = next((b for b in self.buttons() if b.text() == Finta.premi), None)
        return Finta.risposta

    def clickedButton(self):  # noqa: N802
        return self._premuto

    @staticmethod
    def information(*a, **k):
        Finta.viste.append(a[2] if len(a) > 2 else "")
        return QMessageBox.Ok

    @staticmethod
    def warning(*a, **k):
        Finta.viste.append(a[2] if len(a) > 2 else "")
        return Finta.risposta


qt.QMessageBox = Finta

# ---------------- freno: si chiede, e solo col si' si riparte ----------------
giri = []
win._avvia_giro = lambda radice, rimovibile, dopo_freno=False: giri.append((radice, dopo_freno))
voce = {"volume": "DISCO", "root": str(disco), "freno": {"n": 80, "totale": 100, "dove": "x"}}
Finta.risposta = QMessageBox.No
win.on_run_finished(voce)
assert not giri, "ripartito senza consenso"
assert "80" in Finta.viste[-1] and "100" in Finta.viste[-1], Finta.viste[-1]
Finta.risposta = QMessageBox.Yes
win.on_run_finished(voce)
assert giri == [(disco, True)], giri
toast = []
win.toast = lambda testo, variante="": toast.append((testo, variante))
win.on_run_finished(dict(voce, root=str(tmp / "SPARITO")))
assert len(giri) == 1 and toast and toast[-1][1] == "err", toast
del win._avvia_giro
print("freno: No non riparte, Si' riparte con il freno saltato, disco sparito avvisa")

# ---------------- uscita durante un giro ----------------
fermati = []
originale_stop = ub.request_stop
ub.request_stop = lambda: fermati.append(1)
win.busy = True
Finta.premi = qt.t("Annulla")
win.quit_app()
assert not win._quitting and not win._esci_a_fine and not fermati
Finta.premi = qt.t("Esci appena finisce")
win.show()
win.quit_app()
assert win._esci_a_fine and not win._quitting and not win.isVisible() and not fermati
print("uscita: Annulla non fa niente, 'appena finisce' nasconde e aspetta")
win._esci_a_fine = False
Finta.premi = qt.t("Esci subito")
win.close = lambda: None                     # chiudere davvero spegnerebbe il test
win.quit_app()
assert fermati and win._quitting
win._quitting = False
win.busy = False
ub.request_stop = originale_stop
del win.close
print("uscita: 'subito' ferma il giro ed esce")

# ---------------- giro vero, poi verifica completa dal pulsante ----------------
win._avvia_giro(disco, True)
aspetta_fine()
copia = tmp / "Backup" / "DISCO" / "Documenti"
assert len(list(copia.glob("*.txt"))) == 5, list(copia.iterdir())
dialoghi = []
qt.EventiDialog.exec = lambda self: dialoghi.append(self)
toast.clear()
win.verify_now()
aspetta_fine()
assert toast and toast[-1][1] == "ok" and not dialoghi, (toast, dialoghi)
(copia / "d2.txt").write_text("alterato", encoding="utf-8")
win.verify_now()
aspetta_fine()
assert len(dialoghi) == 1, "differenza non mostrata"
print("verifica: tutto ok con un messaggio, differenza mostrata nel dettaglio")

# disco staccato durante la verifica: l'app non deve restare bloccata su "occupato"
originale_verifica = ub.verifica_completa
def verifica_lenta(*a, **k):
    time.sleep(0.3)
    return {"verificati": 0, "diversi": 0, "mancanti": 0, "eventi": []}
ub.verifica_completa = verifica_lenta
win.verify_now()
win.volume = None                             # il disco se n'e' andato
aspetta_fine()
ub.verifica_completa = originale_verifica
win.refresh_volumes()
print("verifica: disco sparito a meta', l'app torna libera")

# ---------------- configurazione guidata ----------------
guida = qt.PrimoAvvio(win)
assert guida.disco()["label"] == "DISCO"
guida.cartelle_push.set_rows([{"path": str(tmp / "Progetto"), "name": "Progetto"}])
guida.cartelle_pull.set_rows([{"path": "Documenti", "name": ""}])
guida.salva()
piano = json.loads((tmp / "Backup" / "backup.json").read_text(encoding="utf-8"))
assert piano["only_serials"] == ["AB12-CD34"], piano
assert piano["push"]["folders"] and piano["pull"]["folders"], piano
assert json.loads(ub.CONFIG_PATH.read_text(encoding="utf-8"))["wizard_done"] is True
assert win.sw_watch.isChecked(), "senza sorveglianza il piano non parte"
win.sw_watch.setChecked(False)
print("guida: piano legato al numero di serie, sorveglianza accesa")

# ---------------- disinstalla ----------------
chiamate = []
ub.disinstalla = lambda togli_impostazioni: chiamate.append(togli_impostazioni) or []
win.close = lambda: None
Finta.risposta = QMessageBox.Cancel
win.uninstall()
assert not chiamate
Finta.risposta = QMessageBox.Ok
win.uninstall()
assert chiamate == [False], chiamate
assert json.loads(ub.CONFIG_PATH.read_text(encoding="utf-8"))["autostart"] is False
print("disinstalla: Annulla non tocca niente; OK toglie e lascia l'avvio spento")

# ---------------- stile e pulsanti dei dialoghi ----------------
assert "down-arrow" in qt.stile_app()
qt.traduci_qt(app)
assert app.translate("QPlatformTheme", "Cancel") == "Annulla", app.translate("QPlatformTheme", "Cancel")
print("dialoghi: freccia dei menu e pulsanti standard in italiano")

print("\nAPP NUOVE OK")
