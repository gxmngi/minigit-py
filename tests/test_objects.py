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



