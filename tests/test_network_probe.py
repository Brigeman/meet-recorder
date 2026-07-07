from collections import namedtuple

import psutil

from meetrec.detector.probes.network import probe_meeting_app_network


Addr = namedtuple("Addr", ["ip", "port"])
Conn = namedtuple("Conn", ["pid", "raddr", "type", "status"])


class _FakeProcess:
    def __init__(self, conns):
        self._conns = conns

    def net_connections(self, kind="inet"):
        return self._conns


def _patch_processes(monkeypatch, conns_by_pid):
    def fake_process(pid):
        if pid not in conns_by_pid:
            raise psutil.NoSuchProcess(pid)
        return _FakeProcess(conns_by_pid[pid])

    monkeypatch.setattr("psutil.Process", fake_process)


def test_meeting_network_active_with_public_udp(monkeypatch):
    # Active detection requires a strong per-PID signal (>= 6 public UDP conns).
    conns = [Conn(pid=100, raddr=Addr("52.112.12.2", 3478 + i), type=2, status="") for i in range(6)]
    _patch_processes(monkeypatch, {100: conns})

    active, count, sample_pid = probe_meeting_app_network({100})
    assert active
    assert count == 6
    assert sample_pid == 100


def test_meeting_network_ignores_private_and_unrelated(monkeypatch):
    conns_by_pid = {
        100: [Conn(pid=100, raddr=Addr("192.168.1.20", 3478), type=2, status="")],
    }
    _patch_processes(monkeypatch, conns_by_pid)

    active, count, _ = probe_meeting_app_network({100})
    assert not active
    assert count == 0
