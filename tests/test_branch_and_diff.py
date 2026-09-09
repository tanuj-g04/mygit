import os

import pytest

from mygit import objects, repository


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repository.init(".")
    return tmp_path


def _commit(repo, message):
    tree_sha1 = objects.write_tree(str(repo))
    parent_sha1 = repository.get_current_commit()
    commit_sha1 = objects.commit_tree(tree_sha1, parent_sha1, message)
    repository.update_ref(repository.get_head_ref(), commit_sha1)
    return commit_sha1


# --- branches ---

def test_list_branches_empty_initially(repo):
    assert repository.list_branches() == []


def test_create_branch_requires_a_commit(repo):
    with pytest.raises(ValueError):
        from mygit.cli import cmd_branch
        cmd_branch(type("Args", (), {"name": "feature"})())


def test_create_branch_points_at_current_commit(repo):
    (repo / "a.txt").write_text("A")
    commit1 = _commit(repo, "first")

    repository.update_ref("refs/heads/feature", commit1)
    assert "feature" in repository.list_branches()
    assert repository.read_ref("refs/heads/feature") == commit1


# --- checkout ---

def test_checkout_restores_files_from_target_branch(repo):
    (repo / "a.txt").write_text("version 1")
    commit1 = _commit(repo, "first")
    repository.update_ref("refs/heads/feature", commit1)

    (repo / "a.txt").write_text("version 2")
    _commit(repo, "second")  # advances master, feature still points at commit1

    # Switch to feature -- working dir should revert to "version 1"
    feature_commit = repository.read_ref("refs/heads/feature")
    tree_sha1 = objects.read_commit(feature_commit)["tree"]
    objects.checkout_tree(tree_sha1, str(repo))

    assert (repo / "a.txt").read_text() == "version 1"


def test_checkout_removes_files_not_in_target_tree(repo):
    (repo / "a.txt").write_text("A")
    commit1 = _commit(repo, "first")

    (repo / "b.txt").write_text("B")
    _commit(repo, "second")

    # Check out commit1's tree -- b.txt (added after commit1) should be removed
    tree_sha1 = objects.read_commit(commit1)["tree"]
    objects.checkout_tree(tree_sha1, str(repo))

    assert (repo / "a.txt").exists()
    assert not (repo / "b.txt").exists()


def test_checkout_updates_head(repo):
    (repo / "a.txt").write_text("A")
    commit1 = _commit(repo, "first")
    repository.update_ref("refs/heads/feature", commit1)

    from mygit.cli import cmd_checkout
    cmd_checkout(type("Args", (), {"branch": "feature"})())

    assert repository.get_head_ref() == "refs/heads/feature"


def test_checkout_nonexistent_branch_raises(repo):
    from mygit.cli import cmd_checkout
    with pytest.raises(FileNotFoundError):
        cmd_checkout(type("Args", (), {"branch": "does-not-exist"})())


# --- diff ---

def test_diff_detects_added_file(repo):
    _commit(repo, "empty commit")
    (repo / "new.txt").write_text("new content")

    tree_sha1 = objects.read_commit(repository.get_current_commit())["tree"]
    changes = objects.diff_working_directory(str(repo), tree_sha1)

    assert len(changes) == 1
    assert changes[0]["status"] == "added"
    assert changes[0]["path"] == "new.txt"


def test_diff_detects_removed_file(repo):
    (repo / "a.txt").write_text("A")
    commit1 = _commit(repo, "first")
    os.remove(repo / "a.txt")

    tree_sha1 = objects.read_commit(commit1)["tree"]
    changes = objects.diff_working_directory(str(repo), tree_sha1)

    assert len(changes) == 1
    assert changes[0]["status"] == "removed"


def test_diff_detects_modified_file_with_line_diff(repo):
    (repo / "a.txt").write_text("line one\nline two\n")
    commit1 = _commit(repo, "first")
    (repo / "a.txt").write_text("line one\nline TWO CHANGED\n")

    tree_sha1 = objects.read_commit(commit1)["tree"]
    changes = objects.diff_working_directory(str(repo), tree_sha1)

    assert len(changes) == 1
    assert changes[0]["status"] == "modified"
    diff_text = "".join(changes[0]["diff"])
    assert "line TWO CHANGED" in diff_text


def test_diff_no_changes_returns_empty(repo):
    (repo / "a.txt").write_text("A")
    commit1 = _commit(repo, "first")

    tree_sha1 = objects.read_commit(commit1)["tree"]
    changes = objects.diff_working_directory(str(repo), tree_sha1)

    assert changes == []
