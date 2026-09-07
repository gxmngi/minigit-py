"""Command-line interface for minigit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from minigit.objects import GitBlob, object_hash, object_read, object_write
from minigit.repository import repo_create, repo_find


def cmd_init(args: argparse.Namespace) -> int:
    """Handle 'minigit init [path]'."""
    try:
        repo = repo_create(args.path)
        print(f"Initialized empty Git repository in {repo.gitdir}")
        return 0
    except Exception as exc:
        print(f"fatal: {exc}", file=sys.stderr)
        return 1


def cmd_hash_object(args: argparse.Namespace) -> int:
    """Handle 'minigit hash-object [-w] [-t type] <file>'."""
    try:
        path = Path(args.file)
        if not path.is_file():
            print(f"fatal: Cannot open '{args.file}': No such file", file=sys.stderr)
            return 1
        data = path.read_bytes()

        repo = repo_find() if args.write else None

        blob = GitBlob()
        blob.deserialize(data)
        blob.fmt = args.type.encode("ascii")

        sha = object_write(blob, repo=repo)
        print(sha)
        return 0
    except Exception as exc:
        print(f"fatal: {exc}", file=sys.stderr)
        return 1


def cmd_cat_file(args: argparse.Namespace) -> int:
    """Handle 'minigit cat-file (-p | -t | -s) <object>'."""
    try:
        repo = repo_find()
        obj = object_read(repo, args.object)

        if args.type:
            print(obj.fmt.decode("ascii"))
        elif args.size:
            print(len(obj.serialize()))
        elif args.pretty:
            sys.stdout.buffer.write(obj.serialize())
            sys.stdout.buffer.flush()

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

    # hash-object
    hash_parser = subparsers.add_parser(
        "hash-object",
        help="Compute object ID and optionally create a blob from a file.",
    )
    hash_parser.add_argument(
        "-t",
        "--type",
        dest="type",
        default="blob",
        choices=["blob", "commit", "tree", "tag"],
        help="Specify the type (default: 'blob').",
    )
    hash_parser.add_argument(
        "-w",
        "--write",
        dest="write",
        action="store_true",
        help="Actually write the object into the object database.",
    )
    hash_parser.add_argument(
        "file",
        help="Read object from <file>.",
    )
    hash_parser.set_defaults(func=cmd_hash_object)

    # cat-file
    cat_parser = subparsers.add_parser(
        "cat-file",
        help="Provide content or type and size information for repository objects.",
    )
    cat_group = cat_parser.add_mutually_exclusive_group(required=True)
    cat_group.add_argument(
        "-p",
        dest="pretty",
        action="store_true",
        help="Pretty-print the contents of <object> based on its type.",
    )
    cat_group.add_argument(
        "-t",
        dest="type",
        action="store_true",
        help="Show object type.",
    )
    cat_group.add_argument(
        "-s",
        dest="size",
        action="store_true",
        help="Show object size.",
    )
    cat_parser.add_argument(
        "object",
        help="The name of the object to show (SHA-1 hash).",
    )
    cat_parser.set_defaults(func=cmd_cat_file)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

