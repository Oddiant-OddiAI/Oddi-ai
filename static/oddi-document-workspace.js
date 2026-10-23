(function attachOddiDocumentWorkspace() {
    const formatLabels = {
        pdf: "PDF document",
        docx: "Microsoft Word",
        md: "Markdown document",
        txt: "Plain text",
        html: "HTML document",
        rtf: "Rich Text Format",
        png: "PNG image"
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
            <section class="oddi-document-workspace" role="dialog" aria-modal="false" aria-labelledby="oddiDocumentWorkspaceTitle" tabindex="-1">
                <header class="oddi-document-workspace-header">
                    <div class="oddi-document-workspace-heading">
                        <span class="oddi-document-workspace-kicker">ODDI WRITING</span>
                        <h1 id="oddiDocumentWorkspaceTitle"></h1>
                        <span class="oddi-document-workspace-saved" aria-live="polite">Saved to this chat</span>
                    </div>
                    <div class="oddi-document-workspace-actions" role="toolbar" aria-label="Document actions">
                        <button class="oddi-document-workspace-icon oddi-document-workspace-copy" type="button" aria-label="Copy document" title="Copy document"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h3"/></svg></button>
                        <button class="oddi-document-workspace-icon oddi-document-workspace-undo" type="button" aria-label="Undo" title="Undo" disabled><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 14 4 9l5-5"/><path d="M4 9h9a7 7 0 0 1 0 14h-2"/></svg></button>
                        <button class="oddi-document-workspace-icon oddi-document-workspace-redo" type="button" aria-label="Redo" title="Redo" disabled><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 14 5-5-5-5"/><path d="M20 9h-9a7 7 0 0 0 0 14h2"/></svg></button>
                        <div class="oddi-document-workspace-download-wrap">
                            <button class="oddi-document-workspace-download" type="button" aria-haspopup="menu" aria-expanded="false" aria-controls="oddiDocumentDownloadMenu" title="Download document">
                                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12m0 0 5-5m-5 5-5-5M4 20h16"/></svg><span>Download</span><svg class="oddi-document-workspace-chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>
                            </button>
                            <div class="oddi-document-workspace-menu" id="oddiDocumentDownloadMenu" role="menu" hidden>
                                <button type="button" role="menuitem" data-document-format="pdf"><span class="oddi-format-icon is-pdf">PDF</span><span>PDF document <small>Recommended</small></span></button>
                                <button type="button" role="menuitem" data-document-format="docx"><span class="oddi-format-icon is-word">W</span><span>Microsoft Word <small>.docx</small></span></button>
                                <button type="button" role="menuitem" data-document-format="md"><span class="oddi-format-icon is-markdown">M</span><span>Markdown document <small>.md</small></span></button>
                                <button type="button" role="menuitem" data-document-format="txt"><span class="oddi-format-icon is-text">TXT</span><span>Plain text <small>.txt</small></span></button>
                                <button type="button" role="menuitem" data-document-format="html"><span class="oddi-format-icon is-html">H</span><span>HTML document <small>.html</small></span></button>
                                <button type="button" role="menuitem" data-document-format="rtf"><span class="oddi-format-icon is-rtf">R</span><span>Rich Text Format <small>.rtf</small></span></button>
                            </div>
                        </div>
                        <button class="oddi-document-workspace-edit" type="button">Edit</button>
                        <button class="oddi-document-workspace-cancel" type="button" hidden>Cancel</button>
                        <button class="oddi-document-workspace-icon oddi-document-workspace-fullscreen" type="button" aria-label="Expand editor" title="Expand editor"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 4H4v4M16 4h4v4M20 16v4h-4M4 16v4h4"/></svg></button>
                        <button class="oddi-document-workspace-icon oddi-document-workspace-close" type="button" aria-label="Close document editor" title="Close"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg></button>
                    </div>
                </header>
                <div class="oddi-document-workspace-status" role="status" aria-live="polite"></div>
                <article class="oddi-document-workspace-content" aria-label="Generated document" contenteditable="false"></article>
            </section>
        `;
        document.body.appendChild(overlay);

        const content = overlay.querySelector(".oddi-document-workspace-content");
        refs = {
            overlay,
            dialog: overlay.querySelector(".oddi-document-workspace"),
            title: overlay.querySelector("#oddiDocumentWorkspaceTitle"),
            saved: overlay.querySelector(".oddi-document-workspace-saved"),
            content,
            status: overlay.querySelector(".oddi-document-workspace-status"),
            download: overlay.querySelector(".oddi-document-workspace-download"),
            menu: overlay.querySelector(".oddi-document-workspace-menu"),
            edit: overlay.querySelector(".oddi-document-workspace-edit"),
            cancel: overlay.querySelector(".oddi-document-workspace-cancel"),
            copy: overlay.querySelector(".oddi-document-workspace-copy"),
            undo: overlay.querySelector(".oddi-document-workspace-undo"),
            redo: overlay.querySelector(".oddi-document-workspace-redo"),
            fullscreen: overlay.querySelector(".oddi-document-workspace-fullscreen"),
            savedHtml: "",
            opener: null
        };

        overlay.querySelector(".oddi-document-workspace-close").addEventListener("click", closeWorkspace);
        document.addEventListener("keydown", event => {
            if (event.key !== "Escape" || refs.overlay.hidden) return;
            if (!refs.menu.hidden) closeDownloadMenu();
            else closeWorkspace();
        });
        document.addEventListener("click", event => {
            if (refs && !refs.overlay.hidden && !refs.menu.contains(event.target) && event.target !== refs.download && !refs.download.contains(event.target)) {
                closeDownloadMenu();
            }
        });

        refs.download.addEventListener("click", () => toggleDownloadMenu());
        refs.menu.addEventListener("click", event => {
            const formatButton = event.target.closest("[data-document-format]");
            if (!formatButton || formatButton.disabled) return;
            closeDownloadMenu();
            void downloadCurrentDocument(formatButton.dataset.documentFormat);
        });
        refs.edit.addEventListener("click", saveOrEdit);
        refs.cancel.addEventListener("click", () => {
            content.innerHTML = refs.savedHtml;
            leaveEditMode();
            setStatus("Edits discarded.");
        });
        content.addEventListener("input", updateUndoRedoState);
        refs.undo.addEventListener("click", () => runEditCommand("undo"));
        refs.redo.addEventListener("click", () => runEditCommand("redo"));
        refs.fullscreen.addEventListener("click", toggleExpanded);
        refs.copy.addEventListener("click", copyCurrentDocument);
        return refs;
    }

    function setStatus(message, isError = false) {
        if (!refs) return;
        refs.status.textContent = String(message || "");
        refs.status.classList.toggle("is-error", !!isError);
    }

    function setSavedLabel(message, isError = false) {
        if (!refs) return;
        refs.saved.textContent = String(message || "");
        refs.saved.classList.toggle("is-error", !!isError);
    }

    function savedLabel() {
        return String(state?.savedLabel || "Saved to this chat");
    }

    function toggleDownloadMenu(forceOpen) {
        if (!refs) return;
        const open = forceOpen === undefined ? refs.menu.hidden : !!forceOpen;
        refs.menu.hidden = !open;
        refs.download.setAttribute("aria-expanded", open ? "true" : "false");
    }

    function closeDownloadMenu() {
        if (!refs) return;
        refs.menu.hidden = true;
        refs.download.setAttribute("aria-expanded", "false");
    }

    function toggleExpanded() {
        if (!refs) return;
        const expanded = !refs.overlay.classList.contains("is-expanded");
        refs.overlay.classList.toggle("is-expanded", expanded);
        document.body.classList.toggle("oddi-document-side-panel-expanded", expanded);
        refs.fullscreen.setAttribute("aria-label", expanded ? "Restore editor size" : "Expand editor");
        refs.fullscreen.title = expanded ? "Restore editor size" : "Expand editor";
        setTimeout(() => window.dispatchEvent(new Event("resize")), 40);
    }

    function updateUndoRedoState() {
        if (!refs) return;
        const enabled = !!state?.editing;
        refs.undo.disabled = !enabled;
        refs.redo.disabled = !enabled;
    }

    function runEditCommand(command) {
        if (!state?.editing || !refs) return;
        refs.content.focus({preventScroll: true});
        document.execCommand(command);
        updateUndoRedoState();
    }

    async function saveOrEdit() {
        if (!state || state.generating) return;
        if (!state.editing) {
            refs.savedHtml = refs.content.innerHTML;
            state.editing = true;
            refs.content.contentEditable = "true";
            refs.content.classList.add("is-editing");
            refs.edit.textContent = "Save changes";
            refs.cancel.hidden = false;
            setStatus("Edit the document directly, then save your changes.");
            setSavedLabel("Unsaved edits");
            updateUndoRedoState();
            refs.content.focus({preventScroll: true});
            return;
        }

        const markdown = String(state.serializeMarkdown?.(refs.content) || "").trim();
        if (!markdown) {
            setStatus("Document content cannot be empty.", true);
            return;
        }
        refs.edit.disabled = true;
        refs.cancel.disabled = true;
        setStatus("Saving changes…");
        setSavedLabel("Saving…");
        try {
            const saved = await state.onSave?.({markdown, title: state.title});
            if (saved === false) throw new Error("Save failed. Your edits are still here; try again.");
            state.markdown = markdown;
            if (state.renderMarkdown) {
                refs.content.innerHTML = state.renderMarkdown(markdown);
                state.enhance?.(refs.content);
            }
            refs.savedHtml = refs.content.innerHTML;
            leaveEditMode();
            setStatus(`${savedLabel()}.`);
            setSavedLabel(savedLabel());
        } catch (error) {
            setStatus(error?.message || "Save failed. Your edits are still here; try again.", true);
            setSavedLabel("Not saved", true);
        } finally {
            refs.edit.disabled = false;
            refs.cancel.disabled = false;
        }
    }

    function leaveEditMode() {
        if (!refs || !state) return;
        state.editing = false;
        refs.content.contentEditable = "false";
        refs.content.classList.remove("is-editing");
        refs.edit.textContent = "Edit";
        refs.cancel.hidden = true;
        updateUndoRedoState();
    }

    function setGenerating(generating) {
        if (!refs || !state) return;
        state.generating = !!generating;
        refs.download.disabled = state.generating;
        refs.edit.disabled = state.generating;
        refs.copy.disabled = state.generating;
        refs.menu.querySelectorAll("[data-document-format]").forEach(button => {
            button.disabled = state.generating;
        });
        if (!state.generating && state.editing) leaveEditMode();
    }

    function open(options = {}) {
        ensureWorkspace();
        const documentKey = String(options.documentKey || options.title || "document");
        if (!refs.overlay.hidden && state?.documentKey === documentKey) {
            if (options.opener) refs.opener = options.opener;
            if (!state.editing && typeof options.markdown === "string") {
                state.title = String(options.title || state.title || "Document draft").trim() || "Document draft";
                state.renderMarkdown = options.renderMarkdown || state.renderMarkdown;
                state.enhance = options.enhance || state.enhance;
                state.serializeMarkdown = options.serializeMarkdown || state.serializeMarkdown;
                state.onSave = options.onSave || state.onSave;
                state.createPdfBlob = options.createPdfBlob || state.createPdfBlob;
                state.createDocxBlob = options.createDocxBlob || state.createDocxBlob;
                state.savedLabel = options.savedLabel || state.savedLabel || "Saved to this chat";
                refs.title.textContent = state.title;
                update(options.markdown, {status: options.status || "Ready to edit or download."});
            }
            if (options.focus !== false) refs.content.focus({preventScroll: true});
            return true;
        }
        if (state?.editing) {
            setStatus("Save or cancel your current document edits before opening another document.", true);
            return false;
        }

        state = {
            documentKey,
            title: String(options.title || "Document draft").trim() || "Document draft",
            markdown: "",
            renderMarkdown: options.renderMarkdown,
            enhance: options.enhance,
            serializeMarkdown: options.serializeMarkdown,
            onSave: options.onSave,
            createPdfBlob: options.createPdfBlob,
            createDocxBlob: options.createDocxBlob,
            savedLabel: options.savedLabel || "Saved to this chat",
            generating: false,
            editing: false
        };
        refs.opener = options.opener || refs.opener;
        refs.title.textContent = state.title;
        refs.content.contentEditable = "false";
        refs.content.classList.remove("is-editing");
        refs.content.innerHTML = "";
        refs.savedHtml = "";
        refs.edit.textContent = "Edit";
        refs.cancel.hidden = true;
        refs.fullscreen.setAttribute("aria-label", "Expand editor");
        refs.fullscreen.title = "Expand editor";
        refs.overlay.classList.add("is-docked");
        refs.overlay.classList.remove("is-expanded");
        refs.overlay.hidden = false;
        refs.overlay.setAttribute("aria-hidden", "false");
        document.body.classList.add("oddi-document-side-panel-open");
        document.body.classList.remove("oddi-document-side-panel-expanded");
        closeDownloadMenu();
        setSavedLabel(savedLabel());
        if (typeof options.markdown === "string") {
            update(options.markdown, {status: options.status || "Ready to edit or download."});
        } else {
            setGenerating(!!options.generating);
            setStatus(options.status || "Preparing your document…", !!options.error);
        }
        if (options.focus !== false) refs.content.focus({preventScroll: true});
        setTimeout(() => window.dispatchEvent(new Event("resize")), 40);
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
        refs.savedHtml = refs.content.innerHTML;
        setSavedLabel(savedLabel());
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

    function plainTextFromMarkdown(markdown) {
        return String(markdown || "")
            .replace(/^#{1,6}\s+/gm, "")
            .replace(/^\s*[-*+]\s+/gm, match => `${match.match(/^\s*/)[0]}• `)
            .replace(/\*\*(.*?)\*\*/g, "$1")
            .replace(/\*([^*]+)\*/g, "$1")
            .replace(/`([^`]+)`/g, "$1")
            .replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, "$1 — $2")
            .replace(/^[-=_]{3,}$/gm, "")
            .trim();
    }

    function escapeRtf(text) {
        let output = "";
        for (let index = 0; index < text.length; index += 1) {
            const character = text[index];
            const code = text.charCodeAt(index);
            if (character === "\\" || character === "{" || character === "}") output += `\\${character}`;
            else if (character === "\n") output += "\\par\n";
            else if (character === "\r") continue;
            else if (code < 128) output += character;
            else output += `\\u${code > 32767 ? code - 65536 : code}?`;
        }
        return output;
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

    async function copyCurrentDocument() {
        if (!state) return;
        const markdown = String(state.serializeMarkdown?.(refs.content) || state.markdown || "");
        const html = `<article>${refs.content.innerHTML}</article>`;
        try {
            if (navigator.clipboard?.write && window.ClipboardItem) {
                await navigator.clipboard.write([new ClipboardItem({
                    "text/html": new Blob([html], {type: "text/html"}),
                    "text/plain": new Blob([plainTextFromMarkdown(markdown)], {type: "text/plain;charset=utf-8"})
                })]);
            } else if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(plainTextFromMarkdown(markdown));
            } else {
                const area = document.createElement("textarea");
                area.value = plainTextFromMarkdown(markdown);
                document.body.appendChild(area);
                area.select();
                document.execCommand("copy");
                area.remove();
            }
            setStatus("Document copied.");
        } catch (_) {
            setStatus("Copy is unavailable in this browser.", true);
        }
    }

    async function downloadCurrentDocument(format = "pdf") {
        if (!state || state.generating) return;
        const markdown = String(state.serializeMarkdown?.(refs.content) || state.markdown || "").trim();
        if (!markdown) {
            setStatus("There is no document content to download yet.", true);
            return;
        }
        refs.download.disabled = true;
        setStatus(`Preparing ${formatLabels[format] || "file"}…`);
        try {
            const title = sanitizeFilename(state.title);
            const firstHeading = refs.content.querySelector(":scope > h1");
            const titleAlreadyPresent = !!firstHeading && String(firstHeading.textContent || "").trim().toLowerCase().includes(state.title.toLowerCase());
            const titleMarkup = titleAlreadyPresent ? "" : `<h1>${escapeHtml(state.title)}</h1>`;
            const markdownWithTitle = titleAlreadyPresent ? markdown : `# ${state.title}\n\n${markdown}`;
            const html = `<!doctype html><html><head><meta charset="utf-8"><title>${escapeHtml(state.title)}</title><style>body{max-width:850px;margin:36px auto;padding:0 28px;color:#111;font:14px/1.6 Arial,sans-serif}h1,h2,h3,h4{line-height:1.25;margin:1.1em 0 .4em}p{margin:.55em 0 1em}ul,ol{padding-left:26px}table{width:100%;border-collapse:collapse;margin:16px 0}th,td{border:1px solid #999;padding:7px 9px;text-align:left}blockquote{border-left:3px solid #888;padding-left:14px;color:#444}pre{white-space:pre-wrap;background:#f5f5f5;padding:12px}code{font-family:Consolas,monospace}</style></head><body><article>${titleMarkup}${refs.content.innerHTML}</article></body></html>`;
            const plainText = plainTextFromMarkdown(markdownWithTitle);
            let blob;
            if (format === "pdf") {
                if (typeof state.createPdfBlob !== "function") throw new Error("PDF export is unavailable right now.");
                const exportRoot = document.createElement("article");
                exportRoot.innerHTML = `${titleMarkup}${refs.content.innerHTML}`;
                blob = await state.createPdfBlob(exportRoot);
            } else if (format === "docx") {
                if (typeof state.createDocxBlob !== "function") throw new Error("Word export is unavailable right now.");
                blob = await state.createDocxBlob(html);
            } else if (format === "html") {
                blob = new Blob([html], {type: "text/html;charset=utf-8"});
            } else if (format === "md") {
                blob = new Blob([markdownWithTitle], {type: "text/markdown;charset=utf-8"});
            } else if (format === "rtf") {
                const content = `{\\rtf1\\ansi\\deff0{\\fonttbl{\\f0 Arial;}}\\viewkind4\\uc1\\pard\\f0\\fs22 ${escapeRtf(plainText)}}`;
                blob = new Blob([content], {type: "application/rtf;charset=utf-8"});
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
            } else {
                blob = new Blob([plainText], {type: "text/plain;charset=utf-8"});
            }
            if (!(blob instanceof Blob) || !blob.size) throw new Error("The exported file was empty. Your document is still available here; try again.");
            saveBlob(blob, `${title}.${format}`);
            setStatus(`${formatLabels[format] || "File"} downloaded.`);
        } catch (error) {
            console.error("Document export failed:", error);
            setStatus(error?.message || "Download failed. Your document is still available here; try again.", true);
        } finally {
            refs.download.disabled = false;
        }
    }

    function closeWorkspace() {
        if (!refs || refs.overlay.hidden) return true;
        if (state?.editing) {
            setStatus("Save or cancel your edits before closing the editor.", true);
            return false;
        }
        closeDownloadMenu();
        refs.overlay.hidden = true;
        refs.overlay.setAttribute("aria-hidden", "true");
        refs.overlay.classList.remove("is-expanded");
        document.body.classList.remove("oddi-document-side-panel-open", "oddi-document-side-panel-expanded");
        const opener = refs.opener;
        refs.opener = null;
        if (opener?.isConnected) opener.focus({preventScroll: true});
        setTimeout(() => window.dispatchEvent(new Event("resize")), 40);
        return true;
    }

    window.OddiDocumentWorkspace = {
        open,
        update,
        close: closeWorkspace,
        download: downloadCurrentDocument,
        isEditing: () => !!state?.editing,
        notify: (message, isError = false) => setStatus(message, isError),
        isOpen: () => !!refs && !refs.overlay.hidden,
        activeDocumentKey: () => String(state?.documentKey || "")
    };
})();
