import atexit
import os
import sys

from winrec.config import LOCK_FILE


def acquire_single_instance() -> bool:
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    try:
        if os.path.exists(LOCK_FILE):
            with open(LOCK_FILE, encoding="utf-8") as f:
                old_pid = int(f.read().strip() or "0")
            if old_pid and _pid_alive(old_pid):
                return False
        with open(LOCK_FILE, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        atexit.register(release_single_instance)
        return True
    except OSError:
        return True


def release_single_instance() -> None:
    try:
        if os.path.exists(LOCK_FILE):
            with open(LOCK_FILE, encoding="utf-8") as f:
                if f.read().strip() == str(os.getpid()):
                    os.remove(LOCK_FILE)
    except OSError:
        pass


def _pid_alive(pid: int) -> bool:
    if sys.platform != "win32":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    import ctypes

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    kernel32.CloseHandle(handle)
    return True
