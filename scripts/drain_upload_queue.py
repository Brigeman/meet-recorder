#!/usr/bin/env python3
"""Drain pending Calls upload queue once (dev / verification)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from meetrec.calls.client import build_call_title, compute_duration_sec, upload_call
from meetrec.calls.queue import list_pending_jobs, pending_count, process_job
from meetrec.config import load_config


def main() -> int:
    cfg = load_config()
    token = (cfg.get("calls_device_token") or "").strip()
    if not cfg.get("calls_setup_completed") or not token:
        print("Calls not paired — run scripts/pair_calls.py first", file=sys.stderr)
        return 2

    before = pending_count()
    print(f"Pending uploads: {before}")
    if before == 0:
        return 0

    results = {"success": 0, "failed": 0, "retry": 0, "busy": 0}
    for job in list_pending_jobs():
        result = process_job(
            job,
            token=token,
            upload_fn=upload_call,
            build_title_fn=build_call_title,
            duration_fn=compute_duration_sec,
        )
        results[result] = results.get(result, 0) + 1
        print(f"  job {job.get('job_id', '')[:8]}… -> {result}")

    after = pending_count()
    print(f"Done. Pending now: {after} ({results})")
    return 0 if after < before else 1


if __name__ == "__main__":
    raise SystemExit(main())
