"""Git Object Model: Blobs, Trees, Commits, and Tags.

Under the hood, every Git object is stored with a universal header:
    b"[type] [size]\\x00[content]"

And its unique identifier (Object ID) is the 40-character hexadecimal SHA-1
hash of that entire byte string.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import time
import zlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from minigit.repository import GitRepository


@dataclass
class GitTreeLeaf:
    """Represents a single file or subdirectory entry inside a Git tree."""

    mode: str
    path: str
    sha: str


class GitObject:
    """Base class for all Git objects (blob, commit, tree, tag)."""

    fmt: bytes = b""

    def __init__(self, data: bytes | None = None) -> None:
        if data is not None:
            self.deserialize(data)
        else:
            self.init()

    def init(self) -> None:
        """Initialize empty object fields."""
        pass

    def serialize(self) -> bytes:
        """Must be implemented by subclasses to convert object to raw bytes."""
        raise NotImplementedError("Subclasses must implement serialize()")

    def deserialize(self, data: bytes) -> None:
        """Must be implemented by subclasses to parse raw bytes into fields."""
        raise NotImplementedError("Subclasses must implement deserialize()")


class GitBlob(GitObject):
    """A Git Blob (Binary Large Object) stores raw file contents.

    Notice that a blob does NOT store the filename, timestamp, or permissions!
    It only stores the pure bytes of the file.
    """

    fmt = b"blob"

    def init(self) -> None:
        self.blobdata = b""

    def serialize(self) -> bytes:
        return self.blobdata

    def deserialize(self, data: bytes) -> None:
        self.blobdata = data


class GitTree(GitObject):
    """A Git Tree stores directory contents (linking names to Blobs or sub-Trees)."""

    fmt = b"tree"

    def init(self) -> None:
        self.items: list[GitTreeLeaf] = []

    def serialize(self) -> bytes:
        def sort_key(leaf: GitTreeLeaf) -> bytes:
            name = leaf.path
            if leaf.mode.startswith("4") or leaf.mode.startswith("04"):
                name += "/"
            return name.encode("utf-8")

        sorted_items = sorted(self.items, key=sort_key)
        out = bytearray()
        for item in sorted_items:
            mode = "40000" if item.mode in ("040000", "40000") else item.mode
            out.extend(f"{mode} {item.path}\x00".encode("utf-8"))
            out.extend(bytes.fromhex(item.sha))
        return bytes(out)

    def deserialize(self, data: bytes) -> None:
        self.items = []
        pos = 0
        max_len = len(data)
        while pos < max_len:
            space_idx = data.find(b" ", pos)
            if space_idx == -1:
                raise ValueError("Malformed tree object: missing space delimiter")
            mode = data[pos:space_idx].decode("ascii")

            null_idx = data.find(b"\x00", space_idx)
            if null_idx == -1:
                raise ValueError("Malformed tree object: missing null byte delimiter")
            path = data[space_idx + 1 : null_idx].decode("utf-8", errors="replace")

            sha_bytes = data[null_idx + 1 : null_idx + 21]
            if len(sha_bytes) != 20:
                raise ValueError("Malformed tree object: truncated SHA-1 bytes")
            sha = sha_bytes.hex()

            self.items.append(GitTreeLeaf(mode=mode, path=path, sha=sha))
            pos = null_idx + 21


class GitCommit(GitObject):
    """A Git Commit links a tree snapshot, parent commit(s), author metadata, and message."""

    fmt = b"commit"

    def init(self) -> None:
        self.tree: str = ""
        self.parents: list[str] = []
        self.author: str = ""
        self.committer: str = ""
        self.message: str = ""

    def serialize(self) -> bytes:
        lines = [f"tree {self.tree}"]
        for parent in self.parents:
            lines.append(f"parent {parent}")
        if self.author:
            lines.append(f"author {self.author}")
        if self.committer:
            lines.append(f"committer {self.committer}")
        lines.append("")
        msg = self.message.rstrip("\n") + "\n"
        lines.append(msg)
        return "\n".join(lines).encode("utf-8")

    def deserialize(self, data: bytes) -> None:
        text = data.decode("utf-8", errors="replace")
        header_part, _, message_part = text.partition("\n\n")
        self.message = message_part
        self.parents = []
        self.tree = ""
        self.author = ""
        self.committer = ""

        for line in header_part.splitlines():
            if line.startswith("tree "):
                self.tree = line[5:].strip()
            elif line.startswith("parent "):
                self.parents.append(line[7:].strip())
            elif line.startswith("author "):
                self.author = line[7:].strip()
            elif line.startswith("committer "):
                self.committer = line[10:].strip()


def default_author_committer() -> str:
    """Generate author/committer string: Name <email> timestamp timezone."""
    name = os.environ.get("GIT_AUTHOR_NAME", "Minigit Operator")
    email = os.environ.get("GIT_AUTHOR_EMAIL", "operator@minigit.local")
    now = int(time.time())

    if time.localtime().tm_isdst and time.daylight:
        tz_offset_sec = -time.altzone
    else:
        tz_offset_sec = -time.timezone

    tz_hours = tz_offset_sec // 3600
    tz_mins = abs(tz_offset_sec % 3600) // 60
    tz_sign = "+" if tz_hours >= 0 else "-"
    tz_str = f"{tz_sign}{abs(tz_hours):02d}{tz_mins:02d}"
    return f"{name} <{email}> {now} {tz_str}"


def object_format(data: bytes, fmt: bytes = b"blob") -> bytes:
    """Format raw data into standard Git object format: [type] [size]\x00[data]."""
    header = f"{fmt.decode('ascii')} {len(data)}\x00".encode("ascii")
    return header + data


def object_hash(data: bytes, fmt: bytes = b"blob") -> tuple[str, bytes]:
    """Calculate SHA-1 hash for a Git object and return (40-hex-sha, full_formatted_data)."""
    formatted = object_format(data, fmt=fmt)
    sha = hashlib.sha1(formatted).hexdigest()
    return sha, formatted


def object_write(obj: GitObject, repo: GitRepository | None = None) -> str:
    """Serialize, format, hash, and optionally write a GitObject to the repository database."""
    data = obj.serialize()
    sha, formatted = object_hash(data, fmt=obj.fmt)

    if repo is not None:
        path = repo.repo_file("objects", sha[:2], sha[2:], mkdir=True)
        if not path.exists():
            path.write_bytes(zlib.compress(formatted))

    return sha


OBJECT_CLASSES: dict[bytes, type[GitObject]] = {
    b"blob": GitBlob,
    b"tree": GitTree,
    b"commit": GitCommit,
}


def object_read(repo: GitRepository, sha: str) -> GitObject:
    """Read an object from repository database by its SHA-1 hash and return GitObject."""
    path = repo.repo_file("objects", sha[:2], sha[2:])

    if not path.is_file():
        raise FileNotFoundError(f"Object {sha} not found")

    raw = zlib.decompress(path.read_bytes())

    # Read object type (ends at first space)
    space_idx = raw.find(b" ")
    if space_idx == -1:
        raise ValueError(f"Malformed object {sha}: missing type header delimiter")
    fmt = raw[:space_idx]

    # Read object size (ends at first null byte)
    null_idx = raw.find(b"\x00", space_idx)
    if null_idx == -1:
        raise ValueError(f"Malformed object {sha}: missing null byte delimiter")
    size = int(raw[space_idx + 1 : null_idx].decode("ascii"))

    payload = raw[null_idx + 1 :]
    if len(payload) != size:
        raise ValueError(f"Malformed object {sha}: bad length ({len(payload)} != {size})")

    cls = OBJECT_CLASSES.get(fmt)
    if not cls:
        raise ValueError(f"Unknown object type: {fmt.decode('ascii', errors='replace')}")

    obj = cls()
    obj.deserialize(payload)
    return obj


def tree_write_from_directory(
    directory: str | Path,
    repo: GitRepository,
    ignore_names: set[str] | None = None,
    is_root: bool = True,
) -> str:
    """Recursively traverse a directory, store blobs and sub-trees, and return root tree SHA-1."""
    dir_path = Path(directory).resolve()
    if ignore_names is None:
        ignore_names = {".git", ".pytest_cache", "__pycache__", ".venv", "venv", ".egg-info"}

    tree = GitTree()

    # Iterate sorted entries in directory
    for entry in sorted(dir_path.iterdir(), key=lambda p: p.name):
        if entry.name in ignore_names or entry.name.endswith(".egg-info"):
            continue

        if entry.is_dir():
            # Recursively build sub-tree
            sub_sha = tree_write_from_directory(
                entry, repo, ignore_names=ignore_names, is_root=False
            )
            # Git does not track empty directories
            if sub_sha:
                tree.items.append(
                    GitTreeLeaf(
                        mode="040000",
                        path=entry.name,
                        sha=sub_sha,
                    )
                )
        elif entry.is_file():
            data = entry.read_bytes()
            blob = GitBlob()
            blob.deserialize(data)
            blob_sha = object_write(blob, repo=repo)

            mode = "100644"
            if os.name != "nt" and os.access(entry, os.X_OK):
                mode = "100755"

            tree.items.append(
                GitTreeLeaf(
                    mode=mode,
                    path=entry.name,
                    sha=blob_sha,
                )
            )

    if not tree.items and not is_root:
        return ""

    return object_write(tree, repo=repo)



