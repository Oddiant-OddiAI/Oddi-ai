/* 
   CHAT EXPORT / SHARE
   Exports ONLY the currently selected conversation.
   The visible chat DOM is cloned so rendered KaTeX, tables and code
   formatting are preserved in HTML/print exports.
 */

const exportChatBtn = document.getElementById("exportChatBtn");
const exportChatMenu = document.getElementById("exportChatMenu");
const exportChatWrap = document.getElementById("exportChatWrap");

function getCurrentExportConversation() {
    if (currentConversation === null || currentConversation === undefined) {
        return null;
    }

    const conversation = conversations[currentConversation];
    if (!conversation || !Array.isArray(conversation.messages)) {
        return null;
    }

    if (!conversation.messages.length) {
        return null;
    }

    return conversation;
}

function closeExportMenu() {
    if (!exportChatMenu) return;
    exportChatMenu.classList.remove("show");
    exportChatMenu.setAttribute("aria-hidden", "true");
    exportChatBtn?.setAttribute("aria-expanded", "false");
}

function toggleExportMenu() {
    if (!exportChatMenu) return;

    const conversation = getCurrentExportConversation();
    if (!conversation) {
        alert("Open a chat with at least one message before exporting.");
        return;
    }

    const willShow = !exportChatMenu.classList.contains("show");
    exportChatMenu.classList.toggle("show", willShow);
    exportChatMenu.setAttribute("aria-hidden", String(!willShow));
    exportChatBtn?.setAttribute("aria-expanded", String(willShow));
}

function sanitizeExportFilename(value) {
    const name = String(value || "Oddi Chat")
        .replace(/[<>:"/\\|?*\x00-\x1F]/g, "")
        .replace(/\s+/g, " ")
        .trim();

    return (name || "Oddi Chat").slice(0, 90);
}

function downloadExportFile(content, filename, type) {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
}

function getExportClone() {
    const source = document.getElementById("chatbox");
    if (!source) return null;

    const clone = source.cloneNode(true);

    // IMPORTANT: do not keep the live #chatbox id. The live chatbox has
    // viewport/scroll constraints which made the PDF canvas capture only a
    // blank page. The export copy must behave like a normal flowing document.
    clone.removeAttribute("id");
    clone.classList.add("oddi-export-chat-clone");

    clone.querySelectorAll(".user-actions, .bot-actions, .message-sound-btn, .message-action-btn")
        .forEach(node => node.remove());

    clone.querySelectorAll(".ai-code-copy").forEach(node => node.remove());
    clone.querySelectorAll("button").forEach(node => node.remove());

    return clone;
}

function buildExportDocument(conversation, clone) {
    const title = escapeHtml(conversation.title || "Oddi Chat");
    const exportedAt = new Date().toLocaleString();
    const bodyHtml = clone?.innerHTML || "";

    return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title} — Oddi AI</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.22/dist/katex.min.css">
<style>
body{margin:0;padding:32px;background:#fff;color:#111;font-family:Arial,Helvetica,sans-serif;line-height:1.6}
.export-page{max-width:900px;margin:0 auto}.export-title{margin:0 0 4px;font-size:26px}.export-meta{margin:0 0 26px;color:#666;font-size:12px}
.user-message,.bot-message{margin:0 0 20px;padding:14px;border:1px solid #ddd;border-radius:10px;page-break-inside:avoid;break-inside:avoid}
.bot-header,.user-message-header{font-weight:700;margin-bottom:8px}.user-actions,.bot-actions,.message-sound-btn,.message-action-btn,.ai-code-copy{display:none!important}
.katex-display{overflow-x:auto;overflow-y:hidden;margin:1em 0}pre{padding:12px;background:#f5f5f5;border-radius:8px;white-space:pre-wrap;overflow-wrap:anywhere}code{font-family:Consolas,monospace}table{width:100%;border-collapse:collapse}th,td{border:1px solid #bbb;padding:7px;text-align:left}th{background:#f1f1f1}img{max-width:100%}
</style>
</head>
<body><main class="export-page">
<h1 class="export-title">${title}</h1>
<p class="export-meta">Exported from Oddi AI · ${escapeHtml(exportedAt)}</p>
${bodyHtml}
</main></body></html>`;
}

function buildPlainTextExport(conversation) {
    const lines = [];
    lines.push(conversation.title || "Oddi Chat");
    lines.push("=".repeat(Math.min(80, Math.max(10, String(conversation.title || "Oddi Chat").length))));
    lines.push("");

    conversation.messages.forEach((msg, index) => {
        const role = msg.role === "user" ? "You" : "Oddi AI";
        lines.push(`${role}:`);
        lines.push(String(msg.text || "").trim());
        if (Array.isArray(msg.files) && msg.files.length) {
            lines.push(`Attachments: ${msg.files.join(", ")}`);
        }
        if (Array.isArray(msg.fileRefs) && msg.fileRefs.length) {
            lines.push(`Attachments: ${msg.fileRefs.map(file => file.name).join(", ")}`);
        }
        if (index < conversation.messages.length - 1) lines.push("", "---", "");
    });

    return lines.join("\n");
}

function exportCurrentChatAsHtml() {
    const conversation = getCurrentExportConversation();
    if (!conversation) return;

    const clone = getExportClone();
    if (!clone) return;

    const html = buildExportDocument(conversation, clone);
    downloadExportFile(
        html,
        `${sanitizeExportFilename(conversation.title)}.html`,
        "text/html;charset=utf-8"
    );
}

function exportCurrentChatAsTxt() {
    const conversation = getCurrentExportConversation();
    if (!conversation) return;

    downloadExportFile(
        buildPlainTextExport(conversation),
        `${sanitizeExportFilename(conversation.title)}.txt`,
        "text/plain;charset=utf-8"
    );
}

async function createCurrentChatPdfBlob() {
    const conversation = getCurrentExportConversation();
    if (!conversation) return null;

    const JsPDF = window.jspdf?.jsPDF;
    const html2canvasFn = window.html2canvas;
    if (typeof JsPDF !== "function" || typeof html2canvasFn !== "function") {
        throw new Error("PDF export libraries are unavailable.");
    }

    const clone = getExportClone();
    if (!clone) return null;

    const root = document.createElement("div");
    root.className = "oddi-export-pdf-root";
    root.innerHTML = `
        <h1 class="export-chat-title">${escapeHtml(conversation.title || "Oddi Chat")}</h1>
        <p class="export-chat-meta">Exported from Oddi AI · ${escapeHtml(new Date().toLocaleString())}</p>
    `;
    root.appendChild(clone);

    // Render in a real, viewport-sized document so html2canvas gets the same
    // layout a user sees, but keep the export layer visually unobtrusive.
    Object.assign(root.style, {
        position: "fixed",
        left: "0",
        top: "0",
        width: "794px",
        height: "auto",
        minHeight: "1123px",
        maxHeight: "none",
        overflow: "visible",
        zIndex: "2147483647",
        pointerEvents: "none",
        visibility: "visible",
        opacity: "1",
        background: "#ffffff",
        color: "#111111",
        boxSizing: "border-box"
    });

    document.body.appendChild(root);

    try {
        const exportClone = root.querySelector(".oddi-export-chat-clone");
        if (exportClone) {
            Object.assign(exportClone.style, {
                width: "100%",
                maxWidth: "none",
                height: "auto",
                minHeight: "0",
                maxHeight: "none",
                overflow: "visible",
                position: "static",
                display: "block",
                transform: "none",
                boxSizing: "border-box"
            });

            exportClone.querySelectorAll("*").forEach(node => {
                const el = /** @type {HTMLElement} */ (node);
                el.style.maxHeight = "none";
                el.style.transform = "none";
                if (el.tagName !== "PRE" && getComputedStyle(el).overflow !== "visible") {
                    el.style.overflow = "visible";
                }
            });
        }

        if (document.fonts?.ready) await document.fonts.ready;
        const images = Array.from(root.querySelectorAll("img"));
        await Promise.all(images.map(img => {
            if (img.complete) return Promise.resolve();
            return new Promise(resolve => {
                img.addEventListener("load", resolve, { once: true });
                img.addEventListener("error", resolve, { once: true });
            });
        }));
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));

        const width = Math.max(794, Math.ceil(root.scrollWidth || root.getBoundingClientRect().width));
        const height = Math.max(1123, Math.ceil(root.scrollHeight || root.getBoundingClientRect().height));
        root.style.width = `${width}px`;
        root.style.height = `${height}px`;

        // html2canvas is called directly instead of html2pdf's Worker/output
        // pipeline. This avoids the blank-PDF failure seen when outputPdf()
        // was fed the live app's constrained chat DOM.
        let scale = Math.min(2, Math.max(1.5, window.devicePixelRatio || 1.5));
        const maxCanvasDimension = 30000;
        if (height * scale > maxCanvasDimension) scale = maxCanvasDimension / height;
        scale = Math.max(1, scale);

        const canvas = await html2canvasFn(root, {
            scale,
            useCORS: true,
            allowTaint: false,
            backgroundColor: "#ffffff",
            logging: false,
            width,
            height,
            windowWidth: width,
            windowHeight: height,
            scrollX: 0,
            scrollY: 0
        });

        if (!canvas || canvas.width < 2 || canvas.height < 2) {
            throw new Error("The PDF canvas was empty.");
        }

        const pdf = new JsPDF({ unit: "pt", format: "a4", orientation: "portrait", compress: true });
        const pageWidth = pdf.internal.pageSize.getWidth();
        const pageHeight = pdf.internal.pageSize.getHeight();
        const margin = 28;
        const contentWidth = pageWidth - margin * 2;
        const contentHeight = pageHeight - margin * 2;
        const pxToPt = contentWidth / canvas.width;
        const sliceHeightPx = Math.max(1, Math.floor(contentHeight / pxToPt));

        let offsetY = 0;
        let pageIndex = 0;
        while (offsetY < canvas.height) {
            const sliceHeight = Math.min(sliceHeightPx, canvas.height - offsetY);
            const slice = document.createElement("canvas");
            slice.width = canvas.width;
            slice.height = sliceHeight;
            const ctx = slice.getContext("2d", { alpha: false });
            if (!ctx) throw new Error("Could not create PDF page canvas.");
            ctx.fillStyle = "#ffffff";
            ctx.fillRect(0, 0, slice.width, slice.height);
            ctx.drawImage(canvas, 0, offsetY, canvas.width, sliceHeight, 0, 0, canvas.width, sliceHeight);

            if (pageIndex > 0) pdf.addPage();
            pdf.addImage(
                slice.toDataURL("image/jpeg", 0.96),
                "JPEG",
                margin,
                margin,
                contentWidth,
                sliceHeight * pxToPt,
                undefined,
                "FAST"
            );

            offsetY += sliceHeight;
            pageIndex++;
        }

        return pdf.output("blob");
    } finally {
        root.remove();
    }
}
function downloadPdfBlob(blob, conversation) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${sanitizeExportFilename(conversation.title)}.pdf`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
}

async function exportCurrentChatAsPdf() {
    const conversation = getCurrentExportConversation();
    if (!conversation) return;

    try {
        const blob = await createCurrentChatPdfBlob();
        if (!blob) return;
        downloadPdfBlob(blob, conversation);
    } catch (error) {
        console.error("Could not export PDF:", error);
        alert("Could not create the PDF. Please try again.");
    }
}
function buildDocxHtml(conversation, clone) {
    const title = escapeHtml(conversation.title || "Oddi Chat");
    return `<!doctype html><html><head><meta charset="utf-8"><style>
        body{font-family:Arial,sans-serif;color:#111;line-height:1.5}h1{font-size:24pt}h2,h3{font-size:15pt}table{border-collapse:collapse;width:100%}th,td{border:1px solid #999;padding:6px}pre{background:#f3f3f3;padding:8px}code{font-family:Consolas,monospace}.katex-display{text-align:center;margin:12px 0}
    </style></head><body><h1>${title}</h1><p>Exported from Oddi AI · ${escapeHtml(new Date().toLocaleString())}</p>${clone?.innerHTML || ""}</body></html>`;
}

function exportCurrentChatAsDocx() {
    const conversation = getCurrentExportConversation();
    if (!conversation) return;
    const clone = getExportClone();
    if (!clone) return;

    if (!window.htmlDocx || typeof window.htmlDocx.asBlob !== "function") {
        alert("Word export is unavailable right now. Please check your internet connection and try again.");
        return;
    }

    try {
        const blob = window.htmlDocx.asBlob(buildDocxHtml(conversation, clone));
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `${sanitizeExportFilename(conversation.title)}.docx`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 30000);
    } catch (error) {
        console.error("Could not export DOCX:", error);
        alert("Could not create the Word document.");
    }
}

async function exportCurrentChatAsPptx() {
    const conversation = getCurrentExportConversation();
    if (!conversation) return;

    if (typeof window.PptxGenJS !== "function") {
        alert("PowerPoint export is unavailable right now. Please check your internet connection and try again.");
        return;
    }

    try {
        const pptx = new window.PptxGenJS();
        pptx.layout = "LAYOUT_WIDE";
        pptx.author = "Oddi AI";
        pptx.subject = conversation.title || "Oddi Chat";
        pptx.title = conversation.title || "Oddi Chat";
        pptx.company = "Oddi AI";
        pptx.lang = "en-US";

        const messages = conversation.messages || [];
        const chunks = [];
        const maxChars = 2600;
        messages.forEach(msg => {
            const role = msg.role === "user" ? "You" : "Oddi AI";
            const raw = String(msg.text || msg.content || "").trim();
            if (!raw) return;
            for (let i = 0; i < raw.length; i += maxChars) {
                chunks.push({ role, text: raw.slice(i, i + maxChars) });
            }
        });

        if (!chunks.length) chunks.push({ role: "Oddi AI", text: "No messages." });

        const titleSlide = pptx.addSlide();
        titleSlide.addText(conversation.title || "Oddi Chat", { x:0.6, y:2.2, w:12.1, h:0.7, fontSize:28, bold:true, color:"111111", align:"center" });
        titleSlide.addText(`Exported from Oddi AI · ${new Date().toLocaleString()}`, { x:1.2, y:3.05, w:11, h:0.35, fontSize:12, color:"666666", align:"center" });

        chunks.forEach((chunk, index) => {
            const slide = pptx.addSlide();
            slide.addText(chunk.role, { x:0.55, y:0.35, w:2.0, h:0.35, fontSize:17, bold:true, color:"111111" });
            slide.addText(chunk.text, { x:0.55, y:0.9, w:12.1, h:5.7, fontSize:14, color:"222222", breakLine:false, valign:"top", margin:0.08, fit:"shrink" });
            slide.addText(`${index + 1} / ${chunks.length}`, { x:11.7, y:7.0, w:1, h:0.2, fontSize:8, color:"777777", align:"right" });
        });

        await pptx.writeFile({ fileName: `${sanitizeExportFilename(conversation.title)}.pptx` });
    } catch (error) {
        console.error("Could not export PPTX:", error);
        alert("Could not create the PowerPoint file.");
    }
}

function openShareModal() {
    const conversation = getCurrentExportConversation();
    if (!conversation) return;
    const modal = document.getElementById("oddiShareModal");
    if (!modal) return;
    modal.classList.add("show");
    modal.setAttribute("aria-hidden", "false");
}

function closeShareModal() {
    const modal = document.getElementById("oddiShareModal");
    if (!modal) return;
    modal.classList.remove("show");
    modal.setAttribute("aria-hidden", "true");
}

async function shareCurrentChat() {
    const conversation = getCurrentExportConversation();
    if (!conversation) return;
    const select = document.getElementById("oddiShareFormat");
    if (select) select.value = "pdf";
    openShareModal();
}

async function createShareFile(format, conversation) {
    const safeName = sanitizeExportFilename(conversation.title);

    if (format === "pdf") {
        const blob = await createCurrentChatPdfBlob();
        return blob ? new File([blob], `${safeName}.pdf`, { type: "application/pdf" }) : null;
    }

    if (format === "html") {
        const clone = getExportClone();
        if (!clone) return null;
        return new File([buildExportDocument(conversation, clone)], `${safeName}.html`, { type: "text/html" });
    }

    if (format === "txt") {
        return new File([buildPlainTextExport(conversation)], `${safeName}.txt`, { type: "text/plain" });
    }

    if (format === "docx") {
        if (!window.htmlDocx || typeof window.htmlDocx.asBlob !== "function") throw new Error("Word export is unavailable.");
        const clone = getExportClone();
        if (!clone) return null;
        const blob = window.htmlDocx.asBlob(buildDocxHtml(conversation, clone));
        return new File([blob], `${safeName}.docx`, { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" });
    }

    if (format === "pptx") {
        if (typeof window.PptxGenJS !== "function") throw new Error("PowerPoint export is unavailable.");
        const pptx = new window.PptxGenJS();
        pptx.layout = "LAYOUT_WIDE";
        pptx.author = "Oddi AI";
        pptx.subject = conversation.title || "Oddi Chat";
        pptx.title = conversation.title || "Oddi Chat";
        pptx.company = "Oddi AI";
        pptx.lang = "en-US";
        const messages = conversation.messages || [];
        const chunks = [];
        const maxChars = 2600;
        messages.forEach(msg => {
            const role = msg.role === "user" ? "You" : "Oddi AI";
            const raw = String(msg.text || msg.content || "").trim();
            if (!raw) return;
            for (let i = 0; i < raw.length; i += maxChars) chunks.push({ role, text: raw.slice(i, i + maxChars) });
        });
        if (!chunks.length) chunks.push({ role: "Oddi AI", text: "No messages." });
        const titleSlide = pptx.addSlide();
        titleSlide.addText(conversation.title || "Oddi Chat", { x:0.6, y:2.2, w:12.1, h:0.7, fontSize:28, bold:true, color:"111111", align:"center" });
        titleSlide.addText(`Exported from Oddi AI · ${new Date().toLocaleString()}`, { x:1.2, y:3.05, w:11, h:0.35, fontSize:12, color:"666666", align:"center" });
        chunks.forEach(chunk => {
            const slide = pptx.addSlide();
            slide.addText(chunk.role, { x:0.55, y:0.35, w:2.0, h:0.35, fontSize:17, bold:true, color:"111111" });
            slide.addText(chunk.text, { x:0.55, y:0.9, w:12.1, h:5.7, fontSize:14, color:"222222", breakLine:false, valign:"top", margin:0.05, fit:"shrink" });
        });
        const data = await pptx.write({ outputType: "blob" });
        return new File([data], `${safeName}.pptx`, { type: "application/vnd.openxmlformats-officedocument.presentationml.presentation" });
    }

    return null;
}

function getSelectedShareFormat() {
    return document.getElementById("oddiShareFormat")?.value || "pdf";
}

async function handleShareTarget(target) {
    const conversation = getCurrentExportConversation();
    if (!conversation) return;
    const format = getSelectedShareFormat();
    const text = buildPlainTextExport(conversation);
    const title = conversation.title || "Oddi Chat";

    if (target === "copy") {
        try {
            await navigator.clipboard.writeText(text);
            closeShareModal();
            alert("Chat copied to clipboard.");
        } catch (error) {
            alert("Could not copy the chat.");
        }
        return;
    }

    if (target === "whatsapp") {
        try {
            const file = await createShareFile(format, conversation);
            // On browsers with a real file-share API (typically mobile), use
            // it so the selected PDF/DOCX/etc. can be attached to WhatsApp.
            if (file && navigator.canShare && navigator.canShare({ files: [file] }) && navigator.share) {
                await navigator.share({ title, text: `Shared from Oddi AI: ${title}`, files: [file] });
                closeShareModal();
                return;
            }

            // WhatsApp Web does not expose a browser API that lets a website
            // silently attach a local File to a chat. Download the selected
            // file first, then open WhatsApp Web with the chat text so the user
            // can attach the downloaded file normally.
            if (file) {
                downloadExportFile(await file.arrayBuffer(), file.name, file.type);
                const url = `https://web.whatsapp.com/send?text=${encodeURIComponent(`Shared from Oddi AI: ${title}`)}`;
                window.open(url, "_blank", "noopener,noreferrer");
                closeShareModal();
                setTimeout(() => alert(`${file.name} was downloaded. In WhatsApp Web, open the chat and attach this file.`), 250);
                return;
            }
        } catch (error) {
            if (error?.name === "AbortError") return;
            console.error("WhatsApp sharing failed:", error);
        }

        const url = `https://web.whatsapp.com/send?text=${encodeURIComponent(text)}`;
        window.open(url, "_blank", "noopener,noreferrer");
        return;
    }

    if (target === "email") {
        const body = format === "txt" ? text : `${text}\n\n(Attachment sharing depends on your mail app.)`;
        const subject = encodeURIComponent(title);
        window.location.href = `mailto:?subject=${subject}&body=${encodeURIComponent(body)}`;
        return;
    }

    if (target === "more") {
        try {
            const file = await createShareFile(format, conversation);
            if (file && navigator.canShare && navigator.canShare({ files: [file] }) && navigator.share) {
                await navigator.share({ title, text: `Shared from Oddi AI: ${title}`, files: [file] });
                closeShareModal();
                return;
            }
            if (navigator.share) {
                await navigator.share({ title, text });
                closeShareModal();
                return;
            }
        } catch (error) {
            if (error?.name === "AbortError") return;
        }
        try {
            await navigator.clipboard.writeText(text);
            closeShareModal();
            alert("Your browser does not provide native share options here. The chat was copied so you can paste it into any app.");
        } catch (error) {
            alert("More sharing options are not available in this browser.");
        }
    }
}
async function copyCurrentChat() {
    const conversation = getCurrentExportConversation();
    if (!conversation) return;

    try {
        await navigator.clipboard.writeText(buildPlainTextExport(conversation));
        alert("Conversation copied to clipboard.");
    } catch (error) {
        console.error("Could not copy conversation:", error);
        alert("Could not copy the conversation.");
    }
}

exportChatBtn?.addEventListener("click", event => {
    event.stopPropagation();
    toggleExportMenu();
});

exportChatMenu?.addEventListener("click", async event => {
    const actionButton = event.target.closest("button[data-export-action]");
    if (!actionButton) return;

    const action = actionButton.dataset.exportAction;
    closeExportMenu();

    if (action === "pdf") await exportCurrentChatAsPdf();
    if (action === "docx") exportCurrentChatAsDocx();
    if (action === "pptx") await exportCurrentChatAsPptx();
    if (action === "html") exportCurrentChatAsHtml();
    if (action === "txt") exportCurrentChatAsTxt();
    if (action === "copy") await copyCurrentChat();
    if (action === "share") await shareCurrentChat();
});

document.getElementById("oddiShareClose")?.addEventListener("click", closeShareModal);
document.getElementById("oddiShareModal")?.addEventListener("click", event => {
    if (event.target.id === "oddiShareModal") closeShareModal();
    const button = event.target.closest("button[data-share-target]");
    if (button) handleShareTarget(button.dataset.shareTarget);
});

document.addEventListener("click", event => {
    if (exportChatWrap && !exportChatWrap.contains(event.target)) {
        closeExportMenu();
    }
});

document.addEventListener("keydown", event => {
    if (event.key === "Escape") {
        closeExportMenu();
        closeShareModal();
    }
});
