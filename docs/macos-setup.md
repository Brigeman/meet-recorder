# macOS setup (without Developer ID)

One-time setup on each Mac for ad-hoc / unsigned builds distributed outside the App Store.

## Install

1. Copy `Desktop Meeting Recorder.app` to `/Applications`.
2. Remove Gatekeeper quarantine (fixes `zsh: killed` on `Install.command` and blocked launch):

```bash
xattr -dr com.apple.quarantine "/Applications/Desktop Meeting Recorder.app"
```

3. Launch the app from `/Applications` (not from the DMG mount).

## Privacy permissions

Open **System Settings → Privacy & Security** and grant:

| Permission | Why |
|------------|-----|
| **Screen Recording** | Window titles for browser meetings (Google Meet, etc.) and in-call title hints |
| **Accessibility** | Foreground app / window detection |
| **Microphone** | Confirm the prompt on first recording attempt |

The app runs as a menu-bar utility (no Dock icon). Look for the recorder icon in the top menu bar.

## Autostart

A Launch Agent (`ai.o2consult.meetrec`) is registered when you enable autostart in Settings. After permissions are granted, the app can start at login.

## After each rebuild / update

Ad-hoc builds get a new code signature (cdhash). macOS treats each build as a new app for TCC (privacy) purposes. **Repeat the steps above** after installing a new version:

- Remove quarantine with `xattr`
- Re-grant Screen Recording, Accessibility, and Microphone if prompts do not appear or detection stops working

Developer ID signing and notarization (not covered here) reduce this friction for wide distribution.

## Logs

```text
~/Documents/Desktop Meeting Recordings/logs/
  meetrec-gui-YYYY-MM-DD.log
  meetrec-detector-YYYY-MM-DD.log
  meetrec-recorder-YYYY-MM-DD.log
```

Successful startup shows `app_start` in the GUI log and `detector_started` in the detector log.

## Troubleshooting

- **No menu bar icon**: kill stale instances (`pkill -f "Desktop Meeting Recorder"`), remove lock file at `~/Library/Application Support/Desktop Meeting Recorder/meetrec.lock`, reinstall and re-grant permissions.
- **Desktop Teams/Zoom not detected**: mic + system audio during the call is usually enough; Screen Recording is optional for desktop apps.
- **Browser Meet not detected**: enable Screen Recording so window titles are visible to the detector.
