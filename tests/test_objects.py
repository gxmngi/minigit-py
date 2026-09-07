import zlib
from pathlib import Path

import pytest
from minigit.objects import GitBlob, object_format, object_hash, object_write
from minigit.repository import repo_create


def test_object_format_blob():
    data = b"hello world\n"
    formatted = object_format(data, fmt=b"blob")
    assert formatted == b"blob 12\x00hello world\n"


def test_empty_blob_hash():
    # In Git, the SHA-1 of an empty blob is universally known
    sha, formatted = object_hash(b"", fmt=b"blob")
    assert formatted == b"blob 0\x00"
    assert sha == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"


def test_hello_world_blob_hash():
    data = b"hello world\n"
    sha, _ = object_hash(data, fmt=b"blob")
    # Matches official git hash-object
    assert sha == "3b18e512dba79e4c8300dd08aeb37f8e728b8dad"


def test_git_blob_serialize_deserialize():
    blob = GitBlob()
    blob.deserialize(b"sample payload")
    assert blob.serialize() == b"sample payload"


def test_object_write_to_repo(tmp_path: Path):
    repo = repo_create(tmp_path / "repo")
    blob = GitBlob()
    blob.deserialize(b"hello world\n")

    sha = object_write(blob, repo=repo)
    assert sha == "3b18e512dba79e4c8300dd08aeb37f8e728b8dad"

    obj_file = repo.gitdir / "objects" / "3b" / "18e512dba79e4c8300dd08aeb37f8e728b8dad"
    assert obj_file.is_file()

    # Verify zlib compressed content
    raw_compressed = obj_file.read_bytes()
    decompressed = zlib.decompress(raw_compressed)
    assert decompressed == b"blob 12\x00hello world\n"


def test_object_read_from_repo(tmp_path: Path):
    from minigit.objects import object_read

    repo = repo_create(tmp_path / "repo")
    blob = GitBlob()
    blob.deserialize(b"systematic trading with Python\n")

    sha = object_write(blob, repo=repo)
    read_obj = object_read(repo, sha)

    assert isinstance(read_obj, GitBlob)
    assert read_obj.fmt == b"blob"
    assert read_obj.serialize() == b"systematic trading with Python\n"


def test_object_read_missing_raises(tmp_path: Path):
    from minigit.objects import object_read

    repo = repo_create(tmp_path / "repo")
    with pytest.raises(FileNotFoundError):
        object_read(repo, "0" * 40)


def test_cli_cat_file_modes(tmp_path: Path, monkeypatch, capsys):
    import os
    from minigit.cli import main

    repo = repo_create(tmp_path / "repo")
    blob = GitBlob()
    blob.deserialize(b"testing cli cat-file\n")
    sha = object_write(blob, repo=repo)

    monkeypatch.chdir(repo.worktree)

    # Test type flag (-t)
    assert main(["cat-file", "-t", sha]) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "blob"

    # Test size flag (-s)
    assert main(["cat-file", "-s", sha]) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == str(len(b"testing cli cat-file\n"))


def test_tree_serialize_deserialize():
    from minigit.objects import GitTree, GitTreeLeaf

    tree = GitTree()
    tree.items = [
        GitTreeLeaf(mode="100644", path="file1.txt", sha="3b18e512dba79e4c8300dd08aeb37f8e728b8dad"),
        GitTreeLeaf(mode="100755", path="script.sh", sha="e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"),
    ]

    serialized = tree.serialize()
    new_tree = GitTree()
    new_tree.deserialize(serialized)

    assert len(new_tree.items) == 2
    assert new_tree.items[0].path == "file1.txt"
    assert new_tree.items[0].mode == "100644"
    assert new_tree.items[0].sha == "3b18e512dba79e4c8300dd08aeb37f8e728b8dad"
    assert new_tree.items[1].path == "script.sh"


def test_cli_ls_tree(tmp_path: Path, monkeypatch, capsys):
    from minigit.cli import main
    from minigit.objects import GitTree, GitTreeLeaf

    repo = repo_create(tmp_path / "repo")
    tree = GitTree()
    tree.items = [
        GitTreeLeaf(mode="100644", path="test.txt", sha="3b18e512dba79e4c8300dd08aeb37f8e728b8dad")
    ]
    tree_sha = object_write(tree, repo=repo)

    monkeypatch.chdir(repo.worktree)

    # Standard ls-tree
    assert main(["ls-tree", tree_sha]) == 0
    captured = capsys.readouterr()
    assert "100644 blob 3b18e512dba79e4c8300dd08aeb37f8e728b8dad\ttest.txt" in captured.out

    # ls-tree --name-only
    assert main(["ls-tree", "--name-only", tree_sha]) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "test.txt"


def test_tree_write_from_directory(tmp_path: Path):
    from minigit.objects import GitTree, object_read, tree_write_from_directory

    repo = repo_create(tmp_path / "repo")
    work = repo.worktree

    # Create root files
    (work / "file1.txt").write_bytes(b"hello file 1\n")
    (work / "file2.txt").write_bytes(b"hello file 2\n")

    # Create sub-directory with file
    sub = work / "subfolder"
    sub.mkdir()
    (sub / "nested.txt").write_bytes(b"hello nested\n")

    root_tree_sha = tree_write_from_directory(work, repo)
    assert root_tree_sha

    # Verify root tree
    root_tree = object_read(repo, root_tree_sha)
    assert isinstance(root_tree, GitTree)
    assert len(root_tree.items) == 3

    names = [leaf.path for leaf in root_tree.items]
    assert "file1.txt" in names
    assert "file2.txt" in names
    assert "subfolder" in names

    # Subfolder should be mode 40000 and point to another GitTree
    sub_leaf = next(item for item in root_tree.items if item.path == "subfolder")
    assert sub_leaf.mode in ("40000", "040000")
    sub_tree = object_read(repo, sub_leaf.sha)
    assert isinstance(sub_tree, GitTree)
    assert len(sub_tree.items) == 1
    assert sub_tree.items[0].path == "nested.txt"


def test_cli_write_tree(tmp_path: Path, monkeypatch, capsys):
    from minigit.cli import main

    repo = repo_create(tmp_path / "repo")
    (repo.worktree / "sample.txt").write_bytes(b"content\n")

    monkeypatch.chdir(repo.worktree)
    assert main(["write-tree"]) == 0
    captured = capsys.readouterr()
    tree_sha = captured.out.strip()
    assert len(tree_sha) == 40


def test_write_tree_parity_with_official_git(tmp_path: Path):
    import shutil
    import subprocess
    from minigit.objects import tree_write_from_directory
    from minigit.repository import repo_find

    if not shutil.which("git"):
        pytest.skip("Git binary not found in system PATH")

    d = tmp_path / "parity_repo"
    d.mkdir()
    subprocess.run(["git", "init", str(d)], check=True, capture_output=True)

    (d / "file.txt").write_bytes(b"hello git\n")
    sub = d / "sub"
    sub.mkdir()
    (sub / "inner.txt").write_bytes(b"nested data\n")

    repo = repo_find(d)
    minigit_sha = tree_write_from_directory(d, repo)

    subprocess.run(["git", "add", "."], cwd=str(d), check=True, capture_output=True)
    git_sha = subprocess.run(
        ["git", "write-tree"], cwd=str(d), capture_output=True, text=True, check=True
    ).stdout.strip()

    assert minigit_sha == git_sha






