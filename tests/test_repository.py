"""Unit tests for Git repository initialization and discovery."""

import os
from pathlib import Path

import pytest
from minigit.repository import GitRepository, repo_create, repo_find


def test_repo_create_creates_git_structure(tmp_path: Path):
    target = tmp_path / "sample_repo"
    repo = repo_create(target)

    assert repo.gitdir.is_dir()
    assert (repo.gitdir / "branches").is_dir()
    assert (repo.gitdir / "objects").is_dir()
    assert (repo.gitdir / "refs" / "heads").is_dir()
    assert (repo.gitdir / "refs" / "tags").is_dir()

    # Check HEAD points to main
    head_content = (repo.gitdir / "HEAD").read_text(encoding="utf-8")
    assert head_content.strip() == "ref: refs/heads/main"

    # Check config
    config_content = (repo.gitdir / "config").read_text(encoding="utf-8")
    assert "[core]" in config_content
    assert "repositoryformatversion = 0" in config_content


def test_repo_create_in_existing_empty_dir(tmp_path: Path):
    target = tmp_path / "empty_dir"
    target.mkdir()
    repo = repo_create(target)
    assert (target / ".git").is_dir()
    assert repo.worktree == target


def test_repo_create_fails_if_already_git_repo(tmp_path: Path):
    target = tmp_path / "duplicate_repo"
    repo_create(target)
    with pytest.raises(FileExistsError):
        repo_create(target)


def test_repo_find_discovers_parent_repo(tmp_path: Path):
    root = tmp_path / "workspace"
    repo = repo_create(root)

    subdir = root / "sub1" / "sub2"
    subdir.mkdir(parents=True)

    found = repo_find(subdir)
    assert found is not None
    assert found.worktree == repo.worktree
    assert found.gitdir == repo.gitdir


def test_repo_find_raises_when_outside_git(tmp_path: Path):
    non_repo = tmp_path / "not_git"
    non_repo.mkdir()
    with pytest.raises(FileNotFoundError):
        repo_find(non_repo, stop_at=tmp_path)

