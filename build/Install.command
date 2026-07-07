#!/bin/bash
set -euo pipefail

APP_NAME="Desktop Meeting Recorder.app"
VOL="$(cd "$(dirname "$0")" && pwd)"
SRC="$VOL/$APP_NAME"
DST="/Applications/$APP_NAME"

if [[ ! -d "$SRC" ]]; then
  osascript -e 'display alert "Desktop Meeting Recorder" message "Не найдено приложение в этой папке. Откройте DMG и запустите Install.command из окна установки." as critical'
  exit 1
fi

echo "→ Копирую в Applications..."
rm -rf "$DST"
ditto "$SRC" "$DST"
xattr -cr "$DST" 2>/dev/null || true
xattr -rd com.apple.quarantine "$DST" 2>/dev/null || true
xattr -rd com.apple.provenance "$DST" 2>/dev/null || true

echo "→ Запускаю через Finder (без Terminal)..."
open "$DST"
