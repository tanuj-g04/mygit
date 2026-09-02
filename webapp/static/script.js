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

document.getElementById("hash-only-btn").addEventListener("click", () => hashObject(false));
document.getElementById("hash-store-btn").addEventListener("click", () => hashObject(true));
document.getElementById("retrieve-btn").addEventListener("click", retrieveObject);
document.getElementById("refresh-btn").addEventListener("click", loadObjects);

loadStatus();
loadObjects();
