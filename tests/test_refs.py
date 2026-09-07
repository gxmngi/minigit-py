"""Unit tests for Git references, branches, and ref resolution."""

from pathlib import Path
import pytest

from minigit.cli import main
from minigit.objects import GitCommit, GitTree, object_write
from minigit.refs import (
    branch_create,
    get_current_branch,
    ref_list,
    ref_resolve,
    ref_update,
)
from minigit.repository import repo_create


def test_ref_update_and_resolve(tmp_path: Path):
    repo = repo_create(tmp_path / "repo")
    fake_sha = "a" * 40

    ref_update(repo, "refs/heads/main", fake_sha)

    # Should resolve by full ref
    assert ref_resolve(repo, "refs/heads/main") == fake_sha
    # Should resolve by short branch name
    assert ref_resolve(repo, "main") == fake_sha
    # HEAD points to refs/heads/main, so resolving HEAD should follow the symref
    assert ref_resolve(repo, "HEAD") == fake_sha


def test_get_current_branch(tmp_path: Path):
    repo = repo_create(tmp_path / "repo")
    assert get_current_branch(repo) == "main"


def test_branch_create_and_list(tmp_path: Path):
    repo = repo_create(tmp_path / "repo")
    fake_sha = "b" * 40
    ref_update(repo, "refs/heads/main", fake_sha)

    # Create new branch 'feature-login' from main
    sha = branch_create(repo, "feature-login", "main")
    assert sha == fake_sha

    # Cannot create duplicate branch
    with pytest.raises(FileExistsError):
        branch_create(repo, "feature-login", "main")

    branches = ref_list(repo, "refs/heads")
    assert "main" in branches
    assert "feature-login" in branches
    assert branches["feature-login"] == fake_sha


def test_cli_branch_and_update_ref(tmp_path: Path, monkeypatch, capsys):
    repo = repo_create(tmp_path / "repo")
    fake_sha = "c" * 40

    monkeypatch.chdir(repo.worktree)

    # update-ref
    assert main(["update-ref", "refs/heads/main", fake_sha]) == 0
    assert ref_resolve(repo, "main") == fake_sha

    # branch create
    assert main(["branch", "dev"]) == 0
    assert ref_resolve(repo, "dev") == fake_sha

    # branch list
    assert main(["branch"]) == 0
    captured = capsys.readouterr()
    assert "* main" in captured.out
    assert "  dev" in captured.out


def test_checkout_restores_working_tree(tmp_path: Path):
    from minigit.objects import GitBlob, GitCommit, GitTree, GitTreeLeaf, object_write
    from minigit.refs import checkout

    repo = repo_create(tmp_path / "repo")

    # 1. Create Commit 1 (file.txt = "version 1")
    blob1 = GitBlob()
    blob1.deserialize(b"version 1\n")
    blob1_sha = object_write(blob1, repo)

    tree1 = GitTree()
    tree1.items = [GitTreeLeaf(mode="100644", path="file.txt", sha=blob1_sha)]
    tree1_sha = object_write(tree1, repo)

    c1 = GitCommit()
    c1.tree = tree1_sha
    c1.author = "Rusdan <rusdan@example.com> 1725700000 +0700"
    c1.committer = c1.author
    c1.message = "Commit 1"
    c1_sha = object_write(c1, repo)
    ref_update(repo, "refs/heads/main", c1_sha)

    # 2. Create Commit 2 (file.txt = "version 2")
    blob2 = GitBlob()
    blob2.deserialize(b"version 2\n")
    blob2_sha = object_write(blob2, repo)

    tree2 = GitTree()
    tree2.items = [GitTreeLeaf(mode="100644", path="file.txt", sha=blob2_sha)]
    tree2_sha = object_write(tree2, repo)

    c2 = GitCommit()
    c2.tree = tree2_sha
    c2.parents = [c1_sha]
    c2.author = "Rusdan <rusdan@example.com> 1725700100 +0700"
    c2.committer = c2.author
    c2.message = "Commit 2"
    c2_sha = object_write(c2, repo)
    ref_update(repo, "refs/heads/v2-branch", c2_sha)

    # Checkout v2-branch: file.txt should become "version 2\n"
    checkout(repo, "v2-branch")
    assert get_current_branch(repo) == "v2-branch"
    file_on_disk = repo.worktree / "file.txt"
    assert file_on_disk.is_file()
    assert file_on_disk.read_bytes() == b"version 2\n"

    # Checkout main: file.txt should become "version 1\n"
    checkout(repo, "main")
    assert get_current_branch(repo) == "main"
    assert file_on_disk.read_bytes() == b"version 1\n"


def test_cli_checkout_b_flag(tmp_path: Path, monkeypatch, capsys):
    from minigit.objects import GitBlob, GitCommit, GitTree, GitTreeLeaf, object_write

    repo = repo_create(tmp_path / "repo")
    blob = GitBlob()
    blob.deserialize(b"initial\n")
    b_sha = object_write(blob, repo)

    tree = GitTree()
    tree.items = [GitTreeLeaf(mode="100644", path="a.txt", sha=b_sha)]
    t_sha = object_write(tree, repo)

    c = GitCommit()
    c.tree = t_sha
    c.message = "init"
    c_sha = object_write(c, repo)
    ref_update(repo, "refs/heads/main", c_sha)

    monkeypatch.chdir(repo.worktree)

    # checkout -b new-feature
    assert main(["checkout", "-b", "new-feature"]) == 0
    assert get_current_branch(repo) == "new-feature"

    captured = capsys.readouterr()
    assert "Switched to branch 'new-feature'" in captured.out


