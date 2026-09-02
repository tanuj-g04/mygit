async function loadStatus() {
    const res = await fetch("/api/status");
    const data = await res.json();
    document.getElementById("repo-path").textContent = "Repo: " + data.repo_path;
}

async function hashObject(write) {
    const content = document.getElementById("content-input").value;
    const resultEl = document.getElementById("hash-result");

    if (!content) {
        resultEl.innerHTML = '<span class="badge error">Type some content first</span>';
        return;
    }

    const res = await fetch("/api/hash-object", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content, write }),
    });
    const data = await res.json();

    let badge;
    if (!write) {
        badge = '<span class="badge existing">preview only — not stored</span>';
    } else if (data.already_existed) {
        badge = '<span class="badge existing">already existed — no new object written</span>';
    } else {
        badge = '<span class="badge new">new object stored</span>';
    }

    resultEl.innerHTML = `Hash: <span class="hash">${data.hash}</span>${badge}`;

    if (write) {
        loadObjects();
    }
}

async function retrieveObject() {
    const hash = document.getElementById("retrieve-input").value.trim();
    const resultEl = document.getElementById("retrieve-result");

    if (!hash) {
        resultEl.innerHTML = '<span class="badge error">Paste a hash first</span>';
        return;
    }

    const res = await fetch("/api/cat-file/" + encodeURIComponent(hash));
    if (res.status === 404) {
        resultEl.innerHTML = '<span class="badge error">Object not found</span>';
        return;
    }
    const data = await res.json();
    resultEl.innerHTML =
        `Type: ${data.type}    Size: ${data.size} bytes\n` +
        `Content:\n${escapeHtml(data.content)}`;
}

async function loadObjects() {
    const res = await fetch("/api/objects");
    const objects = await res.json();
    const tbody = document.getElementById("objects-body");
    const emptyState = document.getElementById("empty-state");

    tbody.innerHTML = "";

    if (objects.length === 0) {
        emptyState.style.display = "block";
        return;
    }
    emptyState.style.display = "none";

    for (const obj of objects) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td class="hash-cell" title="Click to retrieve">${obj.hash.slice(0, 12)}...</td>
            <td>${obj.type}</td>
            <td>${obj.size}</td>
            <td>${escapeHtml(obj.preview)}</td>
        `;
        tr.querySelector(".hash-cell").addEventListener("click", () => {
            document.getElementById("retrieve-input").value = obj.hash;
            retrieveObject();
        });
        tbody.appendChild(tr);
    }
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

// --- Working files (Day 2) ---

async function saveFile() {
    const name = document.getElementById("file-name-input").value.trim();
    const content = document.getElementById("file-content-input").value;

    if (!name) {
        alert("Enter a filename first");
        return;
    }

    await fetch("/api/files", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, content }),
    });

    document.getElementById("file-name-input").value = "";
    document.getElementById("file-content-input").value = "";
    loadFiles();
}

async function deleteFile(name) {
    await fetch("/api/files/" + encodeURIComponent(name), { method: "DELETE" });
    loadFiles();
}

async function loadFiles() {
    const res = await fetch("/api/files");
    const files = await res.json();
    const list = document.getElementById("files-list");
    const emptyState = document.getElementById("files-empty-state");

    list.innerHTML = "";

    if (files.length === 0) {
        emptyState.style.display = "block";
        return;
    }
    emptyState.style.display = "none";

    for (const file of files) {
        const li = document.createElement("li");
        const preview = file.content.length > 40 ? file.content.slice(0, 40) + "..." : file.content;
        li.innerHTML = `
            <span>${escapeHtml(file.name)}</span>
            <span class="file-preview">${escapeHtml(preview)}</span>
        `;
        const delBtn = document.createElement("button");
        delBtn.textContent = "Delete";
        delBtn.addEventListener("click", () => deleteFile(file.name));
        li.appendChild(delBtn);
        list.appendChild(li);
    }
}

// --- Commit (Day 2) ---

async function makeCommit() {
    const message = document.getElementById("commit-message-input").value.trim();
    const resultEl = document.getElementById("commit-result");

    if (!message) {
        resultEl.innerHTML = '<span class="badge error">Enter a commit message first</span>';
        return;
    }

    const res = await fetch("/api/commit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
    });
    const data = await res.json();

    if (data.error) {
        resultEl.innerHTML = `<span class="badge error">${escapeHtml(data.error)}</span>`;
        return;
    }

    resultEl.innerHTML =
        `Commit: <span class="hash">${data.hash}</span>\n` +
        `Tree: ${data.tree}\n` +
        `Parent: ${data.parent || "(none — first commit)"}`;

    document.getElementById("commit-message-input").value = "";
    loadLog();
    loadObjects();
}

// --- Log / history (Day 2) ---

async function loadLog() {
    const res = await fetch("/api/log");
    const history = await res.json();
    const list = document.getElementById("log-list");
    const emptyState = document.getElementById("log-empty-state");

    list.innerHTML = "";

    if (history.length === 0) {
        emptyState.style.display = "block";
        return;
    }
    emptyState.style.display = "none";

    for (const commit of history) {
        const card = document.createElement("div");
        card.className = "commit-card";
        card.innerHTML = `
            <div class="commit-hash">commit ${commit.hash}</div>
            <div class="commit-message">${escapeHtml(commit.message)}</div>
            <button class="commit-tree-toggle">Show files snapshotted</button>
            <div class="tree-entries" data-tree="${commit.tree}"></div>
        `;
        const toggleBtn = card.querySelector(".commit-tree-toggle");
        const entriesDiv = card.querySelector(".tree-entries");
        toggleBtn.addEventListener("click", () => toggleTreeEntries(entriesDiv));
        list.appendChild(card);
    }
}

async function toggleTreeEntries(entriesDiv) {
    const isVisible = entriesDiv.classList.contains("visible");
    if (isVisible) {
        entriesDiv.classList.remove("visible");
        return;
    }

    if (!entriesDiv.dataset.loaded) {
        const treeSha = entriesDiv.dataset.tree;
        const res = await fetch("/api/tree/" + treeSha);
        const entries = await res.json();

        if (entries.length === 0) {
            entriesDiv.innerHTML = "<div>(empty tree)</div>";
        } else {
            entriesDiv.innerHTML = entries.map(e =>
                `<div class="${e.type === 'tree' ? 'entry-type-tree' : ''}">${e.type}  ${e.sha1.slice(0, 10)}...  ${escapeHtml(e.name)}</div>`
            ).join("");
        }
        entriesDiv.dataset.loaded = "true";
    }

    entriesDiv.classList.add("visible");
}

document.getElementById("hash-only-btn").addEventListener("click", () => hashObject(false));
document.getElementById("hash-store-btn").addEventListener("click", () => hashObject(true));
document.getElementById("retrieve-btn").addEventListener("click", retrieveObject);
document.getElementById("refresh-btn").addEventListener("click", loadObjects);
document.getElementById("save-file-btn").addEventListener("click", saveFile);
document.getElementById("commit-btn").addEventListener("click", makeCommit);
document.getElementById("refresh-log-btn").addEventListener("click", loadLog);

loadStatus();
loadObjects();
loadFiles();
loadLog();
