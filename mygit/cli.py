"""
Command-line interface: argparse subcommands dispatching to the
underlying repository/objects logic. Kept deliberately thin -- this
file should only parse args and print output, never contain real logic.
"""

import argparse
import sys

from . import objects, repository


def cmd_init(args):
    repository.init(args.path)


def cmd_hash_object(args):
    with open(args.file, "rb") as f:
        data = f.read()
    sha1 = objects.hash_object(data, write=args.write)
    print(sha1)


def cmd_cat_file(args):
    obj_type, data = objects.read_object(args.object)
    if args.type_only:
        print(obj_type)
    elif args.size_only:
        print(len(data))
    else:
        # pretty-print: write raw bytes so binary-safe content round-trips
        sys.stdout.buffer.write(data)


def build_parser():
    parser = argparse.ArgumentParser(prog="mygit", description="A minimal git internals clone.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_init = subparsers.add_parser("init", help="Create an empty mygit repository")
    p_init.add_argument("path", nargs="?", default=".", help="Where to create the repo (default: current directory)")
    p_init.set_defaults(func=cmd_init)

    p_hash = subparsers.add_parser("hash-object", help="Compute object hash for a file, optionally storing it")
    p_hash.add_argument("file", help="Path to the file to hash")
    p_hash.add_argument("-w", "--write", dest="write", action="store_true", default=False,
                         help="write the object to the store (default: just print the hash)")
    p_hash.set_defaults(func=cmd_hash_object)

    p_cat = subparsers.add_parser("cat-file", help="Show contents (or metadata) of a stored object")
    p_cat.add_argument("object", help="SHA-1 hash of the object")
    group = p_cat.add_mutually_exclusive_group()
    group.add_argument("-t", dest="type_only", action="store_true", help="show object type only")
    group.add_argument("-s", dest="size_only", action="store_true", help="show object size only")
    p_cat.set_defaults(func=cmd_cat_file, type_only=False, size_only=False)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
