"""Log giornaliero, disco sparito, sorgente illeggibile, freno, impostazioni
sul disco, verifica completa, disinstallazione."""
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub

tmp = Path(tempfile.mkdtemp(prefix="robusto_"))
ub._config_cache.update({"verify_percent": 0, "keep_versions": False})

# ---------------- 9. log giornaliero, 30 giorni ----------------
cartella_log = tmp / "_logs"
ub.setup_log(str(cartella_log / "usb-backup.log"))
ub.log("prova")
oggi = cartella_log / f"usb-backup-{datetime.now():%Y%m%d}.log"
assert oggi.is_file() and "prova" in oggi.read_text(encoding="utf-8"), list(cartella_log.iterdir())
vecchio = cartella_log / f"usb-backup-{(datetime.now() - timedelta(days=45)):%Y%m%d}.log"
recente = cartella_log / f"usb-backup-{(datetime.now() - timedelta(days=10)):%Y%m%d}.log"
altro = cartella_log / "appunti-miei.log"
for f in (vecchio, recente, altro):
    f.write_text("x", encoding="utf-8")
os.utime(vecchio, (time.time(), time.time()))      # data del file recente: conta il nome
assert ub.pulisci_log_vecchi() == 1
assert not vecchio.exists() and recente.exists() and altro.exists()
print("log: un file per giorno, tolto quello di 45 giorni, tenuti gli altri")
ub.setup_log(None)

# ---------------- 1. sorgente illeggibile: la copia non si tocca ----------------
src = tmp / "src"
dst = tmp / "dst"
(src / "sotto").mkdir(parents=True)
for i in range(5):
    (src / "sotto" / f"f{i}.txt").write_text(str(i), encoding="utf-8")
ub.mirror_tree(src, dst, [], True, ub.new_stats())
originale_voci = os.scandir
def scandir_rotto(percorso):
    if str(percorso).endswith("sotto"):
        raise PermissionError("negato")
    return originale_voci(percorso)
os.scandir = scandir_rotto
stats = ub.new_stats()
ub.mirror_tree(src, dst, [], True, stats)
os.scandir = originale_voci
assert stats["deleted"] == 0, "cartella illeggibile scambiata per vuota: copia spostata in __deleted"
assert len(list((dst / "sotto").glob("*.txt"))) == 5
assert stats["errors"] == 1
print("sorgente illeggibile: saltata, zero file spostati in __deleted")

# ---------------- 1. disco staccato a meta' ----------------
righe = []
ub.add_log_sink(righe.append)
molti = tmp / "molti"
molti.mkdir()
for i in range(300):
    (molti / f"g{i}.bin").write_bytes(os.urandom(2000))
arrivo = tmp / "disco"
originale_copia = ub.copy_atomic
contati = {"n": 0}
def copia_poi_stacca(a, b, *args, **kw):
    contati["n"] += 1
    if contati["n"] == 40:
        shutil.rmtree(arrivo, ignore_errors=True)       # il disco "sparisce"
        raise OSError("dispositivo non pronto")
    return originale_copia(a, b, *args, **kw)
ub.copy_atomic = copia_poi_stacca
# un thread solo: con piu' thread Windows non lascia cancellare una cartella
# con file aperti, e il disco "staccato" risulterebbe ancora li'
ub._config_cache["copy_threads"] = 1
stats = ub.new_stats()
ub.run_jobs("prova", [(molti, arrivo)], [], False, stats)
ub.copy_atomic = originale_copia
ub._config_cache["copy_threads"] = 8
errori_copia = [r for r in righe if "[errore] copia" in r or "[error] copy" in r]
assert stats.get("disco_sparito"), stats
assert len(errori_copia) <= 1, f"{len(errori_copia)} errori uno per file invece di un messaggio solo"
assert stats["errors"] == 1, stats["errors"]
assert any("staccato" in r or "unplugged" in r for r in righe)
print(f"disco staccato: 1 messaggio invece di {300 - 40} errori")

# ---------------- 3. freno sulle modifiche di massa ----------------
progetto = tmp / "progetto"
copia = tmp / "copia"
progetto.mkdir()
for i in range(100):
    (progetto / f"m{i}.py").write_text("originale", encoding="utf-8")
ub.mirror_tree(progetto, copia, [], False, ub.new_stats())
futuro = time.time() + 60
for i in range(60):                          # 60% dei file cambia tutto insieme
    f = progetto / f"m{i}.py"
    f.write_text("cifrato!!", encoding="utf-8")
    os.utime(f, (futuro, futuro))
ub._config_cache.update({"mass_change_brake": True, "mass_change_percent": 30,
                         "mass_change_min": 50})
stats = ub.new_stats()
ub.run_jobs("freno", [(progetto, copia)], [], False, stats)
assert stats.get("freno") and stats["freno"]["n"] == 60, stats.get("freno")
assert (copia / "m0.py").read_text(encoding="utf-8") == "originale", "sovrascritto nonostante il freno"
print("freno: 60 file su 100 stavano per cambiare, fermo, copia intatta")

ub.salta_freno_una_volta()                   # l'utente ha detto: procedi
stats = ub.new_stats()
ub.run_jobs("freno", [(progetto, copia)], [], False, stats)
assert not stats.get("freno") and stats["copied"] == 60
assert (copia / "m0.py").read_text(encoding="utf-8") == "cifrato!!"
print("freno: dopo il consenso procede")

ub._config_cache["mass_change_brake"] = False   # l'opzione spenta deve contare
for i in range(60):
    os.utime(progetto / f"m{i}.py", (futuro + 60, futuro + 60))
    (progetto / f"m{i}.py").write_text("ancora", encoding="utf-8")
    os.utime(progetto / f"m{i}.py", (futuro + 60, futuro + 60))
stats = ub.new_stats()
ub.run_jobs("freno", [(progetto, copia)], [], False, stats)
assert not stats.get("freno") and stats["copied"] == 60
ub._config_cache["mass_change_brake"] = True
print("freno spento: nessuna domanda")

# ---------------- 6. impostazioni salvate sul disco ----------------
ub.CONFIG_PATH = tmp / "config.json"
ub.CONFIG_PATH.write_text(json.dumps({"dest_root": str(tmp / "Backup")}), encoding="utf-8")
cfg = ub.load_config()
ub._config_cache.update({"verify_percent": 0})
(tmp / "Backup").mkdir()
(tmp / "Backup" / "backup.json").write_text(json.dumps({"pc_name": "pc-casa",
    "push": {"folders": [str(progetto)]}}), encoding="utf-8")
chiavetta = tmp / "CHIAVETTA"
chiavetta.mkdir()
salvato = ub.salva_impostazioni_sul_disco(chiavetta, cfg)
assert salvato == chiavetta / ".usb-backup" / "impostazioni-pc-casa.json", salvato
dati = json.loads(salvato.read_text(encoding="utf-8"))
assert dati["piano"]["pc_name"] == "pc-casa" and "dest_root" not in dati["config"]
nuova, piano = ub.import_settings(salvato, cfg)
assert piano["push"]["folders"] == [str(progetto)]
print("impostazioni sul disco: salvate e reimportabili")

# ---------------- 8. verifica completa ----------------
ub.volume_label = lambda r: "CHIAVETTA"
ub.volume_serial = lambda r: ""
(chiavetta / "Documenti").mkdir()
for i in range(10):
    (chiavetta / "Documenti" / f"d{i}.txt").write_text(f"doc {i}", encoding="utf-8")
(chiavetta / "backup.json").write_text(json.dumps({"folders": ["Documenti"]}), encoding="utf-8")
ub._config_cache["mass_change_brake"] = False
ub.handle_volume(chiavetta, cfg, True)
esito = ub.verifica_completa(chiavetta, cfg, True)
assert esito["verificati"] >= 10 and esito["diversi"] == 0 and esito["mancanti"] == 0, esito
copia_doc = tmp / "Backup" / "CHIAVETTA" / "Documenti"
with open(copia_doc / "d3.txt", "r+b") as fh:          # un byte cambiato, stessa dimensione
    fh.seek(0); fh.write(b"D")
(copia_doc / "d7.txt").unlink()
esito = ub.verifica_completa(chiavetta, cfg, True)
assert esito["diversi"] == 1 and esito["mancanti"] == 1, esito
problemi = sorted(Path(e["path"]).name for e in esito["eventi"])
assert problemi == ["d3.txt", "d7.txt"], problemi
print("verifica completa: tutto identico; poi trovati il file alterato e quello mancante")

# ---------------- 2. disinstallazione ----------------
ub._run_cancella = lambda: None
chiamate = []
ub.run_hidden = lambda comando, **kw: (chiamate.append(comando),
                                       type("E", (), {"returncode": 0, "stdout": "", "stderr": ""})())[1]
cfg_file = ub.CONFIG_PATH
assert cfg_file.exists()
ub.disinstalla(togli_impostazioni=False)
assert cfg_file.exists(), "ha tolto la configurazione senza che fosse chiesto"
ub.disinstalla(togli_impostazioni=True)
assert not cfg_file.exists()
assert (tmp / "Backup" / "backup.json").exists(), "il piano del PC non va mai toccato"
assert copia_doc.exists(), "i backup non vanno mai toccati"
print("disinstalla: avvio automatico e collegamenti via, backup e piano intatti")

shutil.rmtree(ub.L(tmp), ignore_errors=True)
print("\nROBUSTEZZA OK")
