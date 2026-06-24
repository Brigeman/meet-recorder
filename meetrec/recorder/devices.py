"""WASAPI device selection — Windows-only, re-exported for tests."""

import sys

if sys.platform == "win32":
    from meetrec.platform.windows.devices import *  # noqa: F403
else:
    def default_output_key(p):  # noqa: ARG001
        return None

    def default_input_key(p):  # noqa: ARG001
        return None

    def find_loopback_device(p):  # noqa: ARG001
        raise RuntimeError("Loopback capture is only available on Windows")

    def find_mic_device(p):  # noqa: ARG001
        return None
