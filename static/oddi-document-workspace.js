(function attachOddiDocumentWorkspace() {
    const formatLabels = {
        pdf: "PDF",
        docx: "Word (.docx)",
        html: "HTML",
        txt: "Text (.txt)",
        md: "Markdown (.md)",
        png: "PNG image (short documents)"
    };
    let state = null;
    let refs = null;

    function ensureWorkspace() {
        if (refs?.overlay?.isConnected) return refs;

        const overlay = document.createElement("div");
        overlay.id = "oddiDocumentWorkspaceOverlay";
        overlay.className = "oddi-document-workspace-overlay";
        overlay.hidden = true;
        overlay.setAttribute("aria-hidden", "true");
        overlay.innerHTML = `
            <section class="oddi-document-workspace" role="dialog" aria-modal="true" aria-labelledby="oddiDocumentWorkspaceTitle" tabindex="-1">
                <header class="oddi-document-workspace-header">
                    <div class="oddi-document-workspace-heading">
                        <span class="oddi-document-workspace-kicker">ODDI DOCUMENT EDITOR</span>
                        <h1 id="oddiDocumentWorkspaceTitle"></h1>
                    </div>
                    <button class="oddi-document-workspace-close" type="button" aria-label="Close document editor" title="Close">×</button>
                </header>
                <div class="oddi-document-workspace-toolbar" role="toolbar" aria-label="Document actions">
                    <label class="oddi-document-workspace-format-label">Download as
                        <select class="oddi-document-workspace-format" aria-label="Choose document download format">
                            <option value="pdf">PDF</option>
                            <option value="docx">Word (.docx)</option>
                            <option value="html">HTML</option>
                            <option value="txt">Text (.txt)</option>
                            <option value="md">Markdown (.md)</option>
                            <option value="png">PNG image (short documents)</option>
                        </select>
                    </label>
                    <button class="oddi-document-workspace-download" type="button">Download</button>
                    <button class="oddi-document-workspace-edit" type="button">Edit</button>
                    <button class="oddi-document-workspace-cancel" type="button" hidden>Cancel</button>
                    <button class="oddi-document-workspace-copy" type="button">Copy</button>
                </div>
                <div class="oddi-document-workspace-status" role="status" aria-live="polite"></div>
                <article class="oddi-document-workspace-content" aria-label="Generated document" contenteditable="false"></article>
            </section>
        `;
        document.body.appendChild(overlay);

        const dialog = overlay.querySelector(".oddi-document-workspace");
        const content = overlay.querySelector(".oddi-document-workspace-content");
        const editButton = overlay.querySelector(".oddi-document-workspace-edit");
        const cancelButton = overlay.querySelector(".oddi-document-workspace-cancel");
        refs = {
            overlay,
            dialog,
            title: overlay.querySelector("#oddiDocumentWorkspaceTitle"),
            content,
            status: overlay.querySelector(".oddi-document-workspace-status"),
            format: overlay.querySelector(".oddi-document-workspace-format"),
            download: overlay.querySelector(".oddi-document-workspace-download"),
            edit: editButton,
            cancel: cancelButton,
            copy: overlay.querySelector(".oddi-document-workspace-copy"),
            savedHtml: ""
        };

        const close = () => closeWorkspace();
        overlay.querySelector(".oddi-document-workspace-close").addEventListener("click", close);
        overlay.addEventListener("click", event => {
            if (event.target === overlay) close();
        });
        document.addEventListener("keydown", event => {
            if (event.key === "Escape" && !overlay.hidden) close();
        });

        editButton.addEventListener("click", async () => {
            if (!state || state.generating) return;
            if (!state.editing) {
                refs.savedHtml = content.innerHTML;
                state.editing = true;
                content.contentEditable = "true";
                content.classList.add("is-editing");
                editButton.textContent = "Save changes";
                cancelButton.hidden = false;
                setStatus("Edit the document, then save your changes.");
                content.focus();
                return;
            }

            const markdown = String(state.serializeMarkdown?.(content) || "").trim();
            if (!markdown) {
                setStatus("Document content cannot be empty.", true);
                return;
            }
            editButton.disabled = true;
            cancelButton.disabled = true;
            setStatus("Saving changes…");
            try {
                const saved = await state.onSave?.({ markdown, title: state.title });
                if (saved === false) throw new Error("Save failed. Your edits are still here; try again.");
                state.markdown = markdown;
                if (state.renderMarkdown) {
                    content.innerHTML = state.renderMarkdown(markdown);
                    state.enhance?.(content);
                }
                refs.savedHtml = content.innerHTML;
                leaveEditMode();
                setStatus("Saved.");
            } catch (error) {
                setStatus(error?.message || "Save failed. Your edits are still here; try again.", true);
            } finally {
                editButton.disabled = false;
                cancelButton.disabled = false;
            }
        });

        cancelButton.addEventListener("click", () => {
            content.innerHTML = refs.savedHtml;
            leaveEditMode();
            setStatus("Edits discarded.");
        });

        refs.copy.addEventListener("click", async () => {
            if (!state) return;
            try {
                const markdown = String(state.serializeMarkdown?.(content) || state.markdown || "");
                if (navigator.clipboard?.writeText) {
                    await navigator.clipboard.writeText(markdown);
                } else {
                    const area = document.createElement("textarea");
                    area.value = markdown;
                    document.body.appendChild(area);
                    area.select();
                    document.execCommand("copy");
                    area.remove();
                }
                setStatus("Document copied.");
            } catch (_) {
                setStatus("Copy is unavailable in this browser.", true);
            }
        });

        refs.download.addEventListener("click", () => downloadCurrentDocument());
        return refs;
    }

    function setStatus(message, isError = false) {
        if (!refs) return;
        refs.status.textContent = String(message || "");
        refs.status.classList.toggle("is-error", !!isError);
    }

    function leaveEditMode() {
        if (!refs || !state) return;
        state.editing = false;
        refs.content.contentEditable = "false";
        refs.content.classList.remove("is-editing");
        refs.edit.textContent = "Edit";
        refs.cancel.hidden = true;
    }

    function setGenerating(generating) {
        if (!refs || !state) return;
        state.generating = !!generating;
        refs.download.disabled = state.generating;
        refs.format.disabled = state.generating;
        refs.edit.disabled = state.generating;
        refs.copy.disabled = state.generating;
        if (!state.generating && state.editing) leaveEditMode();
    }

    function open(options = {}) {
        ensureWorkspace();
        if (state?.editing) {
            setStatus("Save or cancel your current edits before opening another document.", true);
            return false;
        }
        state = {
            title: String(options.title || "Document draft").trim() || "Document draft",
            markdown: "",
            renderMarkdown: options.renderMarkdown,
            enhance: options.enhance,
            serializeMarkdown: options.serializeMarkdown,
            onSave: options.onSave,
            createPdfBlob: options.createPdfBlob,
            createDocxBlob: options.createDocxBlob,
            generating: false,
            editing: false
        };
        refs.title.textContent = state.title;
        refs.format.value = formatLabels[options.format] ? options.format : "pdf";
        refs.content.contentEditable = "false";
        refs.content.classList.remove("is-editing");
        refs.content.innerHTML = "";
        refs.savedHtml = "";
        refs.edit.textContent = "Edit";
        refs.cancel.hidden = true;
        refs.overlay.hidden = false;
        refs.overlay.setAttribute("aria-hidden", "false");
        document.body.classList.add("oddi-document-workspace-open");
        if (typeof options.markdown === "string") update(options.markdown, {
            status: options.status || "Ready to edit or download.",
            generating: !!options.generating,
            error: !!options.error
        });
        else {
            setGenerating(!!options.generating);
            setStatus(options.status || "Preparing your document…", !!options.error);
        }
        if (options.focus !== false) refs.overlay.querySelector(".oddi-document-workspace-close")?.focus({ preventScroll: true });
        return true;
    }

    function update(markdown, options = {}) {
        if (!refs || !state) return false;
        const source = String(markdown || "");
        state.markdown = source;
        refs.content.innerHTML = state.renderMarkdown
            ? state.renderMarkdown(source)
            : `<pre>${escapeHtml(source)}</pre>`;
        state.enhance?.(refs.content);
        if (options.status !== undefined) setStatus(options.status, !!options.error);
        setGenerating(options.generating === undefined ? state.generating : options.generating);
        return true;
    }

    function escapeHtml(text) {
        return String(text).replace(/[&<>"']/g, character => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
        })[character]);
    }

    function sanitizeFilename(title) {
        return String(title || "Document")
            .normalize("NFKC")
            .replace(/[<>:"/\\|?*\u0000-\u001f]/g, " ")
            .replace(/\s+/g, " ")
            .trim()
            .slice(0, 90) || "Document";
    }

    function saveBlob(blob, filename) {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 30000);
    }

    async function downloadCurrentDocument() {
        if (!state || state.generating) return;
        const format = refs.format.value;
        const markdown = String(state.serializeMarkdown?.(refs.content) || state.markdown || "").trim();
        if (!markdown) {
            setStatus("There is no document content to download yet.", true);
            return;
        }
        refs.download.disabled = true;
        setStatus(`Preparing ${formatLabels[format] || format}…`);
        try {
            const title = sanitizeFilename(state.title);
            const firstHeading = refs.content.querySelector(":scope > h1");
            const titleAlreadyPresent = !!firstHeading && String(firstHeading.textContent || "").trim().toLowerCase().includes(state.title.toLowerCase());
            const titleMarkup = titleAlreadyPresent ? "" : `<h1>${escapeHtml(state.title)}</h1>`;
            const markdownWithTitle = titleAlreadyPresent ? markdown : `# ${state.title}\n\n${markdown}`;
            const html = `<!doctype html><html><head><meta charset="utf-8"><title>${escapeHtml(state.title)}</title><style>body{max-width:850px;margin:36px auto;padding:0 28px;color:#111;font:14px/1.6 Arial,sans-serif}h1,h2,h3,h4{line-height:1.25;margin:1.1em 0 .4em}p{margin:.55em 0}ul,ol{padding-left:26px}table{width:100%;border-collapse:collapse;margin:16px 0}th,td{border:1px solid #999;padding:7px 9px;text-align:left}blockquote{border-left:3px solid #888;padding-left:14px;color:#444}pre{white-space:pre-wrap;background:#f5f5f5;padding:12px}code{font-family:Consolas,monospace}</style></head><body><article>${titleMarkup}${refs.content.innerHTML}</article></body></html>`;
            let blob;
            if (format === "pdf") {
                if (typeof state.createPdfBlob !== "function") throw new Error("PDF export is unavailable right now.");
                const exportRoot = document.createElement("article");
                exportRoot.innerHTML = `${titleMarkup}${refs.content.innerHTML}`;
                blob = await state.createPdfBlob(exportRoot);
            } else if (format === "png") {
                if (typeof window.html2canvas !== "function") throw new Error("PNG export is unavailable right now.");
                const imageRoot = document.createElement("article");
                imageRoot.style.cssText = "position:fixed;left:-100000px;top:0;width:850px;padding:44px;box-sizing:border-box;background:#fff;color:#111;font:14px/1.6 Arial,sans-serif;";
                imageRoot.innerHTML = `${titleMarkup}${refs.content.innerHTML}`;
                document.body.appendChild(imageRoot);
                try {
                    if (imageRoot.scrollHeight > 12000) throw new Error("PNG export is limited to short documents. Use PDF for a long document.");
                    const canvas = await window.html2canvas(imageRoot, {scale: 1.5, backgroundColor: "#fff", useCORS: true, logging: false});
                    if (!canvas || canvas.width * canvas.height > 40000000) throw new Error("This document is too large for one PNG image. Use PDF instead.");
                    blob = await new Promise((resolve, reject) => canvas.toBlob(value => value ? resolve(value) : reject(new Error("Could not create the PNG image.")), "image/png"));
                } finally {
                    imageRoot.remove();
                }
            } else if (format === "docx") {
                if (typeof state.createDocxBlob !== "function") throw new Error("Word export is unavailable right now.");
                blob = await state.createDocxBlob(html);
            } else if (format === "html") {
                blob = new Blob([html], { type: "text/html;charset=utf-8" });
            } else if (format === "md") {
                blob = new Blob([markdownWithTitle], { type: "text/markdown;charset=utf-8" });
            } else {
                const plainText = markdownWithTitle
                    .replace(/^#{1,6}\s+/gm, "")
                    .replace(/^\s*[-*+]\s+/gm, match => `${match.match(/^\s*/)[0]}• `)
                    .replace(/\*\*(.*?)\*\*/g, "$1")
                    .replace(/\*([^*]+)\*/g, "$1")
                    .replace(/`([^`]+)`/g, "$1")
                    .replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, "$1 — $2")
                    .trim();
                blob = new Blob([plainText], { type: "text/plain;charset=utf-8" });
            }
            if (!(blob instanceof Blob) || !blob.size) throw new Error("The exported file was empty. Your document is still available here; try again.");
            saveBlob(blob, `${title}.${format}`);
            setStatus(`${formatLabels[format] || format} downloaded.`);
        } catch (error) {
            console.error("Document export failed:", error);
            setStatus(error?.message || "Download failed. Your document is still available here; try again.", true);
        } finally {
            refs.download.disabled = false;
        }
    }

    function closeWorkspace() {
        if (!refs) return;
        if (state?.editing) {
            setStatus("Save or cancel your edits before closing the editor.", true);
            return false;
        }
        refs.overlay.hidden = true;
        refs.overlay.setAttribute("aria-hidden", "true");
        document.body.classList.remove("oddi-document-workspace-open");
    }

    window.OddiDocumentWorkspace = {
        open,
        update,
        close: closeWorkspace,
        download: downloadCurrentDocument,
        isEditing: () => !!state?.editing,
        notify: (message, isError = false) => setStatus(message, isError),
        isOpen: () => !!refs && !refs.overlay.hidden
    };
})();
