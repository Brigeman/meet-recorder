import json
import sys
from typing import Any, Iterator


def write_jsonl_line(obj: dict[str, Any], stream=None) -> None:
    stream = stream or sys.stdout
    stream.write(json.dumps(obj, ensure_ascii=True) + "\n")
    stream.flush()


def read_jsonl_line(line: str) -> dict[str, Any] | None:
    line = line.strip()
    if not line:
        return None
    return json.loads(line)


def iter_jsonl(stream) -> Iterator[dict[str, Any]]:
    for line in stream:
        obj = read_jsonl_line(line)
        if obj is not None:
            yield obj
