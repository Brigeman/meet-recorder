"""Known Calls projects cache for per-recording selection."""

from __future__ import annotations


def _normalize_project_id(project_id: str | None) -> str | None:
    if project_id is None:
        return None
    value = str(project_id).strip()
    return value or None


def list_known_projects(config: dict) -> list[dict[str, str]]:
    raw = config.get("calls_known_projects") or []
    projects: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        pid = _normalize_project_id(item.get("id"))
        if not pid or pid in seen:
            continue
        name = str(item.get("name") or pid).strip() or pid
        projects.append({"id": pid, "name": name})
        seen.add(pid)
    default_id = _normalize_project_id(config.get("calls_default_project_id"))
    if default_id and default_id not in seen:
        projects.insert(0, {"id": default_id, "name": default_id})
    return projects


def remember_project(config: dict, *, project_id: str | None, name: str | None = None) -> dict:
    pid = _normalize_project_id(project_id)
    if not pid:
        return config
    updated = dict(config)
    projects = list_known_projects(updated)
    label = (name or pid).strip() or pid
    merged = [{"id": pid, "name": label}]
    for item in projects:
        if item["id"] != pid:
            merged.append(item)
    updated["calls_known_projects"] = merged[:20]
    return updated


def default_project_id(config: dict) -> str | None:
    last = _normalize_project_id(config.get("calls_last_project_id"))
    if last:
        return last
    return _normalize_project_id(config.get("calls_default_project_id"))


def apply_session_project(config: dict, project_id: str | None) -> dict:
    updated = dict(config)
    pid = _normalize_project_id(project_id)
    updated["calls_last_project_id"] = pid
    if pid:
        updated = remember_project(updated, project_id=pid)
    return updated
