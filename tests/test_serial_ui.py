"""Vincolo al numero di serie: motore e app."""
import json, os, shutil, sys, tempfile
from pathlib import Path
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub

tmp = Path(tempfile.mkdtemp(prefix="ser_"))
disco = tmp / "SSD"; disco.mkdir()
altro = tmp / "ALTRO"; altro.mkdir()
dest = tmp / "Backup"; dest.mkdir()
ub.CONFIG_PATH = tmp / "config.json"
ub.CONFIG_PATH.write_text(json.dumps({"dest_root": str(dest), "notify": False,
                                      "log_file": str(tmp / "log.txt")}), encoding="utf-8")
seriali = {str(disco): "AABB1122", str(altro): "99887766"}
ub.volume_serial = lambda root: seriali.get(str(root), "")
ub.volume_label = lambda root: Path(root).name
ub.list_volumes = lambda inc: [(disco, True), (altro, True)]

# --- motore: il serial vince sulle altre regole ---
piano = {"only_serials": ["AABB1122"], "push": {"folders": ["x"]}}
assert ub.volume_matches(piano, disco, "SSD", True) is True
assert ub.volume_matches(piano, altro, "ALTRO", True) is False
assert ub.volume_matches(piano, altro, "SSD", True) is False, "etichetta copiata: deve fallire lo stesso"
piano2 = {"only_serials": ["AABB1122"], "only_volumes": ["ALTRO"]}
assert ub.volume_matches(piano2, altro, "ALTRO", True) is False, "il serial deve vincere"
print("motore: il vincolo al serial tiene, anche con etichetta uguale")

# --- app: bottone Lega ---
from PySide6.QtWidgets import QApplication
import usb_backup_qt as qt
app = QApplication(sys.argv)
win = qt.Window()
assert win.volume["serial"] == "AABB1122", win.volume
assert win.lbl_serial.text() == "nessun vincolo"
win.bind_serial()
assert win._only_serials == ["AABB1122"], win._only_serials
assert "legato a AABB1122" in win.lbl_serial.text(), win.lbl_serial.text()
win.push_folders.set_rows([{"path": str(tmp / "roba"), "as": "roba"}])
(tmp / "roba").mkdir()
assert win.save_pc_plan() is True
salvato = json.loads((dest / "backup.json").read_text(encoding="utf-8"))
assert salvato["only_serials"] == ["AABB1122"], salvato
print("app: piano salvato col vincolo", salvato["only_serials"])

win.load_pc_plan()
assert win._only_serials == ["AABB1122"], "vincolo non riletto"
win.unbind_serial()
assert win.lbl_serial.text() == "nessun vincolo"
print("app: vincolo riletto e rimosso")
win.close()
shutil.rmtree(tmp, ignore_errors=True)
print("\nSERIAL OK")
