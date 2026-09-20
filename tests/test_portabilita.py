"""Esporta/importa la configurazione, e avviso sui dischi fermi da troppo."""
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

tmp = Path(tempfile.mkdtemp(prefix="port_"))
disco = tmp / "SSD"
disco.mkdir()
casa = tmp / "casa"
(casa / "Backup" / "_logs").mkdir(parents=True)
ufficio = tmp / "ufficio"
(ufficio / "Backup" / "_logs").mkdir(parents=True)

# ---------------- PC di casa: config e piano ----------------
ub.CONFIG_PATH = tmp / "config_casa.json"
cfg_casa = {
    "dest_root": str(casa / "Backup"),
    "log_file": str(casa / "Backup" / "_logs" / "log.txt"),
    "notify": False,
    "copy_threads": 4,
    "use_gitignore": True,
    "verify_percent": 5,
    "watch_enabled": True,
    "default_exclude": ["*.tmp", "roba_mia"],
}
ub.CONFIG_PATH.write_text(json.dumps(cfg_casa), encoding="utf-8")
cfg_casa = ub.load_config()
ub.setup_log(cfg_casa["log_file"])
(Path(cfg_casa["dest_root"]) / ub.MARKER_NAME).write_text(json.dumps({
    "pc_name": "pc-casa",
    "only_serials": ["AABB1122"],
    "push": {"folders": [{"path": "C:/WorkArea", "as": "WorkArea"}]},
    "pull": {"folders": ["Codice"]},
}), encoding="utf-8")

percorso = ub.export_settings(disco, cfg_casa)
assert percorso.is_file()
dati = json.loads(percorso.read_text(encoding="utf-8"))
assert dati["da_pc"] == "pc-casa"
assert "dest_root" not in dati["config"], "ha esportato un percorso locale"
assert "log_file" not in dati["config"], "ha esportato il file di log"
assert "watch_enabled" not in dati["config"], "ha esportato lo stato dell'interruttore"
assert dati["config"]["copy_threads"] == 4
assert dati["piano"]["push"]["folders"][0]["as"] == "WorkArea"
print("esportato:", percorso.name, "->", sorted(dati["config"]))

# ---------------- PC dell'ufficio: importa ----------------
ub.CONFIG_PATH = tmp / "config_ufficio.json"
cfg_ufficio = {
    "dest_root": str(ufficio / "Backup"),
    "log_file": str(ufficio / "Backup" / "_logs" / "log.txt"),
    "notify": False,
    "copy_threads": 8,
    "use_gitignore": False,
}
ub.CONFIG_PATH.write_text(json.dumps(cfg_ufficio), encoding="utf-8")
cfg_ufficio = ub.load_config()

nuova, piano = ub.import_settings(percorso, cfg_ufficio)
assert nuova["dest_root"] == str(ufficio / "Backup"), "ha sovrascritto la cartella locale"
assert nuova["log_file"] == cfg_ufficio["log_file"], "ha sovrascritto il log locale"
assert nuova["copy_threads"] == 4, "non ha preso le impostazioni condivise"
assert nuova["use_gitignore"] is True
assert nuova["default_exclude"] == ["*.tmp", "roba_mia"]
assert "only_serials" not in piano, "ha importato il vincolo al disco dell'altro PC"
assert "pc_name" not in piano, "ha importato il nome dell'altro PC"
assert piano["pull"]["folders"] == ["Codice"], piano
print("importato: impostazioni condivise sì, roba locale e vincoli no")

# ---------------- avviso sui dischi fermi ----------------
ub.setup_log(str(ufficio / "Backup" / "_logs" / "log.txt"))
adesso = datetime.now()
storia = [
    {"quando": (adesso - timedelta(days=0.2)).isoformat(timespec="seconds"),
     "volume": "COLLEGATO-OGGI", "copiati": 1},
    {"quando": (adesso - timedelta(days=12)).isoformat(timespec="seconds"),
     "volume": "SSD-DIMENTICATO", "copiati": 30},
    {"quando": (adesso - timedelta(days=40)).isoformat(timespec="seconds"),
     "volume": "CHIAVETTA-VECCHIA", "copiati": 5},
]
ub.history_path().write_text(json.dumps(storia), encoding="utf-8")
giorni = ub.giorni_da_ultimo_backup()
assert round(giorni["SSD-DIMENTICATO"]) == 12, giorni
assert round(giorni["CHIAVETTA-VECCHIA"]) == 40, giorni
print("giorni dall'ultimo giro:", {k: round(v) for k, v in giorni.items()})

_orig = ub.load_config
ub.load_config = lambda: {**_orig(), "dest_root": str(ufficio / "Backup"),
                          "log_file": str(ufficio / "Backup" / "_logs" / "log.txt"),
                          "notify": False, "stale_days": 7}
ub.list_volumes = lambda inc: [(disco, True)]
ub.volume_label = lambda r: "COLLEGATO-OGGI"      # quello collegato ora
ub.volume_serial = lambda r: "ZZZZ"

from PySide6.QtWidgets import QApplication  # noqa: E402
import usb_backup_qt as qt  # noqa: E402

app = QApplication(sys.argv)
win = qt.Window()
assert win.avviso.isVisible() is False or win.avviso.text(), "avviso non calcolato"
testo = win.avviso.text()
assert "SSD-DIMENTICATO da 12 giorni" in testo, testo
assert "CHIAVETTA-VECCHIA da 40 giorni" in testo, testo
assert "COLLEGATO-OGGI" not in testo, "avvisa su un disco che e' collegato adesso"
print("avviso:", testo[:88])
win.close()

shutil.rmtree(tmp, ignore_errors=True)
print("\nPORTABILITA OK")
