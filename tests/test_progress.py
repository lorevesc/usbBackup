"""Verifica la barra: righe \r, percentuali crescenti, riga finale al 100%."""
import os, shutil, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub

righe = []
ub.add_log_sink(righe.append)
ub.setup_log(None)
ub.PROGRESS_EVERY = 0.0          # nel test vogliamo ogni aggiornamento

tmp = Path(tempfile.mkdtemp(prefix="prog_"))
src = tmp / "sorgente"; dst = tmp / "copia"
for i in range(25):
    f = src / f"sub{i % 4}" / f"file{i}.bin"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(os.urandom(40_000))

files, total = ub.scan_tree(src, [])
print(f"scan: {files} file, {ub.human_bytes(total)}")
assert files == 25 and total == 25 * 40_000

stats = ub.new_stats()
ub.run_jobs("sorgente", [(src, dst)], [], False, stats)

barre = [r[1:] for r in righe if r.startswith(ub.PROGRESS_MARK)]
assert barre, "nessuna riga di avanzamento"
print("prima :", barre[0])
print("mezzo :", barre[len(barre) // 2])
print("ultima:", barre[-1])
assert "[" in barre[0] and "]" in barre[0]
percentuali = [int(b.split("%")[0].split("]")[-1]) for b in barre[:-1]]
assert percentuali == sorted(percentuali), "percentuali non crescenti"
assert percentuali[-1] == 100, percentuali[-1]
assert "100%" in barre[-1] and "copiati in" in barre[-1]
assert stats["copied"] == 25

# secondo giro: niente da copiare, la barra arriva comunque a 100
righe.clear()
stats2 = ub.new_stats()
ub.run_jobs("sorgente", [(src, dst)], [], False, stats2)
assert stats2["skipped"] == 25 and stats2["copied"] == 0
assert [r[1:] for r in righe if r.startswith(ub.PROGRESS_MARK)][-1].count("#") >= 22

# il file di log non deve riempirsi di barre
logfile = tmp / "log.txt"
ub.setup_log(str(logfile))
shutil.rmtree(dst)
ub.run_jobs("sorgente", [(src, dst)], [], False, ub.new_stats())
testo = logfile.read_text(encoding="utf-8")
assert "[" not in testo.split("conto i file")[-1].split("\n")[0] or "%" not in testo
assert "%" not in testo, "le barre sono finite nel file di log"
print("file di log pulito:", len(testo.splitlines()), "righe")

shutil.rmtree(tmp, ignore_errors=True)
print("\nPROGRESS OK")
