#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 not found"
  exit 1
fi

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f "meetrec/platform/macos/helper/MeetRecSystemAudio" ]; then
  bash meetrec/platform/macos/helper/build.sh
fi

python3 -m meetrec
