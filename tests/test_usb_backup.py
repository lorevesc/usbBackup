"""Test end-to-end dei tre piani, con una cartella temporanea al posto della chiavetta."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub

tmp = Path(tempfile.mkdtemp(prefix="usbtest_"))
stick = tmp / "stick"
home = tmp / "home"
dest = home / "Backup"
pcfolder = home / "Progetti"

# --- chiavetta --------------------------------------------------------------
(stick / "Documenti" / "sub").mkdir(parents=True)
(stick / "Documenti" / "a.txt").write_text("ciao")
(stick / "Documenti" / "sub" / "b.txt").write_text("mondo")
(stick / "Documenti" / "scarta.tmp").write_text("x")
(stick / "foto").mkdir()
(stick / "foto" / "p.jpg").write_bytes(b"\xff\xd8jpeg")
(stick / "System Volume Information").mkdir()
(stick / "System Volume Information" / "junk").write_text("no")
(stick / "backup.json").write_text(json.dumps({
    "name": "chiavetta-test",
    "folders": ["Documenti", {"path": "foto", "as": "foto-stick"}],
    "exclude": ["*.tmp"],
}), encoding="utf-8")

# --- PC ---------------------------------------------------------------------
(pcfolder / "code").mkdir(parents=True)
(pcfolder / "code" / "main.py").write_text("print(1)")
(pcfolder / "code" / "__pycache__").mkdir()
(pcfolder / "code" / "__pycache__" / "x.pyc").write_text("bin")
dest.mkdir(parents=True)
(dest / "backup.json").write_text(json.dumps({
    "pc_name": "PC-TEST",
    "only_volumes": ["chiavetta-test"],
    "push": {"folders": [str(pcfolder)], "exclude": ["__pycache__"]},
    "pull": {"folders": ["foto"]},
}), encoding="utf-8")

cfg = dict(ub.DEFAULT_CONFIG)
cfg["dest_root"] = str(dest)
cfg["notify"] = False
ub.setup_log(None)
ub.volume_label = lambda root: "chiavetta-test"

print("=== run 1 ===")
assert ub.handle_volume(stick, cfg, removable=True) is True

def tree(base):
    return sorted(str(p.relative_to(base)).replace("\\", "/")
                  for p in base.rglob("*") if p.is_file())

print("\ndest:", tree(dest))
print("stick:", tree(stick))

expected_dest = {
    "chiavetta-test/Documenti/a.txt",
    "chiavetta-test/Documenti/sub/b.txt",
    "chiavetta-test/foto-stick/p.jpg",
    "chiavetta-test/foto/p.jpg",   # il pull atterra sotto il NOME DEL DISCO
}
got = set(tree(dest))
missing = expected_dest - got
assert not missing, f"mancano: {missing}"
assert not any(p.endswith(".tmp") for p in got), "esclusione *.tmp fallita"
assert not any("System Volume Information" in p for p in got), "esclusione default fallita"

expected_stick = {"backup/PC-TEST/Progetti/code/main.py"}
gots = set(tree(stick))
assert expected_stick <= gots, f"push fallito: {gots}"
assert not any("__pycache__" in p for p in gots), "esclusione push fallita"
assert not any("backup/PC-TEST/Progetti/code/main.py" in p and False for p in gots)

# --- run 2: incrementale ----------------------------------------------------
print("\n=== run 2 (incrementale) ===")
stats_before = []
orig = ub.mirror_tree
copied_total = {"n": 0}
def spy(*args, **kwargs):
    stats = args[4] if len(args) > 4 else kwargs["stats"]
    before = stats["copied"]
    orig(*args, **kwargs)
    copied_total["n"] += stats["copied"] - before
ub.mirror_tree = spy
ub.handle_volume(stick, cfg, removable=True)
ub.mirror_tree = orig
assert copied_total["n"] == 0, f"run 2 ha ricopiato {copied_total['n']} file"

# --- run 3: un file modificato ---------------------------------------------
print("\n=== run 3 (un file modificato) ===")
(stick / "Documenti" / "a.txt").write_text("ciao ciao ciao")
copied_total["n"] = 0
ub.mirror_tree = spy
ub.handle_volume(stick, cfg, removable=True)
ub.mirror_tree = orig
assert copied_total["n"] == 1, f"attesi 1 file ricopiato, trovati {copied_total['n']}"
assert (dest / "chiavetta-test/Documenti/a.txt").read_text() == "ciao ciao ciao"

# --- filtro only_volumes ----------------------------------------------------
plan = {"only_volumes": ["ALTRA*"], "push": {"folders": ["x"]}}
assert ub.volume_matches(plan, stick, "chiavetta-test", True) is False
assert ub.volume_matches(plan, stick, "ALTRA-CHIAVE", True) is True
assert ub.volume_matches({"push": {}}, stick, "x", removable=False) is False
# senza un disco indicato il piano non parte da nessuna parte, nemmeno sulle rimovibili
assert ub.volume_matches({"push": {}}, stick, "x", removable=True) is False
# la lettera di unita' non e' un disco: "D:\\" non deve valere per chi oggi e' D:
per_lettera = {"only_volumes": [str(stick), "D:\\", "D:"], "push": {"folders": ["x"]}}
assert ub.volume_matches(per_lettera, stick, "chiavetta-test", True) is False
assert ub.piano_senza_disco(per_lettera) and ub.piano_senza_disco({"push": {}})
assert not ub.piano_senza_disco({"only_volumes": ["Ssd Esterno", "D:\\"]})
assert ub.volume_matches({"only_volumes": ["Ssd Esterno", "D:\\"]}, stick, "Volume", False) is False
assert ub.volume_matches({"only_volumes": ["Ssd Esterno", "D:\\"]}, stick, "Ssd Esterno", False) is True

# --- no loop: pull non risucchia il push ------------------------------------
assert not (dest / "chiavetta-test" / "backup").exists(), "pull ha ripreso i dati del push"

print("\nricevute:", (dest / "chiavetta-test" / "_last_backup.txt").read_text().strip())
shutil.rmtree(tmp, ignore_errors=True)
print("\nTUTTI I TEST OK")
