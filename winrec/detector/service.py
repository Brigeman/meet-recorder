"""Detector service — JSONL events on stdout."""

import logging
import os
import sys
import time

import comtypes

from winrec.config import POLL_INTERVAL, load_config, setup_logging
from winrec.detector.probes import (
    probe_audio_activity,
    probe_browser_meeting,
    probe_foreground,
    probe_running_apps,
)
from winrec.detector.scoring import (
    SignalSnapshot,
    SustainTracker,
    compute_matched,
    compute_score,
    context_key,
    match_title_hint,
    primary_app,
)
from winrec.ipc.protocol import write_jsonl_line
from winrec.logging_util import log_event

log = logging.getLogger(__name__)


def collect_snapshot() -> SignalSnapshot:
    mic_active, loopback_active = probe_audio_activity()
    browser_meeting, browser_app, browser_tab, browser_pid = probe_browser_meeting()
    fg_app, window_title = probe_foreground()
    apps_running = probe_running_apps()
    title_hint = match_title_hint(window_title)

    snap = SignalSnapshot(
        mic_active=mic_active,
        loopback_active=loopback_active,
        apps_running=apps_running,
        foreground_app=fg_app if fg_app and fg_app in apps_running.union({fg_app}) else fg_app,
        title_hint_app=title_hint,
        browser_meeting=browser_meeting,
        browser_app=browser_app,
        browser_tab=browser_tab,
        browser_pid=browser_pid,
        window_title=window_title or browser_tab,
    )
    if fg_app and fg_app not in snap.apps_running:
        snap.apps_running = apps_running | {fg_app}
    return snap


def run_detector() -> None:
    setup_logging()
    comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
    cfg = load_config()
    threshold = cfg.get("prompt_threshold", 70)
    tracker = SustainTracker(
        threshold=threshold,
        web_sustain=cfg.get("web_sustain_seconds", 2.5),
        desktop_sustain=cfg.get("desktop_sustain_seconds", 7.0),
    )
    trace = os.environ.get("WINREC_DETECTOR_TRACE", "").strip() == "1"
    log_event("detector_started")
    write_jsonl_line({"type": "heartbeat", "timestamp": time.time()})

    while True:
        try:
            snap = collect_snapshot()
            matched = compute_matched(snap)
            score = compute_score(snap)
            sustained, sustain_elapsed = tracker.update(score, snap)
            app = primary_app(snap)
            ctx = context_key(snap)

            if trace:
                log.info(
                    "signal_score | score=%s app=%s matched=%s sustain=%.1f",
                    score,
                    app,
                    ",".join(matched),
                    sustain_elapsed,
                )

            if score >= threshold and sustained:
                write_jsonl_line(
                    {
                        "type": "call_candidate",
                        "score": score,
                        "app": app,
                        "source": "audio_context",
                        "matched": matched,
                        "context_key": ctx,
                        "timestamp": time.time(),
                    }
                )
                log_event("call_candidate", score=score, app=app, context_key=ctx)
            else:
                write_jsonl_line(
                    {
                        "type": "no_call",
                        "score": score,
                        "matched": matched,
                        "timestamp": time.time(),
                    }
                )
        except Exception as e:
            log.error("detector loop error: %s", e)
            write_jsonl_line({"type": "error", "message": str(e), "timestamp": time.time()})

        time.sleep(POLL_INTERVAL)


def main() -> None:
    try:
        run_detector()
    except KeyboardInterrupt:
        pass
    finally:
        log_event("detector_stopped")


if __name__ == "__main__":
    main()
