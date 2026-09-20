"""Quanto costa il giro di controllo quando non c'e' niente da copiare.

Confronta la versione attuale con quella del commit precedente, che faceva
una chiamata stat per ogni file da tutte e due le parti.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
import usb_backup as ub

N = 8000
ub.setup_log(None)
tmp = Path(tempfile.mkdtemp(prefix="bench_scan_"))
src = tmp / "src"
for i in range(N):
    f = src / f"d{i % 60}" / f"f{i}.txt"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(os.urandom(2000))
dst = tmp / "dst"
ub.mirror_tree(src, dst, [], False, ub.new_stats(), threads=8)   # prima copia


def misura(modulo, etichetta):
    tempi = []
    for _ in range(3):
        stats = modulo.new_stats()
        avvio = time.perf_counter()
        modulo.mirror_tree(src, dst, [], False, stats, threads=8)
        tempi.append(time.perf_counter() - avvio)
        assert stats["skipped"] == N, stats
        assert stats["copied"] == 0, stats
    migliore = min(tempi)
    print(f"  {etichetta:<22} {migliore*1000:7.0f} ms   {N/migliore:8.0f} file/s")
    return migliore


print(f"{N} file gia' copiati, si misura solo il confronto\n")
adesso = misura(ub, "con scandir (adesso)")

# versione precedente, presa da git
vecchio_sorgente = subprocess.run(
    ["git", "show", "HEAD:usb_backup.py"], cwd=RADICE,
    capture_output=True, text=True)
if vecchio_sorgente.returncode == 0:
    vecchio_file = tmp / "usb_backup_vecchio.py"
    vecchio_file.write_text(vecchio_sorgente.stdout, encoding="utf-8")
    sys.path.insert(0, str(tmp))
    import importlib.util
    spec = importlib.util.spec_from_file_location("usb_backup_vecchio", vecchio_file)
    vecchio = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vecchio)
    vecchio.setup_log(None)
    prima = misura(vecchio, "con stat (commit prec.)")
    print(f"\n  guadagno: {prima/adesso:.1f}x")
else:
    print("  (nessun commit precedente con cui confrontare)")

shutil.rmtree(tmp, ignore_errors=True)
