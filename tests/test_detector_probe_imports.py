"""Guard against probe import mistakes that crash WinRec.Detector.exe at startup."""

import ast
from pathlib import Path

_PROBES = Path(__file__).resolve().parents[1] / "meetrec" / "detector" / "probes"


def _imports_match_title_hint_from_apps(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module != "meetrec.detector.apps":
            continue
        if any(alias.name == "match_title_hint" for alias in node.names):
            return True
    return False


def test_probes_do_not_import_match_title_hint_from_apps():
    for name in ("browser.py", "foreground.py"):
        assert not _imports_match_title_hint_from_apps(_PROBES / name), name
