"""
Repository-level operations: finding the .mygit directory, initializing
a new repo, and resolving paths within it.

Design note: real Git calls this directory ".git". We use ".mygit" so a
mygit-managed folder can coexist with an actual git repo (useful while
developing/testing this project inside a git-tracked folder).
"""

import os

MYGIT_DIR = ".mygit"


def find_repo_root(start_path=None):
    """
    Walk upward from start_path (default: cwd) looking for a .mygit
    directory, the same way real git searches upward for .git so that
    commands work from any subdirectory of the repo.

    Returns the absolute path to the directory CONTAINING .mygit,
    or None if no repo is found.
    """
    path = os.path.abspath(start_path or os.getcwd())

    while True:
        if os.path.isdir(os.path.join(path, MYGIT_DIR)):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            # Reached filesystem root without finding .mygit
            return None
        path = parent


def get_mygit_dir(start_path=None):
    """
    Return the absolute path to the .mygit directory for the current
    repo, raising a clear error if we're not inside a repo at all.
    """
    root = find_repo_root(start_path)
    if root is None:
        raise FileNotFoundError(
            "not a mygit repository (or any parent up to mount point)"
        )
    return os.path.join(root, MYGIT_DIR)


def init(path="."):
    """
    Initialize a new mygit repository at `path`.

    Creates:
        .mygit/
            objects/   -- content-addressable object store (blobs, trees, commits)
            refs/
                heads/  -- branch pointers (used starting Day 2)
            HEAD        -- points at the current branch (used starting Day 2)

    Idempotent: re-running init on an existing repo is a no-op that
    reports the existing path, matching real git's behavior.
    """
    abs_path = os.path.abspath(path)
    mygit_dir = os.path.join(abs_path, MYGIT_DIR)

    if os.path.isdir(mygit_dir):
        print(f"Reinitialized existing mygit repository in {mygit_dir}")
        return mygit_dir

    os.makedirs(os.path.join(mygit_dir, "objects"))
    os.makedirs(os.path.join(mygit_dir, "refs", "heads"))

    # HEAD is a symbolic reference to the current branch. We default to
    # "master" as the initial branch name; it doesn't need to exist yet
    # as an actual ref file until the first commit is made.
    with open(os.path.join(mygit_dir, "HEAD"), "w") as f:
        f.write("ref: refs/heads/master\n")

    print(f"Initialized empty mygit repository in {mygit_dir}")
    return mygit_dir
