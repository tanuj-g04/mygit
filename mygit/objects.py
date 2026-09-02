"""
The object store: content-addressable storage for blobs.

Core idea (same as real Git):
    1. Take an object's raw content.
    2. Prepend a header: "{type} {byte_length}\\0"
    3. SHA-1 hash the header + content together -> this hash IS the object's
       identity (its "address" in the store).
    4. zlib-compress the header + content and write it to disk at
       .mygit/objects/<first 2 hex chars>/<remaining 38 hex chars>

The header matters for two reasons:
    - It makes the hash depend on the object's TYPE, not just its bytes,
      so a blob and a tree that happen to contain the same bytes never
      collide.
    - It stores the length, which lets cat-file validate that decompressed
      content matches what was recorded (a basic integrity check).

Splitting the hash into a 2-char directory + 38-char filename is a real
Git convention: it keeps any single directory from accumulating too many
files as the repo grows (a filesystem performance concern, not a
correctness one).
"""

import hashlib
import os
import time
import zlib

from .repository import MYGIT_DIR, get_mygit_dir


def hash_object(data, obj_type="blob", write=True):
    """
    Compute the SHA-1 hash of `data` (bytes) with a git-style object
    header, optionally writing it to the object store.

    Args:
        data: raw content as bytes.
        obj_type: object type string, e.g. "blob" (trees/commits come Day 2).
        write: if True, persist the compressed object to .mygit/objects/.

    Returns:
        The 40-character hex SHA-1 digest identifying this object.
    """
    header = f"{obj_type} {len(data)}\0".encode()
    full_data = header + data
    sha1 = hashlib.sha1(full_data).hexdigest()

    if write:
        _write_object(sha1, full_data)

    return sha1


def _write_object(sha1, full_data):
    """
    Compress and store an object under .mygit/objects/<sha1[:2]>/<sha1[2:]>.

    We compress with zlib (same as real git) primarily to mirror the
    format, and secondarily because it's genuinely useful for text-heavy
    source repos.
    """
    mygit_dir = get_mygit_dir()
    obj_dir = os.path.join(mygit_dir, "objects", sha1[:2])
    obj_path = os.path.join(obj_dir, sha1[2:])

    if os.path.exists(obj_path):
        # Content-addressing means identical content is already stored
        # under this exact hash -- nothing to do. This is the dedup
        # property that makes git's storage efficient.
        return

    os.makedirs(obj_dir, exist_ok=True)
    compressed = zlib.compress(full_data)
    with open(obj_path, "wb") as f:
        f.write(compressed)


def read_object(sha1):
    """
    Retrieve and decompress an object by its hash, verifying its header.

    Returns:
        (obj_type, data) -- the object's type string and raw content bytes
        (header and length prefix stripped off).

    Raises:
        ValueError: if the stored length doesn't match the actual content
            length (corruption check).
        FileNotFoundError: if no object exists for this hash.
    """
    mygit_dir = get_mygit_dir()
    obj_path = os.path.join(mygit_dir, "objects", sha1[:2], sha1[2:])

    if not os.path.exists(obj_path):
        raise FileNotFoundError(f"object {sha1} not found")

    with open(obj_path, "rb") as f:
        full_data = zlib.decompress(f.read())

    # Header format: "{type} {length}\0{content}"
    header, data = full_data.split(b"\0", maxsplit=1)
    obj_type, size_str = header.decode().split(" ")
    size = int(size_str)

    if size != len(data):
        raise ValueError(
            f"object {sha1} is corrupted: header declares {size} bytes, "
            f"actual content is {len(data)} bytes"
        )

    return obj_type, data


# ---------------------------------------------------------------------------
# Tree objects: a snapshot of a directory's structure.
#
# A tree is a sorted list of entries, one per file or subdirectory it
# contains. Each entry is: "{mode} {type} {sha1}\t{name}\n"
#   - mode: "100644" for a regular file, "40000" for a subdirectory
#     (we don't track executable/symlink bits -- a known simplification)
#   - type: "blob" (file) or "tree" (subdirectory)
#   - sha1: the hash of that file's blob, or that subdirectory's own tree
#   - name: the file/directory's name (NOT its full path -- trees nest,
#     so a subdirectory's contents live in ITS tree object, not this one)
#
# NOTE on format: real git stores tree entries in a binary format (raw
# 20-byte SHA digests, not hex text), so our tree hashes will NOT match
# real git's hashes for the same directory the way our blob hashes did.
# We use a plain-text format here for readability and simplicity; the
# underlying concept (sorted list of name -> hash pointers) is identical.
# ---------------------------------------------------------------------------

def write_tree(dir_path):
    """
    Recursively snapshot `dir_path`: write a blob for every file and a
    tree object (recursively) for every subdirectory, then write and
    return the hash of the tree object describing dir_path itself.

    This always excludes the .mygit directory -- we're snapshotting the
    working files, never our own metadata.

    Because entries are sorted by name and hashed deterministically, an
    unchanged directory always produces the exact same tree hash -- so a
    commit whose working tree didn't change reuses the existing tree
    object instead of creating a new one (the same dedup property blobs
    get, one level up).
    """
    entries = []

    for name in sorted(os.listdir(dir_path)):
        if name == MYGIT_DIR:
            continue

        full_path = os.path.join(dir_path, name)

        if os.path.isdir(full_path):
            sha1 = write_tree(full_path)
            mode, obj_type = "40000", "tree"
        else:
            with open(full_path, "rb") as f:
                data = f.read()
            sha1 = hash_object(data, obj_type="blob", write=True)
            mode, obj_type = "100644", "blob"

        entries.append(f"{mode} {obj_type} {sha1}\t{name}\n")

    tree_data = "".join(entries).encode()
    return hash_object(tree_data, obj_type="tree", write=True)


def read_tree(sha1):
    """
    Parse a tree object back into a list of entry dicts:
    [{"mode": ..., "type": ..., "sha1": ..., "name": ...}, ...]
    """
    obj_type, data = read_object(sha1)
    if obj_type != "tree":
        raise ValueError(f"object {sha1} is a {obj_type}, not a tree")

    entries = []
    for line in data.decode().splitlines():
        meta, name = line.split("\t", maxsplit=1)
        mode, entry_type, entry_sha1 = meta.split(" ")
        entries.append({"mode": mode, "type": entry_type, "sha1": entry_sha1, "name": name})
    return entries


# ---------------------------------------------------------------------------
# Commit objects: a tree snapshot + a pointer to the previous commit + a
# message. The parent pointer is what turns a pile of snapshots into
# actual HISTORY -- `log` just walks this chain backward.
# ---------------------------------------------------------------------------

def commit_tree(tree_sha1, parent_sha1, message, author="mygit user <user@example.com>"):
    """
    Create and store a commit object.

    Args:
        tree_sha1: hash of the tree this commit snapshots.
        parent_sha1: hash of the previous commit, or None for the very
            first commit in the repo's history (no parent).
        message: commit message.
        author: placeholder identity string (real git reads this from
            git config; we don't implement config, so it's fixed for now).

    Returns:
        The new commit object's hash.
    """
    timestamp = int(time.time())

    lines = [f"tree {tree_sha1}"]
    if parent_sha1:
        lines.append(f"parent {parent_sha1}")
    lines.append(f"author {author} {timestamp}")
    lines.append(f"committer {author} {timestamp}")
    lines.append("")
    lines.append(message)
    lines.append("")

    commit_data = "\n".join(lines).encode()
    return hash_object(commit_data, obj_type="commit", write=True)


def read_commit(sha1):
    """
    Parse a commit object into a dict:
    {"tree": ..., "parent": ... or None, "author": ..., "committer": ..., "message": ...}
    """
    obj_type, data = read_object(sha1)
    if obj_type != "commit":
        raise ValueError(f"object {sha1} is a {obj_type}, not a commit")

    header, message = data.decode().split("\n\n", maxsplit=1)

    result = {"tree": None, "parent": None, "author": None, "committer": None}
    for line in header.splitlines():
        key, _, value = line.partition(" ")
        if key in result:
            result[key] = value

    result["message"] = message.rstrip("\n")
    return result
