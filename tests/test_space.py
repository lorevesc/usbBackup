"""Spazio insufficiente: prima di partire, e a meta' strada."""
import os, shutil, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub

righe = []
ub.add_log_sink(lambda r: righe.append(r))
ub.setup_log(None)

tmp = Path(tempfile.mkdtemp(prefix="space_"))
src = tmp / "src"; src.mkdir()
for i in range(10):
    (src / f"f{i}.bin").write_bytes(os.urandom(100_000))   # 1 MB in tutto

# ---------- 1. non ci sta proprio: non deve copiare niente ----------
ub.free_space = lambda p: 10_000                      # 10 KB liberi
dst = tmp / "dst_piccolo"
stats = ub.new_stats()
ub.run_jobs("prova", [(src, dst)], [], False, stats)
assert stats["copied"] == 0, stats
assert not dst.exists() or not any(dst.rglob("*.bin")), "ha copiato lo stesso"
assert stats["errors"] == 1
assert any("non ci sta" in r for r in righe), righe[-3:]
print("1. rifiutato in partenza:", [r for r in righe if "non ci sta" in r][0].split("  ")[-1])

# ---------- 2. spazio che finisce a meta' ----------
righe.clear()
restante = {"free": 500_000 + ub.SPACE_MARGIN}        # basta per ~5 file
ub.free_space = lambda p: restante["free"]
dst2 = tmp / "dst_medio"
dst2.mkdir(); (dst2 / "gia_qui.txt").write_text("x")  # destinazione non vuota
orig_copy = shutil.copy2
def copy_spendendo(a, b, *args, **kw):
    orig_copy(a, b, *args, **kw)
    restante["free"] -= Path(a).stat().st_size
shutil.copy2 = copy_spendendo
stats2 = ub.new_stats()
ub.run_jobs("prova2", [(src, dst2)], [], False, stats2)
shutil.copy2 = orig_copy
copiati = len(list(dst2.rglob("*.bin")))
assert 0 < copiati < 10, f"copiati {copiati}, doveva fermarsi a meta'"
assert stats2["errors"] >= 1
assert any("spazio esaurito" in r for r in righe), righe[-3:]
print(f"2. fermato a {copiati}/10 file:",
      [r for r in righe if "spazio esaurito" in r][0].split("]")[-1].strip()[:70])
assert any("riprende da dove era" in r for r in righe)

# ---------- 3. spazio abbondante: nessun intralcio ----------
righe.clear()
ub.free_space = lambda p: 500 * 1024**3
stats3 = ub.new_stats()
ub.run_jobs("prova3", [(src, tmp / "dst_grande")], [], False, stats3)
assert stats3["copied"] == 10 and stats3["errors"] == 0, stats3
assert not any("attenzione" in r for r in righe)
assert not any("stima del giro scorso" in r for r in righe), "ha riusato i totali di un giro interrotto"
print("3. spazio abbondante: 10/10 copiati, nessun avviso, nessuna stima falsa")

shutil.rmtree(tmp, ignore_errors=True)
print("\nSPACE OK")
