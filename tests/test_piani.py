"""Piu' piani sul PC, uno per disco: ogni disco riceve e da' solo le sue cartelle."""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usb_backup as ub

tmp = Path(tempfile.mkdtemp(prefix="piani_"))
ssd, kingston, altro = tmp / "SSD", tmp / "KINGSTON", tmp / "ALTRO"
for disco in (ssd, kingston, altro):
    disco.mkdir()
(ssd / "Codice").mkdir()
(ssd / "Codice" / "main.py").write_text("print(1)", encoding="utf-8")
lavoro, documenti = tmp / "WorkArea", tmp / "Documenti"
for cartella, nome in ((lavoro, "app.py"), (documenti, "lettera.txt")):
    cartella.mkdir()
    (cartella / nome).write_text(nome, encoding="utf-8")

SERIALI = {str(ssd): "1A2B-3C4D", str(kingston): "9F8E-7D6C", str(altro): "0000-1111"}
ub.volume_serial = lambda r: SERIALI.get(str(r), "")
ub.volume_label = lambda r: Path(r).name
ub.CONFIG_PATH = tmp / "config.json"
ub.CONFIG_PATH.write_text(json.dumps({
    "notify": False, "dest_root": str(tmp / "Backup"), "log_file": str(tmp / "log.txt"),
    "language": "it", "autostart": False, "verify_percent": 0, "save_settings_on_disk": False,
}), encoding="utf-8")
cfg = ub.load_config()
(tmp / "Backup").mkdir()
file_pc = tmp / "Backup" / "backup.json"

# ---------------- formato: dividere e riunire ----------------
piatto = {"pc_name": "laptop", "only_serials": ["X"], "push": {"folders": ["a"]}}
comuni, piani = ub.dividi_piani(piatto)
assert comuni == {"pc_name": "laptop"} and len(piani) == 1 and "pc_name" not in piani[0]
assert ub.unisci_piani(comuni, piani) == piatto, "un piano solo deve restare nel formato di sempre"
assert ub.dividi_piani(None) == ({}, [])
print("formato: un piano resta piatto, compatibile con le versioni vecchie")

file_pc.write_text(json.dumps({
    "pc_name": "laptop",
    "piani": [
        {"only_serials": ["1A2B-3C4D"], "push": {"folders": [str(lavoro)]},
         "pull": {"folders": ["Codice"]}, "sync": []},
        {"only_serials": ["9F8E-7D6C"], "push": {"folders": [str(documenti)]}},
    ],
}), encoding="utf-8")
tutti = ub.piani_del_pc(ub.read_pc_plan(cfg))
assert [p["pc_name"] for p in tutti] == ["laptop", "laptop"], "il nome del PC vale per tutti"

# ---------------- motore: ogni disco il suo ----------------
assert len(ub.piani_per_volume(cfg, ssd, "SSD", True)) == 1
assert len(ub.piani_per_volume(cfg, altro, "ALTRO", True)) == 0
ub.handle_volume(ssd, cfg, True)
ub.handle_volume(kingston, cfg, True)
ub.handle_volume(altro, cfg, True)
assert (ssd / "backup" / "laptop" / "WorkArea" / "app.py").is_file()
assert not (ssd / "backup" / "laptop" / "Documenti").exists(), "i Documenti sono andati sull'SSD"
assert (kingston / "backup" / "laptop" / "Documenti" / "lettera.txt").is_file()
assert not (kingston / "backup" / "laptop" / "WorkArea").exists(), "WorkArea e' andata sulla KINGSTON"
assert (tmp / "Backup" / "SSD" / "Codice" / "main.py").is_file(), "pull dell'SSD mancante"
assert not (altro / "backup").exists(), "un disco senza piano ha ricevuto qualcosa"
print("motore: WorkArea solo sull'SSD, Documenti solo sulla KINGSTON, nulla sul terzo disco")

coppie_ssd = {c[0] for c in ub.coppie_del_volume(ssd, cfg, True)}
coppie_king = [c for c in ub.coppie_del_volume(kingston, cfg, True)]
assert coppie_ssd == {"push", "pull"} and len(coppie_king) == 1, (coppie_ssd, coppie_king)
esito = ub.verifica_completa(kingston, cfg, True)
assert esito["verificati"] == 1 and not esito.get("eventi"), esito
print("verifica completa: guarda solo il piano del disco")

# ---------------- importare: i seriali dentro i piani restano ----------------
esportato = ub.export_settings(tmp, cfg)
_, piano_importato = ub.import_settings(esportato, cfg)
assert [p["only_serials"] for p in piano_importato["piani"]] == [["1A2B-3C4D"], ["9F8E-7D6C"]]
assert "pc_name" not in piano_importato
print("import: i piani restano distinti per disco")

# ---------------- app ----------------
ub.list_volumes = lambda inc: [(ssd, False), (kingston, True)]
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402
import usb_backup_qt as qt  # noqa: E402

app = QApplication(sys.argv)
win = qt.Window()
win.refresh_volumes()
assert all(v["pc_plan"] for v in win.volumes), "badge 'piano PC' mancante"
assert win.pc_scelta.count() == 2
assert "SSD" in win.pc_scelta.itemText(0) and "KINGSTON" in win.pc_scelta.itemText(1), \
    [win.pc_scelta.itemText(i) for i in range(2)]
assert [r["path"] for r in win.push_folders.get_rows()] == [str(lavoro)]
win.pc_scelta.setCurrentIndex(1)
assert [r["path"] for r in win.push_folders.get_rows()] == [str(documenti)]
assert win._only_serials == ["9F8E-7D6C"]
musica = tmp / "Musica"
musica.mkdir()
win.push_folders.set_rows(win.push_folders.get_rows() + [{"path": str(musica), "name": ""}])
win.pc_scelta.setCurrentIndex(0)
win.pc_scelta.setCurrentIndex(1)
assert len(win.push_folders.get_rows()) == 2, "modifica persa cambiando piano"
print("app: un piano per disco nel menu, le modifiche restano cambiando piano")

toast = []
win.toast = lambda testo, variante="": toast.append((testo, variante))
win.volume = next(v for v in win.volumes if v["label"] == "KINGSTON")
win.nuovo_piano()
assert win.pc_scelta.count() == 3 and win._only_serials == [], \
    "la KINGSTON ha gia' un piano: il nuovo non deve legarsi a lei"
assert win.save_pc_plan() is False and toast[-1][1] == "err", "salvato un piano vuoto"
qt.QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
win.togli_piano()
assert win.pc_scelta.count() == 2
assert win.save_pc_plan() is True
salvato = json.loads(file_pc.read_text(encoding="utf-8"))
assert salvato["pc_name"] == "laptop" and len(salvato["piani"]) == 2, salvato
assert len(salvato["piani"][1]["push"]["folders"]) == 2
assert "sync" in salvato["piani"][0], "chiave non mostrata dall'app persa al salvataggio"
print("app: nuovo piano, piano vuoto rifiutato, tolto, salvato con le chiavi nascoste")

win.pc_scelta.setCurrentIndex(1)
win.togli_piano()
assert win.save_pc_plan() is True
salvato = json.loads(file_pc.read_text(encoding="utf-8"))
assert "piani" not in salvato and salvato["only_serials"] == ["1A2B-3C4D"], salvato
print("app: tornati a un piano solo, il file torna nel formato di sempre")

# ---------------- configurazione guidata ----------------
file_pc.write_text(json.dumps({"pc_name": "laptop", "piani": [
    {"only_serials": ["1A2B-3C4D"], "push": {"folders": [str(lavoro)]}},
    {"only_serials": ["9F8E-7D6C"], "push": {"folders": [str(documenti)], "delete_extra": True}},
]}), encoding="utf-8")
win.load_pc_plan()
guida = qt.PrimoAvvio(win)
guida.scelta_disco.setCurrentIndex([v["label"] for v in guida.volumi].index("KINGSTON"))
guida.cartelle_push.set_rows([{"path": str(musica), "name": ""}])
guida.salva()
salvato = json.loads(file_pc.read_text(encoding="utf-8"))
assert len(salvato["piani"]) == 2, "la guida ha aggiunto un piano invece di aggiornare quello del disco"
assert salvato["piani"][1]["push"]["folders"][0].endswith("Musica"), salvato["piani"][1]
assert salvato["piani"][0]["push"]["folders"] == [str(lavoro)], "toccato il piano dell'altro disco"
assert salvato["piani"][1]["push"]["delete_extra"] is True, "la guida ha spento delete_extra"
win.sw_watch.setChecked(False)

SERIALI[str(altro)] = "0000-1111"
ub.list_volumes = lambda inc: [(ssd, False), (kingston, True), (altro, True)]
win.refresh_volumes()
guida = qt.PrimoAvvio(win)
guida.scelta_disco.setCurrentIndex([v["label"] for v in guida.volumi].index("ALTRO"))
guida.cartelle_push.set_rows([{"path": str(documenti), "name": ""}])
guida.salva()
salvato = json.loads(file_pc.read_text(encoding="utf-8"))
assert len(salvato["piani"]) == 3 and salvato["piani"][2]["only_serials"] == ["0000-1111"]
win.sw_watch.setChecked(False)
print("guida: aggiorna il piano del disco scelto, per un disco nuovo ne aggiunge uno")

# ---------------- nome nel menu subito aggiornato ----------------
win.load_pc_plan()
win.pc_scelta.setCurrentIndex(2)
win.unbind_serial()
win.pc_only.setPlainText("CHIAVETTA-NUOVA")
assert "CHIAVETTA-NUOVA" in win.pc_scelta.itemText(2), win.pc_scelta.itemText(2)
print("menu: il nome del piano segue il filtro mentre lo scrivi")

# ---------------- piani sovrapposti: avviso al salvataggio ----------------
avvisi = []
qt.QMessageBox.warning = staticmethod(lambda *a, **k: avvisi.append(a[2]) or QMessageBox.Ok)
win.pc_only.setPlainText("")
win.bind_serial()                              # win.volume e' la KINGSTON: gia' nel piano 2
assert win.save_pc_plan() is True
assert avvisi and "KINGSTON" in avvisi[-1] and "2" in avvisi[-1] and "3" in avvisi[-1], avvisi
avvisi.clear()
win.unbind_serial()
win.pc_only.setPlainText("NESSUNO")
assert win.save_pc_plan() is True and not avvisi, avvisi
print("sovrapposti: due piani sulla KINGSTON avvisano; separati, nessun avviso")

# ---------------- riepilogo e notifica tradotti ----------------
import i18n  # noqa: E402
i18n.set_language("en")
assert ub.tf("vol.part", nome="x", copiati=1, errori=0) == "x: 1 copied, 0 errors"
assert "errors" in ub.tf("notify.body", n=1, mb="0.1", errori=0)
i18n.set_language("it")
print("riepilogo e notifica: in inglese niente italiano")

print("\nPIANI OK")
