#!/usr/bin/env python3
"""USB backup watcher - Windows + macOS, solo stdlib.

Sorveglia i volumi USB. A ogni volume collegato esegue fino a tre piani:

1. PIANO CHIAVETTA - se la chiavetta ha `backup.json` nella sua root:
       <chiavetta>/<cartella>  ->  <dest_root>/<nome-chiavetta>/<cartella>

2. PUSH  - se il PC ha `<dest_root>/backup.json` con sezione "push":
       <cartella del PC>       ->  <chiavetta>/backup/<nome-PC>/<cartella>

3. PULL  - se il PC ha `<dest_root>/backup.json` con sezione "pull":
       <chiavetta>/<cartella>  ->  <dest_root>/<nome-PC>/<cartella>

Copia sempre in mirror incrementale: solo file nuovi o modificati.
"""
from __future__ import annotations

import argparse
import ctypes
import fnmatch
import hashlib
import json
import random
import re
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from i18n import set_language, t, tf  # noqa: E402

IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"

# Da eseguibile compilato la cartella e' quella dell'exe, non quella temporanea
# in cui PyInstaller scompatta il codice: cosi' config.json sta accanto al
# programma e l'utente lo trova.
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"
MARKER_NAME = "backup.json"
MTIME_TOLERANCE = 2.0  # secondi (FAT32 ha risoluzione 2s)


def stesse_date(a: float, b: float) -> bool:
    """Due date di modifica indicano lo stesso file?

    Oltre ai 2 secondi di arrotondamento di FAT32, si accetta uno scarto di
    un'ora esatta: FAT32 ed exFAT salvano l'ora locale, e al cambio dell'ora
    legale tutti i file sembrerebbero modificati di 3600 secondi. Senza
    questa tolleranza, due volte l'anno si ricopierebbe tutto da capo.
    Chi la ritiene troppo larga puo' spegnerla con "dst_tolerance": false.
    """
    diff = abs(a - b)
    if diff <= MTIME_TOLERANCE:
        return True
    return (_config_cache.get("dst_tolerance", True)
            and abs(diff - 3600) <= MTIME_TOLERANCE)

DEFAULT_CONFIG = {
    "dest_root": str(Path.home() / "Backup"),
    "poll_seconds": 3,
    "include_fixed_drives": True,
    "notify": True,
    "rescan_cooldown_minutes": 15,
    "missing_polls_before_removed": 3,
    "copy_threads": 8,
    "log_days": 30,
    "mass_change_brake": True,
    "mass_change_percent": 30,
    "mass_change_min": 50,
    "save_settings_on_disk": True,
    "keep_versions": False,
    "low_priority": True,
    "notify_errors": True,
    "dst_tolerance": True,
    "verify_percent": 1,
    "use_gitignore": False,
    "stale_days": 7,
    "language": "auto",
    "autostart": True,
    "run_on_start": True,
    "close_to_tray": True,
    "start_minimized": False,
    "heartbeat_minutes": 0,
    "log_file": str(Path.home() / "Backup" / "_logs" / "usb-backup.log"),
    "default_exclude": [
        "System Volume Information", "$RECYCLE.BIN", ".Spotlight-V100",
        ".Trashes", ".fseventsd", "._*", "Thumbs.db", ".DS_Store",
    ],
}

INVALID_NAME_CHARS = '<>:"/\\|?*'

# Niente viene mai cancellato davvero: quello che sparisce da un lato finisce
# qui, con la stessa struttura di cartelle, pronto da recuperare a mano.
TRASH_DIR = "__deleted"

# Quando un file viene sostituito da una versione nuova, quella vecchia puo'
# essere messa da parte qui ("keep_versions"): senza, un file rovinato sul PC
# - svuotato, corrotto, cifrato - al giro dopo rovinerebbe anche il backup.
VERSIONS_DIR = "__versions"


_B = chr(92)                                   # la barra rovesciata
_PREFISSO_LUNGO = _B + _B + "?" + _B            # il prefisso dei percorsi estesi
_PREFISSO_UNC = _PREFISSO_LUNGO + "UNC" + _B    # idem, per le cartelle di rete


def L(percorso) -> str:
    """Percorso utilizzabile anche oltre i 260 caratteri su Windows.

    Windows accetta percorsi lunghi solo se c'e' la chiave di registro
    LongPathsEnabled *e* il programma lo dichiara nel manifesto. Il prefisso
    dei percorsi estesi invece funziona sempre, a patto che il percorso sia
    assoluto: in un repository con node_modules i 260 caratteri si superano
    in fretta.
    """
    testo = os.fspath(percorso)
    if not IS_WIN or testo.startswith(_PREFISSO_LUNGO):
        return testo
    testo = os.path.abspath(testo)
    if testo.startswith(_B + _B):                   # cartella di rete
        return _PREFISSO_UNC + testo[2:]
    return _PREFISSO_LUNGO + testo


def to_versions(base: Path, rel: str) -> Path:
    """Sposta `base/rel` in `base/__versions/rel`, con data e ora nel nome.

    A differenza del cestino le versioni si accumulano: ognuna ha il suo
    orario, e nessuna sovrascrive la precedente.
    """
    source = base / rel
    relativo = Path(rel)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = (base / VERSIONS_DIR / relativo.parent
              / f"{relativo.stem}.{stamp}{relativo.suffix}")
    progressivo = 1
    while os.path.exists(L(target)):          # due versioni nello stesso secondo
        progressivo += 1
        target = (base / VERSIONS_DIR / relativo.parent
                  / f"{relativo.stem}.{stamp}-{progressivo}{relativo.suffix}")
    os.makedirs(L(target.parent), exist_ok=True)
    shutil.move(L(source), L(target))
    return target


def to_trash(base: Path, rel: str) -> Path:
    """Sposta `base/rel` in `base/__deleted/rel`. Ritorna la nuova posizione."""
    source = base / rel
    target = base / TRASH_DIR / rel
    if os.path.exists(L(target)):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = target.with_name(f"{target.stem}.{stamp}{target.suffix}")
    os.makedirs(L(target.parent), exist_ok=True)
    shutil.move(L(source), L(target))
    return target


# --------------------------------------------------------------------------
# config + log
# --------------------------------------------------------------------------

def load_config() -> dict:
    global _config_cache
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig")))
        except Exception as exc:  # config rotta non deve bloccare il watcher
            print(f"[warn] config.json illeggibile ({exc}), uso i default")
    _config_cache = cfg
    set_language(str(cfg.get("language", "auto")))
    return cfg


_config_cache: dict = dict(DEFAULT_CONFIG)


def dest_root_of(cfg: dict) -> Path:
    return Path(str(cfg["dest_root"])).expanduser()


_log_file: Path | None = None
_log_sinks: list = []


def add_log_sink(fn) -> None:
    """Registra un callback che riceve ogni riga di log (usato dalla GUI)."""
    _log_sinks.append(fn)


def setup_log(path: str | None) -> None:
    global _log_file
    if not path:
        _log_file = None
        return
    _log_file = Path(path).expanduser()
    try:
        _log_file.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        _log_file = None


_log_giorno = ""


def log_di_oggi() -> Path | None:
    """Il file di log del giorno: usb-backup-AAAAMMGG.log accanto a quello configurato."""
    if _log_file is None:
        return None
    suffisso = _log_file.suffix or ".log"
    return _log_file.with_name(f"{_log_file.stem}-{datetime.now():%Y%m%d}{suffisso}")


def pulisci_log_vecchi() -> int:
    """Toglie i log giornalieri piu' vecchi di `log_days` giorni (30 di default).

    Si guarda la data scritta nel nome, non quella del file: copiare la
    cartella da un'altra parte non deve far sembrare nuovi i log vecchi.
    """
    giorni = int(_config_cache.get("log_days", 30))
    if _log_file is None or giorni <= 0:
        return 0
    suffisso = _log_file.suffix or ".log"
    schema = re.compile(rf"^{re.escape(_log_file.stem)}-(\d{{8}}){re.escape(suffisso)}$")
    limite = (datetime.now() - timedelta(days=giorni)).strftime("%Y%m%d")
    tolti = 0
    try:
        for voce in _log_file.parent.iterdir():
            trovato = schema.match(voce.name)
            if trovato and trovato.group(1) < limite:
                voce.unlink()
                tolti += 1
    except OSError:
        pass
    return tolti


def log(msg: str) -> None:
    global _log_giorno
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    for sink in _log_sinks:
        try:
            sink(line)
        except Exception:
            pass
    destinazione = log_di_oggi()
    if destinazione is not None:
        oggi = destinazione.name
        if oggi != _log_giorno:             # giorno nuovo: file nuovo, e si fa pulizia
            _log_giorno = oggi
            pulisci_log_vecchi()
        try:
            with destinazione.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except Exception:
            pass


# --------------------------------------------------------------------------
# avanzamento, in stile shell:
#   Codice  [######------------]  34%   54.2k/159.6k file   9.6/28.3 GB   18 MB/s   ETA 17m
# --------------------------------------------------------------------------

_progress_last = 0.0
PROGRESS_MARK = "\r"        # le righe che iniziano cosi' sostituiscono la precedente
PROGRESS_EVERY = 0.4        # secondi fra un aggiornamento e l'altro


def human_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def human_count(n: int) -> str:
    return f"{n / 1000:.1f}k" if n >= 10000 else str(n)


def human_time(seconds: float) -> str:
    seconds = int(max(0, seconds))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


def log_progress(text: str, force: bool = False) -> None:
    """Riga di avanzamento: non finisce nel file di log, si riscrive sul posto."""
    global _progress_last
    now = time.time()
    if not force and now - _progress_last < PROGRESS_EVERY:
        return
    _progress_last = now
    for sink in _log_sinks:
        try:
            sink(PROGRESS_MARK + text)
        except Exception:
            pass
    try:
        if sys.stdout is not None and sys.stdout.isatty():
            print("\r" + text.ljust(110)[:110], end="", flush=True)
    except Exception:
        pass


class Progress:
    """Conta i file man mano e disegna la barra."""

    WIDTH = 22

    def __init__(self, label: str, total_files: int, total_bytes: int):
        self.label = label
        self.total_files = max(0, total_files)
        self.total_bytes = max(0, total_bytes)
        self.files = 0
        self.seen_bytes = 0
        self.copied_bytes = 0
        self.started = time.time()

    def advance(self, size: int, copied: bool) -> None:
        self.files += 1
        self.seen_bytes += size
        if copied:
            self.copied_bytes += size
        log_progress(self.render())

    def render(self) -> str:
        frac = (self.seen_bytes / self.total_bytes if self.total_bytes
                else (self.files / self.total_files if self.total_files else 0.0))
        frac = min(1.0, max(0.0, frac))
        filled = int(frac * self.WIDTH)
        bar = "#" * filled + "-" * (self.WIDTH - filled)
        elapsed = max(0.001, time.time() - self.started)
        speed = self.copied_bytes / elapsed
        parts = [f"{self.label}  [{bar}] {frac * 100:3.0f}%",
                 tf("progress.files", fatti=human_count(self.files),
                    totale=human_count(self.total_files)),
                 f"{human_bytes(self.seen_bytes)}/{human_bytes(self.total_bytes)}"]
        if self.copied_bytes:
            parts.append(f"{human_bytes(speed)}/s")
            remaining = self.total_bytes - self.seen_bytes
            # la stima usa la velocita' di copia vera, non i file saltati
            done_ratio = self.copied_bytes / max(1, self.seen_bytes)
            if speed > 0 and remaining > 0:
                parts.append(f"ETA {human_time(remaining * done_ratio / speed)}")
        return "   ".join(parts)

    def finish(self) -> None:
        elapsed = time.time() - self.started
        log_progress(f"{self.label}  [{'#' * self.WIDTH}] 100%   "
                     + tf("progress.done", files=human_count(self.files),
                          size=human_bytes(self.copied_bytes),
                          tempo=human_time(elapsed)), force=True)


def scan_tree(base: Path, excludes: list[str]) -> tuple[int, int]:
    """Conta file e byte di una cartella, rispettando le esclusioni."""
    files = total = 0
    if not os.path.isdir(L(base)):
        return 0, 0
    pila: list[tuple[str, Path]] = [(L(base), Path("."))]
    while pila:
        cartella, rel = pila.pop()
        try:
            with os.scandir(cartella) as elenco:
                for voce in elenco:
                    if is_excluded(rel / voce.name, voce.name, excludes):
                        continue
                    try:
                        if voce.is_dir(follow_symlinks=False):
                            pila.append((voce.path, rel / voce.name))
                        else:
                            total += voce.stat(follow_symlinks=False).st_size
                            files += 1
                    except OSError:
                        continue
        except OSError:
            continue
    return files, total


CREATE_NO_WINDOW = 0x08000000    # niente finestra nera che lampeggia


def run_hidden(comando: list[str], **kw):
    """subprocess.run senza far sbattere in faccia una console.

    Su Windows ogni processo a riga di comando apre la sua finestra: per una
    notifica di fine backup significa un lampo nero sullo schermo.
    """
    if IS_WIN:
        kw.setdefault("creationflags", CREATE_NO_WINDOW)
    return subprocess.run(comando, **kw)


def notify(title: str, message: str) -> None:
    try:
        if IS_MAC:
            script = (f'display notification {json.dumps(message)} '
                      f'with title {json.dumps(title)}')
            run_hidden(["osascript", "-e", script],
                           check=False, capture_output=True, timeout=10)
        elif IS_WIN:
            ps = (
                '[Windows.UI.Notifications.ToastNotificationManager,'
                ' Windows.UI.Notifications, ContentType=WindowsRuntime] > $null;'
                '$t=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(2);'
                '$n=$t.GetElementsByTagName("text");'
                f'$n.Item(0).AppendChild($t.CreateTextNode({json.dumps(title)}))>$null;'
                f'$n.Item(1).AppendChild($t.CreateTextNode({json.dumps(message)}))>$null;'
                '[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('
                '"USB Backup").Show([Windows.UI.Notifications.ToastNotification]::new($t));'
            )
            run_hidden(["powershell", "-NoProfile", "-Command", ps],
                           check=False, capture_output=True, timeout=20)
    except Exception:
        pass


# --------------------------------------------------------------------------
# enumerazione volumi -> lista di (percorso, e_rimovibile)
# --------------------------------------------------------------------------

def _win_volumes(include_fixed: bool) -> list[tuple[Path, bool]]:
    k32 = ctypes.windll.kernel32
    mask = k32.GetLogicalDrives()
    system_drive = os.environ.get("SystemDrive", "C:").upper().rstrip("\\")
    out: list[tuple[Path, bool]] = []
    for i in range(26):
        if not (mask >> i) & 1:
            continue
        letter = chr(ord("A") + i)
        root = f"{letter}:\\"
        dtype = k32.GetDriveTypeW(ctypes.c_wchar_p(root))
        # 2 = DRIVE_REMOVABLE, 3 = DRIVE_FIXED (gli SSD USB si presentano spesso cosi')
        if dtype == 2:
            out.append((Path(root), True))
        elif include_fixed and dtype == 3 and f"{letter}:" != system_drive:
            out.append((Path(root), False))
    return out


def _win_label(root: Path) -> str:
    k32 = ctypes.windll.kernel32
    name = ctypes.create_unicode_buffer(261)
    fs = ctypes.create_unicode_buffer(261)
    serial = ctypes.c_ulong()
    comp_len = ctypes.c_ulong()
    flags = ctypes.c_ulong()
    ok = k32.GetVolumeInformationW(
        ctypes.c_wchar_p(str(root)), name, 261,
        ctypes.byref(serial), ctypes.byref(comp_len), ctypes.byref(flags), fs, 261,
    )
    if ok and name.value.strip():
        return name.value.strip()
    if ok and serial.value:
        return f"VOL-{serial.value:08X}"
    return f"DRIVE-{str(root)[0]}"


def volume_serial(root: Path) -> str:
    """Identificativo del volume, che non cambia se cambia lettera o etichetta.

    La lettera D: domani puo' essere un'altra chiavetta e l'etichetta la
    cambia chiunque: il serial e' l'unica cosa su cui valga la pena legare
    un piano di backup.
    """
    if IS_WIN:
        serial = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(str(root)), None, 0, ctypes.byref(serial),
            None, None, None, 0)
        return f"{serial.value:08X}" if ok and serial.value else ""
    if IS_MAC:
        try:
            uscita = run_hidden(["diskutil", "info", str(root)],
                                    capture_output=True, text=True, timeout=10)
            for riga in uscita.stdout.splitlines():
                if "Volume UUID" in riga:
                    return riga.split(":", 1)[1].strip()
        except Exception:
            pass
    try:
        return str(os.stat(root).st_dev)
    except OSError:
        return ""


def _mac_volumes() -> list[tuple[Path, bool]]:
    base = Path("/Volumes")
    if not base.is_dir():
        return []
    out: list[tuple[Path, bool]] = []
    for entry in base.iterdir():
        try:
            if entry.is_symlink() or not entry.is_dir():
                continue
            if os.path.realpath(entry) == "/":  # volume di boot
                continue
            if not os.path.ismount(entry):
                continue
        except OSError:
            continue
        out.append((entry, True))
    return out


def _linux_volumes() -> list[tuple[Path, bool]]:
    seen: dict[str, Path] = {}
    for base in (Path("/media"), Path("/run/media"), Path("/mnt")):
        if not base.is_dir():
            continue
        candidates: list[Path] = []
        try:
            for entry in base.iterdir():
                candidates.append(entry)
                if entry.is_dir():
                    candidates.extend(entry.iterdir())
        except OSError:
            continue
        for entry in candidates:
            try:
                if entry.is_dir() and os.path.ismount(entry):
                    seen[str(entry)] = entry
            except OSError:
                continue
    return [(p, True) for p in seen.values()]


def list_volumes(include_fixed: bool) -> list[tuple[Path, bool]]:
    if IS_WIN:
        return _win_volumes(include_fixed)
    if IS_MAC:
        return _mac_volumes()
    return _linux_volumes()


def volume_label(root: Path) -> str:
    if IS_WIN:
        return _win_label(root)
    return root.name or str(root).strip("/").replace("/", "-") or "VOLUME"


def safe_name(name: str) -> str:
    cleaned = "".join("_" if ch in INVALID_NAME_CHARS or ord(ch) < 32 else ch for ch in name)
    cleaned = cleaned.strip().strip(".")
    return cleaned or "VOLUME"


def machine_name(plan: dict | None = None) -> str:
    if plan and plan.get("pc_name"):
        return safe_name(str(plan["pc_name"]))
    return safe_name(socket.gethostname().split(".")[0])


# --------------------------------------------------------------------------
# motore di copia
# --------------------------------------------------------------------------

def _norm(path: Path) -> str:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    return os.path.normcase(str(resolved))


def new_stats() -> dict:
    return {"copied": 0, "skipped": 0, "deleted": 0, "errors": 0, "bytes": 0}


def is_excluded(rel_path: Path, name: str, patterns: list[str]) -> bool:
    rel = rel_path.as_posix()
    for pat in patterns:
        if fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(rel, pat):
            return True
    return False


def needs_copy(src: Path, dst: Path) -> bool:
    try:
        s = os.stat(L(src))
        d = os.stat(L(dst))
    except OSError:
        return True
    if s.st_size != d.st_size:
        return True
    return not stesse_date(s.st_mtime, d.st_mtime)


EVENTI_MAX = 200     # oltre, un giro disastroso gonfierebbe lo storico


def annota(stats: dict, tipo: str, **dati) -> None:
    """Ricorda cosa e' successo in un giro, per vederlo poi nello storico."""
    elenco = stats.setdefault("eventi", [])
    if len(elenco) < EVENTI_MAX:
        elenco.append({"tipo": tipo, **{k: str(v) for k, v in dati.items()}})
    else:
        stats["eventi_persi"] = stats.get("eventi_persi", 0) + 1


def priorita_bassa(attiva: bool = True) -> None:
    """Mette il thread corrente in secondo piano per disco e memoria.

    Copia lo stesso, ma lascia la precedenza a quello che stai facendo:
    un giro da decine di GB non si sente piu' mentre lavori. Riguarda solo
    il thread che copia, non l'interfaccia.
    """
    if not _config_cache.get("low_priority", True):
        return
    try:
        if IS_WIN:
            k32 = ctypes.windll.kernel32
            k32.GetCurrentThread.restype = ctypes.c_void_p
            k32.SetThreadPriority.argtypes = [ctypes.c_void_p, ctypes.c_int]
            # THREAD_MODE_BACKGROUND_BEGIN / _END
            k32.SetThreadPriority(k32.GetCurrentThread(),
                                  0x00010000 if attiva else 0x00020000)
        elif IS_MAC:
            libc = ctypes.CDLL("libc.dylib")
            # setiopolicy_np(IOPOL_TYPE_DISK, IOPOL_SCOPE_THREAD, THROTTLE / DEFAULT)
            libc.setiopolicy_np(0, 1, 3 if attiva else 0)
    except Exception:
        pass


_run_sinks: list = []


def add_run_sink(fn) -> None:
    """Registra chi vuole sapere com'e' andato ogni giro (l'app, per gli avvisi)."""
    _run_sinks.append(fn)


_stop = threading.Event()


def request_stop() -> None:
    """Chiede al giro in corso di fermarsi appena finisce il file corrente."""
    _stop.set()


def clear_stop() -> None:
    _stop.clear()


def stop_requested() -> bool:
    return _stop.is_set()


class Stopped(Exception):
    """Interrotto su richiesta: non e' un errore, e' una scelta."""


class DiscoSparito(Exception):
    """Il disco e' stato staccato a meta' giro: si ferma tutto, con un messaggio solo."""


class TroppeModifiche(Exception):
    """Il giro stava per sovrascrivere troppi file: potrebbe essere un danno."""

    def __init__(self, n: int, totale: int, dove: Path):
        super().__init__(f"{n}/{totale} in {dove}")
        self.n, self.totale, self.dove = n, totale, dove


_freno_sospeso = threading.Event()


def salta_freno_una_volta() -> None:
    """L'utente ha visto l'avviso e ha detto di procedere: vale per il prossimo giro."""
    _freno_sospeso.set()


def _radice_sparita(*percorsi: Path) -> bool:
    """Uno dei due lati della copia non c'e' piu'? (disco staccato, rete caduta)"""
    for percorso in percorsi:
        ancora = Path(percorso).anchor or str(percorso)
        if not os.path.exists(L(ancora)) or not os.path.exists(L(percorso)):
            return True
    return False


PART_SUFFIX = ".usbpart"      # copia in corso: se resta, e' roba interrotta


def copy_atomic(src: Path, dst: Path, versioni_base: Path | None = None) -> Path | None:
    """Copia su un file di appoggio e poi rinomina.

    Se si stacca la chiavetta a meta' copia resta solo il file `.usbpart`,
    che al giro dopo viene buttato: senza questo, il file di destinazione
    resterebbe troncato ma con data e dimensione da file nuovo, quindi
    nessuno lo ricopierebbe mai piu'.

    Con `versioni_base` la versione che sta per essere sostituita viene
    messa da parte in __versions. Ritorna dove e' finita, o None.
    """
    tmp = dst.with_name(dst.name + PART_SUFFIX)
    salvata = None
    try:
        shutil.copy2(L(src), L(tmp))          # prima la copia nuova, intera
        if versioni_base is not None and os.path.exists(L(dst)):
            salvata = to_versions(versioni_base, dst.relative_to(versioni_base).as_posix())
        os.replace(L(tmp), L(dst))
        return salvata
    except BaseException:
        try:
            if os.path.exists(L(tmp)):
                os.unlink(L(tmp))
            # se la vecchia versione era gia' stata spostata, torna al suo posto
            if salvata is not None and not os.path.exists(L(dst)):
                shutil.move(L(salvata), L(dst))
        except OSError:
            pass
        raise


def file_digest(path: Path, chunk: int = 1 << 20) -> str:
    """sha256 letto a blocchi: niente file interi in memoria."""
    h = hashlib.sha256()
    with open(L(path), "rb") as fh:
        for pezzo in iter(lambda: fh.read(chunk), b""):
            h.update(pezzo)
    return h.hexdigest()


def verify_sample(coppie: list[tuple[Path, Path]], percento: float,
                  stats: dict) -> None:
    """Ricontrolla col digest una fetta dei file appena copiati.

    Le chiavette si corrompono in silenzio: un backup mai verificato e' una
    speranza, non un backup. Si controlla una percentuale, non tutto, per
    non raddoppiare i tempi.
    """
    if percento <= 0 or not coppie:
        return
    quanti = max(1, min(len(coppie), round(len(coppie) * percento / 100)))
    campione = random.sample(coppie, quanti)
    log(tf("verify.start", quanti=quanti, totale=len(coppie)))
    sbagliati = 0
    for sorgente, copia in campione:
        if stop_requested():
            break
        try:
            if file_digest(sorgente) != file_digest(copia):
                sbagliati += 1
                log(tf("verify.bad", file=copia))
                annota(stats, "errore", path=copia, msg="verify")
        except OSError as exc:
            sbagliati += 1
            log(tf("err.verify", path=copia, err=exc))
    stats["verificati"] = stats.get("verificati", 0) + quanti - sbagliati
    if sbagliati:
        stats["errors"] += sbagliati
        log(tf("verify.summary", sbagliati=sbagliati, quanti=quanti))


class GitIgnore:
    """Legge i .gitignore incontrati e dice cosa saltare.

    Non e' git: niente pattern esotici. Copre quello che serve davvero in un
    repo - righe di commento, cartelle con la barra finale, ancoraggio con la
    barra iniziale, glob con * e ?, negazioni con !. Le regole di una cartella
    valgono anche per tutto quello che sta sotto, come in git.
    """

    def __init__(self) -> None:
        self.regole: dict[str, list[tuple[str, bool, bool]]] = {}

    def carica(self, cartella: Path, rel: str) -> bool:
        """Legge il .gitignore di questa cartella. Ritorna True se ce n'era uno."""
        percorso = cartella / ".gitignore"
        if not percorso.is_file():
            return False
        regole: list[tuple[str, bool, bool]] = []
        try:
            testo = percorso.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        for riga in testo.splitlines():
            riga = riga.strip()
            if not riga or riga.startswith("#"):
                continue
            nega = riga.startswith("!")
            if nega:
                riga = riga[1:].strip()
            solo_cartelle = riga.endswith("/")
            # come in git: una barra all'inizio o in mezzo ancora il pattern
            # a questa cartella; senza barre vale a qualunque profondita'
            ancorato = riga.startswith("/") or "/" in riga.rstrip("/")
            riga = riga.strip("/")
            if riga:
                regole.append((riga, solo_cartelle, nega, ancorato))
        if regole:
            self.regole[rel] = regole
        return bool(regole)

    def _applica(self, regole, percorso: str, nome: str, e_cartella: bool) -> bool | None:
        esito = None
        for schema, solo_cartelle, nega, ancorato in regole:
            if solo_cartelle and not e_cartella:
                continue
            if ancorato:
                colpito = (fnmatch.fnmatch(percorso, schema)
                           or percorso.startswith(schema.rstrip("/") + "/"))
            else:
                colpito = (fnmatch.fnmatch(nome, schema)
                           or any(fnmatch.fnmatch(pezzo, schema)
                                  for pezzo in percorso.split("/")))
            if colpito:
                esito = not nega     # l'ultima regola che colpisce decide, come in git
        return esito

    def ignora(self, rel_dir: str, nome: str, e_cartella: bool) -> bool:
        """`rel_dir` e' la cartella (relativa alla radice), `nome` la voce."""
        intero = f"{rel_dir}/{nome}" if rel_dir else nome
        decisione = None
        for base, regole in self.regole.items():
            if base and not (intero == base or intero.startswith(base + "/")):
                continue
            relativo = intero[len(base) + 1:] if base else intero
            esito = self._applica(regole, relativo, nome, e_cartella)
            if esito is not None:
                decisione = esito      # le regole piu' interne vengono dopo e vincono
        return bool(decisione)


def mirror_tree(src: Path, dst: Path, excludes: list[str], delete_extra: bool,
                stats: dict, skip_paths: set[str] | None = None,
                progress: "Progress | None" = None,
                guard: "SpaceGuard | None" = None,
                threads: int = 1,
                copiati: list | None = None,
                gitignore: bool = False) -> None:
    skip = set(skip_paths or ())
    skip.add(_norm(dst))
    os.makedirs(L(dst), exist_ok=True)
    kept: dict[Path, set[str]] = {}
    da_copiare: list[tuple[Path, Path, int]] = []
    ignora = GitIgnore() if gitignore else None

    # --- 1. giro dell'albero: decide cosa copiare, cosa saltare ---
    # Si usa os.scandir invece di os.walk: su Windows l'elenco di una cartella
    # porta gia' con se' dimensione e data di ogni voce, quindi non serve una
    # chiamata stat per file. La destinazione si legge una volta per cartella
    # invece di interrogarla file per file: su 100.000 file sono 200.000
    # chiamate di sistema in meno.
    def voci(cartella: Path) -> dict[str, tuple[int, float, bool]] | None:
        """Il contenuto di una cartella, o None se non si riesce a leggerla.

        None e' diverso da vuota: se l'elenco della sorgente fallisce (disco
        staccato, permessi) non bisogna concludere che la cartella e' vuota,
        perche' con delete_extra si sposterebbe in __deleted tutta la copia.
        """
        trovate: dict[str, tuple[int, float, bool]] = {}
        try:
            with os.scandir(L(cartella)) as elenco:
                for voce in elenco:
                    try:
                        info = voce.stat(follow_symlinks=False)
                        trovate[voce.name] = (info.st_size, info.st_mtime,
                                              voce.is_dir(follow_symlinks=False))
                    except OSError:
                        continue
        except OSError:
            return None
        return trovate

    da_visitare: list[tuple[Path, Path]] = [(src, Path("."))]
    while da_visitare:
        if stop_requested():
            raise Stopped()
        here, rel = da_visitare.pop()
        rel_posix = "" if str(rel) == "." else rel.as_posix()
        if ignora is not None:
            ignora.carica(here, rel_posix)

        sorgenti = voci(here)
        if sorgenti is None:
            if _radice_sparita(src, dst):
                raise DiscoSparito(str(src))
            # cartella illeggibile: si salta, e soprattutto non si cancella
            # niente di quello che le corrisponde nella copia
            log(tf("err.read", path=here))
            annota(stats, "errore", path=here, msg="read")
            stats["errors"] += 1
            continue
        target_dir = dst / rel
        try:
            os.makedirs(L(target_dir), exist_ok=True)
        except OSError as exc:
            log(tf("err.mkdir", path=target_dir, err=exc))
            annota(stats, "errore", path=target_dir, msg=exc)
            stats["errors"] += 1
            continue
        destinazioni = voci(target_dir) or {}

        names: set[str] = set()
        for nome, (size, mtime, e_cartella) in sorted(sorgenti.items()):
            if is_excluded(rel / nome, nome, excludes):
                continue
            if ignora is not None and ignora.ignora(rel_posix, nome, e_cartella):
                continue
            if e_cartella:
                if _norm(here / nome) in skip:
                    continue
                names.add(nome)
                da_visitare.append((here / nome, rel / nome))
                continue
            if nome.endswith(PART_SUFFIX):
                continue
            names.add(nome)
            gia = destinazioni.get(nome)
            uguale = (gia is not None and not gia[2]
                      and gia[0] == size and stesse_date(gia[1], mtime))
            if uguale:
                stats["skipped"] += 1
                if progress:
                    progress.advance(size, copied=False)
            else:
                da_copiare.append((here / nome, target_dir / nome, size))
        kept[target_dir] = names

    # --- freno: troppe sovrascritture tutte insieme? ---
    # Un ransomware, o un checkout su un branch vecchio, cambiano meta' dei
    # file in un colpo: meglio fermarsi e chiedere che propagare il danno.
    sovrascritture = sum(1 for _, d_file, _ in da_copiare
                         if os.path.exists(L(d_file)))
    tracciati = stats["skipped"] + sovrascritture
    if (_config_cache.get("mass_change_brake", True) and not _freno_sospeso.is_set()
            and sovrascritture >= int(_config_cache.get("mass_change_min", 50))
            and sovrascritture * 100 >= tracciati * int(_config_cache.get("mass_change_percent", 30))):
        raise TroppeModifiche(sovrascritture, tracciati, dst)

    # --- 2. copie vere, in parallelo se richiesto ---
    if da_copiare:
        versioni = dst if _config_cache.get("keep_versions", False) else None
        fatte = _esegui_copie(da_copiare, stats, progress, guard, threads,
                              versioni_base=versioni, radici=(src, dst))
        if copiati is not None:
            copiati.extend(fatte)
    if stop_requested():
        raise Stopped()

    # --- 3. cio' che non c'e' piu' nella sorgente ---
    if not delete_extra:
        return
    for target_dir, names in kept.items():
        try:
            for nome in os.listdir(L(target_dir)):
                if nome in names or nome in (TRASH_DIR, VERSIONS_DIR, SYNC_STATE_DIR):
                    continue
                entry = target_dir / nome
                if nome.endswith(PART_SUFFIX):         # avanzo di una copia interrotta
                    os.unlink(L(entry))
                    continue
                finito = to_trash(dst, entry.relative_to(dst).as_posix())
                annota(stats, "cestino", originale=entry, salvato=finito)
                stats["deleted"] += 1
        except OSError as exc:
            log(tf("err.trash", path=target_dir, err=exc))
            annota(stats, "errore", path=target_dir, msg=exc)
            stats["errors"] += 1


def _esegui_copie(lavori: list[tuple[Path, Path, int]], stats: dict,
                  progress: "Progress | None", guard: "SpaceGuard | None",
                  threads: int,
                  versioni_base: Path | None = None,
                  radici: tuple[Path, ...] = ()) -> list[tuple[Path, Path]]:
    """Copia la lista di file, con piu' thread se conviene.

    Su tanti file piccoli il tempo se ne va in apertura e chiusura, non in
    banda: qualche thread in piu' tiene occupato il disco mentre gli altri
    aspettano il filesystem.
    """
    lock = threading.Lock()
    fermati = threading.Event()
    senza_spazio: list[NoSpace] = []
    sparito: list[DiscoSparito] = []

    riuscite: list[tuple[Path, Path]] = []

    def uno(lavoro: tuple[Path, Path, int]) -> None:
        s_file, d_file, size = lavoro
        if fermati.is_set() or stop_requested():
            return
        priorita_bassa(True)
        try:
            with lock:
                if guard:
                    guard.reserve(size)      # spazio prenotato, non solo controllato
        except NoSpace as exc:
            fermati.set()
            with lock:
                senza_spazio.append(exc)
            return
        try:
            if versioni_base is not None:
                salvata = copy_atomic(s_file, d_file, versioni_base=versioni_base)
            else:
                salvata = copy_atomic(s_file, d_file)
        except OSError as exc:
            with lock:
                if guard:
                    guard.release(size)      # non si e' scritto niente: lo restituisco
                if radici and _radice_sparita(*radici):
                    # disco staccato: un messaggio solo, non uno per file
                    if not sparito:
                        sparito.append(DiscoSparito(str(exc)))
                    fermati.set()
                    return
                log(tf("err.copy", path=s_file, err=exc))
                annota(stats, "errore", path=s_file, msg=exc)
                stats["errors"] += 1
                if progress:
                    progress.advance(size, copied=False)
            return
        with lock:
            if guard:
                guard.done(size)
            stats["copied"] += 1
            stats["bytes"] += size
            riuscite.append((s_file, d_file))
            if salvata is not None:
                stats["versioned"] = stats.get("versioned", 0) + 1
                annota(stats, "versione", originale=d_file, salvato=salvata)
            if progress:
                progress.advance(size, copied=True)

    if threads <= 1:
        for lavoro in lavori:
            uno(lavoro)
    else:
        with ThreadPoolExecutor(max_workers=threads) as pool:
            list(pool.map(uno, lavori))

    if sparito:
        raise sparito[0]
    if senza_spazio:
        raise senza_spazio[0]
    return riuscite


def summarize(stats: dict, elapsed: float) -> str:
    mb = stats["bytes"] / (1024 * 1024)
    return tf("summary", copiati=stats["copied"], mb=f"{mb:.1f}",
              invariati=stats["skipped"], cestinati=stats["deleted"],
              errori=stats["errors"], secondi=f"{elapsed:.1f}")


def write_receipt(base: Path, summary: str) -> None:
    try:
        base.mkdir(parents=True, exist_ok=True)
        (base / "_last_backup.txt").write_text(
            f"{datetime.now():%Y-%m-%d %H:%M:%S}\n{summary}\n", encoding="utf-8")
    except OSError:
        pass


# --------------------------------------------------------------------------
# lettura dei piani
# --------------------------------------------------------------------------

def read_json_file(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        log(tf("err.json.invalid", path=path, err=exc))
        return None
    if not isinstance(data, dict):
        log(tf("err.json.notobj", path=path))
        return None
    return data


def read_stick_plan(root: Path) -> dict | None:
    return read_json_file(root / MARKER_NAME)


def read_pc_plan(cfg: dict) -> dict | None:
    return read_json_file(dest_root_of(cfg) / MARKER_NAME)


# Il file del PC puo' avere un piano solo (formato di sempre) o piu' piani,
# uno per disco:  {"pc_name": ..., "piani": [{"only_serials": [...], "push": ...}, ...]}
# Le chiavi fuori da "piani" valgono per tutti; qui sotto quelle che nel
# formato a piano unico sono comuni e non del piano.
CHIAVI_COMUNI = ("pc_name",)


def dividi_piani(file: dict | None) -> tuple[dict, list[dict]]:
    """(chiavi comuni, elenco dei piani) da un file del PC, in tutti e due i formati."""
    if not file:
        return {}, []
    if isinstance(file.get("piani"), list):
        comuni = {k: v for k, v in file.items() if k != "piani"}
        return comuni, [dict(p) for p in file["piani"] if isinstance(p, dict)]
    comuni = {k: file[k] for k in CHIAVI_COMUNI if k in file}
    return comuni, [{k: v for k, v in file.items() if k not in CHIAVI_COMUNI}]


def unisci_piani(comuni: dict, piani: list[dict]) -> dict:
    """Il contrario di dividi_piani. Con un piano solo si scrive il formato di
    sempre, che anche le versioni vecchie del programma sanno leggere."""
    if len(piani) == 1:
        return dict(comuni, **piani[0])
    return dict(comuni, piani=piani)


def piani_del_pc(file: dict | None) -> list[dict]:
    """Ogni piano completo delle chiavi comuni: pronto per volume_matches e i run_*."""
    comuni, piani = dividi_piani(file)
    return [dict(comuni, **p) for p in piani]


def piani_per_volume(cfg: dict, root: Path, label: str, removable: bool) -> list[dict]:
    return [p for p in piani_del_pc(read_pc_plan(cfg))
            if volume_matches(p, root, label, removable)]


def resolve_entries(spec: dict, absolute: bool) -> list[tuple[str, str]]:
    """Ritorna [(percorso sorgente, nome cartella di destinazione)].

    `absolute=False`: percorsi relativi alla root del volume.
    `absolute=True` : percorsi assoluti sul PC (push).
    """
    raw = spec.get("folders", [])
    if isinstance(raw, str):
        raw = [raw]
    entries: list[tuple[str, str]] = []
    for item in raw:
        if isinstance(item, str):
            src, alias = item, ""
        elif isinstance(item, dict):
            src, alias = str(item.get("path", "")), str(item.get("as", "") or "")
        else:
            continue
        src = src.strip()
        if absolute:
            if not src:
                continue
            if not alias:
                name = Path(src.rstrip("/\\")).name
                alias = name or Path(src).drive.rstrip(":") or "root"
        else:
            src = src.replace("\\", "/").strip("/")
            if src == ".":
                src = ""
            if not alias:
                alias = Path(src).name if src else "root"
        if alias.strip() in (".", "/", "\\"):
            # "as": "." = il contenuto va dritto nella destinazione, senza
            # creare un'altra cartella con lo stesso nome dentro
            entries.append((src, ""))
            continue
        entries.append((src, safe_name(alias)))
    return entries


def volume_matches(plan: dict, root: Path, label: str, removable: bool) -> bool:
    """Il piano del PC si applica a questo volume?"""
    # il serial vince su tutto: se il piano e' legato a un disco preciso,
    # su nessun altro deve partire, nemmeno se ha la stessa etichetta
    serials = plan.get("only_serials")
    if serials:
        if isinstance(serials, str):
            serials = [serials]
        mio = volume_serial(root).upper()
        return bool(mio) and any(mio == str(x).upper().strip() for x in serials)

    patterns = plan.get("only_volumes")
    if patterns:
        if isinstance(patterns, str):
            patterns = [patterns]
        return any(
            fnmatch.fnmatch(label, str(p)) or fnmatch.fnmatch(str(root), str(p))
            for p in patterns
        )
    # Senza filtro esplicito si lavora solo sui volumi davvero rimovibili:
    # mai su un disco interno secondario.
    return removable


# --------------------------------------------------------------------------
# i tre piani
# --------------------------------------------------------------------------

class NoSpace(Exception):
    """Spazio finito sul disco di destinazione: il piano si ferma qui."""


SPACE_MARGIN = 256 * 1024 * 1024     # 256 MB di riserva, non si scende sotto


def free_space(path: Path) -> int:
    """Byte liberi sul volume che ospita `path` (risale ai genitori se serve)."""
    probe = path
    for _ in range(6):
        try:
            return shutil.disk_usage(probe).free
        except OSError:
            if probe.parent == probe:
                break
            probe = probe.parent
    return 0


class SpaceGuard:
    """Tiene il conto dello spazio libero mentre si copia, senza chiederlo al
    sistema a ogni file."""

    RECHECK_EVERY = 300

    def __init__(self, dest: Path, margin: int = SPACE_MARGIN):
        self.dest = dest
        self.margin = margin
        self.free = free_space(dest)
        self.pending = 0          # prenotato ma non ancora scritto sul disco
        self.copied_since_check = 0

    def _refresh(self) -> None:
        # lo spazio vero meno quello gia' promesso alle copie in volo: senza
        # sottrarre le prenotazioni si ricomincerebbe a concedere spazio
        # che e' gia' stato impegnato
        self.free = free_space(self.dest) - self.pending
        self.copied_since_check = 0

    def reserve(self, size: int) -> None:
        """Mette da parte lo spazio PRIMA di copiare.

        Con piu' thread non basta controllare: otto controlli passerebbero
        tutti prima che il primo file venga scritto, e lo spazio si sfora.
        Qui lo spazio viene sottratto subito, e restituito se la copia fallisce.
        """
        if self.copied_since_check >= self.RECHECK_EVERY:
            self._refresh()
        if self.free - size < self.margin:
            self._refresh()                         # ultima verifica vera
            if self.free - size < self.margin:
                raise NoSpace(
                    f"su {self.dest}: liberi {human_bytes(self.free)}, "
                    f"servono {human_bytes(size)} piu' la riserva di "
                    f"{human_bytes(self.margin)}")
        self.free -= size
        self.pending += size
        self.copied_since_check += 1

    def done(self, size: int) -> None:
        """Copia finita: lo spazio era gia' stato sottratto, tolgo la prenotazione."""
        self.pending = max(0, self.pending - size)

    def release(self, size: int) -> None:
        """Copia fallita: niente e' stato scritto, restituisco lo spazio."""
        self.free += size
        self.pending = max(0, self.pending - size)


HISTORY_MAX = 200


def history_path() -> Path:
    base = _log_file.parent if _log_file is not None else APP_DIR
    return base / "history.json"


def read_history() -> list[dict]:
    try:
        data = json.loads(history_path().read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def record_history(voce: dict) -> None:
    """Aggiunge un giro allo storico, tenendo solo gli ultimi."""
    try:
        storia = read_history()
        storia.insert(0, voce)
        del storia[HISTORY_MAX:]
        path = history_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(storia, indent=1, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        log(tf("err.history", err=exc))


SETTINGS_FILE = "usb-backup-impostazioni.json"

# Cio' che e' proprio di questa macchina e non va portato altrove: percorsi
# locali, nome del PC, vincoli a un disco preciso.
CHIAVI_LOCALI = ("dest_root", "log_file", "watch_enabled")


def export_settings(dove: Path, cfg: dict) -> Path:
    """Scrive impostazioni e piano su un disco, per riportarli su un altro PC."""
    piano = read_pc_plan(cfg) or {}
    dati = {
        "creato": datetime.now().isoformat(timespec="seconds"),
        "da_pc": machine_name(piano),
        "config": {k: v for k, v in cfg.items() if k not in CHIAVI_LOCALI},
        "piano": piano,
    }
    percorso = Path(dove) / SETTINGS_FILE
    percorso.write_text(json.dumps(dati, indent=2, ensure_ascii=False), encoding="utf-8")
    log(tf("exported", path=percorso))
    return percorso


IMPOSTAZIONI_SUL_DISCO = ".usb-backup"


def salva_impostazioni_sul_disco(root: Path, cfg: dict) -> Path | None:
    """Una copia di impostazioni e piano sul disco, a ogni giro.

    Se il PC si rompe, sul disco c'e' il backup ma anche il piano che diceva
    cosa copiare e dove: su un PC nuovo basta importarlo. Un file per PC.
    """
    try:
        cartella = Path(root) / IMPOSTAZIONI_SUL_DISCO
        os.makedirs(L(cartella), exist_ok=True)
        piano = read_pc_plan(cfg) or {}
        dati = {
            "creato": datetime.now().isoformat(timespec="seconds"),
            "da_pc": machine_name(piano),
            "config": {k: v for k, v in cfg.items() if k not in CHIAVI_LOCALI},
            "piano": piano,
        }
        percorso = cartella / f"impostazioni-{machine_name(piano)}.json"
        percorso.write_text(json.dumps(dati, indent=2, ensure_ascii=False), encoding="utf-8")
        return percorso
    except OSError:
        return None                         # disco in sola lettura: pazienza


def import_settings(percorso: Path, cfg: dict) -> tuple[dict, dict]:
    """Legge un file esportato. Ritorna (config aggiornata, piano).

    I percorsi locali di questa macchina restano quelli che sono: importare
    il `dest_root` di un altro PC creerebbe cartelle a caso.
    """
    dati = json.loads(Path(percorso).read_text(encoding="utf-8-sig"))
    if not isinstance(dati, dict) or "config" not in dati:
        raise ValueError("file di impostazioni non riconosciuto")
    nuova = dict(cfg)
    for chiave, valore in (dati.get("config") or {}).items():
        if chiave not in CHIAVI_LOCALI:
            nuova[chiave] = valore
    piano = dict(dati.get("piano") or {})
    # il vincolo al disco e il nome del PC appartengono all'altra macchina.
    # Con piu' piani invece il numero di serie e' proprio cio' che li distingue
    # (ed e' del disco, non del PC): quelli dentro "piani" restano.
    piano.pop("only_serials", None)
    piano.pop("pc_name", None)
    return nuova, piano


def chiave_disco(serial: str, label: str) -> str:
    """Come riconoscere un disco nello storico.

    Il numero di serie, quando c'e': l'etichetta la cambia chiunque, e due
    chiavette con lo stesso nome finirebbero mescolate.
    """
    serial = (serial or "").strip().upper()
    return f"serial:{serial}" if serial else f"nome:{label}"


def dischi_visti() -> dict[str, dict]:
    """Ogni disco dello storico: nome piu' recente, ultimo giro, giorni passati."""
    adesso = datetime.now()
    visti: dict[str, dict] = {}
    for voce in read_history():                     # il piu' recente viene prima
        nome = str(voce.get("volume", ""))
        chiave = chiave_disco(str(voce.get("serial") or ""), nome)
        if chiave in visti or chiave == "nome:":
            continue
        try:
            quando = datetime.fromisoformat(str(voce.get("quando")))
        except (TypeError, ValueError):
            continue
        visti[chiave] = {"nome": nome, "quando": quando,
                         "giorni": (adesso - quando).total_seconds() / 86400}
    # le voci vecchie, registrate prima che si salvasse il serial, non devono
    # far comparire lo stesso disco una seconda volta sotto il solo nome
    con_serial = {d["nome"] for k, d in visti.items() if k.startswith("serial:")}
    for chiave in [k for k, d in visti.items()
                   if k.startswith("nome:") and d["nome"] in con_serial]:
        del visti[chiave]
    return visti


def giorni_da_ultimo_backup() -> dict[str, float]:
    """Da quanti giorni non colleghi ciascun disco, per nome."""
    return {d["nome"]: d["giorni"] for d in dischi_visti().values()}


def dischi_fermi(soglia: float, collegati: set[str], cfg: dict) -> list[dict]:
    """Dischi da segnalare: fermi da troppo, non collegati adesso, non dimenticati.

    Un disco dimenticato torna a essere segnalato se lo ricolleghi: da quel
    giro in poi e' di nuovo uno dei tuoi.
    """
    ignorati = cfg.get("stale_ignore") or {}
    fermi = []
    for chiave, disco in dischi_visti().items():
        if disco["giorni"] < soglia or chiave in collegati:
            continue
        dimenticato = str(ignorati.get(chiave) or "")
        if dimenticato and dimenticato >= disco["quando"].isoformat(timespec="seconds"):
            continue
        fermi.append({"chiave": chiave, **disco})
    return sorted(fermi, key=lambda d: -d["giorni"])


def dimentica_dischi(chiavi: list[str], cfg: dict) -> dict:
    """Non segnalare piu' questi dischi (finche' non vengono ricollegati)."""
    nuova = dict(cfg)
    ignorati = dict(nuova.get("stale_ignore") or {})
    adesso = datetime.now().isoformat(timespec="seconds")
    for chiave in chiavi:
        ignorati[chiave] = adesso
    nuova["stale_ignore"] = ignorati
    CONFIG_PATH.write_text(json.dumps(nuova, indent=2, ensure_ascii=False), encoding="utf-8")
    return load_config()


def _totals_path() -> Path:
    base = _log_file.parent if _log_file is not None else APP_DIR
    return base / "scan-totals.json"


def _load_totals(key: str) -> tuple[int, int] | None:
    try:
        data = json.loads(_totals_path().read_text(encoding="utf-8"))
        entry = data.get(key)
        return (int(entry[0]), int(entry[1])) if entry else None
    except Exception:
        return None


def _save_totals(key: str, files: int, size: int) -> None:
    try:
        path = _totals_path()
        data = {}
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        # butta via le voci di cartelle che non esistono piu', se no il file
        # cresce per sempre con percorsi morti
        data = {k: v for k, v in data.items()
                if all(Path(part).exists() for part in k.split("|"))}
        data[key] = [files, size]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    except Exception:
        pass


def run_jobs(label: str, jobs: list[tuple[Path, Path]], excludes: list[str],
             delete_extra: bool, stats: dict, skip_paths: set[str] | None = None) -> None:
    """Copia mostrando la barra.

    I totali del giro precedente fanno da stima, cosi' non serve percorrere
    l'albero due volte: su 100.000 file la sola conta costa piu' di un minuto.
    Si conta davvero solo la prima volta.
    """
    key = "|".join(str(src) for src, _ in jobs)
    cached = _load_totals(key)
    if cached:
        files, total = cached
        log(tf("count.estimate", files=human_count(files), size=human_bytes(total)))
    else:
        log(tf("count.first", label=label))
        files = total = 0
        for src, _dst in jobs:
            count, size = scan_tree(src, excludes)
            files += count
            total += size
        log(tf("count.done", files=human_count(files), size=human_bytes(total)))
    # --- spazio: si controlla prima di muovere un byte ---
    target = jobs[0][1] if jobs else None
    guard = None
    if target is not None:
        libero = free_space(target)
        vuota = not (target.exists() and any(target.iterdir()))
        log(tf("space.check", disco=Path(target).anchor or target,
               libero=human_bytes(libero), serve=human_bytes(total)))
        if vuota and libero < total + SPACE_MARGIN:
            mancano = total + SPACE_MARGIN - libero
            log(tf("space.short", quanto=human_bytes(mancano)))
            stats["errors"] += 1
            return
        if libero < total + SPACE_MARGIN:
            # destinazione gia' popolata: la maggior parte dei file verra'
            # saltata, si prova, ma sorvegliando lo spazio a ogni copia
            log(tf("space.tight", libero=human_bytes(libero), totale=human_bytes(total)))
        guard = SpaceGuard(target)

    progress = Progress(label, files, total)
    threads = max(1, int(_config_cache.get("copy_threads", 8)))
    copiati: list[tuple[Path, Path]] = []
    try:
        for src, dst in jobs:
            log(tf("job", src=src, dst=dst))
            mirror_tree(src, dst, excludes, delete_extra, stats,
                        skip_paths=skip_paths, progress=progress, guard=guard,
                        threads=threads, copiati=copiati,
                        gitignore=bool(_config_cache.get("use_gitignore", False)))
        interrotto = False
    except Stopped:
        log(tf("stopped", n=stats["copied"]))
        interrotto = True
    except DiscoSparito:
        log(tf("disk.gone", n=stats["copied"]))
        annota(stats, "errore", path=label, msg="disk.gone")
        stats["errors"] += 1
        stats["disco_sparito"] = True
        interrotto = True
    except TroppeModifiche as freno:
        log(tf("brake", n=freno.n, totale=freno.totale, path=freno.dove))
        annota(stats, "freno", path=freno.dove, n=freno.n, totale=freno.totale)
        stats["freno"] = {"n": freno.n, "totale": freno.totale, "dove": str(freno.dove)}
        interrotto = True
    except NoSpace as exc:
        log(tf("space.out", dettaglio=exc))
        log(tf("space.out.more", n=stats["copied"]))
        stats["errors"] += 1
        interrotto = True
    progress.finish()
    if not interrotto:
        verify_sample(copiati, float(_config_cache.get("verify_percent", 1)), stats)
    if not interrotto:
        # dopo un'interruzione i totali sono parziali: sarebbero una stima falsa
        _save_totals(key, progress.files, progress.seen_bytes)


def _excludes_for(cfg: dict, spec: dict) -> list[str]:
    out = list(cfg.get("default_exclude", [])) + list(spec.get("exclude", []) or [])
    out += [MARKER_NAME, TRASH_DIR, VERSIONS_DIR, SYNC_STATE_DIR]
    return out


def run_stick_plan(root: Path, cfg: dict, spec: dict) -> tuple[str, dict] | None:
    """Chiavetta -> PC, cartelle elencate dalla chiavetta."""
    label = safe_name(str(spec.get("name") or volume_label(root)))
    dest_root = Path(str(spec.get("dest_root") or cfg["dest_root"])).expanduser()
    target_base = dest_root / label
    entries = resolve_entries(spec, absolute=False)
    if not entries:
        log(tf("plan.empty", path=root / MARKER_NAME))
        return None

    log(tf("plan.stick", root=root, dest=target_base))
    started = time.time()
    stats = new_stats()
    excludes = _excludes_for(cfg, spec)

    jobs = []
    for rel_src, alias in entries:
        src = (root / rel_src) if rel_src else root
        if not _inside(src, root):
            log(tf("skip.outside", path=rel_src))
            stats["errors"] += 1
            continue
        if not src.is_dir():
            log(tf("skip.missing.stick", path=rel_src or "."))
            stats["errors"] += 1
            continue
        jobs.append((src, target_base / alias if alias else target_base))

    run_jobs(label, jobs, excludes, bool(spec.get("delete_extra", False)), stats)

    summary = summarize(stats, time.time() - started)
    log(tf("plan.stick.end", name=label, summary=summary))
    write_receipt(target_base, summary)
    return (f"{label} (chiavetta->PC)", stats)


def run_push(root: Path, cfg: dict, plan: dict, pc: str) -> tuple[str, dict] | None:
    """PC -> chiavetta: <chiavetta>/backup/<nome-PC>/<cartella>."""
    spec = plan.get("push") or {}
    entries = resolve_entries(spec, absolute=True)
    if not entries:
        return None

    subdir = str(spec.get("target_subdir", "backup")).strip("/\\")
    target_base = (root / subdir) if subdir else root
    # con "use_pc_folder": false si scrive dritto nella cartella indicata,
    # senza il livello intermedio col nome del PC
    if spec.get("use_pc_folder", True):
        target_base = target_base / pc
    log(tf("plan.push", pc=pc, dest=target_base))
    started = time.time()
    stats = new_stats()
    excludes = _excludes_for(cfg, spec)
    skip = {_norm(root)}  # non ricopiare la chiavetta dentro se' stessa

    jobs = []
    for raw_src, alias in entries:
        src = Path(raw_src).expanduser()
        if not src.is_dir():
            log(tf("skip.missing.pc", path=src))
            stats["errors"] += 1
            continue
        if _inside(src, root):
            log(tf("skip.already.stick", path=src))
            stats["errors"] += 1
            continue
        jobs.append((src, target_base / alias if alias else target_base))

    run_jobs(pc, jobs, excludes, bool(spec.get("delete_extra", False)), stats,
             skip_paths=skip)

    summary = summarize(stats, time.time() - started)
    log(tf("plan.push.end", pc=pc, summary=summary))
    write_receipt(target_base, summary)
    return (f"{pc} (PC->chiavetta)", stats)


def run_pull(root: Path, cfg: dict, plan: dict, pc: str) -> tuple[str, dict] | None:
    """Chiavetta -> PC, cartelle elencate dal PC: <dest_root>/<nome-PC>/<cartella>."""
    spec = plan.get("pull") or {}
    entries = resolve_entries(spec, absolute=False)
    if not entries:
        return None

    # Quello che arriva da un disco sta sotto <dest_root>/<nome del disco>,
    # come nel piano della chiavetta: cosi' la roba di ogni disco resta sua.
    # `dest` serve solo per mandarla altrove (es. una cartella di staging).
    target_base = (Path(str(spec["dest"])).expanduser() if spec.get("dest")
                   else dest_root_of(cfg) / safe_name(volume_label(root)))
    log(tf("plan.pull", root=root, dest=target_base))
    started = time.time()
    stats = new_stats()
    excludes = _excludes_for(cfg, spec)

    push_subdir = str((plan.get("push") or {}).get("target_subdir", "backup")).strip("/\\")
    skip = {_norm(root / push_subdir)} if push_subdir else set()

    jobs = []
    for rel_src, alias in entries:
        src = (root / rel_src) if rel_src else root
        if not _inside(src, root):
            log(tf("skip.outside", path=rel_src))
            stats["errors"] += 1
            continue
        if not src.is_dir():
            log(tf("skip.missing.stick", path=rel_src or "."))
            stats["errors"] += 1
            continue
        jobs.append((src, target_base / alias if alias else target_base))

    run_jobs(volume_label(root), jobs, excludes,
             bool(spec.get("delete_extra", False)), stats, skip_paths=skip)

    summary = summarize(stats, time.time() - started)
    log(tf("plan.pull.end", pc=pc, summary=summary))
    write_receipt(target_base, summary)
    return (f"{pc} (chiavetta->PC)", stats)


# --------------------------------------------------------------------------
# sincronizzazione a due vie (per il codice che gira su piu' macchine)
# --------------------------------------------------------------------------

SYNC_STATE_DIR = ".usbsync"
DELETE_GUARD_RATIO = 0.25   # oltre questa quota di sparizioni non si cancella
DELETE_GUARD_MIN = 20       # ...a meno che i file in gioco siano pochi

SYNC_DEFAULT_EXCLUDE = [
    "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache",
    "dist", "build", "target", ".next", ".gradle", "*.pyc", "*.pyo", "*.class",
    "*.o", "*.obj", ".DS_Store", "Thumbs.db", "*.swp", SYNC_STATE_DIR, TRASH_DIR,
    VERSIONS_DIR,
]


def _state_path(remote: Path, local: Path) -> Path:
    """Un file di stato per ogni coppia (macchina + cartella locale).

    Uno stato condiviso fra i due PC sarebbe sbagliato: al primo collegamento
    l'altra macchina vedrebbe il proprio lato vuoto e leggerebbe la differenza
    come 'cancellati tutti', svuotando la chiavetta.
    """
    key = hashlib.md5(str(local).lower().encode("utf-8")).hexdigest()[:10]
    return remote / SYNC_STATE_DIR / f"{safe_name(socket.gethostname())}-{key}.json"


def _index(base: Path, excludes: list[str]) -> dict[str, tuple[int, float]]:
    """Mappa 'percorso relativo -> (dimensione, data)' di tutti i file.

    Stesso giro del mirror: os.scandir, che porta con se' dimensione e data,
    e percorsi lunghi.
    """
    found: dict[str, tuple[int, float]] = {}
    if not os.path.isdir(L(base)):
        return found
    pila: list[tuple[str, Path]] = [(L(base), Path("."))]
    while pila:
        cartella, rel = pila.pop()
        try:
            with os.scandir(cartella) as elenco:
                for voce in elenco:
                    nome = voce.name
                    if nome == SYNC_STATE_DIR or nome.endswith(PART_SUFFIX):
                        continue
                    if is_excluded(rel / nome, nome, excludes):
                        continue
                    try:
                        if voce.is_dir(follow_symlinks=False):
                            pila.append((voce.path, rel / nome))
                        else:
                            info = voce.stat(follow_symlinks=False)
                            found[(rel / nome).as_posix()] = (info.st_size, info.st_mtime)
                    except OSError:
                        continue
        except OSError:
            continue
    return found


def _same(a, b) -> bool:
    """Due voci dell'indice sono la stessa cosa? (tolleranza FAT32 sulla data)"""
    if a is None or b is None:
        return a is None and b is None
    return a[0] == b[0] and stesse_date(a[1], b[1])


def _load_state(path: Path) -> dict[str, tuple[int, float]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {k: (int(v[0]), float(v[1])) for k, v in (raw.get("files") or {}).items()}
    except Exception:
        return {}


def _save_state(path: Path, index: dict[str, tuple[int, float]]) -> None:
    payload = {
        "updated_by": socket.gethostname(),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "files": {k: [v[0], v[1]] for k, v in sorted(index.items())},
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    except OSError as exc:
        log(tf("err.syncstate", err=exc))


def _copy_file(src: Path, dst: Path, stats: dict, key: str) -> bool:
    """Copia di un file nella sincronizzazione: atomica come nel mirror."""
    try:
        os.makedirs(L(dst.parent), exist_ok=True)
        copy_atomic(src, dst)
        stats[key] += 1
        stats["bytes"] += os.stat(L(src)).st_size
        return True
    except OSError as exc:
        log(tf("err.copy", path=src, err=exc))
        annota(stats, "errore", path=src, msg=exc)
        stats["errors"] += 1
        return False


def _conflict_name(path: Path, who: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    return path.with_name(f"{path.stem}.conflitto-{safe_name(who)}-{stamp}{path.suffix}")


def _prune_empty(base: Path) -> None:
    radice = os.path.normcase(L(base))
    for dirpath, dirnames, filenames in os.walk(L(base), topdown=False):
        if os.path.normcase(dirpath) == radice or filenames:
            continue
        try:
            os.rmdir(dirpath)       # fallisce da solo se non e' vuota: va bene
        except OSError:
            pass


def sync_pair(local: Path, remote: Path, excludes: list[str], stats: dict,
              dry_run: bool = False, conflict: str = "newest") -> None:
    """Sincronizza due cartelle confrontandole con lo stato dell'ultimo giro.

    Sapere com'erano l'ultima volta e' cio' che permette di distinguere
    "modificato di qua" da "cancellato di la'": senza quello stato si
    potrebbero solo copiare file, mai propagare una cancellazione.
    """
    lock = local / ".git" / "index.lock"
    if lock.exists():
        log(tf("skip.git", path=local, lock=lock.name))
        stats["errors"] += 1
        return

    remote.mkdir(parents=True, exist_ok=True)
    state_file = _state_path(remote, local)
    base = _load_state(state_file)
    left = _index(local, excludes)
    right = _index(remote, excludes)
    first_run = not base

    plan_copy: list[tuple[Path, Path, str]] = []
    plan_delete: list[tuple[Path, str]] = []
    conflicts: list[str] = []

    for rel in sorted(set(left) | set(right) | set(base)):
        l_entry, r_entry, b_entry = left.get(rel), right.get(rel), base.get(rel)
        if _same(l_entry, r_entry):
            continue

        l_changed = not _same(l_entry, b_entry)
        r_changed = not _same(r_entry, b_entry)

        if first_run:
            # nessuno stato precedente: non si cancella niente, si uniscono i due lati
            if l_entry is None:
                plan_copy.append((remote / rel, local / rel, "in"))
            elif r_entry is None:
                plan_copy.append((local / rel, remote / rel, "out"))
            else:
                newer_local = l_entry[1] >= r_entry[1]
                plan_copy.append((local / rel, remote / rel, "out") if newer_local
                                 else (remote / rel, local / rel, "in"))
            continue

        if l_changed and not r_changed:
            if l_entry is None:
                plan_delete.append((remote / rel, "remote"))
            else:
                plan_copy.append((local / rel, remote / rel, "out"))
        elif r_changed and not l_changed:
            if r_entry is None:
                plan_delete.append((local / rel, "local"))
            else:
                plan_copy.append((remote / rel, local / rel, "in"))
        elif l_changed and r_changed:
            # toccato dai due lati: una modifica batte sempre una cancellazione
            # (cancellare non lascia una data con cui confrontarsi)
            if l_entry is None:
                plan_copy.append((remote / rel, local / rel, "in"))
                conflicts.append(tf("conf.deleted.here", rel=rel))
            elif r_entry is None:
                plan_copy.append((local / rel, remote / rel, "out"))
                conflicts.append(tf("conf.deleted.there", rel=rel))
            elif conflict == "keep_both":
                conflicts.append(tf("conf.both", rel=rel))
                plan_copy.append((remote / rel, _conflict_name(local / rel, "chiavetta"), "in"))
                plan_copy.append((local / rel, remote / rel, "out"))
            else:
                # vince il piu' recente
                if l_entry[1] >= r_entry[1]:
                    plan_copy.append((local / rel, remote / rel, "out"))
                    conflicts.append(tf("conf.local", rel=rel))
                else:
                    plan_copy.append((remote / rel, local / rel, "in"))
                    conflicts.append(tf("conf.remote", rel=rel))

    # rete di sicurezza: una valanga di cancellazioni e' quasi sempre un errore
    # (cartella sbagliata, disco montato a meta', chiavetta formattata)
    tracked = max(1, len(base))
    if len(plan_delete) > DELETE_GUARD_MIN and len(plan_delete) / tracked > DELETE_GUARD_RATIO:
        log(tf("sync.massdelete", n=len(plan_delete), totale=tracked))
        stats["skipped_deletes"] += len(plan_delete)
        plan_delete = []

    if dry_run:
        stats["planned"] += len(plan_copy) + len(plan_delete)
        return

    for src, dst, direction in plan_copy:
        _copy_file(src, dst, stats, "in" if direction == "in" else "out")

    for target, side in plan_delete:
        base = local if side == "local" else remote
        rel = target.relative_to(base).as_posix()
        try:
            if os.path.exists(L(target)):
                finito = to_trash(base, rel)
                annota(stats, "cestino", originale=target, salvato=finito)
            stats["deleted_local" if side == "local" else "deleted_remote"] += 1
        except OSError as exc:
            log(tf("err.trash.one", path=target, err=exc))
            annota(stats, "errore", path=target, msg=exc)
            stats["errors"] += 1

    _prune_empty(local)
    _prune_empty(remote)

    if conflicts:
        stats["conflicts"] += len(conflicts)
        for name in conflicts[:10]:
            log(tf("sync.conflict", testo=name))
        if len(conflicts) > 10:
            log(tf("sync.conflict.more", n=len(conflicts) - 10))
        stats["conflict_names"].extend(conflicts)

    _save_state(state_file, _index(local, excludes))


def new_sync_stats() -> dict:
    return {"in": 0, "out": 0, "deleted_local": 0, "deleted_remote": 0,
            "conflicts": 0, "errors": 0, "bytes": 0, "planned": 0,
            "skipped_deletes": 0, "conflict_names": []}


def run_sync(root: Path, cfg: dict, plan: dict, pc: str) -> tuple[str, dict] | None:
    """Sincronizza le coppie di cartelle dichiarate nella sezione "sync"."""
    pairs = plan.get("sync") or []
    if isinstance(pairs, dict):
        pairs = [pairs]
    if not pairs:
        return None

    log(tf("sync.start", root=root))
    started = time.time()
    stats = new_sync_stats()

    for item in pairs:
        if not isinstance(item, dict) or not item.get("local"):
            continue
        local = Path(str(item["local"])).expanduser()
        on_stick = str(item.get("on_stick") or f"sync/{local.name}").replace("\\", "/").strip("/")
        remote = root / on_stick
        excludes = (list(cfg.get("default_exclude", []))
                    + list(SYNC_DEFAULT_EXCLUDE)
                    + list(item.get("exclude") or []))
        if not local.is_dir():
            if item.get("create_local"):
                local.mkdir(parents=True, exist_ok=True)
            else:
                log(tf("skip.missing.local", path=local))
                stats["errors"] += 1
                continue
        log(tf("sync.pair", local=local, remote=remote))
        try:
            sync_pair(local, remote, excludes, stats,
                      conflict=str(item.get("conflict") or plan.get("conflict") or "newest"))
        except Exception as exc:
            log(tf("err.sync", path=local, err=exc))
            stats["errors"] += 1

    elapsed = time.time() - started
    mb = stats["bytes"] / (1024 * 1024)
    summary = tf("sync.summary", presi=stats["in"], mandati=stats["out"],
                 mb=f"{mb:.1f}",
                 cestinati=stats["deleted_local"] + stats["deleted_remote"],
                 conflitti=stats["conflicts"], errori=stats["errors"],
                 secondi=f"{elapsed:.1f}")
    log(tf("sync.end", pc=pc, summary=summary))
    if stats["conflicts"]:
        log(tf("sync.conflicts.summary", n=stats["conflicts"]))
    return (f"{pc} (sync)", {"eventi": stats.get("eventi", []),
                             "eventi_persi": stats.get("eventi_persi", 0),
                             "copied": stats["in"] + stats["out"],
                             "skipped": 0, "deleted": stats["deleted_local"] + stats["deleted_remote"],
                             "errors": stats["errors"], "bytes": stats["bytes"]})


def _inside(path: Path, container: Path) -> bool:
    try:
        p = path.resolve()
        c = container.resolve()
    except OSError:
        p, c = path, container
    return p == c or c in p.parents


# --------------------------------------------------------------------------
# orchestrazione per volume
# --------------------------------------------------------------------------

def handle_volume(root: Path, cfg: dict, removable: bool) -> bool:
    priorita_bassa(True)
    try:
        return _handle_volume(root, cfg, removable)
    finally:
        priorita_bassa(False)
        _freno_sospeso.clear()              # il permesso valeva per un giro solo


def _handle_volume(root: Path, cfg: dict, removable: bool) -> bool:
    label = volume_label(root)
    results: list[tuple[str, dict]] = []
    started = time.time()

    stick = read_stick_plan(root)
    if stick:
        res = run_stick_plan(root, cfg, stick)
        if res:
            results.append(res)

    for plan in piani_per_volume(cfg, root, label, removable):
        pc = machine_name(plan)
        for runner in (run_sync, run_pull, run_push):
            if stop_requested() or not os.path.exists(L(root)):
                break
            try:
                res = runner(root, cfg, plan, pc)
            except Exception as exc:
                log(tf("err.plan", piano=runner.__name__, err=exc))
                continue
            if res:
                results.append(res)

    _last_run[str(root)] = time.time()

    if not results:
        return False

    total = new_stats()
    for _, stats in results:
        for key in total:
            total[key] += stats[key]
    parts = " | ".join(
        f"{name}: {s['copied']} copiati, {s['errors']} errori" for name, s in results)
    log(tf("vol.summary", label=label, parts=parts))

    eventi: list[dict] = []
    persi = 0
    versioni = 0
    freno = None
    sparito = False
    for _, singolo in results:
        eventi.extend(singolo.get("eventi", []))
        persi += int(singolo.get("eventi_persi", 0))
        versioni += int(singolo.get("versioned", 0))
        freno = freno or singolo.get("freno")
        sparito = sparito or bool(singolo.get("disco_sparito"))
    if not sparito and cfg.get("save_settings_on_disk", True):
        salva_impostazioni_sul_disco(root, cfg)
    voce = {
        "quando": datetime.now().isoformat(timespec="seconds"),
        "volume": label,
        "root": str(root),
        "freno": freno,
        "disco_sparito": sparito,
        "serial": volume_serial(root),
        "piani": [name for name, _ in results],
        "copiati": total["copied"],
        "invariati": total["skipped"],
        "cestinati": total["deleted"],
        "versioni": versioni,
        "errori": total["errors"],
        "byte": total["bytes"],
        "secondi": round(time.time() - started, 1),
        "eventi": eventi[:EVENTI_MAX],
        "eventi_persi": persi + max(0, len(eventi) - EVENTI_MAX),
    }
    record_history(voce)
    for sink in _run_sinks:
        try:
            sink(voce)
        except Exception:
            pass
    if cfg.get("notify"):
        mb = total["bytes"] / (1024 * 1024)
        notify(f"Backup {label}",
               f"{total['copied']} file ({mb:.1f} MB), {total['errors']} errori")
    return True


# --------------------------------------------------------------------------
# watcher
# --------------------------------------------------------------------------

def wait_ready(root: Path, timeout: float = 20.0) -> bool:
    """Il volume puo' comparire prima di essere leggibile: aspetta."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if root.is_dir():
                os.listdir(root)
                return True
        except OSError:
            pass
        time.sleep(1)
    return False


_last_run: dict[str, float] = {}     # volume -> quando e' stato elaborato l'ultima volta
_misses: dict[str, int] = {}         # volume -> quanti giri di fila risulta assente


def scan_once(cfg: dict, known: set[str] | None = None) -> set[str]:
    include_fixed = bool(cfg.get("include_fixed_drives", True))
    current = {str(path): (path, removable)
               for path, removable in list_volumes(include_fixed)}
    known = set() if known is None else set(known)
    cooldown = float(cfg.get("rescan_cooldown_minutes", 15)) * 60
    tolerate = max(1, int(cfg.get("missing_polls_before_removed", 3)))

    for key, (root, removable) in current.items():
        _misses.pop(key, None)
        if key in known:
            continue
        known.add(key)
        # Un disco che "sparisce" per un attimo (risparmio energetico USB) e
        # torna non deve far ripartire da capo un giro da mezz'ora.
        since = time.time() - _last_run.get(key, 0.0)
        if since < cooldown:
            log(tf("vol.cooldown", root=root, quando=human_time(since), minuti=int(cooldown / 60)))
            continue
        if not wait_ready(root):
            log(tf("vol.unreadable", root=root))
            continue
        try:
            handle_volume(root, cfg, removable)
        except Exception as exc:
            log(tf("err.backup", root=root, err=exc))

    for key in list(known):
        if key in current:
            continue
        _misses[key] = _misses.get(key, 0) + 1
        if _misses[key] >= tolerate:     # assente per piu' giri di fila: staccato davvero
            known.discard(key)
            _misses.pop(key, None)
            log(tf("vol.removed", root=key))
    return known


def watch(cfg: dict, stop_event=None) -> int:
    interval = max(1, int(cfg.get("poll_seconds", 3)))
    log(tf("watch.start", interval=interval, dest=dest_root_of(cfg)))

    presenti = list_volumes(bool(cfg.get("include_fixed_drives", True)))
    if presenti:
        elenco = ", ".join(f"{p} ({volume_label(p)})" for p, _ in presenti)
        log(tf("watch.present", elenco=elenco))
    else:
        log(tf("watch.none"))

    # Di default si parte lavorando anche su quelli gia' collegati: aspettare
    # che l'utente stacchi e riattacchi il disco non ha senso. Il riposo per
    # volume evita comunque di rifare due volte lo stesso giro.
    known = set() if cfg.get("run_on_start", True) else {str(p) for p, _ in presenti}
    # riga di cortesia ogni tanto: non fa nessun lavoro, dice solo che e' vivo.
    # 0 = niente righe
    heartbeat = float(cfg.get("heartbeat_minutes", 0)) * 60
    last_beat = time.time()
    try:
        while not (stop_event is not None and stop_event.is_set()):
            known = scan_once(cfg, known)
            if heartbeat > 0 and time.time() - last_beat >= heartbeat:
                last_beat = time.time()
                log(tf("watch.idle", n=len(known)))
            if stop_event is not None:
                if stop_event.wait(interval):
                    break
            else:
                time.sleep(interval)
    except KeyboardInterrupt:
        pass
    log(tf("watch.stop"))
    return 0


# --------------------------------------------------------------------------
# ripristino da __deleted e __versions
# --------------------------------------------------------------------------

_ORARIO_NEL_NOME = re.compile(r"\.(\d{8}-\d{6})(?:-\d+)?$")


def origine_di(salvato: Path) -> tuple[Path, Path, str] | None:
    """Da un file in __deleted o __versions ricava (radice, posto d'origine, tipo).

    La radice e' la cartella che contiene __deleted/__versions; il posto
    d'origine e' lo stesso percorso relativo, senza l'orario che il nome
    si e' preso quando e' stato messo da parte.
    """
    parti = list(Path(salvato).parts)
    for indice, parte in enumerate(parti):
        if parte in (TRASH_DIR, VERSIONS_DIR):
            radice = Path(*parti[:indice])
            relativo = Path(*parti[indice + 1:])
            nome = _ORARIO_NEL_NOME.sub("", relativo.stem) + relativo.suffix
            tipo = "cestino" if parte == TRASH_DIR else "versione"
            return radice, radice / relativo.parent / nome, tipo
    return None


def elenca_recuperabili(radice: Path, limite: int = 5000) -> list[dict]:
    """Tutto quello che si puo' ripristinare sotto una cartella."""
    trovati: list[dict] = []
    for cartella_corrente, sottocartelle, _file in os.walk(L(radice)):
        for speciale in (TRASH_DIR, VERSIONS_DIR):
            if speciale not in sottocartelle:
                continue
            for dentro, _dirs, nomi in os.walk(os.path.join(cartella_corrente, speciale)):
                for nome in nomi:
                    completo = os.path.join(dentro, nome)
                    salvato = Path(completo[len(_PREFISSO_LUNGO):]
                                   if completo.startswith(_PREFISSO_LUNGO) else completo)
                    origine = origine_di(salvato)
                    if origine is None:
                        continue
                    _radice, originale, tipo = origine
                    try:
                        info = os.stat(completo)
                    except OSError:
                        continue
                    orario = _ORARIO_NEL_NOME.search(salvato.stem)
                    trovati.append({
                        "tipo": tipo,
                        "salvato": str(salvato),
                        "originale": str(originale),
                        "quando": (datetime.strptime(orario.group(1), "%Y%m%d-%H%M%S")
                                   .isoformat(timespec="seconds") if orario else
                                   datetime.fromtimestamp(info.st_mtime)
                                   .isoformat(timespec="seconds")),
                        "byte": info.st_size,
                    })
                    if len(trovati) >= limite:
                        return trovati
        # dentro __deleted e __versions non si scende: li abbiamo gia' letti
        sottocartelle[:] = [d for d in sottocartelle if d not in (TRASH_DIR, VERSIONS_DIR)]
    trovati.sort(key=lambda voce: voce["quando"], reverse=True)
    return trovati


def ripristina(salvato: Path, originale: Path | None = None) -> Path:
    """Rimette a posto un file messo da parte. Non sovrascrive mai niente.

    Se al posto d'origine nel frattempo c'e' un altro file, quello va nelle
    versioni prima di essere sostituito: il ripristino non deve diventare a
    sua volta un modo di perdere dati.
    """
    salvato = Path(salvato)
    origine = origine_di(salvato)
    if origine is None:
        raise ValueError(f"{salvato} non sta in {TRASH_DIR} ne' in {VERSIONS_DIR}")
    radice, dedotto, _tipo = origine
    bersaglio = Path(originale) if originale else dedotto
    if not os.path.exists(L(salvato)):
        raise FileNotFoundError(str(salvato))
    if os.path.exists(L(bersaglio)):
        to_versions(radice, bersaglio.relative_to(radice).as_posix())
    os.makedirs(L(bersaglio.parent), exist_ok=True)
    shutil.move(L(salvato), L(bersaglio))
    log(tf("restored", path=bersaglio))
    return bersaglio


# --------------------------------------------------------------------------
# verifica completa
# --------------------------------------------------------------------------

def coppie_del_volume(root: Path, cfg: dict, removable: bool = True) -> list[tuple[str, Path, Path, list[str]]]:
    """Le coppie (sorgente, copia) che i piani producono per questo disco.

    Stessa logica dei giri veri: serve alla verifica completa per sapere cosa
    confrontare con cosa. La sincronizzazione a due vie resta fuori: li' non
    c'e' un originale e una copia, ma due lati alla pari.
    """
    coppie: list[tuple[str, Path, Path, list[str]]] = []
    root = Path(root)

    spec = read_stick_plan(root)
    if spec:
        nome = safe_name(str(spec.get("name") or volume_label(root)))
        base = Path(str(spec.get("dest_root") or cfg["dest_root"])).expanduser() / nome
        for rel, alias in resolve_entries(spec, absolute=False):
            coppie.append((nome, root / rel if rel else root,
                           base / alias if alias else base, _excludes_for(cfg, spec)))

    for piano in piani_per_volume(cfg, root, volume_label(root), removable):
        pc = machine_name(piano)
        pull = piano.get("pull") or {}
        if pull.get("folders"):
            base = (Path(str(pull["dest"])).expanduser() if pull.get("dest")
                    else dest_root_of(cfg) / safe_name(volume_label(root)))
            for rel, alias in resolve_entries(pull, absolute=False):
                coppie.append(("pull", root / rel if rel else root,
                               base / alias if alias else base, _excludes_for(cfg, pull)))
        push = piano.get("push") or {}
        if push.get("folders"):
            sotto = str(push.get("target_subdir", "backup")).strip("/\\")
            base = (root / sotto) if sotto else root
            if push.get("use_pc_folder", True):
                base = base / pc
            for sorgente, alias in resolve_entries(push, absolute=True):
                coppie.append(("push", Path(sorgente).expanduser(),
                               base / alias if alias else base, _excludes_for(cfg, push)))
    return coppie


def verifica_completa(root: Path, cfg: dict, removable: bool = True) -> dict:
    """Ricontrolla *tutto* il backup di un disco contro gli originali.

    La verifica a campione guarda l'1% di quello che copia; questa guarda ogni
    file, con l'impronta sha256. Lenta, da fare ogni tanto - prima di fidarsi
    di un disco vecchio. Non modifica niente: segnala e basta.
    """
    stats = new_stats()
    stats.update({"verificati": 0, "diversi": 0, "mancanti": 0})
    coppie = coppie_del_volume(root, cfg, removable)
    if not coppie:
        log(tf("verify.full.nothing", root=root))
        return stats

    elenco: list[tuple[Path, Path, int]] = []
    for _nome, sorgente, copia, esclusi in coppie:
        for rel, (dimensione, _data) in _index(sorgente, esclusi).items():
            elenco.append((sorgente / rel, copia / rel, dimensione))
    progresso = Progress(t("verifica"), len(elenco), sum(d for *_x, d in elenco))
    log(tf("verify.full.start", n=len(elenco), root=root))
    priorita_bassa(True)
    try:
        for originale, copia, dimensione in elenco:
            if stop_requested():
                log(tf("stopped", n=stats["verificati"]))
                break
            try:
                if not os.path.exists(L(copia)):
                    stats["mancanti"] += 1
                    annota(stats, "errore", path=copia, msg="missing")
                elif (os.stat(L(copia)).st_size != dimensione
                      or file_digest(originale) != file_digest(copia)):
                    stats["diversi"] += 1
                    annota(stats, "errore", path=copia, msg="verify")
                else:
                    stats["verificati"] += 1
            except OSError as exc:
                if _radice_sparita(Path(root)):
                    log(tf("disk.gone", n=stats["verificati"]))
                    break
                stats["errors"] += 1
                annota(stats, "errore", path=copia, msg=exc)
            progresso.advance(dimensione, copied=True)
    finally:
        priorita_bassa(False)
    progresso.finish()
    log(tf("verify.full.end", ok=stats["verificati"], diversi=stats["diversi"],
           mancanti=stats["mancanti"], errori=stats["errors"]))
    return stats


# --------------------------------------------------------------------------
# disinstallazione
# --------------------------------------------------------------------------

def disinstalla(togli_impostazioni: bool = False) -> list[str]:
    """Toglie quello che il programma ha sparso nel sistema.

    Avvio automatico e collegamenti; a scelta anche config.json. I backup, il
    piano del PC e le copie sui dischi non si toccano mai: sono i tuoi dati.
    """
    fatti: list[str] = []
    if uninstall_autostart() == 0:
        fatti.append(t("avvio automatico"))
    if IS_WIN:
        script = (
            "foreach ($d in @([Environment]::GetFolderPath('Programs'), "
            "                 [Environment]::GetFolderPath('Desktop'))) { "
            "  $p = Join-Path $d 'USB Backup.lnk'; "
            "  if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p; $p } }"
        )
        esito = run_hidden(["powershell", "-NoProfile", "-Command", script],
                           capture_output=True, text=True)
        fatti += [riga.strip() for riga in (esito.stdout or "").splitlines() if riga.strip()]
    if togli_impostazioni and CONFIG_PATH.exists():
        CONFIG_PATH.unlink()
        fatti.append(str(CONFIG_PATH))
    for cosa in fatti:
        log(tf("uninstalled", cosa=cosa))
    return fatti


# --------------------------------------------------------------------------
# collegamenti nel menu Start e sul desktop
# --------------------------------------------------------------------------

def crea_collegamenti(cartelle: list[Path] | None = None,
                      luoghi: tuple[str, ...] = ("Programs", "Desktop")) -> list[Path]:
    """Collegamenti per aprire l'app come una qualsiasi altra.

    Dall'eseguibile puntano all'eseguibile; dal sorgente a pythonw con
    usb_backup_qt.py, senza finestra nera - la strada che funziona anche
    quando Smart App Control blocca l'exe non firmato.
    """
    if not IS_WIN:
        log(tf("shortcuts.only.windows"))
        return []
    if getattr(sys, "frozen", False):
        bersaglio, argomenti, icona = sys.executable, "", sys.executable + ",0"
    else:
        bersaglio = _python_exe()
        argomenti = f'"{APP_DIR / "usb_backup_qt.py"}"'
        icona = str(APP_DIR / "assets" / "icon.ico")
    script = (
        "$w = New-Object -ComObject WScript.Shell; "
        "$fatti = @(); "
        "$dove = if ($env:UB_DIRS) { $env:UB_DIRS -split '[|]' } else { "
        "  $env:UB_SPECIAL -split '[|]' | ForEach-Object { "
        "    [Environment]::GetFolderPath($_) } }; "
        "foreach ($d in $dove) { "
        "  $p = Join-Path $d 'USB Backup.lnk'; "
        "  $s = $w.CreateShortcut($p); "
        "  $s.TargetPath = $env:UB_TARGET; $s.Arguments = $env:UB_ARGS; "
        "  $s.WorkingDirectory = $env:UB_DIR; $s.IconLocation = $env:UB_ICON; "
        "  $s.Description = 'USB Backup'; $s.Save(); $fatti += $p }; "
        "$fatti -join [Environment]::NewLine"
    )
    ambiente = dict(os.environ, UB_TARGET=bersaglio, UB_ARGS=argomenti,
                    UB_DIR=str(APP_DIR), UB_ICON=icona,
                    UB_DIRS="|".join(str(c) for c in (cartelle or [])),
                    UB_SPECIAL="|".join(luoghi))
    esito = run_hidden(["powershell", "-NoProfile", "-Command", script],
                       capture_output=True, text=True, env=ambiente)
    fatti = [Path(r.strip()) for r in (esito.stdout or "").splitlines() if r.strip()]
    for percorso in fatti:
        log(tf("shortcut.made", path=percorso))
    if esito.returncode != 0:
        log(tf("err.shortcut", err=(esito.stderr or "").strip()[-200:]))
    return fatti


# --------------------------------------------------------------------------
# autostart
# --------------------------------------------------------------------------

TASK_NAME = "USB Backup Watcher"
PLIST_LABEL = "com.usbbackup.watcher"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"


def _python_exe(windowless: bool = True) -> str:
    exe = Path(sys.executable)
    if IS_WIN and windowless:
        pyw = exe.with_name("pythonw.exe")
        if pyw.exists():
            return str(pyw)
    return str(exe)


def launch_args(gui: bool = False) -> list[str]:
    """Programma e argomenti da far ripartire al login.

    - dall'eseguibile: l'eseguibile stesso, che riapre l'app nella tray
    - dal sorgente, chiesto dall'app: l'app nella tray (e se Smart App
      Control blocca l'exe non firmato, questa e' la strada)
    - dal sorgente, da riga di comando: il watcher senza interfaccia

    `--tray` fa partire l'app direttamente nella tray: all'accensione del
    computer nessuno vuole una finestra che si apre da sola.
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, "--tray"]
    if gui:
        return [_python_exe(), str(APP_DIR / "usb_backup_qt.py"), "--tray"]
    return [_python_exe(), str(APP_DIR / "usb_backup.py"), "--watch"]


def launch_command(gui: bool = False) -> str:
    return " ".join(f'"{pezzo}"' if not pezzo.startswith("--") else pezzo
                    for pezzo in launch_args(gui))


def _normalizza_comando(testo: str) -> str:
    return " ".join(testo.replace('"', " ").lower().split())


# Su Windows l'avvio automatico sta nella chiave Run del registro dell'utente.
# Un'attivita' pianificata con avvio al login si crea solo da amministratore
# ("Accesso negato" da utente normale): la chiave Run no, ed e' quella che
# Gestione attivita' mostra fra le app di avvio, dove si puo' anche spegnere.
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "USB Backup"


def _run_leggi() -> str | None:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as chiave:
            valore, _tipo = winreg.QueryValueEx(chiave, RUN_NAME)
            return str(valore)
    except OSError:
        return None


def _run_scrivi(comando: str) -> None:
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as chiave:
        winreg.SetValueEx(chiave, RUN_NAME, 0, winreg.REG_SZ, comando)


def _run_cancella() -> None:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as chiave:
            winreg.DeleteValue(chiave, RUN_NAME)
    except FileNotFoundError:
        pass


def autostart_registrato() -> str | None:
    """Il comando che parte al login, se c'e' (None se non e' registrato)."""
    if IS_WIN:
        return _run_leggi()
    if IS_MAC:
        if not PLIST_PATH.exists():
            return None
        pezzi = re.findall(r"<string>(.*?)</string>", PLIST_PATH.read_text(encoding="utf-8"))
        return " ".join(p for p in pezzi if p != PLIST_LABEL and "launchagent.log" not in p)
    return None


def sync_autostart(cfg: dict) -> str:
    """Allinea l'avvio automatico a quello che dice la configurazione.

    Di default e' acceso: l'app si registra da sola al primo avvio. Se nel
    frattempo il programma e' stato spostato, la registrazione viene
    rifatta con il percorso nuovo. Ritorna cosa ha fatto.
    """
    voluto = bool(cfg.get("autostart", True))
    attuale = autostart_registrato()
    if not voluto:
        if attuale is None:
            return "spento"
        uninstall_autostart()
        log(tf("autostart", cosa=t("rimosso"), codice=0))
        return "rimosso"
    atteso = launch_command(gui=True)
    if attuale is not None and _normalizza_comando(attuale) == _normalizza_comando(atteso):
        return "a posto"
    codice = install_autostart(gui=True)
    # "installato" solo se e' vero: prima il log lo diceva anche quando il
    # sistema aveva rifiutato, e per mesi nessuno se n'e' accorto
    log(tf("autostart", cosa=t("installato") if codice == 0 else t("non riuscito"),
           codice=codice))
    return "installato" if codice == 0 else "errore"


def install_autostart(gui: bool = False) -> int:
    if IS_WIN:
        try:
            _run_scrivi(launch_command(gui))
        except OSError as exc:
            log(tf("err.autostart", err=exc))
            return 1
        return 0
    if IS_MAC:
        PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        log_out = Path(load_config()["log_file"]).expanduser().parent / "launchagent.log"
        log_out.parent.mkdir(parents=True, exist_ok=True)
        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{PLIST_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    {"".join(f"<string>{pezzo}</string>" for pezzo in launch_args(gui))}
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key>{"<false/>" if gui or getattr(sys, "frozen", False) else "<true/>"}
  <key>StandardOutPath</key><string>{log_out}</string>
  <key>StandardErrorPath</key><string>{log_out}</string>
</dict>
</plist>
"""
        PLIST_PATH.write_text(plist, encoding="utf-8")
        run_hidden(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
        res = run_hidden(["launchctl", "load", str(PLIST_PATH)],
                             capture_output=True, text=True)
        print((res.stdout or res.stderr).strip() or f"OK, installato: {PLIST_PATH}")
        return res.returncode
    print("Autostart automatico supportato solo su Windows e macOS.")
    return 1


def uninstall_autostart() -> int:
    if IS_WIN:
        try:
            _run_cancella()
        except OSError as exc:
            log(tf("err.autostart", err=exc))
            return 1
        return 0
    if IS_MAC:
        run_hidden(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
        PLIST_PATH.unlink(missing_ok=True)
        print(f"Rimosso: {PLIST_PATH}")
        return 0
    return 1


# --------------------------------------------------------------------------

def cmd_list(cfg: dict) -> int:
    plan = read_pc_plan(cfg)
    pc = machine_name(plan)
    piani = piani_del_pc(plan)
    print(f"PC: {pc}")
    print(f"dest_root: {dest_root_of(cfg)}")
    if plan:
        print(f"piano PC: {dest_root_of(cfg) / MARKER_NAME} ({len(piani)} piani)")
        for n, piano in enumerate(piani, 1):
            sezioni = [s for s in ("push", "pull", "sync") if piano.get(s)]
            filtro = piano.get("only_serials") or piano.get("only_volumes") or "chiavette rimovibili"
            print(f"  {n}. {filtro}: {', '.join(sezioni) or 'nessuna sezione'}")
    else:
        print(f"piano PC: assente ({dest_root_of(cfg) / MARKER_NAME})")
    print("-" * 60)
    vols = list_volumes(bool(cfg.get("include_fixed_drives", True)))
    if not vols:
        print("nessun volume rilevato")
        return 0
    for root, removable in vols:
        label = volume_label(root)
        flags = []
        flags.append("rimovibile" if removable else "fisso")
        flags.append("backup.json OK" if (root / MARKER_NAME).is_file() else "no backup.json")
        quanti = sum(volume_matches(p, root, label, removable) for p in piani)
        if quanti:
            flags.append("piano PC applicabile" if quanti == 1 else f"{quanti} piani PC applicabili")
        print(f"{root}\t{label}\t{', '.join(flags)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Backup automatico delle chiavette USB.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--watch", action="store_true", help="resta in ascolto (default)")
    g.add_argument("--once", action="store_true",
                   help="lavora subito sui volumi gia' collegati ed esci")
    g.add_argument("--list", action="store_true", help="elenca i volumi rilevati ed esci")
    g.add_argument("--install", action="store_true", help="avvio automatico al login")
    g.add_argument("--uninstall", action="store_true", help="rimuovi avvio automatico")
    ap.add_argument("--dest", help="dest_root alternativa (override del config)")
    args = ap.parse_args(argv)

    if args.install:
        return install_autostart()
    if args.uninstall:
        return uninstall_autostart()

    cfg = load_config()
    if args.dest:
        cfg["dest_root"] = args.dest
    setup_log(cfg.get("log_file"))

    if args.list:
        return cmd_list(cfg)
    if args.once:
        scan_once(cfg, set())
        return 0
    return watch(cfg)


if __name__ == "__main__":
    sys.exit(main())
