# Desktop Meeting Recorder

Desktop app that detects likely meeting starts and asks whether to record — **never auto-records**.

When signals suggest a call (Teams, Zoom, Meet in browser, etc.), a compact prompt appears. Recording starts only after you click **Записать**. A floating panel shows timer, mini waveform, and **Stop**.

**Platforms:** Windows 10/11 and macOS 13+ (Apple Silicon).

## Features

- Prompt-before-record (no silent auto-start)
- Multi-process architecture: GUI, detector, recorder (crash isolation)
- Audio-first + context scoring (mic, loopback, apps, browser meetings)
- Dual capture: system audio + microphone → mixed WAV
- Optional MP3/M4A/FLAC/… via FFmpeg
- Sidecar JSON metadata per recording
- Menu bar / system tray controls
- GitHub Release builds on tag push (`v*`)

## macOS — установка

> Полная инструкция: **[docs/macos-setup.md](docs/macos-setup.md)**

1. Скачайте **`DesktopMeetingRecorder-vX.Y.Z-macos.dmg`** из [Releases](https://github.com/Brigeman/meet-recorder/releases).
2. Откройте DMG → дважды кликните **`Install.command`** (или перетащите `.app` в **Applications**).
3. Если macOS блокирует — снимите карантин:

```bash
xattr -dr com.apple.quarantine "/Applications/Desktop Meeting Recorder.app"
open "/Applications/Desktop Meeting Recorder.app"
```

4. Разрешите **Микрофон**, **Запись экрана** и **Универсальный доступ**.
5. Иконка появится в **строке меню** (в Dock приложения нет).

**Не запускайте `.app` прямо из DMG** — сначала скопируйте в Applications.

## Windows — Quick Start

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

- **Windows:** 10/11, Python 3.10+ (3.12 recommended)
- **macOS:** 13+ (Ventura), Apple Silicon, Python 3.12 for dev builds

## Configuration

- **Windows:** `%APPDATA%\Desktop Meeting Recorder\config.json`
- **macOS:** `~/Library/Application Support/Desktop Meeting Recorder/config.json`

Common keys: `prompt_threshold`, cooldowns, `recordings_dir`, `audio_format`, per-app toggles.

## Releases

Push a tag to trigger CI (macOS DMG; Windows job can be re-enabled in workflow when needed):

```bash
git tag v1.1.0
git push origin v1.1.0
```

| Platform | Artifact |
|----------|----------|
| macOS | `DesktopMeetingRecorder-vX.Y.Z-macos.dmg` |
| Windows | `DesktopMeetingRecorder-vX.Y.Z-win64.zip` (last release with Windows build) |

Windows zip contains three exe in one folder — launch **`WinRec.exe`**.

## Logs

```text
{recordings_dir}/logs/
  meetrec-gui-YYYY-MM-DD.log
  meetrec-detector-YYYY-MM-DD.log
  meetrec-recorder-YYYY-MM-DD.log
```

## Development

```bash
pip install -r requirements-dev.txt
pytest
```

macOS helpers:

```bash
bash meetrec/platform/macos/helper/build.sh
./start.sh
```

## Project layout

```text
meetrec/                  # main package (Windows + macOS)
  gui/                      # tray, prompts, panel, settings
  detector/                 # detector service + probes + scoring
  recorder/                 # recorder service + capture
  platform/                 # windows/ and macos/ adapters
  ipc/
winrec/                     # backward-compat shim → meetrec
tests/
build/macrec.spec           # macOS .app bundle
build/meetrec.spec          # Windows exe bundle
.github/workflows/release.yml
docs/macos-setup.md
```

## License

Internal / corporate use — adjust as needed.
