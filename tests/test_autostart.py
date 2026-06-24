import sys
from types import SimpleNamespace

import pytest

from meetrec import autostart


class _FakeWinReg:
    HKEY_CURRENT_USER = object()
    KEY_READ = 1
    KEY_SET_VALUE = 2
    REG_SZ = 3

    def __init__(self):
        self.values = {}
        self.last_path = ""

    def OpenKey(self, _root, path, _zero, _access):
        self.last_path = path
        return _FakeKey(self)

    def QueryValueEx(self, _key, name):
        if name not in self.values:
            raise OSError("missing")
        return self.values[name], self.REG_SZ

    def SetValueEx(self, _key, name, _r, _t, value):
        self.values[name] = value

    def DeleteValue(self, _key, name):
        if name in self.values:
            del self.values[name]
        else:
            raise OSError("missing")


class _FakeKey:
    def __init__(self, reg):
        self.reg = reg

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.mark.skipif(sys.platform != "linux", reason="Only Linux lacks autostart in CI")
def test_autostart_noop_on_non_windows(monkeypatch):
    monkeypatch.setattr(autostart, "is_supported", lambda: False)
    assert autostart.enable("C:\\WinRec.exe") is False
    assert autostart.disable() is False
    assert autostart.get_registered_path() is None


@pytest.mark.skipif(sys.platform != "win32", reason="Windows registry autostart")
def test_autostart_enable_disable(monkeypatch):
    fake_reg = _FakeWinReg()
    monkeypatch.setattr(autostart, "is_supported", lambda: True)
    monkeypatch.setitem(__import__("sys").modules, "winreg", fake_reg)

    assert autostart.enable("C:\\Apps\\WinRec.exe")
    assert autostart.is_enabled()
    assert "MeetRec" in fake_reg.values

    assert autostart.disable()
    assert not autostart.is_enabled()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows frozen executable path")
def test_current_executable_path_for_frozen(monkeypatch):
    import meetrec.platform.windows.autostart as win_autostart

    monkeypatch.setattr(
        win_autostart.sys,
        "frozen",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        win_autostart.sys,
        "executable",
        "C:\\Apps\\WinRec.exe",
        raising=False,
    )
    assert win_autostart.current_executable_path().endswith("WinRec.exe")
