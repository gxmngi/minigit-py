"""Command-line interface for minigit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from minigit.objects import (
    GitBlob,
    GitTree,
    object_hash,
    object_read,
    object_write,
    tree_write_from_directory,
)
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
            if isinstance(obj, GitTree):
                for item in obj.items:
                    mode_str = item.mode.zfill(6)
                    is_tree = mode_str == "040000" or item.mode == "40000"
                    item_type = "tree" if is_tree else "blob"
                    print(f"{mode_str} {item_type} {item.sha}\t{item.path}")
            else:
                sys.stdout.buffer.write(obj.serialize())
                sys.stdout.buffer.flush()

        return 0
    except Exception as exc:
        print(f"fatal: {exc}", file=sys.stderr)
        return 1


def cmd_ls_tree(args: argparse.Namespace) -> int:
    """Handle 'minigit ls-tree [-r] [--name-only] <tree-ish>'."""
    try:
        repo = repo_find()
        obj = object_read(repo, args.tree)
        if not isinstance(obj, GitTree):
            print(f"fatal: not a tree object: {args.tree}", file=sys.stderr)
            return 1

        def print_tree(tree_obj: GitTree, prefix: str = "") -> None:
            for item in tree_obj.items:
                mode_str = item.mode.zfill(6)
                is_tree = mode_str == "040000" or item.mode == "40000"
                item_type = "tree" if is_tree else "blob"
                full_path = f"{prefix}{item.path}"

                if is_tree and args.recursive:
                    sub_obj = object_read(repo, item.sha)
                    if isinstance(sub_obj, GitTree):
                        print_tree(sub_obj, prefix=f"{full_path}/")
                else:
                    if args.name_only:
                        print(full_path)
                    else:
                        print(f"{mode_str} {item_type} {item.sha}\t{full_path}")

        print_tree(obj)
        return 0
    except Exception as exc:
        print(f"fatal: {exc}", file=sys.stderr)
        return 1


def cmd_write_tree(args: argparse.Namespace) -> int:
    """Handle 'minigit write-tree [directory]'."""
    try:
        repo = repo_find()
        target = Path(args.directory).resolve() if args.directory else repo.worktree
        sha = tree_write_from_directory(target, repo)
        print(sha)
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

    # ls-tree
    ls_parser = subparsers.add_parser(
        "ls-tree",
        help="List the contents of a tree object.",
    )
    ls_parser.add_argument(
        "-r",
        "--recursive",
        dest="recursive",
        action="store_true",
        help="Recurse into sub-trees.",
    )
    ls_parser.add_argument(
        "--name-only",
        dest="name_only",
        action="store_true",
        help="List only filenames (one per line).",
    )
    ls_parser.add_argument(
        "tree",
        help="The tree object SHA-1 to list.",
    )
    ls_parser.set_defaults(func=cmd_ls_tree)

    # write-tree
    write_tree_parser = subparsers.add_parser(
        "write-tree",
        help="Create a tree object from the current directory.",
    )
    write_tree_parser.add_argument(
        "directory",
        nargs="?",
        default=None,
        help="Directory to build tree from (default: repository root).",
    )
    write_tree_parser.set_defaults(func=cmd_write_tree)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

