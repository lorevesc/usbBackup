"""L'SSD che sfarfalla non deve far ripartire il giro da capo."""
import sys, tempfile, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub

tmp = Path(tempfile.mkdtemp(prefix="cool_"))
disco = tmp / "SSD"; disco.mkdir()
giri = {"n": 0}
ub.setup_log(None)
ub.volume_label = lambda r: "SSD"
ub.handle_volume = lambda root, cfg, rem: (giri.__setitem__("n", giri["n"] + 1),
                                           ub._last_run.__setitem__(str(root), __import__("time").time()),
                                           True)[-1]
cfg = dict(ub.DEFAULT_CONFIG)
cfg.update({"rescan_cooldown_minutes": 15, "missing_polls_before_removed": 3})

presente = [True]
ub.list_volumes = lambda inc: [(disco, True)] if presente[0] else []

known = ub.scan_once(cfg, set())
assert giri["n"] == 1, giri
presente[0] = False                      # il disco sparisce per un attimo
known = ub.scan_once(cfg, known)
assert known == {str(disco)}, "tolto subito al primo buco"
presente[0] = True                       # e torna
known = ub.scan_once(cfg, known)
assert giri["n"] == 1, f"ha rifatto il giro: {giri['n']}"
print("sfarfallio ignorato, giri:", giri["n"])

presente[0] = False                      # stavolta staccato davvero
for _ in range(3):
    known = ub.scan_once(cfg, known)
assert known == set(), known
print("dopo 3 giri assente: rimosso")

presente[0] = True                       # ricollegato entro il riposo
known = ub.scan_once(cfg, known)
assert giri["n"] == 1, "ha rifatto il giro durante il riposo"
print("ricollegato entro il riposo: saltato")

ub._last_run[str(disco)] = 0             # riposo scaduto
known = ub.scan_once(cfg, set())
assert giri["n"] == 2, giri
print("riposo scaduto: rifatto")
shutil.rmtree(tmp, ignore_errors=True)
print("\nCOOLDOWN OK")

# ---- il watcher lavora anche sui volumi gia' collegati all'avvio ----
import threading, time as _t
disco.mkdir(parents=True, exist_ok=True)   # il blocco sopra aveva ripulito tutto
ub._last_run.clear(); giri["n"] = 0
presente[0] = True
cfg["poll_seconds"] = 1
stop = threading.Event()
t = threading.Thread(target=ub.watch, args=(cfg, stop), daemon=True)
t.start(); _t.sleep(2.5); stop.set(); t.join(timeout=5)
assert giri["n"] == 1, f"volume gia' collegato ignorato all'avvio (giri={giri['n']})"
print("volume gia' collegato: elaborato all'avvio")
import shutil as _sh; _sh.rmtree(disco.parent, ignore_errors=True)
