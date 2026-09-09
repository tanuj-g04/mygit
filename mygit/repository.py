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


# ---------------------------------------------------------------------------
# Refs: named pointers to commits. HEAD is a symbolic ref that points at
# a branch (e.g. "refs/heads/master"); the branch file itself holds the
# actual commit hash. This indirection is what makes `git checkout
# <branch>` work in real git -- it just repoints HEAD. We only support
# a single branch (master) for now; branch creation/switching is a
# Day 3 item, not implemented yet.
# ---------------------------------------------------------------------------

def get_head_ref():
    """
    Return the ref path HEAD currently points at, e.g. "refs/heads/master".

    Raises ValueError if HEAD is "detached" (pointing directly at a
    commit hash rather than a branch) -- we don't support detached HEAD
    yet, so this should never happen through normal mygit commands.
    """
    mygit_dir = get_mygit_dir()
    with open(os.path.join(mygit_dir, "HEAD")) as f:
        content = f.read().strip()

    if not content.startswith("ref: "):
        raise ValueError("detached HEAD is not supported yet")

    return content[len("ref: "):]


def read_ref(ref_path):
    """
    Return the commit hash stored at `ref_path` (e.g. "refs/heads/master"),
    or None if that ref doesn't exist yet -- which is the normal state
    for a brand new repo before its first commit.
    """
    mygit_dir = get_mygit_dir()
    full_path = os.path.join(mygit_dir, ref_path)
    if not os.path.exists(full_path):
        return None
    with open(full_path) as f:
        return f.read().strip()


def update_ref(ref_path, sha1):
    """Point `ref_path` (e.g. "refs/heads/master") at commit `sha1`."""
    mygit_dir = get_mygit_dir()
    full_path = os.path.join(mygit_dir, ref_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w") as f:
        f.write(sha1 + "\n")


def get_current_commit():
    """
    Return the commit hash the current branch points at, or None if the
    branch has no commits yet (a fresh repo, or one where init just ran).
    """
    return read_ref(get_head_ref())


def list_branches():
    """Return the names of all branches (files under refs/heads/), sorted."""
    heads_dir = os.path.join(get_mygit_dir(), "refs", "heads")
    if not os.path.isdir(heads_dir):
        return []
    return sorted(os.listdir(heads_dir))


def set_head_ref(ref_path):
    """
    Point HEAD at a different branch (e.g. "refs/heads/feature"), used by
    checkout. Unlike update_ref (which writes a commit hash into a branch
    file), this rewrites HEAD's symbolic pointer itself.
    """
    mygit_dir = get_mygit_dir()
    with open(os.path.join(mygit_dir, "HEAD"), "w") as f:
        f.write(f"ref: {ref_path}\n")
