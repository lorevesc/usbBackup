"""Dischi fermi: riconosciuti per numero di serie, dimenticabili, e che tornano."""
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub

tmp = Path(tempfile.mkdtemp(prefix="fermi_"))
ub.CONFIG_PATH = tmp / "config.json"
ub.CONFIG_PATH.write_text(json.dumps({"notify": False, "dest_root": str(tmp / "B"),
                                      "log_file": str(tmp / "log.txt")}), encoding="utf-8")
cfg = ub.load_config()
ub.setup_log(cfg["log_file"])
adesso = datetime.now()


def giro(giorni_fa, nome, serial=""):
    return {"quando": (adesso - timedelta(days=giorni_fa)).isoformat(timespec="seconds"),
            "volume": nome, "serial": serial, "copiati": 1}


# due chiavette con lo STESSO nome ma dischi diversi, piu' una voce vecchia
# senza serial, registrata prima che lo si salvasse
storia = [
    giro(1, "KINGSTON", "AAAA1111"),     # usata ieri
    giro(20, "KINGSTON", "BBBB2222"),    # stessa etichetta, altro disco, ferma
    giro(30, "KINGSTON"),                # voce vecchia senza serial: va assorbita
    giro(15, "SSD", "CCCC3333"),
]
ub.history_path().write_text(json.dumps(storia), encoding="utf-8")

visti = ub.dischi_visti()
assert "serial:AAAA1111" in visti and "serial:BBBB2222" in visti, visti
assert "nome:KINGSTON" not in visti, "la voce senza serial ha fatto un doppione"
print("dischi distinti per serial:", sorted(visti))

fermi = ub.dischi_fermi(7, set(), cfg)
chiavi = [d["chiave"] for d in fermi]
assert chiavi == ["serial:BBBB2222", "serial:CCCC3333"], chiavi
print("fermi da piu' di 7 giorni:", [(d["nome"], int(d["giorni"])) for d in fermi])

# collegato adesso: non si segnala
assert [d["chiave"] for d in ub.dischi_fermi(7, {"serial:CCCC3333"}, cfg)] == ["serial:BBBB2222"]
print("un disco collegato adesso non viene segnalato")

# dimenticare
cfg = ub.dimentica_dischi(["serial:BBBB2222"], cfg)
assert "serial:BBBB2222" in cfg["stale_ignore"]
assert [d["chiave"] for d in ub.dischi_fermi(7, set(), cfg)] == ["serial:CCCC3333"]
salvato = json.loads(ub.CONFIG_PATH.read_text(encoding="utf-8"))
assert "serial:BBBB2222" in salvato["stale_ignore"], "non salvato nel config"
print("dimenticato: sparito dall'avviso e salvato nel config")

# se lo ricolleghi e poi torna a restare fermo, torna a essere segnalato
storia.insert(0, giro(0, "KINGSTON", "BBBB2222"))
ub.history_path().write_text(json.dumps(storia), encoding="utf-8")
assert "serial:BBBB2222" not in [d["chiave"] for d in ub.dischi_fermi(7, set(), cfg)]
storia[0] = giro(9, "KINGSTON", "BBBB2222")        # collegato dopo averlo dimenticato
ignorato_quando = cfg["stale_ignore"]["serial:BBBB2222"]
cfg["stale_ignore"]["serial:BBBB2222"] = (adesso - timedelta(days=10)).isoformat(timespec="seconds")
ub.history_path().write_text(json.dumps(storia), encoding="utf-8")
assert "serial:BBBB2222" in [d["chiave"] for d in ub.dischi_fermi(7, set(), cfg)], \
    "ricollegato dopo essere stato dimenticato: deve tornare a contare"
print("ricollegato dopo averlo dimenticato: torna a essere seguito")

# --------------- app: pulsante Dimentica ---------------
ub.history_path().write_text(json.dumps([giro(12, "VECCHIO", "DDDD4444")]), encoding="utf-8")
ub.CONFIG_PATH.write_text(json.dumps({"notify": False, "dest_root": str(tmp / "B"),
                                      "log_file": str(tmp / "log.txt"),
                                      "language": "en"}), encoding="utf-8")
ub.load_config()
ub.list_volumes = lambda inc: []

from PySide6.QtWidgets import QApplication  # noqa: E402
import usb_backup_qt as qt  # noqa: E402

app = QApplication(sys.argv)
win = qt.Window()
win.refresh_volumes()
assert win.avviso_box.isVisibleTo(win) or win._fermi, "avviso non calcolato"
assert "VECCHIO for 12 days" in win.avviso.text(), win.avviso.text()
win.forget_stale()
assert not win._fermi, "dopo Dimentica l'elenco deve essere vuoto"
print("app: avviso in inglese, pulsante Dimentica funziona")
win.close()

shutil.rmtree(tmp, ignore_errors=True)
print("\nDISCHI FERMI OK")
