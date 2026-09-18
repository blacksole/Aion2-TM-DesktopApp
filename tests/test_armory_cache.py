"""The Armory HTTP cache: where it lives, and the one-off move into it.

`_migrate_legacy_cache` moves up to a few hundred MB of downloaded icons and
item details out of the installation directory. It used `Path.replace`, which
is `os.rename` -- same-volume only -- and the frozen Windows case is precisely
the cross-volume one (app on a data drive, `%LOCALAPPDATA%` on the system
drive). These tests fake that failure rather than trusting the happy path.
"""

from __future__ import annotations

import errno
from pathlib import Path

import pytest

import ItemDatabase.app as ida


@pytest.fixture
def legacy_tree(tmp_path, monkeypatch):
    """A populated pre-XDG cache next to a fake install."""
    install = tmp_path / "install"
    (install / "data" / "icons").mkdir(parents=True)
    (install / "data" / "details").mkdir(parents=True)
    (install / "data" / "icons" / "sword.png").write_bytes(b"icon")
    (install / "data" / "details" / "12345.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(ida, "BASE_DIR", install)
    return install


def test_migration_moves_both_cache_dirs(legacy_tree, tmp_path):
    new_root = tmp_path / "cache" / "armory"
    new_root.mkdir(parents=True)

    ida._migrate_legacy_cache(new_root)

    assert (new_root / "icons" / "sword.png").read_bytes() == b"icon"
    assert (new_root / "details" / "12345.json").exists()
    assert not (legacy_tree / "data" / "icons").exists()


def test_migration_falls_back_to_shutil_move_across_volumes(legacy_tree, tmp_path, monkeypatch):
    new_root = tmp_path / "cache" / "armory"
    new_root.mkdir(parents=True)

    def cross_device(self, target):
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    monkeypatch.setattr(Path, "replace", cross_device)

    ida._migrate_legacy_cache(new_root)

    # shutil.move copies across devices, so everything still arrives.
    assert (new_root / "icons" / "sword.png").read_bytes() == b"icon"
    assert (new_root / "details" / "12345.json").exists()
    assert not (legacy_tree / "data" / "icons").exists()


def test_migration_never_overwrites_an_existing_cache(legacy_tree, tmp_path):
    new_root = tmp_path / "cache" / "armory"
    (new_root / "icons").mkdir(parents=True)
    (new_root / "icons" / "sword.png").write_bytes(b"newer")

    ida._migrate_legacy_cache(new_root)

    assert (new_root / "icons" / "sword.png").read_bytes() == b"newer"
    assert (legacy_tree / "data" / "icons" / "sword.png").exists()   # left alone
    assert (new_root / "details" / "12345.json").exists()            # the other half moved


def test_migration_is_idempotent(legacy_tree, tmp_path):
    new_root = tmp_path / "cache" / "armory"
    new_root.mkdir(parents=True)

    ida._migrate_legacy_cache(new_root)
    ida._migrate_legacy_cache(new_root)   # second launch

    assert (new_root / "icons" / "sword.png").read_bytes() == b"icon"


def test_migration_is_a_no_op_when_running_from_source(legacy_tree):
    # Unfrozen, _cache_root() IS the legacy directory: nothing may move.
    same = legacy_tree / "data"

    ida._migrate_legacy_cache(same)

    assert (same / "icons" / "sword.png").exists()


def test_migration_survives_an_unmovable_cache(legacy_tree, tmp_path, monkeypatch):
    new_root = tmp_path / "cache" / "armory"
    new_root.mkdir(parents=True)
    monkeypatch.setattr(Path, "replace", lambda self, t: (_ for _ in ()).throw(OSError("nope")))
    monkeypatch.setattr(ida.shutil, "move", lambda s, t: (_ for _ in ()).throw(OSError("nope")))

    ida._migrate_legacy_cache(new_root)   # must not raise: the app still starts

    assert (legacy_tree / "data" / "icons" / "sword.png").exists()


def test_cache_root_stays_in_the_repo_when_not_frozen():
    # The guarantee that a dev run keeps reusing the cache it already has.
    assert ida._cache_root() == ida.BASE_DIR / "data"
