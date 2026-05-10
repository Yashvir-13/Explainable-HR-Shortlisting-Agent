from __future__ import annotations

import json
from pathlib import Path

from .models import OverrideRecord


def append_override(record: OverrideRecord, log_path: Path = Path("outputs/override_log.jsonl")) -> Path:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json() + "\n")
    return log_path


def read_overrides(log_path: Path = Path("outputs/override_log.jsonl")) -> list[dict]:
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]

