import pytest

from mygit import repository


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repository.init(".")
    return tmp_path


def test_head_ref_defaults_to_master(repo):
    assert repository.get_head_ref() == "refs/heads/master"


def test_current_commit_is_none_before_any_commits(repo):
    assert repository.get_current_commit() is None


def test_update_ref_then_read_ref_round_trips(repo):
    fake_sha1 = "a" * 40
    repository.update_ref("refs/heads/master", fake_sha1)
    assert repository.read_ref("refs/heads/master") == fake_sha1


def test_get_current_commit_reflects_updated_ref(repo):
    fake_sha1 = "b" * 40
    repository.update_ref(repository.get_head_ref(), fake_sha1)
    assert repository.get_current_commit() == fake_sha1


def test_read_ref_missing_returns_none(repo):
    assert repository.read_ref("refs/heads/nonexistent-branch") is None
