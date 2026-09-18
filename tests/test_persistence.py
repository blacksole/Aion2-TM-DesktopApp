"""Unit tests for core/persistence.py -- the atomic-write + self-healing-load
safety net under the profile files. No Qt needed."""

import json
import os
from pathlib import Path

import pytest

from core.persistence import (
    SCHEMA_VERSION,
    atomic_write_json,
    backup_path,
    load_json_with_fallback,
    schema_version_of,
    stamp_schema,
)


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# atomic_write_json
# --------------------------------------------------------------------------

def test_write_creates_file_and_leaves_no_tmp(tmp_path):
    target = tmp_path / "profile.json"

    atomic_write_json(target, {"a": 1})

    assert _read(target) == {"a": 1}
    assert not (tmp_path / "profile.json.tmp").exists()
    assert list(tmp_path.iterdir()) == [target]


def test_write_replaces_content_and_keeps_previous_as_bak(tmp_path):
    target = tmp_path / "profile.json"

    atomic_write_json(target, {"generation": 1})
    atomic_write_json(target, {"generation": 2})

    assert _read(target) == {"generation": 2}
    assert _read(backup_path(target)) == {"generation": 1}
    assert not (tmp_path / "profile.json.tmp").exists()


def test_first_write_creates_no_bak(tmp_path):
    target = tmp_path / "profile.json"

    atomic_write_json(target, {"a": 1})

    assert not backup_path(target).exists()


def test_backup_false_leaves_previous_bak_untouched(tmp_path):
    target = tmp_path / "profile.json"
    atomic_write_json(target, {"generation": 1})

    atomic_write_json(target, {"generation": 2}, backup=False)

    assert _read(target) == {"generation": 2}
    assert not backup_path(target).exists()


def test_write_creates_missing_parent_directory(tmp_path):
    target = tmp_path / "nested" / "dir" / "profile.json"

    atomic_write_json(target, {"a": 1})

    assert _read(target) == {"a": 1}


def test_write_roundtrips_unicode(tmp_path):
    target = tmp_path / "profile.json"

    atomic_write_json(target, {"title": "Prüfsumme — Держава"})

    assert _read(target) == {"title": "Prüfsumme — Держава"}


def test_crash_during_replace_leaves_original_intact(tmp_path, monkeypatch):
    target = tmp_path / "profile.json"
    atomic_write_json(target, {"generation": 1})

    def boom(src, dst):
        raise OSError("simulated crash")

    monkeypatch.setattr(os, "replace", boom)

    with pytest.raises(OSError):
        atomic_write_json(target, {"generation": 2})

    # Original content survives, and no half-written temp file is left behind.
    assert _read(target) == {"generation": 1}
    assert not (tmp_path / "profile.json.tmp").exists()


def test_crash_during_serialization_leaves_original_intact(tmp_path):
    target = tmp_path / "profile.json"
    atomic_write_json(target, {"generation": 1})

    class Unserializable:
        pass

    with pytest.raises(TypeError):
        atomic_write_json(target, {"boom": Unserializable()})

    assert _read(target) == {"generation": 1}
    assert not (tmp_path / "profile.json.tmp").exists()


# --------------------------------------------------------------------------
# schema stamping
# --------------------------------------------------------------------------

def test_schema_version_present_after_write(tmp_path):
    target = tmp_path / "profile.json"

    atomic_write_json(target, stamp_schema({"a": 1}))

    assert _read(target)["schema_version"] == SCHEMA_VERSION


def test_stamp_schema_is_idempotent_and_returns_same_dict():
    data = {"a": 1}

    once = stamp_schema(data)
    twice = stamp_schema(once)

    assert twice is data
    assert twice == {"a": 1, "schema_version": SCHEMA_VERSION}


def test_missing_schema_version_counts_as_zero():
    assert schema_version_of({}) == 0
    assert schema_version_of({"schema_version": "nonsense"}) == 0
    assert schema_version_of({"schema_version": 1}) == 1


# --------------------------------------------------------------------------
# load_json_with_fallback
# --------------------------------------------------------------------------

def test_load_ok(tmp_path):
    target = tmp_path / "profile.json"
    atomic_write_json(target, {"a": 1})

    assert load_json_with_fallback(target) == ({"a": 1}, "ok")


def test_corrupt_main_file_falls_back_to_bak(tmp_path):
    target = tmp_path / "profile.json"
    atomic_write_json(target, {"generation": 1})
    atomic_write_json(target, {"generation": 2})  # rotates generation 1 into .bak
    _write(target, '{"generation": 2, "tasks": [')  # truncated mid-write

    data, status = load_json_with_fallback(target)

    assert status == "bak"
    assert data == {"generation": 1}


@pytest.mark.parametrize(
    "broken",
    ["", "   \n", "{ not json", "[1, 2, 3]", "null", '"a string"'],
    ids=["empty", "whitespace", "truncated", "list", "null", "string"],
)
def test_unusable_main_file_shapes_fall_back_to_bak(tmp_path, broken):
    target = tmp_path / "profile.json"
    atomic_write_json(backup_path(target), {"rescued": True}, backup=False)
    _write(target, broken)

    assert load_json_with_fallback(target) == ({"rescued": True}, "bak")


def test_both_copies_corrupt_returns_empty(tmp_path):
    target = tmp_path / "profile.json"
    _write(target, "{ broken")
    _write(backup_path(target), "also broken")

    assert load_json_with_fallback(target) == ({}, "empty")


def test_missing_file_returns_empty(tmp_path):
    assert load_json_with_fallback(tmp_path / "nope.json") == ({}, "empty")


def test_corrupt_file_is_not_modified_by_loading(tmp_path):
    target = tmp_path / "profile.json"
    _write(target, "{ broken")

    load_json_with_fallback(target)

    # Loading must never repair/truncate/erase the file it could not read --
    # that is what lets the caller refuse to save over it.
    assert target.read_text(encoding="utf-8") == "{ broken"


def test_write_then_load_roundtrip_survives_a_corruption(tmp_path):
    """The whole point, end to end: a profile saved twice and then
    truncated by a crash still comes back as the previous good save."""
    target = tmp_path / "profile.json"
    atomic_write_json(target, stamp_schema({"tasks": ["one"]}))
    atomic_write_json(target, stamp_schema({"tasks": ["one", "two"]}))
    _write(target, '{"tasks": ["one", "tw')

    data, status = load_json_with_fallback(target)

    assert status == "bak"
    assert data["tasks"] == ["one"]
    assert schema_version_of(data) == SCHEMA_VERSION
