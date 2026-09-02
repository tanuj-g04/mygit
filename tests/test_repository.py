import os

import pytest

from mygit import repository


def test_init_creates_expected_structure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repository.init(".")

    mygit_dir = tmp_path / ".mygit"
    assert mygit_dir.is_dir()
    assert (mygit_dir / "objects").is_dir()
    assert (mygit_dir / "refs" / "heads").is_dir()
    assert (mygit_dir / "HEAD").is_file()
    assert (mygit_dir / "HEAD").read_text() == "ref: refs/heads/master\n"


def test_init_is_idempotent(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    repository.init(".")
    repository.init(".")  # should not raise or wipe existing data

    captured = capsys.readouterr()
    assert "Reinitialized existing" in captured.out


def test_find_repo_root_from_subdirectory(tmp_path, monkeypatch):
    """
    A core git property: commands work from ANY subdirectory of the repo,
    not just the root. This walks upward the same way real git does.
    """
    repository.init(str(tmp_path))
    subdir = tmp_path / "a" / "b" / "c"
    subdir.mkdir(parents=True)
    monkeypatch.chdir(subdir)

    root = repository.find_repo_root()
    assert root == str(tmp_path)


def test_find_repo_root_returns_none_outside_any_repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert repository.find_repo_root() is None


def test_get_mygit_dir_raises_outside_repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        repository.get_mygit_dir()
