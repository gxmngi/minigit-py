"""Tests for Three-Way Merge Engine and Conflict Synthesis."""

from pathlib import Path
import pytest

from minigit.cli import main
from minigit.merge import find_merge_base, merge_3way_text, merge_branches
from minigit.objects import GitBlob, GitCommit, GitTree, object_write, tree_write_from_directory
from minigit.refs import branch_create, checkout, ref_resolve, ref_update
from minigit.repository import repo_create


def test_merge_3way_text_clean_disjoint():
    base = ["header\n", "item A\n", "item B\n", "footer\n"]
    # Branch 1 changes item A
    a = ["header\n", "item A modified\n", "item B\n", "footer\n"]
    # Branch 2 changes item B
    b = ["header\n", "item A\n", "item B modified\n", "footer\n"]

    merged, has_conflict = merge_3way_text(base, a, b, label_a="HEAD", label_b="feature")
    assert not has_conflict
    assert merged == ["header\n", "item A modified\n", "item B modified\n", "footer\n"]


def test_merge_3way_text_conflict_synthesis():
    base = ["header\n", "original content\n", "footer\n"]
    a = ["header\n", "author A content\n", "footer\n"]
    b = ["header\n", "author B content\n", "footer\n"]

    merged, has_conflict = merge_3way_text(base, a, b, label_a="HEAD", label_b="feature")
    assert has_conflict

    joined = "".join(merged)
    assert "<<<<<<< HEAD\n" in joined
    assert "author A content\n" in joined
    assert "=======\n" in joined
    assert "author B content\n" in joined
    assert ">>>>>>> feature\n" in joined


def test_find_merge_base(tmp_path: Path):
    repo = repo_create(tmp_path / "repo")
    tree = GitTree()
    tree_sha = object_write(tree, repo=repo)

    # Root commit C0
    c0 = GitCommit()
    c0.tree = tree_sha
    c0.author = "Test <test@example.com> 1000 +0000"
    c0.committer = c0.author
    c0.message = "C0 initial"
    c0_sha = object_write(c0, repo=repo)

    # Branch A: C0 -> C1
    c1 = GitCommit()
    c1.tree = tree_sha
    c1.parents = [c0_sha]
    c1.author = "Test <test@example.com> 1010 +0000"
    c1.committer = c1.author
    c1.message = "C1 branch A"
    c1_sha = object_write(c1, repo=repo)

    # Branch B: C0 -> C2
    c2 = GitCommit()
    c2.tree = tree_sha
    c2.parents = [c0_sha]
    c2.author = "Test <test@example.com> 1020 +0000"
    c2.committer = c2.author
    c2.message = "C2 branch B"
    c2_sha = object_write(c2, repo=repo)

    # LCA should be C0
    base = find_merge_base(repo, c1_sha, c2_sha)
    assert base == c0_sha


def test_fast_forward_merge(tmp_path: Path, monkeypatch, capsys):
    repo = repo_create(tmp_path / "repo")
    work = repo.worktree

    # Initial commit on main
    (work / "file.txt").write_text("initial\n", encoding="utf-8")
    monkeypatch.chdir(work)

    assert main(["write-tree"]) == 0
    t0 = capsys.readouterr().out.strip()
    assert main(["commit-tree", t0, "-m", "Initial commit"]) == 0
    c0 = capsys.readouterr().out.strip()
    ref_update(repo, "refs/heads/main", c0)

    # Create and checkout feature
    branch_create(repo, "feature", "main")
    checkout(repo, "feature")

    # Advance feature branch
    (work / "file.txt").write_text("feature update\n", encoding="utf-8")
    assert main(["write-tree"]) == 0
    t1 = capsys.readouterr().out.strip()
    assert main(["commit-tree", t1, "-p", c0, "-m", "Feature commit"]) == 0
    c1 = capsys.readouterr().out.strip()
    ref_update(repo, "refs/heads/feature", c1)

    # Switch back to main and merge feature (Fast-forward)
    checkout(repo, "main")
    code, msg = merge_branches(repo, "feature")
    assert code == 0
    assert "Fast-forward" in msg
    assert (work / "file.txt").read_text(encoding="utf-8") == "feature update\n"


def test_three_way_merge_clean(tmp_path: Path, monkeypatch, capsys):
    repo = repo_create(tmp_path / "repo")
    work = repo.worktree
    monkeypatch.chdir(work)

    # Common ancestor: base.txt and shared.txt
    (work / "base.txt").write_text("line1\nline2\nline3\n", encoding="utf-8")
    (work / "common.txt").write_text("untouched\n", encoding="utf-8")
    assert main(["write-tree"]) == 0
    t0 = capsys.readouterr().out.strip()
    assert main(["commit-tree", t0, "-m", "C0 base"]) == 0
    c0 = capsys.readouterr().out.strip()
    ref_update(repo, "refs/heads/main", c0)

    # Branch feature
    branch_create(repo, "feature", "main")
    checkout(repo, "feature")
    (work / "base.txt").write_text("line1\nline2\nline3 modified by feature\n", encoding="utf-8")
    assert main(["write-tree"]) == 0
    t_feat = capsys.readouterr().out.strip()
    assert main(["commit-tree", t_feat, "-p", c0, "-m", "Feature edit"]) == 0
    c_feat = capsys.readouterr().out.strip()
    ref_update(repo, "refs/heads/feature", c_feat)

    # Back to main, edit line1 in base.txt (disjoint from feature edit!)
    checkout(repo, "main")
    (work / "base.txt").write_text("line1 modified by main\nline2\nline3\n", encoding="utf-8")
    assert main(["write-tree"]) == 0
    t_main = capsys.readouterr().out.strip()
    assert main(["commit-tree", t_main, "-p", c0, "-m", "Main edit"]) == 0
    c_main = capsys.readouterr().out.strip()
    ref_update(repo, "refs/heads/main", c_main)

    # Merge feature into main
    code, msg = merge_branches(repo, "feature")
    assert code == 0
    assert "three-way" in msg

    # File should have both edits cleanly merged
    expected = "line1 modified by main\nline2\nline3 modified by feature\n"
    assert (work / "base.txt").read_text(encoding="utf-8") == expected


def test_three_way_merge_conflict_markers(tmp_path: Path, monkeypatch, capsys):
    repo = repo_create(tmp_path / "repo")
    work = repo.worktree
    monkeypatch.chdir(work)

    # Common ancestor
    (work / "conflict.txt").write_text("version 1.0\n", encoding="utf-8")
    assert main(["write-tree"]) == 0
    t0 = capsys.readouterr().out.strip()
    assert main(["commit-tree", t0, "-m", "Initial"]) == 0
    c0 = capsys.readouterr().out.strip()
    ref_update(repo, "refs/heads/main", c0)

    # Feature branch edits the same line
    branch_create(repo, "feature-alpha", "main")
    checkout(repo, "feature-alpha")
    (work / "conflict.txt").write_text("version 2.0-alpha\n", encoding="utf-8")
    assert main(["write-tree"]) == 0
    t_feat = capsys.readouterr().out.strip()
    assert main(["commit-tree", t_feat, "-p", c0, "-m", "Feature Alpha"]) == 0
    c_feat = capsys.readouterr().out.strip()
    ref_update(repo, "refs/heads/feature-alpha", c_feat)

    # Main branch edits the same line differently
    checkout(repo, "main")
    (work / "conflict.txt").write_text("version 2.0-main\n", encoding="utf-8")
    assert main(["write-tree"]) == 0
    t_main = capsys.readouterr().out.strip()
    assert main(["commit-tree", t_main, "-p", c0, "-m", "Main Version"]) == 0
    c_main = capsys.readouterr().out.strip()
    ref_update(repo, "refs/heads/main", c_main)

    # Merge should fail and synthesize conflict markers
    code, msg = merge_branches(repo, "feature-alpha")
    assert code == 1
    assert "Automatic merge failed" in msg

    content = (work / "conflict.txt").read_text(encoding="utf-8")
    assert "<<<<<<< HEAD\n" in content
    assert "version 2.0-main\n" in content
    assert "=======\n" in content
    assert "version 2.0-alpha\n" in content
    assert ">>>>>>> feature-alpha\n" in content
