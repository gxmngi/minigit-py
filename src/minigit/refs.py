"""Git Reference and Branch Management.

In Git, references (refs) are simple files that point to commit hashes.
Branches are stored in '.git/refs/heads/<branch>', tags in '.git/refs/tags/<tag>',
and the special symbolic reference '.git/HEAD' points to the currently checked out branch.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from minigit.repository import GitRepository


HEX_SHA1_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def ref_resolve(repo: GitRepository, ref: str) -> str | None:
    """Resolve a reference, branch name, tag, or 40-char SHA to an object SHA-1."""
    if not ref:
        return None

    # 1. If it is already a 40-char SHA-1
    if HEX_SHA1_RE.match(ref):
        return ref

    # 2. Candidate paths in resolution order
    candidates = [
        ref,
        f"refs/{ref}",
        f"refs/heads/{ref}",
        f"refs/tags/{ref}",
        f"refs/remotes/{ref}",
    ]

    for cand in candidates:
        path = repo.repo_file(cand)
        if path.is_file():
            content = path.read_text(encoding="utf-8").strip()
            if content.startswith("ref: "):
                # Follow symbolic reference recursively
                target_ref = content[5:].strip()
                return ref_resolve(repo, target_ref)
            return content

    return None


def ref_update(repo: GitRepository, ref: str, sha: str) -> None:
    """Write or update a reference to point to a given SHA-1."""
    if not HEX_SHA1_RE.match(sha):
        raise ValueError(f"Invalid SHA-1: {sha}")

    # If ref doesn't start with refs/, default to refs/heads/
    if not (ref.startswith("refs/") or ref == "HEAD"):
        ref = f"refs/heads/{ref}"

    ref_path = repo.repo_file(ref, mkdir=True)
    ref_path.write_text(f"{sha}\n", encoding="utf-8")


def get_current_branch(repo: GitRepository) -> str | None:
    """Return the name of the currently checked out branch, or None if in detached HEAD mode."""
    head_path = repo.repo_file("HEAD")
    if not head_path.is_file():
        return None

    content = head_path.read_text(encoding="utf-8").strip()
    if content.startswith("ref: refs/heads/"):
        return content[16:].strip()
    return None


def ref_list(repo: GitRepository, prefix: str = "refs/heads") -> dict[str, str]:
    """List all references under a directory prefix, mapping relative name to SHA-1."""
    base_dir = repo.repo_dir(prefix)
    refs: dict[str, str] = {}

    if not base_dir.is_dir():
        return refs

    for path in sorted(base_dir.rglob("*")):
        if path.is_file():
            rel_name = path.relative_to(base_dir).as_posix()
            sha = ref_resolve(repo, f"{prefix}/{rel_name}")
            if sha:
                refs[rel_name] = sha

    return refs


def branch_create(repo: GitRepository, name: str, start_point: str = "HEAD") -> str:
    """Create a new branch pointing to start_point commit. Returns commit SHA."""
    target_sha = ref_resolve(repo, start_point)
    if not target_sha:
        raise ValueError(f"Not a valid object name: '{start_point}'")

    branch_file = repo.repo_file("refs", "heads", name)
    if branch_file.exists():
        raise FileExistsError(f"A branch named '{name}' already exists.")

    ref_update(repo, f"refs/heads/{name}", target_sha)
    return target_sha


def tree_checkout(repo: GitRepository, tree_sha: str, target_dir: Path | None = None) -> None:
    """Recursively extract a GitTree into the target directory (restoring working files)."""
    from minigit.objects import GitBlob, GitTree, object_read

    if target_dir is None:
        target_dir = repo.worktree

    tree_obj = object_read(repo, tree_sha)
    if not isinstance(tree_obj, GitTree):
        raise ValueError(f"Object {tree_sha} is not a tree.")

    for item in tree_obj.items:
        item_path = target_dir / item.path
        mode_str = item.mode.zfill(6)

        if mode_str == "040000" or item.mode == "40000":
            item_path.mkdir(parents=True, exist_ok=True)
            tree_checkout(repo, item.sha, target_dir=item_path)
        else:
            blob_obj = object_read(repo, item.sha)
            if isinstance(blob_obj, GitBlob):
                item_path.parent.mkdir(parents=True, exist_ok=True)
                item_path.write_bytes(blob_obj.serialize())


def checkout(repo: GitRepository, target: str, create_branch: bool = False) -> str:
    """Check out a branch or commit into the working tree. Returns status message."""
    from minigit.objects import GitCommit, object_read

    if create_branch:
        branch_create(repo, target, "HEAD")

    branch_path = repo.repo_file("refs", "heads", target)
    if branch_path.is_file():
        commit_sha = branch_path.read_text(encoding="utf-8").strip()
        repo.repo_file("HEAD").write_text(f"ref: refs/heads/{target}\n", encoding="utf-8")
        msg = f"Switched to branch '{target}'"
    else:
        commit_sha = ref_resolve(repo, target)
        if not commit_sha:
            raise ValueError(f"pathspec '{target}' did not match any file(s) known to git")
        repo.repo_file("HEAD").write_text(f"{commit_sha}\n", encoding="utf-8")
        msg = f"Note: switching to '{target}'. You are in 'detached HEAD' state."

    commit_obj = object_read(repo, commit_sha)
    if not isinstance(commit_obj, GitCommit):
        raise ValueError(f"Object {commit_sha} is not a commit.")

    tree_checkout(repo, commit_obj.tree)
    return msg


