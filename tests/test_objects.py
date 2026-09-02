"""
Tests for mygit.objects. Each test runs inside a fresh temp directory
with its own initialized repo, so tests never touch each other's state
or the real filesystem outside pytest's tmp_path.
"""

import hashlib
import os

import pytest

from mygit import objects, repository


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Initialize a fresh mygit repo in a temp dir and cd into it."""
    monkeypatch.chdir(tmp_path)
    repository.init(".")
    return tmp_path


def test_hash_object_matches_git_style_sha1(repo):
    """
    Verify our hash exactly matches what real git would compute, since
    the whole point of the header scheme is git-compatibility of the
    hashing algorithm (not full file-format compatibility, since we
    don't implement git's pack format).
    """
    data = b"hello world\n"
    expected_header = f"blob {len(data)}\0".encode()
    expected_sha1 = hashlib.sha1(expected_header + data).hexdigest()

    sha1 = objects.hash_object(data, write=False)

    assert sha1 == expected_sha1
    # Sanity-check against git's well-known hash for this exact content.
    assert sha1 == "3b18e512dba79e4c8300dd08aeb37f8e728b8dad"


def test_write_false_does_not_persist(repo):
    sha1 = objects.hash_object(b"not stored", write=False)
    obj_path = os.path.join(repo, ".mygit", "objects", sha1[:2], sha1[2:])
    assert not os.path.exists(obj_path)


def test_write_true_persists_and_is_retrievable(repo):
    data = b"stored content\n"
    sha1 = objects.hash_object(data, write=True)

    obj_path = os.path.join(repo, ".mygit", "objects", sha1[:2], sha1[2:])
    assert os.path.exists(obj_path)

    obj_type, retrieved = objects.read_object(sha1)
    assert obj_type == "blob"
    assert retrieved == data


def test_identical_content_dedupes_to_same_object(repo):
    """Two files with identical content must hash and store identically."""
    sha1_a = objects.hash_object(b"same content", write=True)
    sha1_b = objects.hash_object(b"same content", write=True)
    assert sha1_a == sha1_b


def test_different_content_produces_different_hashes(repo):
    sha1_a = objects.hash_object(b"content A", write=True)
    sha1_b = objects.hash_object(b"content B", write=True)
    assert sha1_a != sha1_b


def test_read_object_missing_raises(repo):
    with pytest.raises(FileNotFoundError):
        objects.read_object("0" * 40)


def test_read_object_outside_repo_raises(tmp_path, monkeypatch):
    # No .mygit anywhere above this directory.
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        objects.read_object("0" * 40)


def test_binary_content_round_trips(repo):
    """Non-UTF8 bytes must survive the compress/decompress cycle intact."""
    data = bytes(range(256))
    sha1 = objects.hash_object(data, write=True)
    obj_type, retrieved = objects.read_object(sha1)
    assert retrieved == data
