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
import zlib

from .repository import get_mygit_dir


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
