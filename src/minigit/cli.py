"""Command-line interface for minigit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from minigit.repository import repo_create


def cmd_init(args: argparse.Namespace) -> int:
    """Handle 'minigit init [path]'."""
    try:
        repo = repo_create(args.path)
        print(f"Initialized empty Git repository in {repo.gitdir}")
        return 0
    except Exception as exc:
        print(f"fatal: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line arguments parser."""
    parser = argparse.ArgumentParser(
        prog="minigit",
        description="A lightweight Git implementation in Python.",
    )
    subparsers = parser.add_subparsers(title="Commands", dest="command")
    subparsers.required = True

    # init
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a new, empty Git repository.",
    )
    init_parser.add_argument(
        "path",
        metavar="directory",
        nargs="?",
        default=".",
        help="Where to create the repository.",
    )
    init_parser.set_defaults(func=cmd_init)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
