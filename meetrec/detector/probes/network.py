"""Network heuristics for desktop meeting apps."""

from __future__ import annotations

import ipaddress
import logging

import psutil

log = logging.getLogger(__name__)


def probe_meeting_app_network(meeting_pids: set[int]) -> tuple[bool, int, int | None]:
    """Return (active, connection_count, sample_pid)."""
    if not meeting_pids:
        return False, 0, None

    conn_count = 0
    sample_pid: int | None = None
    best_pid: int | None = None
    best_pid_count = 0

    for pid in meeting_pids:
        try:
            pid_count = 0
            for conn in psutil.Process(pid).net_connections(kind="inet"):
                if not _is_public_remote(conn):
                    continue
                if conn.type == 2:
                    pid_count += 1
                elif (conn.status or "").upper() == "ESTABLISHED":
                    pid_count += 1
            if pid_count <= 0:
                continue
            conn_count += pid_count
            if sample_pid is None:
                sample_pid = pid
            if pid_count > best_pid_count:
                best_pid_count = pid_count
                best_pid = pid
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as exc:
            log.debug("meeting net probe skipped pid=%s err=%s", pid, exc)
            continue

    active_pid = best_pid or sample_pid
    # Require strong per-PID signal; total count alone is too noisy for idle Teams/Zoom.
    active = best_pid_count >= 6
    return active, conn_count, active_pid


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
