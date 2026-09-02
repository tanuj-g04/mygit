"""
Tests for mygit.objects' Day 2 additions: write_tree/read_tree and
commit_tree/read_commit.
"""

import os

import pytest

from mygit import objects, repository


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repository.init(".")
    return tmp_path


def test_write_tree_on_empty_directory(repo):
    """An empty (just-initialized) repo should produce a tree with zero entries."""
    sha1 = objects.write_tree(str(repo))
    entries = objects.read_tree(sha1)
    assert entries == []


def test_write_tree_includes_files_and_excludes_mygit_dir(repo):
    (repo / "a.txt").write_text("A")
    (repo / "b.txt").write_text("B")

    sha1 = objects.write_tree(str(repo))
    entries = objects.read_tree(sha1)
    names = {e["name"] for e in entries}

    assert names == {"a.txt", "b.txt"}
    assert ".mygit" not in names


def test_write_tree_entries_are_sorted_by_name(repo):
    (repo / "zebra.txt").write_text("z")
    (repo / "apple.txt").write_text("a")
    (repo / "mango.txt").write_text("m")

    sha1 = objects.write_tree(str(repo))
    entries = objects.read_tree(sha1)
    names = [e["name"] for e in entries]

    assert names == sorted(names)


def test_write_tree_recurses_into_subdirectories(repo):
    subdir = repo / "src"
    subdir.mkdir()
    (subdir / "main.py").write_text("print('hi')")

    sha1 = objects.write_tree(str(repo))
    entries = objects.read_tree(sha1)

    src_entry = next(e for e in entries if e["name"] == "src")
    assert src_entry["type"] == "tree"

    subtree_entries = objects.read_tree(src_entry["sha1"])
    assert subtree_entries[0]["name"] == "main.py"
    assert subtree_entries[0]["type"] == "blob"


def test_write_tree_file_entry_points_at_correct_blob(repo):
    (repo / "file.txt").write_text("hello world")

    sha1 = objects.write_tree(str(repo))
    entries = objects.read_tree(sha1)
    file_entry = entries[0]

    obj_type, content = objects.read_object(file_entry["sha1"])
    assert obj_type == "blob"
    assert content == b"hello world"


def test_identical_directory_state_produces_identical_tree_hash(repo):
    """
    The core dedup property, one level up from blobs: an unchanged
    directory must hash identically every time, since a commit that
    doesn't touch the working tree should reuse the existing tree object.
    """
    (repo / "a.txt").write_text("A")
    sha1_first = objects.write_tree(str(repo))
    sha1_second = objects.write_tree(str(repo))
    assert sha1_first == sha1_second


def test_write_tree_changes_hash_when_content_changes(repo):
    (repo / "a.txt").write_text("A")
    sha1_before = objects.write_tree(str(repo))

    (repo / "a.txt").write_text("A modified")
    sha1_after = objects.write_tree(str(repo))

    assert sha1_before != sha1_after


def test_commit_tree_with_no_parent(repo):
    tree_sha1 = objects.write_tree(str(repo))
    commit_sha1 = objects.commit_tree(tree_sha1, None, "Initial commit")

    commit = objects.read_commit(commit_sha1)
    assert commit["tree"] == tree_sha1
    assert commit["parent"] is None
    assert commit["message"] == "Initial commit"


def test_commit_tree_with_parent_chain(repo):
    tree1 = objects.write_tree(str(repo))
    commit1 = objects.commit_tree(tree1, None, "First")

    (repo / "new.txt").write_text("new file")
    tree2 = objects.write_tree(str(repo))
    commit2 = objects.commit_tree(tree2, commit1, "Second")

    commit2_data = objects.read_commit(commit2)
    assert commit2_data["parent"] == commit1
    assert commit2_data["tree"] == tree2


def test_commit_tree_reading_wrong_type_raises(repo):
    tree_sha1 = objects.write_tree(str(repo))
    with pytest.raises(ValueError):
        objects.read_commit(tree_sha1)  # this is a tree, not a commit


def test_read_tree_reading_wrong_type_raises(repo):
    (repo / "a.txt").write_text("A")
    blob_sha1 = objects.hash_object(b"A", write=True)
    with pytest.raises(ValueError):
        objects.read_tree(blob_sha1)  # this is a blob, not a tree
