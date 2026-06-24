import sys


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("gui", "run"):
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
