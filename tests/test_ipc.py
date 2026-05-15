import json

from winrec.ipc.protocol import read_jsonl_line, write_jsonl_line
from winrec.gui.cooldown import CooldownManager


def test_jsonl_roundtrip(capsys):
    write_jsonl_line({"type": "test", "value": 1})
    captured = capsys.readouterr().out.strip()
    obj = read_jsonl_line(captured)
    assert obj == {"type": "test", "value": 1}


def test_cooldown_dismiss():
    cm = CooldownManager(90, 120)
    assert cm.can_prompt("teams:1:abc")
    cm.record_dismiss("teams:1:abc")
    assert not cm.can_prompt("teams:1:abc")


def test_cooldown_post_stop():
    cm = CooldownManager(90, 120)
    cm.record_post_stop("zoom:2:def")
    assert not cm.can_prompt("zoom:2:def")
