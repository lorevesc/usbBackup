"""Ogni frase passata a t() e ogni messaggio passato a tf() devono esistere nel
vocabolario: altrimenti in inglese compare l'italiano, o il nome del messaggio."""
import ast
import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
import i18n  # noqa: E402
import usb_backup_qt as qt  # noqa: E402

mancano_ui, mancano_msg = set(), set()
for nome in ("usb_backup_qt.py", "usb_backup.py"):
    albero = ast.parse((RADICE / nome).read_text(encoding="utf-8"))
    for nodo in ast.walk(albero):
        if not (isinstance(nodo, ast.Call) and nodo.args):
            continue
        funzione = getattr(nodo.func, "id", "") or getattr(nodo.func, "attr", "")
        primo = nodo.args[0]
        if not (isinstance(primo, ast.Constant) and isinstance(primo.value, str)):
            continue
        if funzione == "t" and primo.value not in i18n.UI:
            mancano_ui.add(f"{nome}:{nodo.lineno}  {primo.value[:60]!r}")
        if funzione == "tf" and primo.value not in i18n.MESSAGGI:
            mancano_msg.add(f"{nome}:{nodo.lineno}  {primo.value!r}")

# il contrario: una frase del vocabolario scritta nel codice senza t() resta in italiano
scoperte = set()
albero = ast.parse((RADICE / "usb_backup_qt.py").read_text(encoding="utf-8"))
coperti = set()
for nodo in ast.walk(albero):
    tradotta = (isinstance(nodo, ast.Call)
                and (getattr(nodo.func, "id", "") or getattr(nodo.func, "attr", "")) in ("t", "tf"))
    tabella = (isinstance(nodo, ast.Assign)
               and any(getattr(x, "id", "") in ("TIPI", "COLONNE", "TESTI") for x in nodo.targets))
    if tradotta or tabella:
        coperti.update(id(x) for x in ast.walk(nodo))
for nodo in ast.walk(albero):
    if (isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) and id(nodo) not in coperti
            and nodo.value in i18n.UI and i18n.UI[nodo.value] != nodo.value):
        scoperte.add(f"usb_backup_qt.py:{nodo.lineno}  {nodo.value[:60]!r}")
assert not scoperte, "frasi del vocabolario usate senza t():\n" + "\n".join(sorted(scoperte))

# frasi tenute in tabelle e tradotte al momento dell'uso
for frase in (list(qt.EventiDialog.TIPI.values()) + list(qt.Window.COLONNE)
              + [x for coppia in qt.PrimoAvvio.TESTI for x in coppia]):
    if frase not in i18n.UI:
        mancano_ui.add(f"tabella  {frase[:60]!r}")

assert not mancano_ui, "frasi senza traduzione:\n" + "\n".join(sorted(mancano_ui))
assert not mancano_msg, "messaggi inesistenti:\n" + "\n".join(sorted(mancano_msg))
print(f"{len(i18n.UI)} frasi e {len(i18n.MESSAGGI)} messaggi: ogni t() e tf() del codice "
      "ha la sua traduzione")
print("\nVOCABOLARIO OK")
