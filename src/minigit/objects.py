"""Git Object Model: Blobs, Trees, Commits, and Tags.

Under the hood, every Git object is stored with a universal header:
    b"[type] [size]\\x00[content]"

And its unique identifier (Object ID) is the 40-character hexadecimal SHA-1
hash of that entire byte string.
"""

from __future__ import annotations

import hashlib
import zlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from minigit.repository import GitRepository


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


def object_format(data: bytes, fmt: bytes = b"blob") -> bytes:
    """Format raw data into standard Git object format: [type] [size]\\x00[data]."""
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


