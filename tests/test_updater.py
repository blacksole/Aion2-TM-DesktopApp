"""Unit tests for the updater's integrity helpers in core/update_checker.py:
SHA-256 verification of the downloaded release ZIP and Zip-Slip-safe
extraction. Pure functions only -- no network, no QThread."""

import hashlib
import zipfile

import pytest

from core.update_checker import (
    is_sha256_hex,
    parse_sha256_sidecar,
    safe_extract,
    select_assets,
    sha256_sidecar_url,
    verify_sha256,
)

_ZIP_NAME = "Aion2_TM.zip"
_BASE_URL = f"https://github.com/blacksole/Aion2-TM-DesktopApp/releases/download/v2.0.7/{_ZIP_NAME}"


def _make_zip(path, members: dict):
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return path


def _payload(tmp_path, content: bytes = b"payload"):
    target = tmp_path / _ZIP_NAME
    target.write_bytes(content)
    return target, hashlib.sha256(content).hexdigest()


# --------------------------------------------------------------------------
# sidecar parsing
# --------------------------------------------------------------------------

def test_parse_coreutils_format():
    digest = "a" * 64
    assert parse_sha256_sidecar(f"{digest}  {_ZIP_NAME}\n") == digest


def test_parse_binary_star_format():
    digest = "b" * 64
    assert parse_sha256_sidecar(f"{digest} *{_ZIP_NAME}") == digest


def test_parse_bare_hex():
    digest = "c" * 64
    assert parse_sha256_sidecar(f"  {digest}  \n") == digest


def test_parse_is_case_insensitive():
    digest = "ABCDEF0123456789" * 4
    assert parse_sha256_sidecar(f"{digest}  {_ZIP_NAME}") == digest.lower()


def test_parse_skips_leading_noise_and_bom():
    digest = "d" * 64
    text = f"\ufeff# checksums\n\n{digest}  {_ZIP_NAME}\n"
    assert parse_sha256_sidecar(text) == digest


@pytest.mark.parametrize(
    "text",
    ["", "   ", "not a hash at all", "a" * 63, "a" * 65, "z" * 64, "<html>404</html>"],
    ids=["empty", "blank", "words", "too-short", "too-long", "non-hex", "html"],
)
def test_parse_rejects_garbage(text):
    assert parse_sha256_sidecar(text) == ""


def test_is_sha256_hex():
    assert is_sha256_hex("0" * 64)
    assert is_sha256_hex(("F" * 64))
    assert not is_sha256_hex("0" * 63)
    assert not is_sha256_hex(None)


# --------------------------------------------------------------------------
# verification
# --------------------------------------------------------------------------

def test_verify_accepts_matching_digest(tmp_path):
    zip_path, digest = _payload(tmp_path)
    assert verify_sha256(zip_path, digest) is True


def test_verify_is_case_insensitive(tmp_path):
    zip_path, digest = _payload(tmp_path)
    assert verify_sha256(zip_path, digest.upper()) is True


def test_verify_rejects_mismatch(tmp_path):
    zip_path, _ = _payload(tmp_path, b"payload")
    other = hashlib.sha256(b"tampered payload").hexdigest()
    assert verify_sha256(zip_path, other) is False


def test_verify_rejects_one_flipped_byte(tmp_path):
    zip_path, digest = _payload(tmp_path, b"payload")
    zip_path.write_bytes(b"payloaD")
    assert verify_sha256(zip_path, digest) is False


@pytest.mark.parametrize("expected", ["", None, "deadbeef", "z" * 64])
def test_verify_rejects_malformed_expectation(tmp_path, expected):
    zip_path, _ = _payload(tmp_path)
    assert verify_sha256(zip_path, expected) is False


def test_verify_reads_files_larger_than_one_chunk(tmp_path):
    content = b"x" * (3 * 1024 * 1024 + 7)
    zip_path, digest = _payload(tmp_path, content)
    assert verify_sha256(zip_path, digest) is True


# --------------------------------------------------------------------------
# Zip-Slip
# --------------------------------------------------------------------------

def test_safe_extract_accepts_normal_members(tmp_path):
    archive = _make_zip(tmp_path / "ok.zip", {
        "Aion2 TM.exe": b"MZ",
        "_internal/core/version.py": b"APP_VERSION = '2.0.8'",
    })
    target = tmp_path / "out"

    safe_extract(archive, target)

    assert (target / "Aion2 TM.exe").read_bytes() == b"MZ"
    assert (target / "_internal" / "core" / "version.py").exists()


def test_safe_extract_creates_the_target_dir(tmp_path):
    archive = _make_zip(tmp_path / "ok.zip", {"a.txt": b"a"})
    target = tmp_path / "does" / "not" / "exist"

    safe_extract(archive, target)

    assert (target / "a.txt").read_bytes() == b"a"


@pytest.mark.parametrize(
    "member",
    [
        "../evil.txt",
        "good/../../evil.txt",
        "/abs/path/evil.txt",
        "/etc/passwd",
        "..\\evil.txt",
        "C:\\Windows\\System32\\evil.dll",
        "\\\\server\\share\\evil.txt",
    ],
    ids=["parent", "nested-parent", "abs", "abs-etc", "win-parent", "win-drive", "unc"],
)
def test_safe_extract_rejects_escaping_members(tmp_path, member):
    archive = _make_zip(tmp_path / "evil.zip", {member: b"pwned"})
    target = tmp_path / "out"

    with pytest.raises(ValueError):
        safe_extract(archive, target)


def test_safe_extract_writes_nothing_when_one_member_is_unsafe(tmp_path):
    archive = _make_zip(tmp_path / "mixed.zip", {
        "innocent.txt": b"fine",
        "../evil.txt": b"pwned",
    })
    target = tmp_path / "out"

    with pytest.raises(ValueError):
        safe_extract(archive, target)

    # Validated up front: not even the harmless member made it to disk.
    assert not (target / "innocent.txt").exists()
    assert not (tmp_path / "evil.txt").exists()


# --------------------------------------------------------------------------
# asset selection
# --------------------------------------------------------------------------

def test_select_assets_picks_zip_and_its_sidecar():
    assets = [
        {"name": "source.tar.gz", "browser_download_url": "https://x/source.tar.gz"},
        {"name": _ZIP_NAME, "browser_download_url": _BASE_URL},
        {"name": f"{_ZIP_NAME}.sha256", "browser_download_url": f"{_BASE_URL}.sha256"},
    ]

    assert select_assets(assets) == (_BASE_URL, f"{_BASE_URL}.sha256")


def test_select_assets_without_sidecar():
    assets = [{"name": _ZIP_NAME, "browser_download_url": _BASE_URL}]
    assert select_assets(assets) == (_BASE_URL, "")


def test_select_assets_with_no_build_asset():
    assert select_assets([{"name": "notes.md", "browser_download_url": "https://x/notes.md"}]) == ("", "")
    assert select_assets([]) == ("", "")


def test_sidecar_url_is_the_asset_url_plus_suffix():
    assert sha256_sidecar_url(_BASE_URL) == f"{_BASE_URL}.sha256"
    assert sha256_sidecar_url("") == ""
