#!/usr/bin/env python3
"""Traduzione dell'interfaccia e dei messaggi.

La lingua di partenza e' l'italiano: le chiavi del vocabolario sono le frasi
italiane cosi' come stanno nel codice. Cosi' non serve inventare sigle, e una
frase senza traduzione resta leggibile invece di diventare `ui.btn.save.42`.

    from i18n import t, tf, set_language

    t("Salva impostazioni")                  -> "Save settings"
    tf("copiati {n} file", n=12)             -> "copied 12 files"

`set_language("auto")` segue la lingua del sistema.
"""
from __future__ import annotations

import locale
import os

LINGUE = ("it", "en")
_lingua = "it"


# --------------------------------------------------------------------------
# interfaccia
# --------------------------------------------------------------------------
UI = {
    # --- barra laterale e testate ---
    "USB Backup": "USB Backup",
    "Chiavette": "Drives",
    "Questo PC": "This PC",
    "Storico": "History",
    "Impostazioni": "Settings",
    "cosa copiare da ogni chiavetta": "what to copy from each drive",
    "cosa scambiare tra PC e chiavetta": "what to exchange between PC and drive",
    "come sono andati gli ultimi giri": "how the last runs went",
    "destinazione, notifiche, avvio automatico": "destination, notifications, autostart",
    "sorveglianza attiva": "watching",
    "sorveglianza spenta": "not watching",
    "Copia da sola a ogni chiavetta collegata.": "Copies by itself whenever a drive is plugged in.",
    "PC: ": "PC: ",

    # --- scheda Chiavette ---
    "Volumi collegati": "Connected volumes",
    "Seleziona una chiavetta per configurarla.": "Pick a drive to set it up.",
    "Aggiorna": "Refresh",
    "Nessun volume collegato": "No volume connected",
    "Infila una chiavetta: compare qui appena il sistema la monta.":
        "Plug a drive in: it shows up here as soon as the system mounts it.",
    "rimovibile": "removable",
    "disco fisso": "fixed disk",
    "backup.json": "backup.json",
    "nessun piano": "no plan",
    "piano PC": "PC plan",
    "backup.json della chiavetta": "the drive's backup.json",
    "CHIAVETTA → PC": "DRIVE → PC",
    "PC → CHIAVETTA": "PC → DRIVE",
    "Nome della cartella di destinazione": "Destination folder name",
    "Vuoto = etichetta del volume.": "Empty = the volume label.",
    "Cartelle della chiavetta da copiare sul PC": "Drive folders to copy to the PC",
    "Esclusioni (una per riga, glob)": "Exclusions (one per line, glob)",
    "Opzioni": "Options",
    "Sposta in __deleted i file spariti dalla chiavetta":
        "Move to __deleted the files gone from the drive",
    "Niente viene mai cancellato: finisce in __deleted, accanto alla copia.":
        "Nothing is ever deleted: it lands in __deleted, next to the copy.",
    "Salva sulla chiavetta": "Save to drive",
    "Backup adesso": "Back up now",
    "Ferma": "Stop",
    "Apri chiavetta": "Open drive",
    "Elimina backup.json": "Delete backup.json",
    "Nessuna cartella impostata.": "No folder set.",
    "+  Aggiungi cartella": "+  Add folder",
    "+  Aggiungi cartella del PC": "+  Add PC folder",
    "+  Aggiungi cartella della chiavetta": "+  Add drive folder",
    "Rimuovi": "Remove",
    "Destinazione:   ": "Destination:   ",

    # --- scheda Questo PC ---
    "Identità e filtro": "Identity and filter",
    "Nome di questo PC": "This PC's name",
    "Vuoto = hostname. È il nome della cartella creata sulla chiavetta.":
        "Empty = hostname. It names the folder created on the drive.",
    "Applica solo a queste chiavette (una per riga, glob)":
        "Only for these drives (one per line, glob)",
    "Vuoto = tutte le chiavette rimovibili, mai i dischi fissi.":
        "Empty = every removable drive, never fixed disks.",
    "Vincolo al disco (numero di serie)": "Bind to a disk (serial number)",
    "Lega al disco selezionato": "Bind to selected disk",
    "Togli il vincolo": "Remove binding",
    "nessun vincolo": "not bound",
    "legato a ": "bound to ",
    "disco non collegato": "disk not connected",
    "Il piu' solido: la lettera di unita' cambia e l'etichetta la cambia chiunque, "
    "il numero di serie no. Se impostato vale solo questo, e le regole qui sopra "
    "vengono ignorate.":
        "The sturdiest option: drive letters change and anyone can rename a label, "
        "the serial number stays. When set, only this counts and the rules above "
        "are ignored.",
    "Push": "Push",
    "Pull": "Pull",
    "Cartelle del PC da spedire sulla chiavetta": "PC folders to send to the drive",
    "Cartella radice sulla chiavetta": "Root folder on the drive",
    "Esclusioni": "Exclusions",
    "Sposta in __deleted sulla chiavetta ciò che non c'è più sul PC":
        "Move to __deleted on the drive what is gone from the PC",
    "Cartelle della chiavetta da prendere": "Drive folders to fetch",
    "Cartella di destinazione sul PC": "Destination folder on the PC",
    "Vuoto = ~/Backup/<nome del disco>. Mettici una cartella di staging se vuoi "
    "confrontare e unire a mano, senza toccare il progetto vero.":
        "Empty = ~/Backup/<disk name>. Point it at a staging folder if you want to "
        "compare and merge by hand, without touching the real project.",
    "Sposta in __deleted sul PC ciò che non c'è più sulla chiavetta":
        "Move to __deleted on the PC what is gone from the drive",
    "Salva piano del PC": "Save PC plan",
    "Ricarica": "Reload",
    "Elimina piano del PC": "Delete PC plan",
    "File: ": "File: ",

    # --- scheda Storico ---
    "Ultimi backup": "Latest backups",
    "Quando": "When",
    "Volume": "Volume",
    "Copiati": "Copied",
    "Invariati": "Unchanged",
    "In __deleted": "To __deleted",
    "Errori": "Errors",
    "Dati": "Data",
    "Durata": "Duration",
    "Apri la cartella dei log": "Open the log folder",
    "Ancora nessun giro: appena ne parte uno compare qui.":
        "No run yet: as soon as one starts it shows up here.",
    " giri registrati - l'ultimo ": " runs recorded - the last one ",
    " alle ": " at ",
    "Non colleghi da un po': ": "Not plugged in for a while: ",
    ".  Il backup di quei dischi e' fermo a quella data.":
        ".  Those disks' backups are frozen at that date.",

    # --- scheda Impostazioni ---
    "Generali": "General",
    "Cartella dei backup sul PC": "Backup folder on the PC",
    "Sfoglia": "Browse",
    "Qui dentro vive anche il backup.json del PC.":
        "The PC's backup.json lives in here too.",
    "File di log": "Log file",
    "Controlla i volumi ogni (secondi)": "Check volumes every (seconds)",
    "Considera anche i dischi \"fissi\" non di sistema":
        "Consider non-system \"fixed\" disks too",
    "Molti SSD USB su Windows si presentano come disco fisso.":
        "Many USB SSDs show up as fixed disks on Windows.",
    "Notifica di sistema a fine backup": "System notification when a backup ends",
    "Chiudendo la finestra resta nella tray": "Closing the window keeps it in the tray",
    "All'avvio parti direttamente nella tray": "Start straight into the tray",
    "Comodo con l'avvio automatico: il programma si accende da solo senza aprirti "
    "la finestra in faccia.":
        "Handy with autostart: the program comes up on its own without throwing a "
        "window in your face.",
    "Rispetta i .gitignore dei progetti": "Honour the projects' .gitignore",
    "Salta quello che git gia' ignora: node_modules, .venv, build. Niente liste da "
    "mantenere a mano.":
        "Skips what git already ignores: node_modules, .venv, build. No lists to "
        "maintain by hand.",
    "Verifica a campione dopo la copia": "Spot check after copying",
    "% dei file copiati, 0 per non verificare":
        "% of copied files, 0 to skip checking",
    "Confronta l'impronta del file copiato con l'originale: le chiavette si "
    "guastano in silenzio.":
        "Compares the copy's fingerprint with the original: drives fail silently.",
    "Esclusioni globali (una per riga)": "Global exclusions (one per line)",
    "Salva impostazioni": "Save settings",
    "Apri cartella backup": "Open backup folder",
    "Apri il log": "Open the log",
    "Esporta sul disco": "Export to disk",
    "Importa da file": "Import from file",
    "Avvio automatico al login": "Start at login",
    "Installa": "Install",
    "Lingua": "Language",
    "Italiano": "Italian",
    "Inglese": "English",
    "Come il sistema": "Follow the system",
    "La lingua cambia alla prossima apertura.": "The language changes next time you open it.",
    "Windows: attività pianificata ONLOGON, senza finestra.  macOS: LaunchAgent "
    "caricato con launchctl.":
        "Windows: ONLOGON scheduled task, no window.  macOS: LaunchAgent loaded "
        "with launchctl.",

    # --- log e stato ---
    "Log": "Log",
    "Pulisci": "Clear",
    "Nascondi": "Hide",
    "Mostra": "Show",
    "Nessuna attività finora.": "Nothing has happened yet.",
    "in attesa": "idle",
    "in ascolto": "listening",
    "backup in corso…": "backup running…",
    "backup terminato": "backup finished",
    "mi fermo appena finisce il file…": "stopping as soon as this file is done…",

    # --- tray ---
    "Apri USB Backup": "Open USB Backup",
    "Sorveglianza": "Watching",
    "Esci": "Quit",
    "USB Backup - sorveglianza ": "USB Backup - watching: ",
    "attiva": "on",
    "spenta": "off",

    # --- messaggi e dialoghi ---
    "Conferma": "Confirm",
    "Eliminare ": "Delete ",
    "?\n\nLa chiavetta non verrà più copiata in automatico.\nI backup già fatti "
    "sul PC restano dove sono.":
        "?\n\nThe drive will no longer be copied automatically.\nBackups already on "
        "the PC stay where they are.",
    "Il backup usa i file già salvati.\n\nSalvare prima le modifiche aperte?":
        "The backup uses the files already saved.\n\nSave your open changes first?",
    "Salvato sulla chiavetta": "Saved to the drive",
    "Piano del PC salvato": "PC plan saved",
    "Impostazioni salvate": "Settings saved",
    "Aggiungi almeno una cartella": "Add at least one folder",
    "Aggiungi almeno una cartella in Push o in Pull":
        "Add at least one folder to Push or Pull",
    "Seleziona prima una chiavetta": "Pick a drive first",
    "Seleziona prima un disco nella scheda Chiavette":
        "Pick a disk in the Drives tab first",
    "Questo disco non espone un numero di serie": "This disk exposes no serial number",
    "Quella cartella non è sulla chiavetta": "That folder is not on the drive",
    "Piano legato a ": "Plan bound to ",
    "Esportato in ": "Exported to ",
    "Non riesco a scrivere: ": "Cannot write: ",
    "Scrittura fallita: ": "Write failed: ",
    "File non valido: ": "Invalid file: ",
    "Importare?": "Import?",
    "Arrivano impostazioni e piano da un'altra macchina.":
        "Settings and plan are coming from another machine.",
    "Restano com'erano: cartella dei backup, file di log e vincoli ":
        "These stay as they are: backup folder, log file and disk ",
    "ai dischi.": "bindings.",
    "I percorsi locali del piano (push) andranno adattati a mano.":
        "The plan's local paths (push) will need adjusting by hand.",
    "Procedo?": "Go ahead?",
    "Importato: controlla i percorsi nella scheda Questo PC":
        "Imported: check the paths in the This PC tab",
    "L'intervallo deve essere un numero": "The interval must be a number",
    "La percentuale di verifica dev'essere un numero":
        "The check percentage must be a number",
    "Log su file disattivato": "Logging to file is off",
    "Avvio automatico ": "Autostart ",
    "installato": "installed",
    "rimosso": "removed",
    "Operazione fallita (codice ": "Operation failed (code ",

    # --- scelta cartelle ---
    "Cartella dentro ": "Folder inside ",
    "Cartella del PC da spedire sulla chiavetta": "PC folder to send to the drive",
    "Dove far atterrare la roba presa dalla chiavetta":
        "Where to drop what is taken from the drive",
    "Cartella dei backup": "Backup folder",
    "File di impostazioni da importare": "Settings file to import",
    "Nome cartella di destinazione": "Destination folder name",
}


# --------------------------------------------------------------------------
# messaggi del motore: hanno parti variabili, quindi vanno per modello
# --------------------------------------------------------------------------
MESSAGGI = {
    "plan.stick": ("[chiavetta->PC] {root} -> {dest}", "[drive->PC] {root} -> {dest}"),
    "plan.stick.end": ("[fine chiavetta->PC] {name}: {summary}",
                       "[drive->PC done] {name}: {summary}"),
    "plan.push": ("[PC->chiavetta] {pc} -> {dest}", "[PC->drive] {pc} -> {dest}"),
    "plan.push.end": ("[fine PC->chiavetta] {pc}: {summary}",
                      "[PC->drive done] {pc}: {summary}"),
    "plan.pull": ("[chiavetta->PC (piano PC)] {root} -> {dest}",
                  "[drive->PC (PC plan)] {root} -> {dest}"),
    "plan.pull.end": ("[fine chiavetta->PC (piano PC)] {pc}: {summary}",
                      "[drive->PC done (PC plan)] {pc}: {summary}"),
    "count.first": ("  primo giro: conto i file di {label}...",
                    "  first run: counting files in {label}..."),
    "count.done": ("  {files} file, {size} da confrontare",
                   "  {files} files, {size} to compare"),
    "count.estimate": ("  circa {files} file, {size} (stima del giro scorso)",
                       "  about {files} files, {size} (last run's estimate)"),
    "space.check": ("  spazio su {disco}: {libero} liberi, {serve} da sistemare",
                    "  space on {disco}: {libero} free, {serve} to handle"),
    "space.short": ("  [errore] non ci sta: mancano {quanto}. Non copio niente.",
                    "  [error] it does not fit: {quanto} missing. Copying nothing."),
    "space.tight": ("  [attenzione] liberi {libero} contro {totale} totali: se non "
                    "basta mi fermo strada facendo",
                    "  [warning] {libero} free against {totale} total: if it runs "
                    "out I stop along the way"),
    "space.out": ("  [errore] spazio esaurito {dettaglio}",
                  "  [error] out of space {dettaglio}"),
    "space.out.more": ("  [errore] copiati {n} file prima di fermarmi; libera spazio "
                       "e rilancia, riprende da dove era",
                       "  [error] copied {n} files before stopping; free some space "
                       "and run again, it picks up where it left off"),
    "stopped": ("  [fermato] interrotto su richiesta dopo {n} file; al prossimo giro "
                "riprende da qui",
                "  [stopped] interrupted on request after {n} files; the next run "
                "picks up from here"),
    "verify.start": ("  verifica a campione: {quanti} file su {totale} copiati",
                     "  spot check: {quanti} files out of {totale} copied"),
    "verify.bad": ("    [errore] copia diversa dall'originale: {file}",
                   "    [error] copy differs from the original: {file}"),
    "verify.summary": ("  [attenzione] {sbagliati} file su {quanti} non corrispondono: "
                       "disco o cavo da controllare",
                       "  [warning] {sbagliati} files out of {quanti} do not match: "
                       "check the disk or the cable"),
    "watch.start": ("[watcher] avviato (poll {interval}s, dest_root {dest})",
                    "[watcher] started (poll {interval}s, dest_root {dest})"),
    "watch.events": ("[watcher] in ascolto sugli eventi di {sistema} (nessuna lettura "
                     "periodica dei dischi)",
                     "[watcher] listening to {sistema} events (no periodic disk reads)"),
    "watch.present": ("[watcher] gia' collegati: {elenco}",
                      "[watcher] already connected: {elenco}"),
    "watch.none": ("[watcher] nessun volume collegato, aspetto",
                   "[watcher] no volume connected, waiting"),
    "watch.stop": ("[watcher] fermato", "[watcher] stopped"),
    "watch.idle": ("[watcher] in ascolto, niente di nuovo ({n} volumi sorvegliati)",
                   "[watcher] listening, nothing new ({n} volumes watched)"),
    "vol.removed": ("[rimosso] {root}", "[removed] {root}"),
    "vol.cooldown": ("[salto] {root}: gia' elaborato {quando} fa (riposo di {minuti} min)",
                     "[skip] {root}: already handled {quando} ago (resting {minuti} min)"),
    "vol.unreadable": ("[salto] {root} non leggibile", "[skip] {root} unreadable"),
    "vol.summary": ("[volume {label}] {parts}", "[volume {label}] {parts}"),
    "vol.nothing": ("[attenzione] {root}: niente da fare - nessun backup.json sulla "
                    "chiavetta e il piano del PC non si applica",
                    "[warning] {root}: nothing to do - no backup.json on the drive and "
                    "the PC plan does not apply"),
    "saved": ("[salvato] {path}", "[saved] {path}"),
    "deleted": ("[eliminato] {path}", "[deleted] {path}"),
    "exported": ("[esportato] {path}", "[exported] {path}"),
    "start.tray": ("[avvio] parto nella tray", "[start] starting in the tray"),
    "autostart": ("[avvio automatico] {cosa} (codice {codice})",
                  "[autostart] {cosa} (code {codice})"),
    "progress.files": ("{fatti}/{totale} file", "{fatti}/{totale} files"),
    "progress.done": ("{files} file   {size} copiati in {tempo}",
                      "{files} files   {size} copied in {tempo}"),
    "summary": ("copiati {copiati} file ({mb} MB), invariati {invariati}, "
                "in __deleted {cestinati}, errori {errori}, in {secondi}s",
                "copied {copiati} files ({mb} MB), unchanged {invariati}, "
                "to __deleted {cestinati}, errors {errori}, in {secondi}s"),
}


# --------------------------------------------------------------------------

def set_language(codice: str) -> str:
    """`it`, `en`, oppure `auto` per seguire il sistema."""
    global _lingua
    if codice == "auto":
        codice = system_language()
    _lingua = codice if codice in LINGUE else "it"
    return _lingua


def get_language() -> str:
    return _lingua


def system_language() -> str:
    for variabile in ("LANG", "LANGUAGE", "LC_ALL"):
        valore = os.environ.get(variabile)
        if valore:
            return "it" if valore.lower().startswith("it") else "en"
    try:
        corrente = locale.getlocale()[0] or ""
    except ValueError:
        corrente = ""
    if not corrente:
        try:
            corrente = locale.getdefaultlocale()[0] or ""
        except Exception:
            corrente = ""
    return "it" if corrente.lower().startswith(("it", "italian")) else "en"


def t(testo: str) -> str:
    """Traduce una frase dell'interfaccia. Se manca, resta l'originale."""
    if _lingua == "it":
        return testo
    return UI.get(testo, testo)


def tf(chiave: str, **valori) -> str:
    """Compone un messaggio del motore nella lingua corrente."""
    modello = MESSAGGI.get(chiave)
    if modello is None:
        return chiave
    testo = modello[0] if _lingua == "it" else modello[1]
    try:
        return testo.format(**valori)
    except (KeyError, IndexError):
        return testo


def mancanti() -> list[str]:
    """Frasi dell'interfaccia senza traduzione inglese: serve ai test."""
    return [chiave for chiave, valore in UI.items() if not valore]
