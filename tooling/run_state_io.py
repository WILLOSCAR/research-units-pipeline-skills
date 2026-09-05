"""Durable JSON/JSONL ledger serialization primitives.

These are the leaf-level I/O helpers the Run state layer builds on: reading and
writing the Harness's JSON snapshot files and appending to its JSONL ledgers.
They hold no shared mutable state and depend only on the filesystem, so they are
kept separate from the mutation helpers in ``tooling.run_state`` (which re-exports
them to preserve its public surface).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from tooling.common import atomic_write_text, ensure_dir


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _last_event_seq(path: Path) -> int:
    if not path.exists():
        return 0
    last = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict) and isinstance(record.get("seq"), int):
                last = max(last, int(record["seq"]))
    return last


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                records.append(payload)
    return records


def read_jsonl_with_errors(path: Path) -> tuple[list[dict[str, Any]], list[int]]:
    """Read valid JSON objects while retaining malformed line numbers for audit."""

    if not path.exists():
        return [], []
    records: list[dict[str, Any]] = []
    malformed: list[int] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                malformed.append(line_number)
                continue
            if isinstance(payload, dict):
                records.append(payload)
            else:
                malformed.append(line_number)
    return records, malformed


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
