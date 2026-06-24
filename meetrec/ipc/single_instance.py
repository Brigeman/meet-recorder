import atexit
import json
import os

from meetrec.config import LOCK_FILE
from meetrec.logging_util import log_event
from meetrec.platform import executable_name_matches

_CREATE_TIME_EPSILON = 1.0


def acquire_single_instance() -> bool:
    try:
        os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
        if os.path.exists(LOCK_FILE):
            record = _read_lock()
            if record is None:
                log_event("single_instance_stale_lock", reason="corrupt")
            elif _is_meetrec_process(
                record.get("pid"), record.get("create_time"), record.get("name")
            ):
                return False
            else:
                log_event("single_instance_stale_lock", pid=record.get("pid"))
        _write_lock()
        atexit.register(release_single_instance)
        return True
    except Exception:
        return True


def release_single_instance() -> None:
    try:
        if os.path.exists(LOCK_FILE):
            record = _read_lock()
            if record is not None and record.get("pid") == os.getpid():
                os.remove(LOCK_FILE)
    except OSError:
        pass


def _read_lock() -> dict | None:
    try:
        with open(LOCK_FILE, encoding="utf-8") as f:
            record = json.load(f)
        if isinstance(record, dict) and "pid" in record:
            return record
        return None
    except (OSError, ValueError):
        return None


def _write_lock() -> None:
    pid = os.getpid()
    create_time = None
    name = None
    try:
        import psutil

        proc = psutil.Process(pid)
        create_time = proc.create_time()
        name = proc.name()
    except Exception:
        pass
    record = {"pid": pid, "create_time": create_time, "name": name}
    with open(LOCK_FILE, "w", encoding="utf-8") as f:
        json.dump(record, f)


def _is_meetrec_process(pid, create_time, name) -> bool:
    if not isinstance(pid, int):
        return False
    try:
        import psutil
    except Exception:
        return False
    try:
        proc = psutil.Process(pid)
        actual_create = proc.create_time()
        actual_name = proc.name()
    except Exception:
        return False

    if create_time is not None and abs(actual_create - create_time) > _CREATE_TIME_EPSILON:
        return False

    if name is not None and actual_name != name:
        if not executable_name_matches(actual_name):
            return False

    return True
