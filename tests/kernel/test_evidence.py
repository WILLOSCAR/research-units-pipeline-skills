"""evidence: the content-addressed store fails closed on anything it cannot verify."""

from __future__ import annotations

import json

import pytest
from helpers import make_store

from rh.kernel.evidence import (
    EvidenceCorrupt,
    EvidenceEntry,
    EvidenceStore,
    sha256_bytes,
    sha256_file,
    sha256_text,
)

BODY = b"Agents retrieve papers before they read them.\n"


def test_hash_helpers_agree(tmp_path):
    path = tmp_path / "body.md"
    path.write_bytes(BODY)

    assert sha256_bytes(BODY) == sha256_file(path) == sha256_text(BODY.decode("utf-8"))
    assert len(sha256_bytes(BODY)) == 64


def test_init_creates_objects_dir_and_empty_index(tmp_path):
    store = EvidenceStore(tmp_path / "evidence")

    store.init()

    assert store.objects.is_dir()
    assert store.index_path.is_file() and store.index_path.read_text() == ""
    assert list(store.entries()) == []


def test_entries_is_empty_when_the_index_does_not_exist(tmp_path):
    assert list(EvidenceStore(tmp_path / "missing").entries()) == []


def test_put_bytes_writes_the_object_and_one_index_line(tmp_path):
    store = make_store(tmp_path)

    entry = store.put_bytes(BODY, "brief.md", "write#1")

    assert entry == EvidenceEntry(sha256_bytes(BODY), "brief.md", "write#1", len(BODY), entry.at)
    assert (store.objects / entry.hash).read_bytes() == BODY
    assert store.has(entry.hash)
    lines = store.index_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {
        "hash": entry.hash,
        "name": "brief.md",
        "produced_by": "write#1",
        "bytes": len(BODY),
        "at": entry.at,
    }


def test_put_bytes_dedupes_by_hash_but_appends_every_index_entry(tmp_path):
    store = make_store(tmp_path)

    first = store.put_bytes(BODY, "brief.md", "write#1")
    second = store.put_bytes(BODY, "brief-copy.md", "write#2")

    assert first.hash == second.hash
    assert [p.name for p in store.objects.iterdir()] == [first.hash]  # one object, no .tmp left behind
    entries = list(store.entries())
    assert [(e.name, e.produced_by) for e in entries] == [("brief.md", "write#1"), ("brief-copy.md", "write#2")]
    assert all(e.hash == first.hash for e in entries)


def test_put_text_and_put_file_hash_the_same_bytes(tmp_path):
    store = make_store(tmp_path)
    path = tmp_path / "brief.md"
    path.write_bytes(BODY)

    from_text = store.put_text(BODY.decode("utf-8"), "brief.md", "write#1")
    from_file = store.put_file(path, "brief.md", "write#1")

    assert from_text.hash == from_file.hash == sha256_bytes(BODY)
    assert store.get_text(from_text.hash) == BODY.decode("utf-8")


def test_get_returns_the_bytes_that_were_put(tmp_path):
    store = make_store(tmp_path)
    digest = store.put_bytes(BODY, "brief.md", "write#1").hash

    assert store.get(digest) == BODY


def test_get_fails_closed_on_a_hash_that_does_not_resolve(tmp_path):
    store = make_store(tmp_path)
    missing = sha256_bytes(b"never stored")

    assert not store.has(missing)
    with pytest.raises(EvidenceCorrupt, match="does not resolve"):
        store.get(missing)


def test_get_fails_closed_on_a_tampered_object(tmp_path):
    store = make_store(tmp_path)
    digest = store.put_bytes(BODY, "brief.md", "write#1").hash

    (store.objects / digest).write_bytes(b"something else entirely")

    assert store.has(digest)  # the file is there ...
    with pytest.raises(EvidenceCorrupt, match="does not match"):
        store.get(digest)  # ... but the store refuses to hand it out
    with pytest.raises(EvidenceCorrupt):
        store.get_text(digest)


def test_verify_all_lists_only_the_broken_hashes_in_order(tmp_path):
    store = make_store(tmp_path)
    good = store.put_bytes(BODY, "brief.md", "write#1").hash
    tampered = store.put_bytes(b"outline", "outline.yml", "outline#1").hash
    (store.objects / tampered).write_bytes(b"edited by hand")
    missing = sha256_bytes(b"missing")

    assert store.verify_all([good, missing, tampered]) == [missing, tampered]
    assert store.verify_all([good]) == []
    assert store.verify_all([]) == []


def test_producer_of_reads_the_index(tmp_path):
    store = make_store(tmp_path)
    digest = store.put_bytes(BODY, "brief.md", "write#1").hash
    store.put_bytes(BODY, "brief-copy.md", "write#2")

    assert store.producer_of(digest) == "write#1"  # first producer wins
    assert store.producer_of(sha256_bytes(b"unknown")) is None


def test_link_into_copies_the_bytes_and_creates_parents(tmp_path):
    store = make_store(tmp_path)
    digest = store.put_bytes(BODY, "brief.md", "write#1").hash
    dest = tmp_path / "steps" / "write" / "pass-2" / "inputs" / "brief.md"

    store.link_into(digest, dest)

    assert dest.read_bytes() == BODY
    dest.write_bytes(b"projection edited")  # projections are untrusted copies ...
    assert store.get(digest) == BODY  # ... so editing one never touches the store


def test_link_into_refuses_corrupt_evidence(tmp_path):
    store = make_store(tmp_path)
    dest = tmp_path / "out" / "brief.md"

    with pytest.raises(EvidenceCorrupt):
        store.link_into(sha256_bytes(b"missing"), dest)
    assert not dest.exists()
