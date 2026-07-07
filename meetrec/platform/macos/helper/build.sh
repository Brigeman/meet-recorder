#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

# System audio (loopback) helper — ScreenCaptureKit.
OUT="${1:-$ROOT/MeetRecSystemAudio}"
swiftc -O -framework ScreenCaptureKit -framework AVFoundation -framework CoreMedia -framework Foundation \
  "$ROOT/SystemAudioCapture.swift" -o "$OUT"
echo "Built $OUT"

# Voice Processing I/O microphone helper — native OS-grade AEC at capture time.
MIC_OUT="${2:-$ROOT/MeetRecVoiceMic}"
swiftc -O -framework AVFoundation -framework Foundation \
  "$ROOT/VoiceProcessingMic.swift" -o "$MIC_OUT"
echo "Built $MIC_OUT"
