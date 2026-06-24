import json
import os

import psutil
import pytest

from winrec.ipc import single_instance


@pytest.fixture
def lock_path(tmp_path, monkeypatch):
    path = str(tmp_path / "winrec.lock")
    monkeypatch.setattr(single_instance, "LOCK_FILE", path)
    return path


def _read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_fresh_acquire_writes_lock_and_returns_true(lock_path):
    assert single_instance.acquire_single_instance() is True
    assert os.path.exists(lock_path)
    record = _read(lock_path)
    assert record["pid"] == os.getpid()


def test_stale_lock_dead_pid_is_overwritten(lock_path, monkeypatch):
    with open(lock_path, "w", encoding="utf-8") as f:
        json.dump({"pid": 999999, "create_time": 1.0, "name": "WinRec.exe"}, f)

    monkeypatch.setattr(single_instance, "_is_winrec_process", lambda *a, **k: False)

    assert single_instance.acquire_single_instance() is True
    assert _read(lock_path)["pid"] == os.getpid()


def test_corrupt_lock_is_treated_as_stale(lock_path):
    with open(lock_path, "w", encoding="utf-8") as f:
        f.write("not-json{{{")

    assert single_instance.acquire_single_instance() is True
    assert _read(lock_path)["pid"] == os.getpid()


def test_live_matching_lock_blocks_acquire(lock_path):
    proc = psutil.Process(os.getpid())
    with open(lock_path, "w", encoding="utf-8") as f:
        json.dump(
            {"pid": os.getpid(), "create_time": proc.create_time(), "name": proc.name()},
            f,
        )

    assert single_instance.acquire_single_instance() is False


def test_mismatched_create_time_is_stale(lock_path):
    proc = psutil.Process(os.getpid())
    with open(lock_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "pid": os.getpid(),
                "create_time": proc.create_time() + 10000.0,
                "name": proc.name(),
            },
            f,
        )

    assert single_instance.acquire_single_instance() is True
    assert _read(lock_path)["create_time"] == pytest.approx(proc.create_time(), abs=1.0)


def test_release_removes_lock_owned_by_current_pid(lock_path):
    assert single_instance.acquire_single_instance() is True
    assert os.path.exists(lock_path)

    single_instance.release_single_instance()
    assert not os.path.exists(lock_path)


def test_release_keeps_lock_owned_by_other_pid(lock_path):
    with open(lock_path, "w", encoding="utf-8") as f:
        json.dump({"pid": 999999, "create_time": 1.0, "name": "other"}, f)

    single_instance.release_single_instance()
    assert os.path.exists(lock_path)
