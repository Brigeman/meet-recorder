"""Entry point — delegates to Desktop Meeting Recorder (winrec)."""

from winrec.gui.app import run_gui


def main():
    raise SystemExit(run_gui())


if __name__ == "__main__":
    main()
