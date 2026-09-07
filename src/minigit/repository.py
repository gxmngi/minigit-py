"""Git repository structure management.

Under the hood, a Git repository is simply a working directory paired with
a hidden '.git' directory that holds the object database, references (branches/tags),
configuration, and current HEAD pointer.
"""

from __future__ import annotations

import configparser
import os
from pathlib import Path


class GitRepository:
    """Represents an active Git repository."""

    def __init__(self, path: str | Path, force: bool = False) -> None:
        self.worktree = Path(path).resolve()
        self.gitdir = self.worktree / ".git"
        self.conf = configparser.ConfigParser()

        if not (force or self.gitdir.is_dir()):
            raise FileNotFoundError(f"Not a Git repository: {self.worktree}")

        # Read configuration file if present
        config_path = self.repo_file("config")
        if config_path.is_file():
            self.conf.read(config_path)
        elif not force:
            raise FileNotFoundError(f"Configuration file missing in {self.gitdir}")

        if not force:
            version = int(self.conf.get("core", "repositoryformatversion", fallback=0))
            if version != 0:
                raise ValueError(f"Unsupported repositoryformatversion: {version}")

    def repo_path(self, *paths: str) -> Path:
        """Compute path under .git directory."""
        return self.gitdir.joinpath(*paths)

    def repo_file(self, *paths: str, mkdir: bool = False) -> Path:
        """Compute path to a file under .git, optionally creating parent dirs."""
        path = self.repo_path(*paths)
        if mkdir:
            path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def repo_dir(self, *paths: str, mkdir: bool = False) -> Path:
        """Compute path to a directory under .git, optionally creating it."""
        path = self.repo_path(*paths)
        if mkdir:
            path.mkdir(parents=True, exist_ok=True)
        return path


def repo_default_config() -> configparser.ConfigParser:
    """Create default Git repository INI configuration."""
    conf = configparser.ConfigParser()
    conf.add_section("core")
    conf.set("core", "repositoryformatversion", "0")
    conf.set("core", "filemode", "false")
    conf.set("core", "bare", "false")
    return conf


def repo_create(path: str | Path) -> GitRepository:
    """Initialize a brand new Git repository at path (mimics 'git init')."""
    target = Path(path).resolve()

    if target.exists():
        if not target.is_dir():
            raise NotADirectoryError(f"{target} is not a directory.")
        if any(target.iterdir()):
            # If target directory already contains files, verify .git does not exist
            if (target / ".git").exists():
                raise FileExistsError(f"{target} is already a Git repository.")
    else:
        target.mkdir(parents=True, exist_ok=True)

    repo = GitRepository(target, force=True)

    # 1. Create directory hierarchy
    repo.repo_dir("branches", mkdir=True)
    repo.repo_dir("objects", mkdir=True)
    repo.repo_dir("refs", "tags", mkdir=True)
    repo.repo_dir("refs", "heads", mkdir=True)

    # 2. .git/description
    desc_file = repo.repo_file("description", mkdir=True)
    desc_file.write_text(
        "Unnamed repository; edit this file 'description' to name the repository.\n",
        encoding="utf-8",
    )

    # 3. .git/HEAD
    head_file = repo.repo_file("HEAD", mkdir=True)
    head_file.write_text("ref: refs/heads/main\n", encoding="utf-8")

    # 4. .git/config
    config_file = repo.repo_file("config", mkdir=True)
    config = repo_default_config()
    with open(config_file, "w", encoding="utf-8") as f:
        config.write(f)

    return repo


def repo_find(
    path: str | Path = ".",
    required: bool = True,
    stop_at: str | Path | None = None,
) -> GitRepository | None:
    """Find the root of the current Git repository by searching upwards."""
    current = Path(path).resolve()
    ceiling = Path(stop_at).resolve() if stop_at else None

    # Check GIT_CEILING_DIRECTORIES environment variable like standard Git
    env_ceilings = [
        Path(p).resolve()
        for p in os.environ.get("GIT_CEILING_DIRECTORIES", "").split(os.pathsep)
        if p.strip()
    ]

    while True:
        if (current / ".git").is_dir():
            return GitRepository(current)

        if ceiling and current == ceiling:
            if required:
                raise FileNotFoundError(f"No Git repository found before ceiling: {ceiling}")
            return None

        if current in env_ceilings:
            if required:
                raise FileNotFoundError(f"Hit ceiling directory: {current}")
            return None

        parent = current.parent
        if parent == current:
            # Reached root of file system
            if required:
                raise FileNotFoundError("Not inside a Git repository (or any parent up to root).")
            return None
        current = parent

