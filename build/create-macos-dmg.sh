#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="Desktop Meeting Recorder"
APP_PATH="$ROOT/dist/${APP_NAME}.app"
OUT_NAME="${1:-DesktopMeetingRecorder-macos.dmg}"

if [[ ! -d "$APP_PATH" ]]; then
  echo "App bundle not found: $APP_PATH" >&2
  exit 1
fi

echo "Signing nested Mach-O binaries..."
while IFS= read -r -d '' binary; do
  codesign --force --sign - "$binary" 2>/dev/null || true
done < <(find "$APP_PATH/Contents" -type f -print0 | while IFS= read -r -d '' f; do
  if file "$f" | grep -q 'Mach-O'; then printf '%s\0' "$f"; fi
done)

echo "Signing app bundle..."
codesign --force --deep --sign - "$APP_PATH"
codesign --verify --deep --strict "$APP_PATH"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

cp -R "$APP_PATH" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
cp "$ROOT/build/macos-first-launch.txt" "$STAGE/Первый запуск.txt"
cp "$ROOT/build/Install.command" "$STAGE/Install.command"
chmod +x "$STAGE/Install.command"
xattr -cr "$STAGE" 2>/dev/null || true

OUT_PATH="$ROOT/$OUT_NAME"
rm -f "$OUT_PATH"

hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder "$STAGE" \
  -ov \
  -format UDZO \
  "$OUT_PATH"

echo "Created $OUT_PATH"
