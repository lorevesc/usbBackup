"""Collegamenti: creati dove richiesto, puntano all'app, senza console."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub

ub.setup_log(None)
if not ub.IS_WIN:
    assert ub.crea_collegamenti() == []
    print("fuori da Windows: nessun collegamento, nessun errore")
    print("\nCOLLEGAMENTI OK")
    sys.exit(0)

tmp = Path(tempfile.mkdtemp(prefix="lnk_"))
start, desktop = tmp / "Start", tmp / "Desktop"
start.mkdir()
desktop.mkdir()

fatti = ub.crea_collegamenti([start, desktop])
assert len(fatti) == 2, fatti
for percorso in (start / "USB Backup.lnk", desktop / "USB Backup.lnk"):
    assert percorso.is_file(), f"manca {percorso}"

# rileggo il collegamento con la stessa interfaccia che usa Windows
lettura = subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:LNK); "
     "$s.TargetPath; $s.Arguments; $s.IconLocation"],
    capture_output=True, text=True, creationflags=0x08000000,
    env={**__import__("os").environ, "LNK": str(start / "USB Backup.lnk")})
bersaglio, argomenti, icona = (lettura.stdout.strip().splitlines() + ["", "", ""])[:3]
print("punta a:", bersaglio, argomenti)

if getattr(sys, "frozen", False):
    assert bersaglio.lower() == sys.executable.lower()
else:
    assert bersaglio.lower().endswith("pythonw.exe"), f"non pythonw: {bersaglio}"
    assert "usb_backup_qt.py" in argomenti, argomenti
    assert icona.lower().split(",")[0].endswith("icon.ico"), icona
print("sorgente: pythonw (niente console) + usb_backup_qt.py, icona dell'app")

shutil.rmtree(tmp, ignore_errors=True)
print("\nCOLLEGAMENTI OK")
