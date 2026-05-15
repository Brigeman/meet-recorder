# Desktop Meeting Recorder

Windows desktop app that detects likely meeting starts and asks whether to record — **never auto-records**.

When signals suggest a call (Teams, Zoom, Meet in browser, etc.), a compact glass-style prompt appears. Recording starts only after you click **Записать**. A floating capsule panel shows timer, mini waveform, and **Stop**.

## Features

- Prompt-before-record (no silent auto-start)
- Multi-process architecture: GUI, detector, recorder (crash isolation)
- Audio-first + context scoring (mic, loopback, apps, browser meetings)
- Glass meeting prompt (320×92) and floating panel (360×48)
- Dual capture: system loopback + microphone → mixed WAV
- Optional MP3/M4A/FLAC/… via FFmpeg
- Sidecar JSON metadata per recording
- System tray: Start/Stop, Open folder, Settings, Quit
- GitHub Release builds on tag push (`v*`)

## Quick Start

```bat
start.bat
```

Or manually:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m winrec
```

Subprocess modes (for debugging):

```bat
python -m winrec detector
python -m winrec recorder
```

## Requirements

- Windows 10/11
- Python 3.10+ (3.12 recommended)

## Configuration

`%APPDATA%\Desktop Meeting Recorder\config.json`

- `prompt_threshold` (default 70)
- `web_sustain_seconds` / `desktop_sustain_seconds`
- `dismiss_cooldown_seconds` / `post_stop_cooldown_seconds`
- `recordings_dir`, `audio_format`, per-app toggles

## Releases

Push a tag to trigger CI:

```bat
git tag v1.0.0
git push origin v1.0.0
```

Artifacts: zip on GitHub Releases containing **three exe in one folder**:

| File | Role |
|------|------|
| `WinRec.exe` | Main app (tray) — **launch this** |
| `WinRec.Detector.exe` | Started automatically by GUI |
| `WinRec.Recorder.exe` | Started automatically by GUI |

Unpack the zip, keep all three files together, double-click `WinRec.exe`.

## Logs

All processes write daily logs under your recordings folder:

```text
{recordings_dir}/logs/
  winrec-gui-2026-05-15.log
  winrec-detector-2026-05-15.log
  winrec-recorder-2026-05-15.log
```

Use **detector** log to see `detector_tick` (score, matched signals, sustain) and `prompt_skipped` in **gui** log when a notification was blocked.

### First release checklist

1. Create a GitHub repository and push the code (this folder is not a git repo until you run `git init`).
2. Tag and push: `git tag v1.0.0 && git push origin v1.0.0`
3. Open **Actions** → wait for `Release` workflow (tests + Windows build).
4. Download `DesktopMeetingRecorder-v1.0.0-win64.zip` from **Releases**.

Windows may show SmartScreen (unsigned build) — choose “Run anyway” for internal testing.

## Project layout

```text
meet recorder/
  winrec/                 # application package (only source tree)
    gui/                  # tray, glass prompt, floating panel, settings
    detector/             # detector service + probes + scoring
    recorder/             # recorder service + WASAPI capture
    ipc/                  # JSONL protocol, subprocess supervisor
    config.py
    __main__.py           # python -m winrec
  tests/
  main.py                 # thin entry → winrec
  start.bat
  build/winrec.spec
  .github/workflows/
```

There is **no** separate top-level `recorder/` or `ui/` — those were legacy Ghost Meet Recorder modules, now removed.

## Development

```bat
pip install -r requirements-dev.txt
pytest
```

## License

Internal / corporate use — adjust as needed.
