"""Foreground probe — platform implementation."""

import sys

if sys.platform == "win32":
    from meetrec.platform.windows.foreground import probe_foreground
elif sys.platform == "darwin":
    from meetrec.platform.macos.foreground import probe_foreground
else:
    def probe_foreground():
        return None, ""
