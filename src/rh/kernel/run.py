"""The Run's single authority: ``run.json`` plus the Evidence store.

Writes happen only inside a ``Transaction``: load under a process lock,
mutate, bump ``version``, replace atomically. Everything else under the
workspace is a projection that the kernel re-derives and never trusts.
"""

from __future__ import annotations

import fcntl
import json
import os
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from rh.kernel.evidence import EvidenceStore
from rh.kernel.records import RunState, decode, encode, now

# File names the kernel and the agent agree on inside a workspace.
GOAL_FILE = "goal.md"
SPEC_FILE = "success_spec.yaml"
GATE_RESULT_FILE = "gate_result.json"
PROOF_PACK_JSON = "proof_pack.json"
PROOF_PACK_MD = "proof_pack.md"


class RunNotFound(FileNotFoundError):
    pass


class RunConflict(RuntimeError):
    """``run.json`` changed under a Transaction; the write was refused."""


def write_json(path: Path, data: object) -> None:
    """Write ``data`` as indented JSON via a temp file and atomic rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


class Workspace:
    """Paths of one Run. Only ``run.json`` and ``evidence/`` are authoritative."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.run_json = self.root / "run.json"
        self.lock_path = self.root / ".run.lock"
        self.trace = self.root / "trace.jsonl"
        self.evidence = EvidenceStore(self.root / "evidence")
        self.steps = self.root / "steps"
        self.decisions = self.root / "decisions"
        self.artifact = self.root / "artifact"
        self.gates = self.root / "gates"
        self.faults = self.root / "faults"

    def exists(self) -> bool:
        return self.run_json.is_file()

    def init(self) -> None:
        for path in (self.root, self.steps, self.decisions, self.artifact, self.gates, self.faults):
            path.mkdir(parents=True, exist_ok=True)
        self.evidence.init()

    def pass_dir(self, pass_id: str) -> Path:
        step, _, n = pass_id.partition("#")
        return self.steps / step / f"pass-{n}"

    # -- authority -------------------------------------------------------------

    def load(self) -> RunState:
        if not self.exists():
            raise RunNotFound(f"no Run at {self.root}")
        return decode(RunState, json.loads(self.run_json.read_text(encoding="utf-8")))

    def _write(self, state: RunState) -> None:
        state.updated_at = now()
        write_json(self.run_json, encode(state))

    @contextmanager
    def locked(self) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)

    @contextmanager
    def transaction(self) -> Iterator[RunState]:
        """Load → mutate → commit with ``version + 1``, atomically, under lock."""
        with self.locked():
            state = self.load()
            expected = state.version
            yield state
            if self.load().version != expected:
                raise RunConflict("run.json changed during the transaction")
            state.version = expected + 1
            self._write(state)

    def create(self, state: RunState) -> None:
        with self.locked():
            if self.exists():
                raise FileExistsError(f"a Run already exists at {self.root}")
            self.init()
            state.version = 1
            self._write(state)

    # -- trace (append-only projection) ---------------------------------------

    def log(self, event: str, **fields: object) -> None:
        line = {"at": now(), "event": event, **fields}
        with self.trace.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")


def new_run_id(kind: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{kind}-{stamp}-{secrets.token_hex(2)}"
