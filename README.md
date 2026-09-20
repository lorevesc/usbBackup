# USB Backup Watcher

Sorveglia i volumi USB su **Windows e macOS**. A ogni chiavetta collegata esegue
fino a tre piani di copia, in base a quali file `backup.json` trova.

Solo libreria standard di Python 3.9+. Nessuna dipendenza da installare.

| Piano | Il `backup.json` sta in | Cosa elenca | Destinazione |
|---|---|---|---|
| 1. chiavetta -> PC | root della chiavetta | cartelle della chiavetta | `~/Backup/<nome-chiavetta>/<cartella>` |
| 2. PC -> chiavetta (`push`) | `~/Backup/backup.json` | cartelle del PC | `<chiavetta>/backup/<nome-PC>/<cartella>` |
| 3. chiavetta -> PC (`pull`) | `~/Backup/backup.json` | cartelle della chiavetta | `~/Backup/<nome-PC>/<cartella>` |

I piani sono indipendenti: puoi usarne uno, due o tutti e tre insieme. `<nome-PC>`
e' l'hostname della macchina (sovrascrivibile con `pc_name`), quindi due computer
diversi scrivono in cartelle diverse sulla stessa chiavetta.

## Applicazione

```bash
pip install PySide6
python usb_backup_qt.py
```

Windows: doppio clic su `start_gui.cmd` (niente finestra console).
macOS: `chmod +x start_gui.command`, poi doppio clic.

PySide6 serve solo all'interfaccia: il motore ([usb_backup.py](usb_backup.py)) e
l'avvio automatico restano a sola libreria standard.

Tre schede, tutto senza aprire un JSON a mano:

- **Chiavette** - card dei volumi collegati con etichetta, percorso e stato
  (rimovibile o disco fisso, se ha gia' un `backup.json`, se il piano del PC lo prende).
  Selezionane uno e componi il suo piano: nome della cartella di destinazione, cartelle
  scelte col dialogo nativo (parte dalla chiavetta e rifiuta percorsi fuori da essa),
  nome di destinazione modificabile riga per riga, esclusioni, `delete_extra`.
  "Salva sulla chiavetta" scrive il `backup.json` nella sua root.
- **Questo PC** - nome del PC, filtro `only_volumes`, sezione **Push** (cartelle del PC
  da spedire sulla chiavetta) e **Pull** (cartelle della chiavetta da prendere).
  "Salva piano del PC" scrive `~/Backup/backup.json`. Sotto ogni titolo c'e' la
  destinazione effettiva, aggiornata mentre scrivi.
- **Impostazioni** - `dest_root`, file di log, intervallo di polling, dischi fissi,
  notifiche, esclusioni globali, e i pulsanti per installare o togliere l'avvio
  automatico al login.

In fondo alla finestra: **Backup adesso** sul volume selezionato, l'interruttore
**sorveglianza** nella barra laterale (fa partire il watcher dentro l'app) e il log in
diretta, ridimensionabile con la maniglia e riducibile con "Nascondi".

L'icona ([appicon.py](appicon.py)) e' disegnata a vettori: `python appicon.py --preview`
rigenera `assets/icon.ico`, `assets/icon.png` e un provino con tutte le misure.

C'e' anche [usb_backup_gui_tk.py](usb_backup_gui_tk.py), la vecchia versione in Tkinter:
piu' brutta, ma senza dipendenze, se su una macchina non vuoi installare PySide6.

## Compilare l'eseguibile

```bash
pip install pyinstaller
python build.py
```

Produce `dist/USB Backup.exe` su Windows (file unico, niente finestra console,
icona inclusa) e `dist/USB Backup.app` su macOS. Python e PySide6 non servono
sulla macchina che lo usa.

Nel pacchetto **non finisce nessuna configurazione**: lo script cancella dalla
cartella `dist` eventuali `config.json`, `backup.json` e `scan-totals.json`.
L'eseguibile parte con i valori di default e scrive il suo `config.json`
**accanto a se stesso** al primo salvataggio, quindi e' portatile: lo copi in
una cartella (o sulla chiavetta stessa) e si porta dietro le sue impostazioni.

L'avvio automatico al login, se lo attivi dall'eseguibile, registra l'eseguibile
stesso invece di Python: riapre l'app, che riprende a sorvegliare se
l'interruttore era acceso.

## Avvio da riga di comando

```bash
python usb_backup.py --list
```

Mostra nome PC, destinazione, piano PC caricato e i volumi visti adesso.

```bash
python usb_backup.py --once
```

Lavora subito sui volumi gia' collegati, poi esce. Utile per provare.

```bash
python usb_backup.py --watch
```

Resta in ascolto e lavora a ogni nuovo volume collegato (default se non passi
niente). I volumi gia' montati all'avvio vengono ignorati: per quelli c'e' `--once`.

## Avvio automatico al login

```bash
python usb_backup.py --install
```

- **Windows**: crea l'attivita' pianificata `USB Backup Watcher` (trigger ONLOGON,
  girata con `pythonw.exe`, quindi senza finestra console).
- **macOS**: scrive `~/Library/LaunchAgents/com.usbbackup.watcher.plist` con
  `RunAtLoad` + `KeepAlive` e lo carica con `launchctl`.

Per rimuoverlo: `python usb_backup.py --uninstall`.

Su macOS la prima copia dentro Documenti/Scrivania/Download chiede il permesso
"accesso a file e cartelle": va concesso a Python (o al Terminale, se lo lanci da li').

---

## Piano 1 - `backup.json` sulla chiavetta

Va nella **root** della chiavetta. Esempio: [`backup.example.json`](backup.example.json)

```json
{
  "name": "chiavetta-lavoro",
  "folders": [
    "Documenti",
    "Progetti/2026",
    { "path": "foto", "as": "foto-chiavetta" }
  ],
  "exclude": ["*.tmp", "~$*", "node_modules"],
  "delete_extra": false
}
```

| Campo | Obbligatorio | Significato |
|---|---|---|
| `folders` | si' | Cartelle da copiare, relative alla root della chiavetta. Stringa, oppure `{"path": ..., "as": ...}` per rinominare la destinazione. `"."` copia tutta la chiavetta (in `root/`). |
| `name` | no | Nome della cartella di destinazione. Default: etichetta del volume (Windows: label o serial; macOS: nome in `/Volumes`). |
| `exclude` | no | Pattern glob su nome o su percorso relativo, sommati agli esclusi globali. |
| `delete_extra` | no | `true` = mirror stretto: cancella dalla destinazione cio' che non c'e' piu' sulla chiavetta. Default `false`. |
| `dest_root` | no | Destinazione diversa solo per questa chiavetta. |

---

## Piani 2 e 3 - `backup.json` nella cartella `~/Backup` del PC

Esempio: [`pc-backup.example.json`](pc-backup.example.json)

```json
{
  "pc_name": null,
  "only_volumes": ["chiavetta-lavoro", "KINGSTON*"],

  "push": {
    "target_subdir": "backup",
    "folders": ["~/Documents/Progetti", { "path": "C:/WorkArea/email_manager", "as": "email-manager" }],
    "exclude": ["*.tmp", "node_modules", ".git", "__pycache__"],
    "delete_extra": false
  },

  "pull": {
    "folders": ["Documenti", { "path": "foto", "as": "foto-chiavetta" }],
    "exclude": ["*.tmp"],
    "delete_extra": false
  }
}
```

| Campo | Significato |
|---|---|
| `pc_name` | Nome cartella per questa macchina. `null` o assente = hostname di sistema. |
| `only_volumes` | Pattern glob su etichetta o percorso del volume. **Se assente, il piano vale per tutti i volumi rimovibili** e mai per i dischi fissi. Mettilo se non vuoi che il push parta su qualsiasi chiavetta infilata. |
| `push.folders` | Cartelle **del PC**, percorsi assoluti (`~` supportata). Finiscono in `<chiavetta>/<target_subdir>/<nome-PC>/<cartella>`. |
| `push.target_subdir` | Cartella radice sulla chiavetta. Default `backup`. |
| `pull.folders` | Cartelle **della chiavetta**, relative alla sua root. Finiscono in `~/Backup/<nome-PC>/<cartella>`. |
| `exclude`, `delete_extra` | Come nel piano 1, per sezione. |

Il `pull` salta automaticamente la cartella scritta dal `push`: i dati spediti
sulla chiavetta non tornano indietro al giro successivo.

---

## `config.json` (impostazioni del PC)

Sta accanto allo script, vale per tutte le chiavette.

| Chiave | Default | Significato |
|---|---|---|
| `dest_root` | `~/Backup` | Radice dei backup sul PC, e posto dove viene cercato il `backup.json` del PC |
| `poll_seconds` | `3` | Intervallo di controllo dei volumi |
| `include_fixed_drives` | `true` | Considera anche i dischi "fissi" non di sistema: molti SSD USB su Windows si presentano come DRIVE_FIXED. Per i piani del PC restano esclusi finche' non li elenchi in `only_volumes` |
| `notify` | `true` | Notifica di sistema a fine lavoro (toast su Windows, Centro Notifiche su macOS) |
| `log_file` | `~/Backup/_logs/usb-backup.log` | Log cumulativo; `null` per disattivarlo |
| `default_exclude` | vedi file | Esclusioni valide ovunque (`System Volume Information`, `.Trashes`, `Thumbs.db`, ...) |

## Portare il codice fra casa e ufficio (staging + merge a mano)

Ogni PC scrive **solo nella propria** cartella sulla chiavetta e legge quella dell'altro
dentro una cartella di staging: il progetto vero non viene mai toccato in automatico,
il merge lo fai tu con il tuo strumento di confronto.

PC di casa (`pc-casa`), in `~/Backup/backup.json`:

| Sezione | Cosa | Dove |
|---|---|---|
| Push | `C:/WorkArea/progetto` | `<chiavetta>/backup/pc-casa/progetto` |
| Pull | `backup/pc-ufficio/progetto` | destinazione `C:/incoming/da-ufficio` |

PC dell'ufficio (`pc-ufficio`), stessa struttura a specchio:

| Sezione | Cosa | Dove |
|---|---|---|
| Push | `D:/dev/repo-lavoro` | `<chiavetta>/backup/pc-ufficio/progetto` |
| Pull | `backup/pc-casa/progetto` | destinazione `D:/incoming/da-casa` |

Le due cartelle locali non devono avere lo stesso percorso: in comune c'e' solo la
chiavetta. Conviene mettere `delete_extra` sul Pull, cosi' lo staging e' la fotografia
esatta dell'ultimo giro (quello che sparisce finisce comunque in `__deleted`).

Per il merge: `git diff --no-index C:/incoming/da-ufficio/progetto C:/WorkArea/progetto`,
oppure un confronto cartelle con WinMerge, Beyond Compare o il tuo IDE.

## Niente viene cancellato: `__deleted`

Quando una copia deve perdere un file (mirror con `delete_extra`, o una cancellazione
propagata dalla sincronizzazione), il file non viene rimosso: viene **spostato** in
`__deleted/` dentro la cartella di destinazione, con la stessa struttura di sottocartelle.
Se ne esiste gia' uno con quel nome, al nuovo viene aggiunta data e ora. Per liberare
spazio si svuota `__deleted` a mano, quando ti va.

## Sincronizzazione a due vie (opzionale)

Oltre a push/pull c'e' una sezione `sync` nel `backup.json` del PC, per chi vuole che
le due cartelle si allineino da sole invece di passare dallo staging:

```json
{
  "sync": [
    { "local": "C:/WorkArea/progetto", "on_stick": "sync/progetto",
      "exclude": ["*.log"], "conflict": "newest" }
  ]
}
```

Confronta i due lati con lo stato dell'ultimo giro (uno per macchina, in
`.usbsync/` sulla chiavetta): cosi' distingue "modificato qui" da "cancellato la'".
Se un file e' stato toccato da tutte e due le parti vince il piu' recente
(`"conflict": "keep_both"` tiene invece tutte e due le versioni). Una modifica batte
sempre una cancellazione. Se le sparizioni sono piu' di un quarto dei file tracciati
non tocca niente e lo scrive nel log: quasi sempre significa percorso sbagliato o
disco montato a meta'. Salta la coppia se trova `.git/index.lock`, cioe' se git sta
lavorando in quel momento.

## Come copia

Mirror incrementale: un file viene ricopiato solo se ha **dimensione diversa** o
**data di modifica diversa** di oltre 2 secondi (tolleranza per FAT32). Il
secondo inserimento della stessa chiavetta e' quindi veloce e non duplica niente.
Date e metadati preservati (`copy2`). Il `backup.json` non viene mai copiato.

In ogni cartella di destinazione viene scritto `_last_backup.txt` con data e
riepilogo dell'ultima esecuzione.

Errori su singoli file (permessi, file aperto, chiavetta staccata a meta')
vengono loggati e contati senza fermare il resto del backup.
