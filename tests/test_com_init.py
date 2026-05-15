"""COM init helper must tolerate RPC_E_CHANGED_MODE."""

from unittest.mock import patch

import pytest

from winrec import com_init


def test_ensure_com_ignores_changed_mode():
    with patch("comtypes.CoInitializeEx", side_effect=OSError(-2147417850, "changed mode")):
        com_init.ensure_com()  # must not raise


def test_ensure_com_reraises_other_oserror():
    with patch("comtypes.CoInitializeEx", side_effect=OSError(1, "other")):
        with pytest.raises(OSError):
            com_init.ensure_com()
