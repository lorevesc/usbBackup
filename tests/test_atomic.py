"""Copia atomica: niente file monchi se la copia si interrompe."""
import os, shutil, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub
ub.setup_log(None)

tmp = Path(tempfile.mkdtemp(prefix="atom_"))
src = tmp / "src"; dst = tmp / "dst"; src.mkdir(); dst.mkdir()
(src / "grande.bin").write_bytes(b"A" * 500_000)
(src / "piccolo.txt").write_text("ciao", encoding="utf-8")

# --- copia normale ---
stats = ub.new_stats()
ub.mirror_tree(src, dst, [], False, stats, threads=1)
assert (dst / "grande.bin").stat().st_size == 500_000
assert not list(dst.glob("*" + ub.PART_SUFFIX)), "ha lasciato file di appoggio"
print("1. copia pulita, nessun", ub.PART_SUFFIX, "residuo")

# --- interruzione a meta': il file buono non deve essere toccato ---
(dst / "grande.bin").unlink()
(dst / "grande.bin").write_bytes(b"VECCHIO")          # versione precedente
vecchia_data = os.stat(dst / "grande.bin").st_mtime
originale = shutil.copy2
def esplodi(a, b, *args, **kw):
    if str(a).endswith("grande.bin"):
        Path(b).write_bytes(b"A" * 120_000)            # scrive a meta'...
        raise OSError("chiavetta staccata")            # ...e muore
    return originale(a, b, *args, **kw)
shutil.copy2 = esplodi
stats2 = ub.new_stats()
ub.mirror_tree(src, dst, [], False, stats2, threads=1)
shutil.copy2 = originale
assert stats2["errors"] == 1, stats2
contenuto = (dst / "grande.bin").read_bytes()
assert contenuto == b"VECCHIO", f"file rovinato: {len(contenuto)} byte"
assert not list(dst.glob("*" + ub.PART_SUFFIX)), "file di appoggio rimasto"
print("2. interrotta: vecchia versione intatta, niente troncature")

# --- il giro dopo la ricopia davvero (non la crede a posto) ---
stats3 = ub.new_stats()
ub.mirror_tree(src, dst, [], False, stats3, threads=1)
assert stats3["copied"] == 1, stats3
assert (dst / "grande.bin").read_bytes() == b"A" * 500_000
print("3. giro successivo: ricopiata per intero")

# --- avanzi .usbpart di una copia morta vengono ignorati e puliti ---
(src / ("orfano.bin" + ub.PART_SUFFIX)).write_bytes(b"x")
(dst / ("orfano.bin" + ub.PART_SUFFIX)).write_bytes(b"x")
stats4 = ub.new_stats()
ub.mirror_tree(src, dst, [], True, stats4, threads=1)
assert not (dst / ("orfano.bin" + ub.PART_SUFFIX)).exists(), "avanzo non pulito"
assert stats4["deleted"] == 0, "ha messo un avanzo nel cestino invece di buttarlo"
print("4. avanzi di copie morte buttati, non archiviati")

shutil.rmtree(tmp, ignore_errors=True)
print("\nATOMIC OK")
