"""Audio probes — platform implementation."""

import sys

if sys.platform == "win32":
    from meetrec.platform.windows.audio import *  # noqa: F403
elif sys.platform == "darwin":
    from meetrec.platform.macos.audio import *  # noqa: F403
else:
    def probe_audio_activity():
        return False, False

    def probe_meeting_app_audio(meeting_pids):
        return False, False, 0.0, 0.0

    def mic_used_by_meeting_process():
        return False
