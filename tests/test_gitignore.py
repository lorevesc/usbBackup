"""Le regole del .gitignore valgono come esclusioni."""
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub

ub.setup_log(None)
ub._config_cache["verify_percent"] = 0

tmp = Path(tempfile.mkdtemp(prefix="gi_"))
src = tmp / "progetto"


def scrivi(rel, righe="x"):
    f = src / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(righe, list):
        righe = "\n".join(righe)
    f.write_text(righe, encoding="utf-8")


scrivi(".gitignore", [
    "# commento da ignorare",
    "node_modules/",
    "*.log",
    "!importante.log",     # in git vince l'ultima regola che colpisce
    "/solo_in_cima.txt",
    "build",
])
scrivi("main.py")
scrivi("debug.log")
scrivi("importante.log")
scrivi("solo_in_cima.txt")
scrivi("sotto/solo_in_cima.txt")          # ancorato in cima: qui sotto si copia
scrivi("node_modules/pacchetto/index.js")
scrivi("build/uscita.bin")
scrivi("src/app.py")
scrivi("src/.gitignore", ["temporaneo/", "*.tmp", "!tenuto.tmp"])
scrivi("src/temporaneo/roba.txt")
scrivi("src/scarto.tmp")
scrivi("src/tenuto.tmp")


def copia(gitignore):
    dst = tmp / ("con" if gitignore else "senza")
    shutil.rmtree(dst, ignore_errors=True)
    ub.mirror_tree(src, dst, [], False, ub.new_stats(), gitignore=gitignore)
    return sorted(p.relative_to(dst).as_posix() for p in dst.rglob("*") if p.is_file())


senza = copia(False)
con = copia(True)
print(f"senza .gitignore: {len(senza)} file")
print(f"con  .gitignore: {len(con)} file")
for f in con:
    print("   ", f)

assert "main.py" in con and "src/app.py" in con
assert not any(f.startswith("node_modules/") for f in con), "node_modules/ copiata"
assert not any(f.startswith("build/") for f in con), "build copiata"
assert "debug.log" not in con, "*.log copiato"
assert "importante.log" in con, "la negazione ! non ha funzionato"
assert "solo_in_cima.txt" not in con, "il pattern ancorato / non ha funzionato"
assert "sotto/solo_in_cima.txt" in con, "il pattern ancorato ha colpito troppo in basso"
assert not any("temporaneo" in f for f in con), ".gitignore annidato ignorato"
assert "src/scarto.tmp" not in con, "*.tmp del .gitignore annidato ignorato"
assert "src/tenuto.tmp" in con, "negazione nel .gitignore annidato ignorata"
assert ".gitignore" in con, "il .gitignore stesso va copiato"
assert len(senza) == 13, senza

shutil.rmtree(tmp, ignore_errors=True)
print("\nGITIGNORE OK")
