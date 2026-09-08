"""Three-Way Merge Engine for MiniGit.

Implements:
1. Lowest Common Ancestor (LCA) search on the commit DAG (`merge-base`).
2. Recursive snapshot flattening for directory trees.
3. Three-way line diff and Git conflict marker synthesis (<<<<<<<, =======, >>>>>>>).
4. Fast-forward detection and multi-parent merge commit creation.
"""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import TYPE_CHECKING

from minigit.objects import (
    GitBlob,
    GitCommit,
    GitTree,
    default_author_committer,
    object_read,
    object_write,
    tree_write_from_directory,
)
from minigit.refs import get_current_branch, ref_resolve, ref_update, tree_checkout

if TYPE_CHECKING:
    from minigit.repository import GitRepository


def get_commit_ancestors_with_depth(repo: GitRepository, start_sha: str) -> dict[str, int]:
    """Traverse commit DAG backwards from start_sha and return mapping of {commit_sha: depth}."""
    depths: dict[str, int] = {}
    queue: list[tuple[str, int]] = [(start_sha, 0)]
    visited: set[str] = {start_sha}

    while queue:
        sha, depth = queue.pop(0)
        depths[sha] = depth

        try:
            commit = object_read(repo, sha)
            if isinstance(commit, GitCommit):
                for parent_sha in commit.parents:
                    if parent_sha not in visited:
                        visited.add(parent_sha)
                        queue.append((parent_sha, depth + 1))
        except Exception:
            continue

    return depths


def find_merge_base(repo: GitRepository, commit_a_sha: str, commit_b_sha: str) -> str | None:
    """Find the Lowest Common Ancestor (LCA) between two commits on the DAG."""
    if commit_a_sha == commit_b_sha:
        return commit_a_sha

    ancestors_a = get_commit_ancestors_with_depth(repo, commit_a_sha)

    queue: list[str] = [commit_b_sha]
    visited: set[str] = {commit_b_sha}
    candidates: list[tuple[int, str]] = []

    while queue:
        sha = queue.pop(0)
        if sha in ancestors_a:
            candidates.append((ancestors_a[sha], sha))

        try:
            commit = object_read(repo, sha)
            if isinstance(commit, GitCommit):
                for parent_sha in commit.parents:
                    if parent_sha not in visited:
                        visited.add(parent_sha)
                        queue.append(parent_sha)
        except Exception:
            continue

    if not candidates:
        return None

    # Sort by minimum depth from commit_a (closest common ancestor)
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def flatten_tree(repo: GitRepository, tree_sha: str | None, prefix: str = "") -> dict[str, str]:
    """Recursively map relative file paths to their blob SHA-1 hashes."""
    if not tree_sha:
        return {}

    try:
        tree = object_read(repo, tree_sha)
    except Exception:
        return {}

    if not isinstance(tree, GitTree):
        return {}

    files: dict[str, str] = {}
    for item in tree.items:
        rel_path = f"{prefix}{item.path}"
        mode_str = item.mode.zfill(6)
        if mode_str == "040000" or item.mode == "40000":
            files.update(flatten_tree(repo, item.sha, prefix=f"{rel_path}/"))
        else:
            files[rel_path] = item.sha

    return files


def _get_hunks(base: list[str], other: list[str]) -> list[tuple[int, int, list[str]]]:
    sm = difflib.SequenceMatcher(None, base, other)
    hunks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            hunks.append((i1, i2, other[j1:j2]))
    return hunks


def merge_3way_text(
    base_lines: list[str],
    a_lines: list[str],
    b_lines: list[str],
    label_a: str = "HEAD",
    label_b: str = "target",
) -> tuple[list[str], bool]:
    """Perform a line-level 3-way text merge and synthesize Git conflict markers."""
    if a_lines == base_lines:
        return list(b_lines), False
    if b_lines == base_lines:
        return list(a_lines), False
    if a_lines == b_lines:
        return list(a_lines), False

    hunks_a = _get_hunks(base_lines, a_lines)
    hunks_b = _get_hunks(base_lines, b_lines)

    events: list[tuple[int, int, str, list[str]]] = []
    for i1, i2, lines in hunks_a:
        events.append((i1, i2, "A", lines))
    for i1, i2, lines in hunks_b:
        events.append((i1, i2, "B", lines))

    events.sort(key=lambda x: (x[0], x[1]))

    merged_events: list[dict] = []
    for ev in events:
        if not merged_events:
            merged_events.append({
                "start": ev[0],
                "end": ev[1],
                "A": ev[3] if ev[2] == "A" else None,
                "B": ev[3] if ev[2] == "B" else None,
            })
        else:
            last = merged_events[-1]
            if ev[0] < last["end"] or (ev[0] == last["end"] and ev[0] == ev[1] and last["start"] == last["end"]):
                last["end"] = max(last["end"], ev[1])
                if ev[2] == "A":
                    last["A"] = ev[3]
                else:
                    last["B"] = ev[3]
            elif ev[0] == last["start"] and ev[1] == last["end"]:
                if ev[2] == "A":
                    last["A"] = ev[3]
                else:
                    last["B"] = ev[3]
            else:
                merged_events.append({
                    "start": ev[0],
                    "end": ev[1],
                    "A": ev[3] if ev[2] == "A" else None,
                    "B": ev[3] if ev[2] == "B" else None,
                })

    result: list[str] = []
    has_conflict = False
    curr_base = 0

    for ev in merged_events:
        start = ev["start"]
        end = ev["end"]

        if start > curr_base:
            result.extend(base_lines[curr_base:start])

        chunk_a = ev["A"]
        chunk_b = ev["B"]

        if chunk_a is not None and chunk_b is None:
            result.extend(chunk_a)
        elif chunk_b is not None and chunk_a is None:
            result.extend(chunk_b)
        else:
            if chunk_a == chunk_b:
                if chunk_a:
                    result.extend(chunk_a)
            else:
                has_conflict = True
                result.append(f"<<<<<<< {label_a}\n")
                if chunk_a:
                    result.extend(chunk_a)
                result.append("=======\n")
                if chunk_b:
                    result.extend(chunk_b)
                result.append(f">>>>>>> {label_b}\n")

        curr_base = end

    if curr_base < len(base_lines):
        result.extend(base_lines[curr_base:])

    return result, has_conflict


def merge_trees(
    repo: GitRepository,
    tree_o_sha: str | None,
    tree_a_sha: str,
    tree_b_sha: str,
    label_a: str = "HEAD",
    label_b: str = "target",
) -> tuple[dict[str, bytes], list[str]]:
    """Perform a 3-way merge on trees O, A, and B. Returns (merged_files, conflict_paths)."""
    files_o = flatten_tree(repo, tree_o_sha)
    files_a = flatten_tree(repo, tree_a_sha)
    files_b = flatten_tree(repo, tree_b_sha)

    all_paths = sorted(set(files_o) | set(files_a) | set(files_b))
    merged_files: dict[str, bytes] = {}
    conflicts: list[str] = []

    for path in all_paths:
        sha_o = files_o.get(path)
        sha_a = files_a.get(path)
        sha_b = files_b.get(path)

        if sha_a == sha_b:
            if sha_a is not None:
                blob = object_read(repo, sha_a)
                merged_files[path] = blob.serialize()
        elif sha_a == sha_o:
            if sha_b is not None:
                blob = object_read(repo, sha_b)
                merged_files[path] = blob.serialize()
        elif sha_b == sha_o:
            if sha_a is not None:
                blob = object_read(repo, sha_a)
                merged_files[path] = blob.serialize()
        else:
            lines_o = (
                object_read(repo, sha_o).serialize().decode("utf-8", errors="replace").splitlines(keepends=True)
                if sha_o
                else []
            )
            lines_a = (
                object_read(repo, sha_a).serialize().decode("utf-8", errors="replace").splitlines(keepends=True)
                if sha_a
                else []
            )
            lines_b = (
                object_read(repo, sha_b).serialize().decode("utf-8", errors="replace").splitlines(keepends=True)
                if sha_b
                else []
            )

            merged_lines, has_conflict = merge_3way_text(
                lines_o, lines_a, lines_b, label_a=label_a, label_b=label_b
            )
            merged_files[path] = "".join(merged_lines).encode("utf-8")
            if has_conflict:
                conflicts.append(path)

    return merged_files, conflicts


def merge_branches(
    repo: GitRepository,
    target_ref_name: str,
    message: str | None = None,
) -> tuple[int, str]:
    """Execute branch merge. Supports fast-forward and recursive 3-way merge with conflict markers."""
    curr_branch = get_current_branch(repo)
    head_sha = ref_resolve(repo, "HEAD")
    if not head_sha:
        return 1, "fatal: HEAD does not point to a valid commit"

    target_sha = ref_resolve(repo, target_ref_name)
    if not target_sha:
        return 1, f"fatal: '{target_ref_name}' - not something we can merge"

    if head_sha == target_sha:
        return 0, "Already up to date."

    base_sha = find_merge_base(repo, head_sha, target_sha)

    # 1. Fast-forward: HEAD is ancestor of target
    if base_sha == head_sha:
        commit_b = object_read(repo, target_sha)
        if not isinstance(commit_b, GitCommit):
            return 1, f"fatal: '{target_sha}' is not a commit"

        tree_checkout(repo, commit_b.tree)
        if curr_branch:
            ref_update(repo, f"refs/heads/{curr_branch}", target_sha)
        else:
            ref_update(repo, "HEAD", target_sha)
        return 0, f"Updating {head_sha[:7]}..{target_sha[:7]}\nFast-forward"

    # 2. Already up to date: target is ancestor of HEAD
    if base_sha == target_sha:
        return 0, "Already up to date."

    # 3. True Three-Way Merge
    commit_a = object_read(repo, head_sha)
    commit_b = object_read(repo, target_sha)
    if not isinstance(commit_a, GitCommit) or not isinstance(commit_b, GitCommit):
        return 1, "fatal: failed to resolve commit objects"

    base_tree_sha = None
    if base_sha:
        base_commit = object_read(repo, base_sha)
        if isinstance(base_commit, GitCommit):
            base_tree_sha = base_commit.tree

    merged_files, conflicts = merge_trees(
        repo,
        base_tree_sha,
        commit_a.tree,
        commit_b.tree,
        label_a="HEAD",
        label_b=target_ref_name,
    )

    # Apply merged files into working directory
    for rel_path, file_bytes in merged_files.items():
        dest = repo.worktree / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(file_bytes)

    # Remove deleted files
    files_a = flatten_tree(repo, commit_a.tree)
    files_b = flatten_tree(repo, commit_b.tree)
    for p in set(files_a) | set(files_b):
        if p not in merged_files:
            target_path = repo.worktree / p
            if target_path.is_file():
                target_path.unlink()

    if conflicts:
        conflict_msg = ["Auto-merging:"]
        for cf in conflicts:
            conflict_msg.append(f"CONFLICT (content): Merge conflict in {cf}")
        conflict_msg.append("Automatic merge failed; fix conflicts and then commit the result.")
        return 1, "\n".join(conflict_msg)

    # 4. Clean merge: create merge commit with 2 parents
    new_tree_sha = tree_write_from_directory(repo.worktree, repo)

    merge_commit = GitCommit()
    merge_commit.tree = new_tree_sha
    merge_commit.parents = [head_sha, target_sha]
    author_meta = default_author_committer()
    merge_commit.author = author_meta
    merge_commit.committer = author_meta

    default_msg = f"Merge branch '{target_ref_name}'"
    if curr_branch:
        default_msg += f" into {curr_branch}"
    merge_commit.message = message if message else default_msg

    new_commit_sha = object_write(merge_commit, repo=repo)

    if curr_branch:
        ref_update(repo, f"refs/heads/{curr_branch}", new_commit_sha)
    else:
        ref_update(repo, "HEAD", new_commit_sha)

    return 0, f"Merge made by the 'three-way' strategy.\n {new_commit_sha[:7]} {merge_commit.message}"
