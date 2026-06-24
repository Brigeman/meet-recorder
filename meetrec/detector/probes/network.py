"""Network heuristics for desktop meeting apps."""

from __future__ import annotations

import ipaddress

import psutil


def probe_meeting_app_network(meeting_pids: set[int]) -> tuple[bool, int, int | None]:
    """Return (active, connection_count, sample_pid)."""
    if not meeting_pids:
        return False, 0, None

    conn_count = 0
    sample_pid: int | None = None
    try:
        for conn in psutil.net_connections(kind="inet"):
            pid = getattr(conn, "pid", None)
            if not pid or pid not in meeting_pids:
                continue
            if not _is_public_remote(conn):
                continue
            if conn.type == 2:
                conn_count += 1
            elif (conn.status or "").upper() == "ESTABLISHED":
                conn_count += 1
            if sample_pid is None:
                sample_pid = pid
    except (psutil.AccessDenied, OSError):
        return False, 0, None

    return conn_count >= 3, conn_count, sample_pid


def _is_public_remote(conn) -> bool:
    raddr = getattr(conn, "raddr", ())
    if not raddr:
        return False
    ip = raddr[0] if isinstance(raddr, tuple) else getattr(raddr, "ip", None)
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )
