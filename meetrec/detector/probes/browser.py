"""Browser meeting probe — platform implementation."""

import sys

if sys.platform == "win32":
    from meetrec.platform.windows.browser import probe_browser_meeting
elif sys.platform == "darwin":
    from meetrec.platform.macos.browser import probe_browser_meeting
else:
    def probe_browser_meeting():
        return False, None, "", 0
