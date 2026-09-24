#!/usr/bin/env python3
"""Traduzione dell'interfaccia e dei messaggi.\n\nLa lingua di partenza e' l'italiano: le chiavi del vocabolario sono le frasi\nitaliane cosi' come stanno nel codice. Cosi' non serve inventare sigle, e una\nfrase senza traduzione resta leggibile invece di diventare `ui.btn.save.42`.\n\n    from i18n import t, tf, set_language\n\n    t("Salva impostazioni")                  -> "Save settings"\n    tf("copiati {n} file", n=12)             -> "copied 12 files"\n\n`set_language("auto")` segue la lingua del sistema.\n"""
from __future__ import annotations

import locale
import os

LINGUE = ("it", "en")
_lingua = "it"


# --------------------------------------------------------------------------
# interfaccia
# --------------------------------------------------------------------------
UI = {
    'Piani di questo PC': 'Plans on this PC',
    "Un piano per disco: cosa mandare e cosa prendere. Legali al numero di serie, cosi' ogni disco fa solo il suo.": 'One plan per disk: what to send and what to fetch. Bind them to the serial number so each disk only does its own.',
    '+  Nuovo piano': '+  New plan',
    'Togli questo piano': 'Remove this plan',
    'Vuoto = hostname. È il nome della cartella creata sulla chiavetta. Vale per tutti i piani.': "Empty = hostname. It's the name of the folder created on the drive. Shared by all plans.",
    'Elimina tutti i piani': 'Delete all plans',
    'tutte le chiavette rimovibili': 'all removable drives',
    'Piano ': 'Plan ',
    'Nuovo piano: scegli le cartelle e premi Salva': 'New plan: pick the folders and press Save',
    'Togliere ': 'Remove ',
    'Piano tolto: premi Salva per confermare': 'Plan removed: press Save to confirm',
    'Windows: chiave Run del registro utente, senza privilegi di amministratore.  macOS: LaunchAgent.': 'Windows: Run key in the user registry, no admin rights needed.  macOS: LaunchAgent.',
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
    "Dimentica": "Forget",
    "Non segnalare piu' questi dischi. Se li ricolleghi, tornano.":
        "Stop flagging these disks. Plug them in again and they come back.",
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
    "non riuscito": "failed",
    "Operazione fallita (codice ": "Operation failed (code ",

    # --- scelta cartelle ---
    "(tutta la chiavetta)": "(whole drive)",
    "Cartella dentro ": "Folder inside ",
    "Cartella del PC da spedire sulla chiavetta": "PC folder to send to the drive",
    "Dove far atterrare la roba presa dalla chiavetta":
        "Where to drop what is taken from the drive",
    "Cartella dei backup": "Backup folder",
    "File di impostazioni da importare": "Settings file to import",
    "Nome cartella di destinazione": "Destination folder name",
    # --- versioni, ripristino, avvisi, collegamenti ---
    "Tieni la versione precedente dei file sovrascritti":
        "Keep the previous version of overwritten files",
    "Se un file si rovina sul PC, la copia buona non viene persa: finisce in "
    "__versions. Occupa spazio.":
        "If a file gets damaged on the PC, the good copy is not lost: it goes to "
        "__versions. It takes up space.",
    "Copia in secondo piano, senza rallentare il PC":
        "Copy in the background, without slowing the PC down",
    "Avvisami se un giro finisce con errori": "Tell me when a run ends with errors",
    "Collegamenti": "Shortcuts",
    "Nel menu Start e sul desktop, con l'icona dell'app e senza finestra nera. Dal "
    "sorgente funzionano anche dove Windows blocca l'eseguibile non firmato.":
        "In the Start menu and on the desktop, with the app icon and no black window. "
        "From source they work even where Windows blocks the unsigned executable.",
    "Crea collegamenti": "Create shortcuts",
    "Collegamento nel menu Start": "Start menu shortcut",
    "Collegamento sul desktop": "Desktop shortcut",
    "Collegamento creato ": "Shortcut created ",
    "nel menu Start": "in the Start menu",
    "sul desktop": "on the desktop",
    "Collegamenti creati: ": "Shortcuts created: ",
    "Collegamenti non creati: guarda il log": "Shortcuts not created: check the log",
    "Doppio clic su un giro per vederne i dettagli.":
        "Double-click a run to see its details.",
    "Dettagli del giro": "Run details",
    "Ripristina da una cartella...": "Restore from a folder...",
    "Seleziona prima un giro nella tabella": "Pick a run in the table first",
    "Cartella in cui cercare file da ripristinare": "Folder to search for files to restore",
    "Niente da ripristinare in quella cartella": "Nothing to restore in that folder",
    "Niente da segnalare: in questo giro non ci sono stati errori, ne' file messi "
    "da parte.":
        "Nothing to report: no errors in this run, and no files set aside.",
    "Tipo": "Type",
    "File": "File",
    "Dettaglio": "Detail",
    "Errore": "Error",
    "Versione salvata": "Saved version",
    "copia diversa dall'originale": "copy differs from the original",
    "Ripristina selezionati": "Restore selected",
    "Rimette i file dov'erano. Se al loro posto c'e' gia' qualcosa, quello va in "
    "__versions: non si perde niente.":
        "Puts the files back where they were. If something is already there, it goes "
        "to __versions: nothing is lost.",
    "Chiudi": "Close",
    # --- freno, verifica, uscita, disinstalla, configurazione guidata ---
    "Fermati se un giro sta per sovrascrivere molti file":
        "Stop if a run is about to overwrite many files",
    "% dei file gia' copiati. Ransomware, o un checkout su un ramo vecchio: meglio "
    "chiedere che propagare.":
        "% of the files already copied. Ransomware, or a checkout of an old branch: "
        "better to ask than to spread it.",
    "La soglia del freno dev'essere un numero": "The brake threshold must be a number",
    "Troppe modifiche tutte insieme": "Too many changes at once",
    "USB Backup: mi sono fermato": "USB Backup: I stopped",
    "USB Backup: disco staccato": "USB Backup: disk unplugged",
    "Il disco non e' piu' collegato": "The disk is no longer connected",
    "Verifica completa": "Full check",
    "Ricontrolla ogni file del backup di questo disco contro l'originale. Lento: da "
    "fare ogni tanto.":
        "Rechecks every file of this disk's backup against the original. Slow: do it "
        "now and then.",
    "verifica in corso…": "checking…",
    "Niente da verificare per questo disco": "Nothing to check for this disk",
    "Sta copiando": "Copying in progress",
    "C'e' un giro in corso. Grazie alla copia atomica uscire adesso non rovina niente, "
    "ma il giro resta a meta'.":
        "A run is in progress. Thanks to atomic copying, quitting now breaks nothing, "
        "but the run stays half done.",
    "Esci appena finisce": "Quit when it's done",
    "Esci subito": "Quit now",
    "Annulla": "Cancel",
    "Disinstalla": "Uninstall",
    "Disinstalla...": "Uninstall...",
    "Toglie avvio automatico e collegamenti, poi chiude l'app. I backup, il piano del "
    "PC e le copie sui dischi non vengono toccati.":
        "Removes autostart and shortcuts, then closes the app. Backups, the PC plan and "
        "the copies on disks are not touched.",
    "Tolgo avvio automatico e collegamenti, poi chiudo l'app.\n\nI backup, il piano "
    "del PC e le copie sui dischi restano dove sono.":
        "I'll remove autostart and shortcuts, then close the app.\n\nBackups, the PC "
        "plan and the copies on disks stay where they are.",
    "Togli anche le impostazioni (config.json)": "Also remove the settings (config.json)",
    "Configurazione guidata": "Guided setup",
    "Tre domande - quale disco, cosa mandare, cosa prendere - e il piano e' fatto. "
    "Utile su un PC nuovo.":
        "Three questions - which disk, what to send, what to fetch - and the plan is "
        "ready. Handy on a new PC.",
    "Avvia la configurazione guidata": "Start the guided setup",
    "Quale disco?": "Which disk?",
    "Scegli la chiavetta o il disco esterno da usare. Il piano verra' legato al suo "
    "numero di serie: non partira' su nessun altro disco.":
        "Pick the stick or external disk to use. The plan will be bound to its serial "
        "number: it won't run on any other disk.",
    "Cosa mandare sul disco?": "What to send to the disk?",
    "Le cartelle del PC da copiare sul disco, in backup/<nome del PC>. Puoi lasciarlo "
    "vuoto.":
        "The PC folders to copy to the disk, in backup/<PC name>. You can leave it empty.",
    "Cosa prendere dal disco?": "What to fetch from the disk?",
    "Le cartelle del disco da copiare sul PC, in ~/Backup/<nome del disco>. Puoi "
    "lasciarlo vuoto.":
        "The disk folders to copy to the PC, in ~/Backup/<disk name>. You can leave it "
        "empty.",
    "Tutto pronto": "All set",
    "Controlla e premi Fine. Si cambia tutto anche dopo, nella scheda Questo PC.":
        "Check and press Finish. Everything can be changed later, in the This PC tab.",
    "Nessun disco collegato: collegalo e premi Aggiorna":
        "No disk connected: plug it in and press Refresh",
    "Salta": "Skip",
    "Indietro": "Back",
    "Avanti": "Next",
    "Fine": "Finish",
    "Disco": "Disk",
    "numero di serie": "serial number",
    "Manda": "Send",
    "Prendi": "Fetch",
    "verifica": "check",
    "avvio automatico": "autostart",
    "Avvia USB Backup all'accensione del computer": "Start USB Backup when the computer starts",
    "Acceso di default. Parte direttamente nella tray, senza aprire la finestra.":
        "On by default. It starts straight into the tray, without opening the window.",
    "Ripristino": "Restore",
    "USB Backup: errori nell'ultimo giro": "USB Backup: errors in the last run",
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
    "err.mkdir": ("    [errore] mkdir {path}: {err}", "    [error] mkdir {path}: {err}"),
    "err.trash": ("    [errore] spostamento in __deleted da {path}: {err}",
                  "    [error] moving to __deleted from {path}: {err}"),
    "err.trash.one": ("    [errore] spostamento in __deleted di {path}: {err}",
                      "    [error] moving {path} to __deleted: {err}"),
    "err.copy": ("    [errore] copia {path}: {err}", "    [error] copy {path}: {err}"),
    "err.verify": ("    [errore] verifica {path}: {err}", "    [error] check {path}: {err}"),
    "err.json.invalid": ("  [errore] {path} non e' JSON valido: {err}",
                         "  [error] {path} is not valid JSON: {err}"),
    "err.json.notobj": ("  [errore] {path} deve contenere un oggetto JSON",
                        "  [error] {path} must contain a JSON object"),
    "err.history": ("[errore] storico non salvato: {err}", "[error] history not saved: {err}"),
    "err.syncstate": ("    [errore] stato di sincronizzazione non salvato: {err}",
                      "    [error] sync state not saved: {err}"),
    "err.sync": ("  [errore] sync {path}: {err}", "  [error] sync {path}: {err}"),
    "err.plan": ("[errore] piano {piano} fallito: {err}", "[error] plan {piano} failed: {err}"),
    "err.backup": ("[errore] backup {root} fallito: {err}",
                   "[error] backup of {root} failed: {err}"),
    "job": ("  {src} -> {dst}", "  {src} -> {dst}"),
    "plan.empty": ("  [attenzione] {path} non elenca nessuna cartella",
                   "  [warning] {path} lists no folders"),
    "skip.outside": ("  [salto] '{path}' esce dalla chiavetta",
                     "  [skip] '{path}' points outside the drive"),
    "skip.missing.stick": ("  [salto] cartella assente sulla chiavetta: {path}",
                           "  [skip] folder missing on the drive: {path}"),
    "skip.missing.pc": ("  [salto] cartella del PC assente: {path}",
                        "  [skip] PC folder missing: {path}"),
    "skip.missing.local": ("  [salto] cartella locale assente: {path}",
                           "  [skip] local folder missing: {path}"),
    "skip.already.stick": ("  [salto] {path} e' gia' sulla chiavetta",
                           "  [skip] {path} is already on the drive"),
    "skip.git": ("  [salto] {path}: git sta lavorando ({lock} presente)",
                 "  [skip] {path}: git is busy ({lock} present)"),
    "sync.start": ("[sync] {root}", "[sync] {root}"),
    "sync.pair": ("  {local}  <->  {remote}", "  {local}  <->  {remote}"),
    "sync.end": ("[fine sync] {pc}: {summary}", "[sync done] {pc}: {summary}"),
    "sync.summary": ("presi {presi}, mandati {mandati} ({mb} MB), spostati in __deleted "
                     "{cestinati}, conflitti {conflitti}, errori {errori}, in {secondi}s",
                     "fetched {presi}, sent {mandati} ({mb} MB), moved to __deleted "
                     "{cestinati}, conflicts {conflitti}, errors {errori}, in {secondi}s"),
    "sync.massdelete": ("  [attenzione] {n} sparizioni su {totale} file: sembra un errore, "
                        "non tocco niente. Controlla i percorsi.",
                        "  [warning] {n} of {totale} files gone: looks like a mistake, "
                        "touching nothing. Check the paths."),
    "sync.conflict": ("    [conflitto] {testo}", "    [conflict] {testo}"),
    "sync.conflict.more": ("    [conflitto] ...e altri {n}", "    [conflict] ...and {n} more"),
    "sync.conflicts.summary": ("  [attenzione] {n} file toccati dalle due parti: ha vinto la "
                               "versione piu' recente (righe [conflitto] qui sopra)",
                               "  [warning] {n} files changed on both sides: the newest "
                               "version won ([conflict] lines above)"),
    "conf.deleted.here": ("{rel}: cancellato qui ma modificato altrove, lo riprendo",
                          "{rel}: deleted here but changed elsewhere, taking it back"),
    "conf.deleted.there": ("{rel}: cancellato altrove ma modificato qui, lo rimando",
                           "{rel}: deleted elsewhere but changed here, sending it again"),
    "conf.both": ("{rel}: tenute tutte e due le versioni", "{rel}: kept both versions"),
    "conf.local": ("{rel}: vince la versione locale (piu' recente)",
                   "{rel}: the local version wins (newer)"),
    "conf.remote": ("{rel}: vince la versione sulla chiavetta (piu' recente)",
                    "{rel}: the drive's version wins (newer)"),
    "stale.item": ("{nome} da {giorni} giorni", "{nome} for {giorni} days"),
    "restored": ("[ripristinato] {path}", "[restored] {path}"),
    "shortcut.made": ("[collegamento] {path}", "[shortcut] {path}"),
    "shortcuts.only.windows": ("[collegamenti] per ora solo su Windows",
                               "[shortcuts] Windows only for now"),
    "err.shortcut": ("[errore] collegamenti: {err}", "[error] shortcuts: {err}"),
    "errors.notice": ("{n} errori durante il backup di {volume}. Apri l'app per i dettagli.",
                      "{n} errors while backing up {volume}. Open the app for details."),
    "errors.tooltip": ("USB Backup - {n} errori da guardare", "USB Backup - {n} errors to look at"),
    "details.summary": ("Errori: {errori}.  File recuperabili: {recuperabili}.",
                        "Errors: {errori}.  Recoverable files: {recuperabili}."),
    "details.lost": ("(altri {n} eventi non registrati: il giro ne ha avuti troppi)",
                     "({n} more events not recorded: the run had too many)"),
    "restore.done": ("Ripristinati {n} file.", "Restored {n} files."),
    "err.autostart": ("[errore] avvio automatico: {err}", "[error] autostart: {err}"),
    "err.read": ("    [errore] cartella illeggibile, saltata senza toccare la copia: {path}",
                 "    [error] unreadable folder, skipped without touching the copy: {path}"),
    "disk.gone": ("  [errore] il disco e' stato staccato: mi fermo qui dopo {n} file. "
                  "Ricollegalo e riprende da dove era.",
                  "  [error] the disk was unplugged: stopping here after {n} files. "
                  "Plug it back in and it picks up where it left off."),
    "brake": ("  [attenzione] stavano per essere sovrascritti {n} file su {totale} in {path}: "
              "mi fermo e ti chiedo prima di procedere",
              "  [warning] {n} of {totale} files in {path} were about to be overwritten: "
              "stopping to ask you first"),
    "verify.full.start": ("[verifica completa] {n} file da ricontrollare su {root}",
                          "[full check] {n} files to recheck on {root}"),
    "verify.full.end": ("[fine verifica] identici {ok}, diversi {diversi}, mancanti {mancanti}, "
                        "errori {errori}",
                        "[check done] identical {ok}, different {diversi}, missing {mancanti}, "
                        "errors {errori}"),
    "verify.full.nothing": ("[verifica completa] nessun piano si applica a {root}",
                            "[full check] no plan applies to {root}"),
    "uninstalled": ("[disinstallato] {cosa}", "[uninstalled] {cosa}"),
    "brake.question": ("Nel giro su {volume} stavano per essere sovrascritti {n} file su "
                       "{totale}. Puo' essere un ransomware, o un checkout su un ramo "
                       "vecchio. Mi sono fermato prima di toccare il backup.\n\n"
                       "Procedo lo stesso?",
                       "In the run on {volume}, {n} of {totale} files were about to be "
                       "overwritten. It may be ransomware, or a checkout of an old "
                       "branch. I stopped before touching the backup.\n\nGo ahead anyway?"),
    "disk.gone.notice": ("{volume} e' stato staccato durante il backup. Ricollegalo per "
                         "completarlo: riprende da dove era.",
                         "{volume} was unplugged during the backup. Plug it back in to "
                         "finish: it picks up where it left off."),
    "verify.all.ok": ("Tutto identico: {n} file verificati", "All identical: {n} files checked"),
    "uninstall.done": ("Fatto: {n} elementi tolti. Per togliere del tutto il programma "
                       "cancella la cartella:\n{cartella}",
                       "Done: {n} items removed. To remove the program entirely, delete "
                       "the folder:\n{cartella}"),
    "err.watchmemory": ("[errore] non riesco a ricordare la sorveglianza: {err}",
                        "[error] cannot remember the watch setting: {err}"),
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
