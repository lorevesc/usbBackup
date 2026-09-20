"""Quanto rendono i thread su molti file piccoli."""
import os, shutil, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub
ub.setup_log(None)

tmp = Path(tempfile.mkdtemp(prefix="bench_"))
src = tmp / "src"
N = 4000
for i in range(N):
    f = src / f"d{i % 40}" / f"f{i}.txt"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(os.urandom(3000))      # file piccoli, come il codice
print(f"{N} file da 3 KB\n")

for thread in (1, 4, 8, 16):
    dst = tmp / f"dst{thread}"
    stats = ub.new_stats()
    inizio = time.time()
    ub.mirror_tree(src, dst, [], False, stats, threads=thread)
    durata = time.time() - inizio
    assert stats["copied"] == N, stats
    print(f"  {thread:2d} thread: {durata:5.2f}s   {N/durata:6.0f} file/s")

shutil.rmtree(tmp, ignore_errors=True)
