# USB Backup

Copia automatica fra il PC e chiavette o dischi esterni, su **Windows e macOS**.
Colleghi il disco e parte da solo: prende dal disco quello che deve prendere,
ci mette sopra quello che deve metterci, e non cancella mai niente.

Interfaccia in **italiano e inglese**.

## Installazione

**Eseguibile** (Windows): `dist/USB Backup.exe`, file unico, niente da
installare. Si compila con `python build.py`, vedi [piu' sotto](#compilare-leseguibile).

**Dal sorgente**: Python 3.9 o successivo.

```bash
pip install PySide6
python usb_backup_qt.py
```

PySide6 serve solo all'interfaccia. Il motore ([usb_backup.py](usb_backup.py))
usa solo la libreria standard e funziona anche da riga di comando.

## Cosa copia

Tre piani, indipendenti: puoi usarne uno, due o tutti e tre.

| Piano | Descritto in | Da | A |
|---|---|---|---|
| chiavetta -> PC | `backup.json` nella root del disco | cartelle del disco | `~/Backup/<nome del disco>/<cartella>` |
| **push** PC -> disco | `~/Backup/backup.json` | cartelle del PC | `<disco>/backup/<nome del PC>/<cartella>` |
| **pull** disco -> PC | `~/Backup/backup.json` | cartelle del disco | `~/Backup/<nome del disco>/<cartella>` |

`<nome del PC>` e' l'hostname (modificabile): due computer scrivono in cartelle
diverse sullo stesso disco. Il pull puo' anche atterrare in una cartella
qualsiasi, per esempio una di staging.

C'e' poi una **sincronizzazione a due vie**, facoltativa, descritta
[in fondo](#sincronizzazione-a-due-vie).

## L'applicazione

Quattro schede:

- **Chiavette** - i volumi collegati, con etichetta, numero di serie e stato.
  Selezionato un disco, componi il piano che vive sul disco stesso.
- **Questo PC** - il piano del PC: push, pull, a quali dischi si applica.
  Il piano si puo' legare al numero di serie di un disco preciso.
- **Storico** - gli ultimi 200 giri: quando, quale disco, quanti file, errori.
- **Impostazioni** - cartella dei backup, lingua, esclusioni, verifica,
  avvio automatico, esporta/importa la configurazione.

In fondo il log in diretta, con la barra di avanzamento; nella barra laterale
l'interruttore della sorveglianza, che viene ricordato fra un'apertura e l'altra.
Chiudendo la finestra il programma resta nella tray vicino all'orologio: doppio
clic per riaprirlo, tasto destro per il menu, *Esci* per chiuderlo davvero.

Se un disco visto in passato non viene collegato da piu' di una settimana, in
cima alla scheda Chiavette compare un avviso. Un disco che non usi piu' si
toglie con *Dimentica*; se lo ricolleghi, torna a essere seguito.

## Quando lavora

In due soli momenti: quando accendi la sorveglianza, sui dischi gia' collegati,
e quando colleghi un disco. Nient'altro.

Fra un collegamento e l'altro non legge niente: su Windows si fa avvisare dal
sistema (`WM_DEVICECHANGE`), su macOS guarda la cartella `/Volumes`. Solo il
watcher da riga di comando controlla l'elenco delle unita' ogni pochi secondi,
e anche quello non tocca i dischi: legge una tabella del sistema.

Un disco che sparisce per un attimo (il risparmio energetico USB lo fa) non fa
ripartire il giro: deve mancare per tre controlli di fila, e dopo un giro lo
stesso disco riposa 15 minuti.

## Sicurezza dei dati

**Niente viene cancellato.** Quello che sparisce da un lato viene spostato in
`__deleted/` dentro la destinazione, con la stessa struttura di cartelle. Si
svuota a mano, quando serve spazio.

**Copia atomica.** Ogni file viene scritto su `nome.usbpart` e rinominato solo a
copia finita. Se stacchi il disco a meta', la versione precedente resta intatta
e il file viene ricopiato al giro dopo. Senza, resterebbe un file troncato con
data e dimensione da file nuovo, che nessun confronto riconoscerebbe piu'.

**Spazio.** Prima di copiare controlla lo spazio libero; se la destinazione e'
vuota e non ci sta, non comincia nemmeno. Durante la copia lo spazio viene
*prenotato* file per file e si ferma prima di riempire il disco, lasciando 256 MB.

**Verifica a campione.** Dopo ogni giro ricalcola lo sha256 di una parte dei
file copiati (1% di default) e la confronta con l'originale: e' il solo modo di
accorgersi dei guasti silenziosi, che per data e dimensione sembrano a posto.

**Vincolo al disco.** Il piano del PC si puo' legare al numero di serie del
volume: la lettera di unita' cambia e l'etichetta la cambia chiunque.

**Percorsi lunghi.** I percorsi oltre i 260 caratteri - normali in un progetto
con `node_modules` - funzionano anche sui PC dove Windows non ha attivato il
supporto, grazie al prefisso dei percorsi estesi.

**Ora legale.** FAT32 ed exFAT salvano le date in ora locale: al cambio dell'ora
tutti i file sembrerebbero modificati di un'ora esatta, e partirebbe una
ricopia completa. Uno scarto di un'ora esatta a parita' di dimensione viene
riconosciuto come lo stesso file (`dst_tolerance`).

**Ferma.** Un giro si interrompe quando vuoi: finisce il file corrente e si
ferma. Al giro dopo riprende da li'.

## Velocita'

Il confronto usa `os.scandir`, che su Windows porta con se' dimensione e data
di ogni voce, e legge la cartella di destinazione una volta sola invece che
file per file: su 8.000 file gia' sincronizzati, **286 ms contro 2.280**.

Le copie vanno in parallelo (`copy_threads`, 8 di default): su file piccoli si
passa da circa 640 a 930 file al secondo.

I totali del giro precedente fanno da stima per la barra di avanzamento, cosi'
l'albero si percorre una volta sola.

## Portare il codice fra casa e ufficio

Ogni PC scrive **solo nella propria** cartella sul disco e legge quella
dell'altro in una cartella di staging: il progetto vero non viene mai toccato
in automatico, il merge lo fai tu.

| | PC di casa | PC dell'ufficio |
|---|---|---|
| Push | `C:/WorkArea/progetto` -> `backup/pc-casa/progetto` | `D:/dev/repo` -> `backup/pc-ufficio/progetto` |
| Pull | `backup/pc-ufficio/progetto` -> `C:/incoming/da-ufficio` | `backup/pc-casa/progetto` -> `D:/incoming/da-casa` |

I percorsi locali possono essere diversi: in comune c'e' solo il disco. Per il
merge: `git diff --no-index C:/incoming/da-ufficio/progetto C:/WorkArea/progetto`,
oppure WinMerge, Beyond Compare o il tuo IDE.

Per configurare il secondo PC in fretta: *Impostazioni* -> **Esporta sul
disco** su una macchina, **Importa da file** sull'altra. Passano le impostazioni
condivisibili e la struttura del piano; restano com'erano cartella dei backup,
file di log, nome del PC e vincoli ai dischi.

## File di configurazione

### `backup.json` sul disco

Nella root del disco. Esempio: [backup.example.json](backup.example.json).

| Campo | Significato |
|---|---|
| `folders` | Cartelle da copiare, relative alla root. Stringa, oppure `{"path": ..., "as": ...}` per rinominare la destinazione. `"as": "."` mette il contenuto direttamente nella destinazione. |
| `name` | Nome della cartella di destinazione. Default: etichetta del volume. |
| `exclude` | Pattern glob, sommati alle esclusioni globali. |
| `delete_extra` | `true`: quello che sparisce dal disco finisce in `__deleted` anche sul PC. |
| `dest_root` | Destinazione diversa solo per questo disco. |

### `~/Backup/backup.json` sul PC

Esempio: [pc-backup.example.json](pc-backup.example.json).

| Campo | Significato |
|---|---|
| `pc_name` | Nome di questa macchina. Assente = hostname. |
| `only_serials` | Numeri di serie dei dischi a cui applicare il piano. Se c'e', vale solo questo. |
| `only_volumes` | Pattern glob su etichetta o lettera. Assente = tutti i dischi rimovibili, mai quelli fissi. |
| `push.folders` | Cartelle del PC, percorsi assoluti (`~` ammessa). |
| `push.target_subdir` | Cartella radice sul disco. Default `backup`. |
| `push.use_pc_folder` | `false` per scrivere senza il livello `<nome del PC>`. |
| `pull.folders` | Cartelle del disco, relative alla root. |
| `pull.dest` | Dove farle atterrare. Default `~/Backup/<nome del disco>`. |
| `exclude`, `delete_extra` | Come sopra, per sezione. |

### `config.json`

Accanto al programma, scritto dall'applicazione. Non e' nel repository: il
modello con tutti i valori di default e' [config.example.json](config.example.json).

| Chiave | Default | Significato |
|---|---|---|
| `dest_root` | `~/Backup` | Radice dei backup sul PC; li' si cerca anche il piano del PC |
| `language` | `auto` | `it`, `en`, oppure `auto` per seguire il sistema |
| `copy_threads` | `8` | Copie in parallelo |
| `verify_percent` | `1` | Percentuale di file ricontrollati dopo la copia; `0` la spegne |
| `use_gitignore` | `false` | Salta quello che i `.gitignore` dei progetti escludono |
| `dst_tolerance` | `true` | Uno scarto di un'ora esatta non conta come modifica |
| `stale_days` | `7` | Dopo quanti giorni avvisare di un disco non collegato; `0` lo spegne |
| `include_fixed_drives` | `true` | Considera anche i dischi fissi non di sistema (molti SSD USB lo sono) |
| `notify` | `true` | Notifica di sistema a fine giro |
| `run_on_start` | `true` | Accendendo la sorveglianza, lavora subito sui dischi gia' collegati |
| `close_to_tray` | `true` | La X della finestra la manda nella tray invece di chiudere |
| `start_minimized` | `false` | All'avvio parte direttamente nella tray |
| `rescan_cooldown_minutes` | `15` | Riposo di un disco dopo un giro |
| `missing_polls_before_removed` | `3` | Assenze di fila prima di considerare un disco staccato |
| `poll_seconds` | `3` | Solo per il watcher da riga di comando |
| `heartbeat_minutes` | `0` | Solo riga di comando: riga "sono vivo" nel log; `0` la spegne |
| `log_file` | `~/Backup/_logs/usb-backup.log` | Log cumulativo; `null` lo spegne |
| `default_exclude` | vedi file | Esclusioni valide ovunque |

L'applicazione ci scrive anche `watch_enabled` (lo stato dell'interruttore) e
`stale_ignore` (i dischi dimenticati).

## Sincronizzazione a due vie

Per chi vuole che due cartelle si allineino da sole invece di passare dallo
staging. Nel piano del PC:

```json
{
  "sync": [
    { "local": "C:/WorkArea/progetto", "on_stick": "sync/progetto",
      "exclude": ["*.log"], "conflict": "newest" }
  ]
}
```

Confronta i due lati con lo stato dell'ultimo giro - uno per macchina, in
`.usbsync/` sul disco - e cosi' distingue "modificato qui" da "cancellato la'".
Se un file e' stato toccato da tutte e due le parti vince il piu' recente
(`"keep_both"` tiene entrambe le versioni); una modifica batte sempre una
cancellazione. Se sparisce piu' di un quarto dei file non tocca niente: quasi
sempre e' un percorso sbagliato. Salta la coppia se git sta lavorando
(`.git/index.lock`). Usa la stessa copia atomica del resto.

## Compilare l'eseguibile

```bash
pip install pyinstaller
python build.py
```

Produce `dist/USB Backup.exe` (Windows) o `dist/USB Backup.app` (macOS, va
compilato su un Mac). Nel pacchetto non finisce nessuna configurazione:
l'eseguibile scrive il suo `config.json` accanto a se', quindi e' portatile.

Se l'eseguibile e' aperto, anche solo nella tray, la compilazione si ferma e lo
dice: non puo' sostituire un file in uso.

### Firma

**Su un PC con Smart App Control attivo** (Windows 11), l'eseguibile non firmato
puo' essere bloccato con "Un criterio di controllo dell'applicazione ha bloccato
il file". La decisione e' per singolo file: una compilazione passa, la successiva
magari no. Finche' non c'e' una firma riconosciuta, la strada sicura e' il
sorgente - `start_gui.cmd` - perche' li' gira `python.exe`, che e' firmato. Anche
l'avvio automatico, attivato dall'app in quel modo, riapre l'app nella tray.

Smart App Control si puo' spegnere, ma **non si riaccende** senza reinstallare
Windows: meglio non farlo per questo.


Un eseguibile non firmato fa comparire "Windows ha protetto il PC", e alcune
policy aziendali lo bloccano del tutto. `build.py` firma da solo se trova un
certificato di firma del codice:

```bash
set USBBACKUP_SIGN_THUMBPRINT=<impronta di un certificato nell'archivio personale>
```

oppure `USBBACKUP_SIGN_PFX` con il percorso di un file `.pfx` e
`USBBACKUP_SIGN_PASSWORD`. Usa `Set-AuthenticodeSignature` di PowerShell, non
serve l'SDK di Windows.

Il certificato va comprato da un'autorita' riconosciuta (per esempio Sectigo,
DigiCert o Certum). Un certificato fatto in casa funziona solo sui PC dove lo
installi a mano fra quelli attendibili.
In alternativa, sul PC dell'ufficio si puo' usare il sorgente con Python.

## Riga di comando

```bash
python usb_backup.py --list       # PC, destinazione, piano e volumi visti adesso
python usb_backup.py --once       # lavora sui volumi collegati ed esce
python usb_backup.py --watch      # resta in ascolto (default)
python usb_backup.py --install    # avvio automatico al login
python usb_backup.py --uninstall
```

L'avvio automatico usa un'attivita' pianificata su Windows e un LaunchAgent su
macOS. Dall'eseguibile registra l'eseguibile stesso, che riprende a sorvegliare
se l'interruttore era acceso. Su macOS la prima copia in Documenti, Scrivania o
Download chiede il permesso di accesso ai file.

## Test

```bash
python tests/run_tests.py             # tutti
python tests/run_tests.py sync stop   # solo quelli il cui nome contiene sync o stop
python tests/run_tests.py --bench     # anche le misure di velocita'
```

Ogni suite gira in un processo separato.
