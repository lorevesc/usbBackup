"""Una sola app per utente: la seconda apertura mostra la prima ed esce."""
import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
import usb_backup_qt as qt  # noqa: E402

app = QApplication(sys.argv)
nome = qt.nome_istanza() + "-test"
assert nome.startswith("usb-backup-")

assert qt.avvisa_istanza_aperta(nome) is False, "nessuna app aperta: deve partire"
print("nessuna istanza: la prima parte normalmente")


class Finta:
    mostrata = 0

    def show_from_tray(self):
        Finta.mostrata += 1


finta = Finta()
from PySide6.QtCore import QObject  # noqa: E402
genitore = QObject()
genitore.show_from_tray = finta.show_from_tray
server = qt.ascolta_altre_aperture(nome, genitore)
assert server.isListening(), "la prima non resta in ascolto"

assert qt.avvisa_istanza_aperta(nome) is True, "la seconda non trova la prima"
for _ in range(50):
    app.processEvents()
    if Finta.mostrata:
        break
assert Finta.mostrata == 1, "la prima non si e' mostrata"
print("seconda apertura: trova la prima, le chiede di mostrarsi, ed esce")

# lo stile della selezione e' esplicito: su Windows 11 lo stile nativo la
# rendeva illeggibile (testo nero su fondo scuro)
assert "::item:selected" in qt.QSS and "selection-color" in qt.QSS
assert "QDialog" in qt.QSS and "QTreeWidget" in qt.QSS
print("stile: selezione e finestre di dialogo hanno colori espliciti")
print("\nISTANZA UNICA OK")
