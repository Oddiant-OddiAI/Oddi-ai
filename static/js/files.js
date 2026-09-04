const ODDI_FILE_DB = "oddi-file-store";
const ODDI_FILE_STORE = "files";

function openOddiFileDB() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(ODDI_FILE_DB, 1);

        request.onupgradeneeded = () => {
            const db = request.result;
            if (!db.objectStoreNames.contains(ODDI_FILE_STORE)) {
                db.createObjectStore(ODDI_FILE_STORE, { keyPath: "id" });
            }
        };

        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

async function storeOddiFile(file) {
    const id = "file-" + Date.now() + "-" + Math.random().toString(36).slice(2);
    const db = await openOddiFileDB();

    return new Promise((resolve, reject) => {
        const tx = db.transaction(ODDI_FILE_STORE, "readwrite");
        tx.objectStore(ODDI_FILE_STORE).put({
            id,
            name: file.name,
            type: file.type || "application/octet-stream",
            blob: file
        });
        tx.oncomplete = () => { db.close(); resolve(id); };
        tx.onerror = () => { db.close(); reject(tx.error); };
    });
}

async function getOddiStoredFile(id) {
    const db = await openOddiFileDB();

    return new Promise((resolve, reject) => {
        const tx = db.transaction(ODDI_FILE_STORE, "readonly");
        const request = tx.objectStore(ODDI_FILE_STORE).get(id);
        request.onsuccess = () => {
            db.close();
            resolve(request.result || null);
        };
        request.onerror = () => {
            db.close();
            reject(request.error);
        };
    });
}

async function openOddiUploadedFile(fileId) {
    try {
        const stored = await getOddiStoredFile(fileId);
        if (!stored || !stored.blob) {
            alert("This uploaded file is no longer available on this device.");
            return;
        }

        const url = URL.createObjectURL(stored.blob);
        const link = document.createElement("a");
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener";
        link.click();

        setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (error) {
        console.error("Could not open uploaded file:", error);
        alert("Could not open this uploaded file.");
    }
}

function buildFileHTML(fileName, fileId = "") {
    const safeName = escapeUserText(fileName);
    const key = escapeUserText(fileId);

    return `
        <div class="message-file"
             ${fileId ? `data-file-key="${key}" role="button" tabindex="0" title="Open ${safeName}"` : ""}>
            ${getFileIcon(fileName)}
            <span>${safeName}</span>
        </div>
    `;
}

