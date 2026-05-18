from collections import namedtuple

from winrec.detector.probes.network import probe_meeting_app_network


Addr = namedtuple("Addr", ["ip", "port"])
Conn = namedtuple("Conn", ["pid", "raddr", "type", "status"])


def test_meeting_network_active_with_public_udp(monkeypatch):
    conns = [
        Conn(pid=100, raddr=Addr("52.112.12.2", 3478), type=2, status=""),
        Conn(pid=100, raddr=Addr("13.107.64.5", 443), type=2, status=""),
        Conn(pid=100, raddr=Addr("20.190.10.3", 443), type=2, status=""),
    ]
    monkeypatch.setattr("psutil.net_connections", lambda kind="inet": conns)

    active, count, sample_pid = probe_meeting_app_network({100})
    assert active
    assert count == 3
    assert sample_pid == 100


def test_meeting_network_ignores_private_and_unrelated(monkeypatch):
    conns = [
        Conn(pid=100, raddr=Addr("192.168.1.20", 3478), type=2, status=""),
        Conn(pid=200, raddr=Addr("52.112.12.2", 3478), type=2, status=""),
    ]
    monkeypatch.setattr("psutil.net_connections", lambda kind="inet": conns)

    active, count, _ = probe_meeting_app_network({100})
    assert not active
    assert count == 0
