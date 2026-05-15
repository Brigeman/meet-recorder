import json
import logging
import time
from typing import Any

log = logging.getLogger("winrec.events")


def log_event(event: str, **fields: Any) -> None:
    payload = {"event": event, "timestamp": time.time(), **fields}
    log.info(json.dumps(payload, ensure_ascii=False))
