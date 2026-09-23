"""Versioni dei file sovrascritti, ripristino, eventi dei giri, priorita' bassa."""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub

ub.setup_log(None)
ub._config_cache["verify_percent"] = 0
tmp = Path(tempfile.mkdtemp(prefix="vers_"))
src = tmp / "pc"
dst = tmp / "ssd"
src.mkdir()
buono = src / "contratto.txt"
buono.write_text("versione BUONA", encoding="utf-8")

# ---------------- 1. senza l'opzione: comportamento di prima ----------------
ub._config_cache["keep_versions"] = False
ub.mirror_tree(src, dst, [], False, ub.new_stats())
buono.write_text("rovinato da un ransomware", encoding="utf-8")
os.utime(buono, (time.time() + 10, time.time() + 10))
ub.mirror_tree(src, dst, [], False, ub.new_stats())
assert not (dst / ub.VERSIONS_DIR).exists(), "versioni create senza l'opzione"
print("senza opzione: nessuna versione (come prima)")

# ---------------- 2. con l'opzione: la versione buona sopravvive ----------------
shutil.rmtree(dst)
buono.write_text("versione BUONA", encoding="utf-8")
ub._config_cache["keep_versions"] = True
ub.mirror_tree(src, dst, [], False, ub.new_stats())
buono.write_text("rovinato da un ransomware", encoding="utf-8")
os.utime(buono, (time.time() + 20, time.time() + 20))
stats = ub.new_stats()
ub.mirror_tree(src, dst, [], False, stats)
assert (dst / "contratto.txt").read_text(encoding="utf-8") == "rovinato da un ransomware"
versioni = list((dst / ub.VERSIONS_DIR).glob("contratto.*.txt"))
assert len(versioni) == 1, versioni
assert versioni[0].read_text(encoding="utf-8") == "versione BUONA", "versione buona persa"
assert stats.get("versioned") == 1, stats
eventi = [e for e in stats["eventi"] if e["tipo"] == "versione"]
assert eventi and eventi[0]["salvato"] == str(versioni[0]), stats["eventi"]
print("con opzione: la versione buona e' in", versioni[0].name)

# un secondo cambiamento non sovrascrive la prima versione: si accumulano
buono.write_text("terza versione", encoding="utf-8")
os.utime(buono, (time.time() + 40, time.time() + 40))
time.sleep(1.1)
ub.mirror_tree(src, dst, [], False, ub.new_stats())
assert len(list((dst / ub.VERSIONS_DIR).glob("contratto.*.txt"))) == 2
print("le versioni si accumulano, nessuna sovrascrive l'altra")

# le versioni non vengono mai copiate come se fossero dati
esclusi = ub._excludes_for({}, {})
assert ub.VERSIONS_DIR in esclusi and ub.VERSIONS_DIR in ub.SYNC_DEFAULT_EXCLUDE

# ---------------- 3. ripristino ----------------
radice, originale, tipo = ub.origine_di(versioni[0])
assert radice == dst and originale == dst / "contratto.txt" and tipo == "versione", \
    (radice, originale, tipo)
recuperabili = ub.elenca_recuperabili(dst)
assert len(recuperabili) == 2 and all(r["tipo"] == "versione" for r in recuperabili)
assert recuperabili[0]["quando"] >= recuperabili[1]["quando"], "ordine: piu' recente prima"

ripristinato = ub.ripristina(versioni[0])
assert ripristinato == dst / "contratto.txt"
assert ripristinato.read_text(encoding="utf-8") == "versione BUONA"
# quello che c'era al suo posto non e' andato perso: e' finito nelle versioni
contenuti = sorted(v.read_text(encoding="utf-8")
                   for v in (dst / ub.VERSIONS_DIR).glob("contratto.*.txt"))
assert "terza versione" in contenuti, contenuti
print("ripristino: tornata la versione buona, quella corrente messa da parte")

# ripristino dal cestino, con una sottocartella
(src / "sotto").mkdir()
(src / "sotto" / "nota.md").write_text("nota", encoding="utf-8")
ub.mirror_tree(src, dst, [], True, ub.new_stats())
(src / "sotto" / "nota.md").unlink()
s2 = ub.new_stats()
ub.mirror_tree(src, dst, [], True, s2)
cestinati = [e for e in s2["eventi"] if e["tipo"] == "cestino"]
assert cestinati, s2
nel_cestino = Path(cestinati[0]["salvato"])
assert nel_cestino.exists()
tornato = ub.ripristina(nel_cestino)
assert tornato == dst / "sotto" / "nota.md" and tornato.read_text(encoding="utf-8") == "nota"
print("ripristino dal cestino: tornato in sotto/nota.md")

# ---------------- 4. eventi nello storico e aggancio ----------------
ub.setup_log(str(tmp / "log.txt"))
ricevuti = []
ub.add_run_sink(ricevuti.append)
disco = tmp / "DISCO"
(disco / "Documenti").mkdir(parents=True)
(disco / "Documenti" / "a.txt").write_text("a", encoding="utf-8")
(disco / "backup.json").write_text(json.dumps({"folders": ["Documenti"]}), encoding="utf-8")
ub.volume_label = lambda r: "DISCO"
ub.volume_serial = lambda r: "ABCD0001"
cfg = dict(ub.DEFAULT_CONFIG, dest_root=str(tmp / "Backup"), notify=False)
ub.handle_volume(disco, cfg, True)
assert ricevuti and ricevuti[-1]["volume"] == "DISCO", "l'app non viene avvisata"
voce = ub.read_history()[0]
assert "eventi" in voce and "versioni" in voce, voce.keys()
print("storico: ogni giro porta i suoi eventi, e l'app viene avvisata")

# ---------------- 5. priorita' bassa: non deve rompere niente ----------------
errori = []
def prova():
    try:
        ub.priorita_bassa(True)
        ub.priorita_bassa(False)
    except Exception as exc:          # pragma: no cover
        errori.append(exc)
t = threading.Thread(target=prova)
t.start(); t.join()
ub._config_cache["low_priority"] = False
ub.priorita_bassa(True)               # spenta: non deve fare niente
ub._config_cache["low_priority"] = True
assert not errori, errori
print("priorita' bassa: accesa e spenta senza errori")

shutil.rmtree(ub.L(tmp), ignore_errors=True)
print("\nVERSIONI E RIPRISTINO OK")
