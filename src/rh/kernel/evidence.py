"""Content-addressed Evidence store.

Every byte the harness will ever reason about lives here under its sha256.
A hash that does not resolve, or a body whose hash no longer matches its
name, is corruption: the store fails closed on it.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator

from rh.kernel.records import now


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


class EvidenceCorrupt(RuntimeError):
    """A hash does not resolve, or its body no longer matches."""


@dataclass(frozen=True)
class EvidenceEntry:
    hash: str
    name: str
    produced_by: str  # pass id, "goal", "spec", "kernel", "human"
    bytes: int
    at: str


class EvidenceStore:
    def __init__(self, root: Path):
        self.root = root
        self.objects = root / "objects"
        self.index_path = root / "index.jsonl"

    def init(self) -> None:
        self.objects.mkdir(parents=True, exist_ok=True)
        self.index_path.touch()

    # -- write ---------------------------------------------------------------

    def put_bytes(self, data: bytes, name: str, produced_by: str) -> EvidenceEntry:
        digest = sha256_bytes(data)
        target = self.objects / digest
        if not target.exists():
            tmp = target.with_suffix(".tmp")
            tmp.write_bytes(data)
            os.replace(tmp, target)
        entry = EvidenceEntry(digest, name, produced_by, len(data), now())
        with self.index_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        return entry

    def put_file(self, path: Path, name: str, produced_by: str) -> EvidenceEntry:
        return self.put_bytes(path.read_bytes(), name, produced_by)

    def put_text(self, text: str, name: str, produced_by: str) -> EvidenceEntry:
        return self.put_bytes(text.encode("utf-8"), name, produced_by)

    # -- read ----------------------------------------------------------------

    def has(self, digest: str) -> bool:
        return (self.objects / digest).is_file()

    def get(self, digest: str) -> bytes:
        path = self.objects / digest
        if not path.is_file():
            raise EvidenceCorrupt(f"evidence {digest[:12]} does not resolve")
        data = path.read_bytes()
        if sha256_bytes(data) != digest:
            raise EvidenceCorrupt(f"evidence {digest[:12]} body does not match its hash")
        return data

    def get_text(self, digest: str) -> str:
        return self.get(digest).decode("utf-8")

    def entries(self) -> Iterator[EvidenceEntry]:
        if not self.index_path.exists():
            return
        with self.index_path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    yield EvidenceEntry(**json.loads(line))

    def producer_of(self, digest: str) -> str | None:
        for entry in self.entries():
            if entry.hash == digest:
                return entry.produced_by
        return None

    def verify_all(self, hashes: list[str]) -> list[str]:
        """Return the hashes that fail to resolve or match."""
        broken: list[str] = []
        for digest in hashes:
            try:
                self.get(digest)
            except EvidenceCorrupt:
                broken.append(digest)
        return broken

    def link_into(self, digest: str, dest: Path) -> None:
        """Materialise ``digest`` at ``dest`` (a copy; projections are untrusted)."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self.get(digest))
