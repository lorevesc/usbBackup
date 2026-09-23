#!/usr/bin/env python3
"""Lancia tutte le suite di test e riassume l'esito.

    python tests/run_tests.py            tutte
    python tests/run_tests.py sync stop  solo quelle il cui nome contiene sync o stop
    python tests/run_tests.py --bench     include anche le misure di velocita'

Ogni suite gira in un processo suo: se una va in crash non si porta dietro
le altre, e nessuna puo' sporcare lo stato di quella dopo.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

QUI = Path(__file__).resolve().parent
VERDE, ROSSO, GRIGIO, FINE = "\033[32m", "\033[31m", "\033[90m", "\033[0m"


def suites(filtri: list[str], bench: bool) -> list[Path]:
    trovate = sorted(QUI.glob("test_*.py"))
    if bench:
        trovate += sorted(QUI.glob("bench_*.py"))
    if filtri:
        trovate = [f for f in trovate if any(x.lower() in f.name.lower() for x in filtri)]
    return trovate


def main() -> int:
    argomenti = [a for a in sys.argv[1:] if not a.startswith("--")]
    bench = "--bench" in sys.argv
    elenco = suites(argomenti, bench)
    if not elenco:
        print("Nessuna suite trovata.")
        return 1

    print(f"{len(elenco)} suite da eseguire\n")
    falliti: list[tuple[str, str]] = []
    inizio = time.time()

    # una casa finta: le suite che non indicano un log o una destinazione non
    # devono scrivere nel ~/Backup vero
    casa = tempfile.mkdtemp(prefix="casa_test_")
    ambiente = dict(os.environ, HOME=casa, USERPROFILE=casa)

    for suite in elenco:
        etichetta = suite.stem.replace("test_", "")
        print(f"  {etichetta:<16}", end="", flush=True)
        avvio = time.time()
        esito = subprocess.run([sys.executable, str(suite)],
                               capture_output=True, text=True, cwd=QUI, env=ambiente)
        durata = time.time() - avvio
        if esito.returncode == 0:
            ultima = [r for r in esito.stdout.strip().splitlines() if r.strip()]
            print(f"{VERDE}OK{FINE}  {GRIGIO}{durata:5.1f}s  "
                  f"{ultima[-1][:44] if ultima else ''}{FINE}")
        else:
            print(f"{ROSSO}FALLITA{FINE}  {GRIGIO}{durata:5.1f}s{FINE}")
            coda = (esito.stdout + esito.stderr).strip().splitlines()
            falliti.append((etichetta, "\n".join(coda[-12:])))

    print(f"\n{len(elenco) - len(falliti)}/{len(elenco)} passate "
          f"in {time.time() - inizio:.1f}s")

    for nome, coda in falliti:
        print(f"\n{ROSSO}--- {nome} ---{FINE}\n{coda}")
    return 1 if falliti else 0


if __name__ == "__main__":
    sys.exit(main())
