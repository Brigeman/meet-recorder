import sys


def _install_gui_crash_capture() -> None:
    """Frozen windowed .app has no console: sys.stderr goes nowhere and native
    aborts (SIGABRT from pyobjc/numpy/etc.) vanish without a trace. Redirect the
    real fd 1/2 to a file and point faulthandler at it so any early startup death
    — before file logging is configured — is always recorded on disk.

    GUI role only: detector/recorder rely on their stderr pipe being read by the
    parent ProcessSupervisor, so redirecting their fd 2 would swallow those logs.
    """
    import faulthandler
    import os
    from datetime import datetime

    try:
        from meetrec.logging_util import log_dir

        crash_dir = log_dir()
    except Exception:
        crash_dir = os.path.expanduser("~/Library/Logs/Desktop Meeting Recorder")
        try:
            os.makedirs(crash_dir, exist_ok=True)
        except Exception:
            return
    path = os.path.join(crash_dir, "meetrec-gui-stderr.log")
    try:
        f = open(path, "a", buffering=1, encoding="utf-8")
        os.dup2(f.fileno(), 1)
        os.dup2(f.fileno(), 2)
        sys.stdout = f
        sys.stderr = f
        faulthandler.enable(file=f, all_threads=True)
        f.write(f"\n==== gui process start pid={os.getpid()} {datetime.now().isoformat()} ====\n")
        f.flush()
    except Exception:
        pass


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("gui", "run"):
        _install_gui_crash_capture()
        from meetrec.gui.app import run_gui

        raise SystemExit(run_gui())
    if sys.argv[1] == "detector":
        from meetrec.detector.service import main as detector_main

        detector_main()
        return
    if sys.argv[1] == "recorder":
        from meetrec.recorder.service import main as recorder_main

        recorder_main()
        return
    print("Usage: python -m meetrec [gui|detector|recorder]")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
