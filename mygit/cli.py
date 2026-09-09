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


def cmd_commit(args):
    """
    Snapshot the entire working directory as a tree, wrap it in a commit
    pointing at the current HEAD commit (if any) as its parent, then
    advance the current branch to the new commit.

    Note: there's no staging area yet, so this always commits the FULL
    current state of the working directory -- there's no equivalent of
    `git add` to select a subset of changes.
    """
    repo_root = repository.find_repo_root()
    if repo_root is None:
        raise FileNotFoundError("not a mygit repository")

    tree_sha1 = objects.write_tree(repo_root)
    parent_sha1 = repository.get_current_commit()
    commit_sha1 = objects.commit_tree(tree_sha1, parent_sha1, args.message)

    repository.update_ref(repository.get_head_ref(), commit_sha1)
    print(commit_sha1)


def cmd_log(args):
    """Walk the parent chain from the current commit backward, printing each."""
    commit_sha1 = repository.get_current_commit()
    if commit_sha1 is None:
        print("no commits yet")
        return

    while commit_sha1:
        commit = objects.read_commit(commit_sha1)
        print(f"commit {commit_sha1}")
        print(f"Author: {commit['author']}")
        print()
        for line in commit["message"].splitlines():
            print(f"    {line}")
        print()
        commit_sha1 = commit["parent"]


def cmd_branch(args):
    """
    No name given: list all branches, marking the current one with '*'.
    Name given: create a new branch pointing at the current commit.
    """
    if args.name:
        commit_sha1 = repository.get_current_commit()
        if commit_sha1 is None:
            raise ValueError("cannot create a branch: no commits yet")
        repository.update_ref(f"refs/heads/{args.name}", commit_sha1)
        print(f"Created branch '{args.name}'")
    else:
        current_ref = repository.get_head_ref()
        for name in repository.list_branches():
            marker = "*" if f"refs/heads/{name}" == current_ref else " "
            print(f"{marker} {name}")


def cmd_checkout(args):
    """
    Switch to another branch: point HEAD at it, then restore the working
    directory to exactly match that branch's latest commit.
    """
    target_ref = f"refs/heads/{args.branch}"
    commit_sha1 = repository.read_ref(target_ref)
    if commit_sha1 is None:
        raise FileNotFoundError(f"branch '{args.branch}' does not exist")

    repo_root = repository.find_repo_root()
    commit = objects.read_commit(commit_sha1)
    objects.checkout_tree(commit["tree"], repo_root)
    repository.set_head_ref(target_ref)
    print(f"Switched to branch '{args.branch}'")


def cmd_diff(args):
    """Show the difference between the working directory and the current HEAD commit."""
    repo_root = repository.find_repo_root()
    commit_sha1 = repository.get_current_commit()
    tree_sha1 = objects.read_commit(commit_sha1)["tree"] if commit_sha1 else None

    changes = objects.diff_working_directory(repo_root, tree_sha1)
    if not changes:
        print("no changes")
        return

    for change in changes:
        if change["status"] == "added":
            print(f"added: {change['path']}")
        elif change["status"] == "removed":
            print(f"removed: {change['path']}")
        else:
            print(f"modified: {change['path']}")
            sys.stdout.writelines(change["diff"])


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

    p_commit = subparsers.add_parser("commit", help="Snapshot the working directory as a new commit")
    p_commit.add_argument("-m", "--message", required=True, help="Commit message")
    p_commit.set_defaults(func=cmd_commit)

    p_log = subparsers.add_parser("log", help="Show commit history")
    p_log.set_defaults(func=cmd_log)

    p_branch = subparsers.add_parser("branch", help="List branches, or create a new one")
    p_branch.add_argument("name", nargs="?", default=None, help="Name of branch to create (omit to list)")
    p_branch.set_defaults(func=cmd_branch)

    p_checkout = subparsers.add_parser("checkout", help="Switch to another branch")
    p_checkout.add_argument("branch", help="Branch name to switch to")
    p_checkout.set_defaults(func=cmd_checkout)

    p_diff = subparsers.add_parser("diff", help="Show changes between the working directory and HEAD")
    p_diff.set_defaults(func=cmd_diff)

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
