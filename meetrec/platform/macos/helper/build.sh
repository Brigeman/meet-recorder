#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:-$ROOT/MeetRecSystemAudio}"
swiftc -O -framework ScreenCaptureKit -framework AVFoundation -framework CoreMedia -framework Foundation \
  "$ROOT/SystemAudioCapture.swift" -o "$OUT"
echo "Built $OUT"
