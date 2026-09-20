"""Stop a meta' giro e verifica a campione."""
import os, shutil, sys, tempfile, threading, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub
righe = []
ub.add_log_sink(lambda r: righe.append(r))
ub.setup_log(None)
ub._config_cache["verify_percent"] = 0

tmp = Path(tempfile.mkdtemp(prefix="stop_"))
src = tmp / "src"; src.mkdir()
for i in range(400):
    (src / f"f{i}.bin").write_bytes(os.urandom(20_000))

# ---------- 1. stop durante il giro ----------
ub.clear_stop()
stats = ub.new_stats()
def ferma_fra_poco():
    time.sleep(0.25)
    ub.request_stop()
threading.Thread(target=ferma_fra_poco, daemon=True).start()
ub.run_jobs("prova", [(src, tmp / "dst")], [], False, stats)
assert any("[fermato]" in r for r in righe), righe[-3:]
copiati = len(list((tmp / "dst").glob("*.bin")))
assert 0 < copiati < 400, f"copiati {copiati}: non si e' fermato a meta'"
assert stats["errors"] == 0, "lo stop non deve contare come errore"
print(f"1. fermato dopo {copiati}/400 file, nessun errore")

# ---------- 2. il giro dopo riprende ----------
ub.clear_stop()
stats2 = ub.new_stats()
ub.run_jobs("prova", [(src, tmp / "dst")], [], False, stats2)
assert stats2["copied"] + copiati >= 400, (copiati, stats2)
assert len(list((tmp / "dst").glob("*.bin"))) == 400
print(f"2. ripreso: altri {stats2['copied']} file, totale 400")

# ---------- 3. verifica a campione: tutto a posto ----------
righe.clear()
ub._config_cache["verify_percent"] = 100
shutil.rmtree(tmp / "dst")
stats3 = ub.new_stats()
ub.run_jobs("prova", [(src, tmp / "dst")], [], False, stats3)
assert stats3.get("verificati") == 400, stats3
assert stats3["errors"] == 0
print("3. verificati tutti e 400, nessuna differenza")

# ---------- 4. copia corrotta: la verifica se ne accorge ----------
righe.clear()
shutil.rmtree(tmp / "dst2", ignore_errors=True)
stats4 = ub.new_stats()
originale = ub.copy_atomic
def sporca(a, b):
    originale(a, b)
    if a.name == "f7.bin":
        with open(b, "r+b") as fh:      # un bit girato, dimensione identica
            fh.seek(999); fh.write(b"\x00")
ub.copy_atomic = sporca
ub.run_jobs("prova2", [(src, tmp / "dst2")], [], False, stats4)
ub.copy_atomic = originale
assert stats4["errors"] >= 1, stats4
assert any("non corrispondono" in r for r in righe), righe[-4:]
guasto = [r for r in righe if "diversa dall'originale" in r]
assert guasto and "f7.bin" in guasto[0], guasto
print("4. file corrotto individuato:", guasto[0].split("originale:")[-1].strip()[-30:])

shutil.rmtree(tmp, ignore_errors=True)
print("\nSTOP + VERIFY OK")
