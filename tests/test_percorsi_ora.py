"""Percorsi oltre i 260 caratteri, cambio dell'ora legale, sync atomica."""
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub

ub.setup_log(None)
ub._config_cache["verify_percent"] = 0
righe = []
ub.add_log_sink(righe.append)
tmp = Path(tempfile.mkdtemp(prefix="lungo_"))

# ---------------- 1. il prefisso dei percorsi estesi ----------------
if ub.IS_WIN:
    B = chr(92)
    locale_ = ub.L("C:/WorkArea/file.txt")
    assert locale_ == B + B + "?" + B + "C:" + B + "WorkArea" + B + "file.txt", locale_
    assert ub.L(locale_) == locale_, "applicato due volte"
    rete = ub.L(B + B + "server" + B + "condivisa" + B + "x.txt")
    assert rete == B + B + "?" + B + "UNC" + B + "server" + B + "condivisa" + B + "x.txt", rete
    print("prefisso: locale, di rete e idempotente")
else:
    assert ub.L("/tmp/x") == "/tmp/x", "fuori da Windows non deve cambiare niente"
    print("prefisso: fuori da Windows lascia i percorsi com'erano")

# ---------------- 2. copia e cestino oltre i 260 caratteri ----------------
src = tmp / "src"
profondo = src
while len(str(profondo)) < 300:          # albero stile node_modules
    profondo = profondo / "pacchetto_con_un_nome_lungo"
file_lungo = profondo / "index.js"
os.makedirs(ub.L(profondo), exist_ok=True)
with open(ub.L(file_lungo), "w", encoding="utf-8") as fh:
    fh.write("module.exports = 42;")
dst = tmp / "dst"
print(f"percorso di prova: {len(str(file_lungo))} caratteri")

stats = ub.new_stats()
ub.mirror_tree(src, dst, [], True, stats, threads=4)
copia = dst / file_lungo.relative_to(src)
assert stats["copied"] == 1 and stats["errors"] == 0, stats
with open(ub.L(copia), encoding="utf-8") as fh:
    assert fh.read() == "module.exports = 42;"
print(f"copia oltre i 260: ok ({len(str(copia))} caratteri a destinazione)")

assert ub.scan_tree(src, [])[0] == 1, "il conteggio non vede il file profondo"

os.unlink(ub.L(file_lungo))              # sparisce dalla sorgente...
stats2 = ub.new_stats()
ub.mirror_tree(src, dst, [], True, stats2, threads=4)
assert stats2["deleted"] >= 1 and stats2["errors"] == 0, stats2
assert not os.path.exists(ub.L(copia)), "non spostato"
nel_cestino = [p for p in (dst / ub.TRASH_DIR).rglob("*")] if (dst / ub.TRASH_DIR).exists() else []
assert os.path.isdir(ub.L(dst / ub.TRASH_DIR)), "cestino non creato"
print("cestino oltre i 260: ok")

# ---------------- 3. ora legale ----------------
ub._config_cache["dst_tolerance"] = True
adesso = time.time()
assert ub.stesse_date(adesso, adesso + 1.5), "arrotondamento FAT32"
assert ub.stesse_date(adesso, adesso + 3600), "ora legale in avanti"
assert ub.stesse_date(adesso, adesso - 3601), "ora legale all'indietro"
assert not ub.stesse_date(adesso, adesso + 1800), "mezz'ora non e' ora legale"
assert not ub.stesse_date(adesso, adesso + 7200), "due ore non sono ora legale"
ub._config_cache["dst_tolerance"] = False
assert not ub.stesse_date(adesso, adesso + 3600), "l'opzione spenta deve contare"
ub._config_cache["dst_tolerance"] = True

piccolo_src = tmp / "ora_src"
piccolo_dst = tmp / "ora_dst"
piccolo_src.mkdir()
for i in range(20):
    (piccolo_src / f"f{i}.txt").write_text(str(i), encoding="utf-8")
ub.mirror_tree(piccolo_src, piccolo_dst, [], False, ub.new_stats())
for f in piccolo_dst.iterdir():            # simulo il cambio d'ora su FAT32
    info = f.stat()
    os.utime(f, (info.st_atime, info.st_mtime + 3600))
stats3 = ub.new_stats()
ub.mirror_tree(piccolo_src, piccolo_dst, [], False, stats3)
assert stats3["copied"] == 0 and stats3["skipped"] == 20, stats3
print("cambio d'ora: 20 file sfasati di un'ora, nessuno ricopiato")

# ---------------- 4. la sincronizzazione copia in modo atomico ----------------
locale_sync = tmp / "sync_locale"
remoto = tmp / "sync_remoto"
locale_sync.mkdir()
(locale_sync / "codice.py").write_text("x = 1", encoding="utf-8")
chiamate = []
originale = ub.copy_atomic
ub.copy_atomic = lambda a, b: (chiamate.append(b), originale(a, b))[1]
stats4 = ub.new_sync_stats()
ub.sync_pair(locale_sync, remoto, list(ub.SYNC_DEFAULT_EXCLUDE), stats4)
ub.copy_atomic = originale
assert chiamate, "la sincronizzazione non passa dalla copia atomica"
assert (remoto / "codice.py").read_text(encoding="utf-8") == "x = 1"
assert not list(remoto.glob("*" + ub.PART_SUFFIX)), "file di appoggio rimasti"
print("sync: copia atomica usata, niente file di appoggio")

# ---------------- 5. nessun messaggio a testo fisso nel motore ----------------
sorgente = (Path(__file__).resolve().parent.parent / "usb_backup.py").read_text(encoding="utf-8")
fissi = [r.strip() for r in sorgente.splitlines() if 'log(f"' in r]
assert not fissi, f"messaggi non tradotti: {fissi[:3]}"
print("motore: tutti i messaggi passano dal vocabolario")

shutil.rmtree(ub.L(tmp), ignore_errors=True)
print("\nPERCORSI E ORA OK")
