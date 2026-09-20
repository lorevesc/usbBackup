"""Test headless dell'app Qt: scrive i piani, li rilegge, li fa eseguire al motore."""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import usb_backup as ub

tmp = Path(tempfile.mkdtemp(prefix="qt_"))
stick = tmp / "KINGSTON"
(stick / "Documenti").mkdir(parents=True)
(stick / "Documenti" / "a.txt").write_text("contenuto", encoding="utf-8")
(stick / "backup" / "pc-casa" / "progetto").mkdir(parents=True)
(stick / "backup" / "pc-casa" / "progetto" / "main.py").write_text("da casa", encoding="utf-8")
dest = tmp / "Backup"
dest.mkdir()
staging = tmp / "incoming" / "da-casa"
locale = tmp / "dev" / "repo-lavoro"
(locale / "src").mkdir(parents=True)
(locale / "src" / "app.py").write_text("lavoro", encoding="utf-8")

ub.list_volumes = lambda include_fixed: [(stick, True)]
ub.volume_label = lambda root: "KINGSTON"
ub.CONFIG_PATH = tmp / "config.json"
_orig = ub.load_config
ub.load_config = lambda: {**_orig(), "dest_root": str(dest), "notify": False}

from PySide6.QtWidgets import QApplication  # noqa: E402
import usb_backup_qt as qt  # noqa: E402

app = QApplication(sys.argv)
win = qt.Window()

assert win.volume and win.volume["path"] == str(stick), win.volume
print("volume visto:", win.volume["label"])

# --- piano del PC: push del progetto, pull in cartella di staging ---
win.pc_name.setText("pc-ufficio")
win.push_folders.set_rows([{"path": str(locale), "as": "progetto"}])
win.pull_folders.set_rows([{"path": "backup/pc-casa/progetto", "as": "progetto"}])
win.pull_dest.setText(str(staging))
win.pull_delete.setChecked(True)
assert win.save_pc_plan() is True

plan = json.loads((dest / "backup.json").read_text(encoding="utf-8"))
assert plan["pull"]["dest"] == str(staging), plan
assert plan["pull"]["delete_extra"] is True
assert plan["push"]["folders"] == [{"path": str(locale), "as": "progetto"}]
print("piano salvato:", json.dumps(plan["pull"], ensure_ascii=False))

win.load_pc_plan()
assert win.pull_dest.text() == str(staging), "destinazione non riletta"

# --- il motore esegue: la roba di casa atterra nello staging, non nel progetto ---
win.cfg = ub.load_config()
assert ub.handle_volume(stick, win.cfg, True) is True
atterrato = staging / "progetto" / "main.py"
assert atterrato.is_file(), sorted(p.name for p in staging.rglob("*"))
assert atterrato.read_text(encoding="utf-8") == "da casa"
assert not (locale / "main.py").exists(), "ha toccato il progetto vero"
assert (stick / "backup" / "pc-ufficio" / "progetto" / "src" / "app.py").is_file(), "push mancato"
print("staging:", atterrato)

# --- cancellazione: finisce in __deleted, non sparisce ---
(stick / "backup" / "pc-casa" / "progetto" / "main.py").unlink()
ub.handle_volume(stick, win.cfg, True)
cestino = staging / "progetto" / ub.TRASH_DIR / "main.py"
assert cestino.is_file(), sorted(str(p) for p in staging.rglob("*"))
assert cestino.read_text(encoding="utf-8") == "da casa", "contenuto perso"
print("finito in:", cestino)

win.close()
shutil.rmtree(tmp, ignore_errors=True)
print("\nQT OK")
