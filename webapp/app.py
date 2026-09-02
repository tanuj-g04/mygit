"""
A tiny Flask web UI that wraps the REAL mygit package (mygit/objects.py,
mygit/repository.py) so you can see content-addressable storage working
visually, instead of only in a terminal.

This does not reimplement any git logic -- every endpoint below is a thin
wrapper calling straight into the same code the CLI uses. Its only job is
to translate HTTP requests into calls to objects.hash_object /
objects.read_object / repository.init, and return JSON.

Run with:
    py app.py        (Windows, if 'python' isn't on PATH)
    python app.py     (Mac/Linux)

Then open http://localhost:5000 in a browser.
"""

import os
import sys

# Make sure the mygit package (one level up) is importable regardless
# of where this script is launched from.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from flask import Flask, jsonify, render_template, request

from mygit import objects, repository

# The demo operates on a dedicated repo folder sitting next to this
# script, so it never touches any other mygit repo on your machine.
DEMO_REPO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_repo")
os.makedirs(DEMO_REPO_DIR, exist_ok=True)

# All repository/objects functions resolve paths relative to the
# current working directory (mirroring how the real CLI works), so we
# switch into the demo repo once at startup and initialize it if needed.
os.chdir(DEMO_REPO_DIR)
repository.init(".")

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def status():
    """Report where the demo repo lives, so the UI can show it."""
    return jsonify({"repo_path": repository.get_mygit_dir()})


@app.route("/api/hash-object", methods=["POST"])
def api_hash_object():
    """
    Body: {"content": "<text>", "write": true/false}
    Mirrors: mygit hash-object [-w] <file>
    """
    payload = request.get_json(force=True) or {}
    content = payload.get("content", "")
    write = bool(payload.get("write", True))

    # Check BEFORE writing whether this exact content already exists,
    # so the UI can tell the user "this was already stored" (the
    # dedup property) versus "this is new".
    sha1_preview = objects.hash_object(content.encode("utf-8"), write=False)
    already_existed = _object_exists(sha1_preview)

    sha1 = objects.hash_object(content.encode("utf-8"), write=write)
    return jsonify({
        "hash": sha1,
        "written": write,
        "already_existed": already_existed,
    })


@app.route("/api/cat-file/<sha1>")
def api_cat_file(sha1):
    """Mirrors: mygit cat-file <hash>"""
    try:
        obj_type, content = objects.read_object(sha1)
    except FileNotFoundError:
        return jsonify({"error": "object not found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "type": obj_type,
        "size": len(content),
        "content": content.decode("utf-8", errors="replace"),
    })


@app.route("/api/objects")
def api_list_objects():
    """
    List every object currently in the store, for the UI's live list.
    Not a real git command (git has no direct equivalent without walking
    history) -- this is a demo-only convenience to make storage visible.
    """
    objects_dir = os.path.join(repository.get_mygit_dir(), "objects")
    result = []

    for prefix in sorted(os.listdir(objects_dir)):
        prefix_path = os.path.join(objects_dir, prefix)
        if not os.path.isdir(prefix_path):
            continue
        for rest in sorted(os.listdir(prefix_path)):
            sha1 = prefix + rest
            obj_type, content = objects.read_object(sha1)
            text = content.decode("utf-8", errors="replace")
            preview = text if len(text) <= 60 else text[:60] + "..."
            result.append({
                "hash": sha1,
                "type": obj_type,
                "size": len(content),
                "preview": preview,
            })

    return jsonify(result)


# ---------------------------------------------------------------------------
# Day 2 additions: managing real working-directory files, committing them,
# and viewing history -- this exercises write_tree/commit_tree/read_commit,
# the same functions the `mygit commit` / `mygit log` CLI commands use.
# ---------------------------------------------------------------------------

def _working_files():
    """List real files sitting in the demo repo's working directory (not .mygit)."""
    names = []
    for name in sorted(os.listdir(DEMO_REPO_DIR)):
        if name == repository.MYGIT_DIR:
            continue
        full_path = os.path.join(DEMO_REPO_DIR, name)
        if os.path.isfile(full_path):
            names.append(name)
    return names


@app.route("/api/files", methods=["GET"])
def api_list_files():
    files = []
    for name in _working_files():
        with open(os.path.join(DEMO_REPO_DIR, name), "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        files.append({"name": name, "content": content})
    return jsonify(files)


@app.route("/api/files", methods=["POST"])
def api_write_file():
    """
    Body: {"name": "<filename>", "content": "<text>"}
    Writes (or overwrites) an actual file in the demo repo's working
    directory -- this is what `commit` will snapshot, mirroring how you'd
    normally edit files on disk before running `mygit commit`.
    """
    payload = request.get_json(force=True) or {}
    # os.path.basename strips any directory components, preventing a
    # filename like "../../etc/passwd" from writing outside the demo repo.
    name = os.path.basename(payload.get("name", "").strip())
    content = payload.get("content", "")

    if not name:
        return jsonify({"error": "filename is required"}), 400

    with open(os.path.join(DEMO_REPO_DIR, name), "w", encoding="utf-8") as f:
        f.write(content)

    return jsonify({"name": name, "content": content})


@app.route("/api/files/<name>", methods=["DELETE"])
def api_delete_file(name):
    name = os.path.basename(name)
    path = os.path.join(DEMO_REPO_DIR, name)
    if os.path.exists(path):
        os.remove(path)
    return jsonify({"deleted": name})


@app.route("/api/commit", methods=["POST"])
def api_commit():
    """
    Body: {"message": "<commit message>"}
    Mirrors: mygit commit -m "<message>"
    Snapshots the CURRENT working files (whatever /api/files shows right
    now) as a tree, wraps it in a commit pointing at the previous commit
    as parent, and advances the branch ref.
    """
    payload = request.get_json(force=True) or {}
    message = payload.get("message", "").strip()
    if not message:
        return jsonify({"error": "commit message is required"}), 400

    tree_sha1 = objects.write_tree(DEMO_REPO_DIR)
    parent_sha1 = repository.get_current_commit()
    commit_sha1 = objects.commit_tree(tree_sha1, parent_sha1, message)
    repository.update_ref(repository.get_head_ref(), commit_sha1)

    return jsonify({"hash": commit_sha1, "tree": tree_sha1, "parent": parent_sha1})


@app.route("/api/log")
def api_log():
    """Mirrors: mygit log -- walks the parent chain from the current commit."""
    commit_sha1 = repository.get_current_commit()
    history = []

    while commit_sha1:
        commit = objects.read_commit(commit_sha1)
        history.append({
            "hash": commit_sha1,
            "tree": commit["tree"],
            "parent": commit["parent"],
            "author": commit["author"],
            "message": commit["message"],
        })
        commit_sha1 = commit["parent"]

    return jsonify(history)


@app.route("/api/tree/<sha1>")
def api_tree(sha1):
    """List a tree object's entries -- what a given commit's snapshot contains."""
    try:
        entries = objects.read_tree(sha1)
    except (FileNotFoundError, ValueError) as e:
        return jsonify({"error": str(e)}), 404
    return jsonify(entries)


def _object_exists(sha1):
    obj_path = os.path.join(repository.get_mygit_dir(), "objects", sha1[:2], sha1[2:])
    return os.path.exists(obj_path)


if __name__ == "__main__":
    print(f"Demo repo initialized at: {repository.get_mygit_dir()}")
    print("Open http://localhost:5000 in your browser")
    # use_reloader=False: the reloader re-execs this script using a
    # relative path captured before we chdir'd into demo_repo, which
    # breaks once we're no longer in the original working directory.
    app.run(debug=True, port=5000, use_reloader=False)
