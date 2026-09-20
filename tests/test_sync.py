"""Simula il giro casa -> chiavetta -> ufficio -> chiavetta -> casa."""
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub

ub.setup_log(None)
tmp = Path(tempfile.mkdtemp(prefix="sync_"))
# apposta due percorsi locali diversi: a casa e in ufficio il progetto sta
# in cartelle che non c'entrano niente fra loro. In comune c'e' solo la
# cartella sulla chiavetta.
casa = tmp / "casa" / "WorkArea" / "progetto"
ufficio = tmp / "ufficio" / "dev" / "repo-lavoro"
stick = tmp / "STICK" / "sync" / "progetto"
casa.mkdir(parents=True)
ufficio.mkdir(parents=True)

EXC = list(ub.SYNC_DEFAULT_EXCLUDE)


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    # date distinte: molti filesystem hanno risoluzione di 1-2 secondi
    stamp = time.time() + write.tick
    write.tick += 3
    os.utime(path, (stamp, stamp))


write.tick = 0


def sync(side: Path, label: str, remote: Path | None = None):
    stats = ub.new_sync_stats()
    ub.sync_pair(side, remote or stick, EXC, stats)
    print(f"  {label}: presi {stats['in']}, mandati {stats['out']}, "
          f"cancellati {stats['deleted_local'] + stats['deleted_remote']}, "
          f"conflitti {stats['conflicts']}, errori {stats['errors']}")
    assert stats["errors"] == 0, stats
    return stats


def files(base: Path):
    skip = (ub.SYNC_STATE_DIR, ub.TRASH_DIR)
    return {p.relative_to(base).as_posix(): p.read_text(encoding="utf-8")
            for p in base.rglob("*")
            if p.is_file() and not any(part in skip for part in p.relative_to(base).parts)}


print("=== 1. a casa scrivo il progetto, poi infilo la chiavetta ===")
write(casa / "main.py", "print('v1')")
write(casa / "lib" / "utils.py", "def a(): pass")
write(casa / "note.txt", "appunti")
write(casa / "__pycache__" / "main.pyc", "binario")   # deve restare fuori
sync(casa, "casa -> chiavetta")
assert "main.py" in files(stick) and "lib/utils.py" in files(stick)
assert not any("__pycache__" in f for f in files(stick)), "esclusioni ignorate"

print("=== 2. in ufficio (altra cartella): primo giro, prendo tutto ===")
sync(ufficio, "chiavetta -> ufficio")
attesi = {k: v for k, v in files(casa).items() if "__pycache__" not in k}
assert files(ufficio) == attesi, "l'ufficio non ha ricevuto tutto"

print("=== 3. lavoro in ufficio: modifico, aggiungo, cancello ===")
write(ufficio / "main.py", "print('v2 ufficio')")
write(ufficio / "nuovo.py", "# scritto in ufficio")
(ufficio / "note.txt").unlink()
sync(ufficio, "ufficio -> chiavetta")

print("=== 4. torno a casa ===")
stats = sync(casa, "chiavetta -> casa")
a_casa = files(casa)
assert a_casa["main.py"] == "print('v2 ufficio')", "modifica dell'ufficio non arrivata"
assert "nuovo.py" in a_casa, "file nuovo non arrivato"
assert "note.txt" not in a_casa, "cancellazione non propagata"
assert stats["deleted_local"] == 1, stats
# il file non e' sparito: sta in __deleted, col contenuto intatto
cestino = casa / ub.TRASH_DIR / "note.txt"
assert cestino.is_file(), f"{cestino} non creato"
assert cestino.read_text(encoding="utf-8") == "appunti", "contenuto perso"
print("   a casa:", sorted(a_casa))
print(f"   note.txt recuperabile in {ub.TRASH_DIR}/")

print("=== 5. niente da fare: secondo giro a vuoto ===")
stats = sync(casa, "casa (nessuna modifica)")
assert stats["in"] == stats["out"] == 0, stats

print("=== 6. conflitto: stesso file toccato dalle due parti, vince il piu' recente ===")
write(casa / "main.py", "print('versione CASA')")       # scritta prima
sync(casa, "casa -> chiavetta")
write(ufficio / "main.py", "print('versione UFFICIO')")  # scritta dopo
# l'ufficio non ha visto il giro di casa: entrambi i lati risultano cambiati
stats = sync(ufficio, "ufficio <-> chiavetta")
assert stats["conflicts"] == 1, stats
assert files(ufficio)["main.py"] == "print('versione UFFICIO')", "non ha vinto il piu' recente"
assert not [f for f in files(ufficio) if ".conflitto-" in f], "ha lasciato copie doppie"
sync(casa, "casa riallineata")
assert files(casa)["main.py"] == "print('versione UFFICIO')", "casa non si e' allineata"
print("   vince l'ufficio, che ha scritto per ultimo")

print("=== 6b. al contrario: se il piu' recente e' quello di casa, vince casa ===")
write(ufficio / "lib" / "utils.py", "def b(): pass")     # prima
sync(ufficio, "ufficio -> chiavetta")
write(casa / "lib" / "utils.py", "def c(): pass")        # dopo
stats = sync(casa, "casa <-> chiavetta")
assert stats["conflicts"] == 1, stats
assert files(casa)["lib/utils.py"] == "def c(): pass", "non ha vinto il piu' recente"
sync(ufficio, "ufficio riallineato")
assert files(ufficio)["lib/utils.py"] == "def c(): pass"
print("   vince casa, che ha scritto per ultima")

print("=== 7. rete di sicurezza contro le cancellazioni di massa ===")
massa = tmp / "massa"
massa_stick = tmp / "STICK" / "sync" / "massa"
massa.mkdir()
for i in range(40):
    write(massa / f"f{i}.txt", str(i))
sync(massa, "primo giro", massa_stick)
for i in range(40):
    (massa / f"f{i}.txt").unlink()
stats = ub.new_sync_stats()
ub.sync_pair(massa, massa_stick, EXC, stats)
assert stats["deleted_remote"] == 0, "ha spostato in massa senza fermarsi"
assert not (massa_stick / ub.TRASH_DIR).exists(), "ha toccato la chiavetta"
assert stats["skipped_deletes"] == 40, stats
print(f"   bloccate {stats['skipped_deletes']} cancellazioni sospette")

print("=== 8. git in corso: la coppia viene saltata ===")
(casa / ".git").mkdir(exist_ok=True)
(casa / ".git" / "index.lock").write_text("")
stats = ub.new_sync_stats()
ub.sync_pair(casa, stick, EXC, stats)
assert stats["errors"] == 1 and stats["in"] == stats["out"] == 0
(casa / ".git" / "index.lock").unlink()
print("   saltata come previsto")

shutil.rmtree(tmp, ignore_errors=True)
print("\nSYNC OK")
