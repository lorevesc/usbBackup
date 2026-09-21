"""Italiano e inglese: interfaccia, messaggi del motore, scelta della lingua."""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import i18n
import usb_backup as ub

# ---------------- vocabolario ----------------
assert not i18n.mancanti(), f"frasi senza traduzione: {i18n.mancanti()[:5]}"
print(f"vocabolario: {len(i18n.UI)} frasi, {len(i18n.MESSAGGI)} messaggi, nessun buco")

i18n.set_language("it")
assert i18n.t("Salva impostazioni") == "Salva impostazioni"
i18n.set_language("en")
assert i18n.t("Salva impostazioni") == "Save settings"
assert i18n.t("Chiavette") == "Drives"
assert i18n.t("frase mai vista") == "frase mai vista", "deve restare l'originale"
print("t(): italiano invariato, inglese tradotto, sconosciute intatte")

# ---------------- messaggi con parti variabili ----------------
i18n.set_language("it")
riga_it = i18n.tf("verify.start", quanti=5, totale=500)
i18n.set_language("en")
riga_en = i18n.tf("verify.start", quanti=5, totale=500)
assert riga_it == "  verifica a campione: 5 file su 500 copiati", riga_it
assert riga_en == "  spot check: 5 files out of 500 copied", riga_en
assert i18n.tf("chiave.inesistente") == "chiave.inesistente"
assert i18n.tf("verify.start") .strip().startswith("spot check"), "parametri mancanti: non deve esplodere"
print("tf():", riga_en.strip())

# tutti i messaggi devono avere gli stessi segnaposto nelle due lingue
import re
for chiave, (it, en) in i18n.MESSAGGI.items():
    campi_it = set(re.findall(r"\{(\w+)\}", it))
    campi_en = set(re.findall(r"\{(\w+)\}", en))
    assert campi_it == campi_en, f"{chiave}: segnaposto diversi {campi_it} vs {campi_en}"
print(f"segnaposto coerenti in tutti i {len(i18n.MESSAGGI)} messaggi")

# ---------------- il motore parla la lingua scelta ----------------
tmp = Path(tempfile.mkdtemp(prefix="lang_"))
righe = []
ub.add_log_sink(righe.append)
ub.setup_log(None)
(tmp / "src").mkdir()
(tmp / "src" / "f.txt").write_text("x", encoding="utf-8")

ub.CONFIG_PATH = tmp / "config.json"
ub.CONFIG_PATH.write_text(json.dumps({"language": "en", "notify": False,
                                      "dest_root": str(tmp / "Backup")}), encoding="utf-8")
cfg = ub.load_config()          # carica la config e imposta la lingua
assert i18n.get_language() == "en", i18n.get_language()
righe.clear()
ub.run_jobs("prova", [(tmp / "src", tmp / "dst")], [], False, ub.new_stats())
testo = "\n".join(righe)
assert "first run: counting files" in testo, testo
assert "space on" in testo, testo
assert "conto i file" not in testo, "e' rimasto qualcosa in italiano"
print("motore in inglese:", [r for r in righe if "counting" in r][0].strip())

ub.CONFIG_PATH.write_text(json.dumps({"language": "it", "notify": False,
                                      "dest_root": str(tmp / "Backup")}), encoding="utf-8")
ub.load_config()
assert i18n.get_language() == "it"
righe.clear()
ub.run_jobs("prova2", [(tmp / "src", tmp / "dst2")], [], False, ub.new_stats())
assert any("spazio su" in r for r in righe), righe
assert not any("space on" in r for r in righe), "e' rimasto qualcosa in inglese"
print("motore in italiano: ", [r for r in righe if "spazio su" in r][0].strip())

# ---------------- l'app in inglese ----------------
# la lingua la decide il file di configurazione, come nell'uso vero
ub.CONFIG_PATH.write_text(json.dumps({"language": "en", "notify": False,
                                      "dest_root": str(tmp / "Backup")}), encoding="utf-8")
ub.load_config()
assert i18n.get_language() == "en"
ub.list_volumes = lambda inc: []

from PySide6.QtWidgets import QApplication  # noqa: E402
import usb_backup_qt as qt  # noqa: E402

app = QApplication(sys.argv)
win = qt.Window()
assert win.h1.text() == "Drives", win.h1.text()
win.show_page(3)
assert win.h1.text() == "Settings", win.h1.text()
assert win.nav_group.button(1).text() == "This PC"
assert win.history_table.horizontalHeaderItem(0).text() == "When"
assert win.cfg_lingua.count() == 3
assert win.cfg_lingua.currentData() == "en", win.cfg_lingua.currentData()
print("app in inglese: schede", [win.nav_group.button(i).text() for i in range(4)])

win.close()
shutil.rmtree(tmp, ignore_errors=True)
print("\nLINGUE OK")
