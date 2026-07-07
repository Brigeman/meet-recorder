#!/usr/bin/env python3
"""Apply Calls pairing code from CLI (dev / headless pairing)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from meetrec.calls.pairing import PairingError, apply_pairing_to_config
from meetrec.config import load_config, save_config


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: pair_calls.py 'v1.…'", file=sys.stderr)
        return 2

    code = sys.argv[1].strip()
    cfg = load_config()
    try:
        cfg = apply_pairing_to_config(cfg, code)
    except PairingError as exc:
        print(f"Pairing failed: {exc}", file=sys.stderr)
        return 1

    save_config(cfg)
    print("Calls paired successfully")
    print(f"  device_id: {cfg.get('calls_device_id')}")
    print(f"  api:       {cfg.get('calls_api_base_url')}")
    print(f"  project:   {cfg.get('calls_default_project_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
