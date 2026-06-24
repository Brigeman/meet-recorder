"""Detector service — JSONL events on stdout."""

import logging
import os
import sys
import time

from meetrec.platform import ensure_native_init

ensure_native_init()

from meetrec.config import POLL_INTERVAL, load_config
from meetrec.detector.apps import list_running_meeting_pids, match_in_call_title
from meetrec.logging_util import log_event, setup_process_logging
from meetrec.detector.probes import (
    probe_audio_activity,
    probe_browser_meeting,
    probe_foreground,
    probe_meeting_app_network,
    probe_running_apps,
)
from meetrec.platform import probe_meeting_app_audio
from meetrec.detector.scoring import (
    AudioStreakTracker,
    SignalSnapshot,
    SustainTracker,
    compute_matched,
    compute_score,
    context_key,
    match_title_hint,
    primary_app,
)
from meetrec.ipc.protocol import write_jsonl_line
log = logging.getLogger(__name__)


def collect_snapshot(enable_network_probe: bool = True) -> SignalSnapshot:
    meeting_pids_map = list_running_meeting_pids()
    meeting_pids = {pid for pids in meeting_pids_map.values() for pid in pids}
    mic_peak_active, loopback_peak_active = probe_audio_activity()
    app_cap_active, app_ren_active, cap_peak, ren_peak = probe_meeting_app_audio(meeting_pids)
    if enable_network_probe:
        net_active, net_count, net_pid = probe_meeting_app_network(meeting_pids)
    else:
        net_active, net_count, net_pid = False, 0, None
    browser_meeting, browser_app, browser_tab, browser_pid = probe_browser_meeting()
    fg_app, window_title = probe_foreground()
    apps_running = probe_running_apps()
    title = window_title or browser_tab
    in_call_app, in_call = match_in_call_title(title)
    title_hint = None if in_call else match_title_hint(title)

    snap = SignalSnapshot(
        mic_active=mic_peak_active,
        loopback_active=loopback_peak_active,
        meeting_capture_active=app_cap_active,
        meeting_render_active=app_ren_active,
        meeting_network_active=net_active,
        meeting_network_count=net_count,
        apps_running=apps_running,
        foreground_app=fg_app if fg_app and fg_app in apps_running.union({fg_app}) else fg_app,
        title_hint_app=title_hint,
        in_call_title_app=in_call_app if in_call else None,
        browser_meeting=browser_meeting,
        browser_app=browser_app,
        browser_tab=browser_tab,
        browser_pid=browser_pid or (net_pid or 0),
        window_title=title,
    )
    if fg_app and fg_app not in snap.apps_running:
        snap.apps_running = apps_running | {fg_app}
    setattr(snap, "_debug_cap_peak", cap_peak)
    setattr(snap, "_debug_ren_peak", ren_peak)
    setattr(snap, "_debug_pids", meeting_pids_map)
    return snap


def run_detector() -> None:
    log_path = setup_process_logging("detector")
    log.info("detector_log_file=%s", log_path)
    cfg = load_config()
    threshold = cfg.get("prompt_threshold", 70)
    web_sustain = cfg.get("web_sustain_seconds", 2.5)
    desktop_sustain = cfg.get("desktop_sustain_seconds", 7.0)
    desktop_strong_sustain = cfg.get("desktop_strong_sustain_seconds", 4.0)
    audio_streak_threshold = cfg.get("audio_streak_seconds_for_call", 8.0)
    tracker = SustainTracker(
        threshold=threshold,
        web_sustain=web_sustain,
        desktop_sustain=desktop_sustain,
        desktop_strong_sustain=desktop_strong_sustain,
    )
    audio_streak_tracker = AudioStreakTracker(threshold_seconds=audio_streak_threshold)
    trace = os.environ.get("MEETREC_DETECTOR_TRACE", "").strip() == "1"
    log_event(
        "detector_started",
        threshold=threshold,
        web_sustain=web_sustain,
        desktop_sustain=desktop_sustain,
        desktop_strong_sustain=desktop_strong_sustain,
        audio_streak_threshold=audio_streak_threshold,
    )
    write_jsonl_line({"type": "heartbeat", "timestamp": time.time()})

    while True:
        try:
            snap = collect_snapshot(enable_network_probe=cfg.get("enable_network_probe", True))
            cap_streak, ren_streak = audio_streak_tracker.update(snap)
            matched = compute_matched(
                snap,
                cap_streak=cap_streak,
                ren_streak=ren_streak,
                audio_streak_threshold=audio_streak_threshold,
            )
            score = compute_score(
                snap,
                cap_streak=cap_streak,
                ren_streak=ren_streak,
                audio_streak_threshold=audio_streak_threshold,
            )
            sustained, sustain_elapsed = tracker.update(score, snap)
            app = primary_app(snap)
            ctx = context_key(snap)

            required_sustain = tracker.required_for(snap)
            log.info(
                "detector_tick score=%s threshold=%s sustained=%s sustain=%.1f/%.1f "
                "app=%s in_call=%s net=%s(%s) audio_app=cap:%s/ren:%s streak=%.1f/%.1f "
                "peaks=%.3f/%.3f "
                "matched=%s context_key=%s",
                score,
                threshold,
                sustained,
                sustain_elapsed,
                required_sustain,
                app,
                bool(snap.in_call_title_app),
                snap.meeting_network_active,
                snap.meeting_network_count,
                snap.meeting_capture_active,
                snap.meeting_render_active,
                cap_streak,
                ren_streak,
                getattr(snap, "_debug_cap_peak", 0.0),
                getattr(snap, "_debug_ren_peak", 0.0),
                ",".join(matched) or "-",
                ctx,
            )

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
