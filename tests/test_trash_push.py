"""Il caso di oggi: cancello sul PC, sull'SSD deve finire in __deleted."""
import json, shutil, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub

tmp = Path(tempfile.mkdtemp(prefix="trash_"))
pc = tmp / "WorkArea"; ssd = tmp / "SSD"; dest = tmp / "Backup"
for nome in ("build1.0", "email_manager", "usb-backup"):
    (pc / nome).mkdir(parents=True)
    (pc / nome / "file.py").write_text(nome, encoding="utf-8")
ssd.mkdir(); dest.mkdir()
(dest / "backup.json").write_text(json.dumps({
    "pc_name": "laptop", "only_volumes": ["*"],
    "push": {"target_subdir": "backup", "folders": [{"path": str(pc), "as": "WorkArea"}],
             "delete_extra": True},
}), encoding="utf-8")

cfg = dict(ub.DEFAULT_CONFIG); cfg["dest_root"] = str(dest); cfg["notify"] = False
ub.setup_log(None); ub.volume_label = lambda r: "SSD"
copia = ssd / "backup" / "laptop" / "WorkArea"

ub.handle_volume(ssd, cfg, True)
assert (copia / "build1.0" / "file.py").is_file()
print("primo giro:", sorted(p.name for p in copia.iterdir()))

# cancello due cartelle sul PC, come hai fatto tu
shutil.rmtree(pc / "build1.0"); shutil.rmtree(pc / "email_manager")
ub._last_run.clear()
ub.handle_volume(ssd, cfg, True)

rimaste = sorted(p.name for p in copia.iterdir() if p.name != ub.TRASH_DIR)
cestino = copia / ub.TRASH_DIR
assert rimaste == ["usb-backup"], rimaste
assert (cestino / "build1.0" / "file.py").read_text(encoding="utf-8") == "build1.0"
assert (cestino / "email_manager" / "file.py").is_file()
print("dopo la cancellazione:", rimaste)
print("in __deleted:", sorted(p.name for p in cestino.iterdir()))

# il riposo evita di rifare tutto se il disco sfarfalla
ub._last_run[str(ssd)] = time.time()
known = ub.scan_once(cfg, set()) if False else None
print("\nTRASH PUSH OK")
shutil.rmtree(tmp, ignore_errors=True)
