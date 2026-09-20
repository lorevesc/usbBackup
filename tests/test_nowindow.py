"""Nessun processo esterno deve far lampeggiare una console."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub

chiamate = []
originale = subprocess.run


def spia(comando, **kw):
    chiamate.append((comando, kw))
    class Finto:
        returncode = 0
        stdout = ""
        stderr = ""
    return Finto()


subprocess.run = spia
ub.notify("prova", "messaggio")
ub.volume_serial(Path("C:/")) if not ub.IS_WIN else None   # su mac userebbe diskutil
subprocess.run = originale

assert chiamate, "notify non ha lanciato niente (o gira su una piattaforma senza notifiche)"
for comando, kw in chiamate:
    nome = comando[0] if isinstance(comando, list) else str(comando)
    if ub.IS_WIN:
        assert kw.get("creationflags") == ub.CREATE_NO_WINDOW, (
            f"{nome} aprirebbe una finestra: creationflags={kw.get('creationflags')}")
    print(f"  {nome}: nascosto correttamente"
          if ub.IS_WIN else f"  {nome}: nessuna finestra da nascondere qui")

# nessuna chiamata diretta deve essere rimasta in giro
sorgenti = [Path(__file__).resolve().parent.parent / n
            for n in ("usb_backup.py", "usb_backup_qt.py")]
for sorgente in sorgenti:
    testo = sorgente.read_text(encoding="utf-8")
    dirette = [r.strip() for r in testo.splitlines()
               if "subprocess.run(" in r and "def run_hidden" not in r
               and "return subprocess.run(comando" not in r
               and not r.strip().startswith("#") and not r.strip().startswith('"""')]
    assert not dirette, f"{sorgente.name}: chiamate diruette non nascoste: {dirette}"
    print(f"  {sorgente.name}: tutte le chiamate passano dal filtro")

print("\nNOWINDOW OK")
