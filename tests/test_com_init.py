"""COM init helper (Windows only; comtypes is not installed on Linux CI)."""

import sys
from unittest.mock import patch

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="COM is Windows-only")
def test_ensure_com_ignores_changed_mode():
    from meetrec import com_init

    err = OSError("changed mode")
    err.winerror = -2147417850
    with patch("comtypes.CoInitializeEx", side_effect=err):
        com_init.ensure_native_init()


@pytest.mark.skipif(sys.platform != "win32", reason="COM is Windows-only")
def test_ensure_com_reraises_other_oserror():
    from meetrec import com_init

    with patch("comtypes.CoInitializeEx", side_effect=OSError(1, "other")):
        with pytest.raises(OSError):
            com_init.ensure_native_init()
