#!/bin/bash
# Avvia l'applicazione su macOS (rendere eseguibile: chmod +x start_gui.command)
cd "$(dirname "$0")"
exec python3 usb_backup_qt.py
