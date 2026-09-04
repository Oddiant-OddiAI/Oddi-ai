/* 
   FILE UPLOAD
 */

const attachBtn =
    document.getElementById(
        "attach-btn"
    );

const fileInput =
    document.getElementById(
        "fileInput"
    );

const attachmentToggle =
    document.getElementById(
        "attachmentToggle"
    );

const attachmentArrow =
    document.getElementById(
        "attachmentArrow"
    );

const attachmentName =
    document.getElementById(
        "attachmentName"
    );

const attachmentList =
    document.getElementById(
        "attachmentList"
    );

attachBtn.onclick = () => {
    fileInput.click();
};

fileInput.onchange = () => {

    if (fileInput.files.length === 0) {
        return;
    }

    const newFiles =
        Array.from(fileInput.files);

    // Add new files without deleting previous files
    newFiles.forEach(file => {

        const alreadyExists =
            selectedFiles.some(existing =>
                existing.name === file.name &&
                existing.size === file.size &&
                existing.lastModified === file.lastModified
            );

        if (!alreadyExists) {
            selectedFiles.push(file);
        }
    });

    // Reset input so the same file can be selected again later
    fileInput.value = "";

    updateAttachmentPreview();

    if (
        input.value
            .trim()
            .toLowerCase() ===
        "analyze my resume"
    ) {
        sendMessage(
            "Analyze my resume"
        );
    }
};

function updateAttachmentPreview() {

    if (!selectedFiles.length) {

        attachmentPreview.style.display =
            "none";

        attachmentName.textContent = "";

        attachmentList.innerHTML = "";

        attachmentList.style.display =
            "none";

        attachmentArrow.textContent = "▴";

        attachmentToggle.setAttribute(
            "aria-expanded",
            "false"
        );

        return;
    }

    // Header text
    attachmentName.textContent =
        selectedFiles.length === 1
            ? "📎 " + selectedFiles[0].name
            : "📎 " +
              selectedFiles.length +
              " files attached";

    // Show preview
    attachmentPreview.style.display =
        "flex";

    // Clear old list
    attachmentList.innerHTML = "";

    // Create one row for every file
    selectedFiles.forEach((file, index) => {

        const row =
            document.createElement("div");

        row.className =
            "attachment-item";

        const name =
            document.createElement("span");

        name.className =
            "attachment-file-name";

        name.textContent =
            "📎 " + file.name;

        const removeBtn =
            document.createElement("button");

        removeBtn.type = "button";

        removeBtn.className =
            "attachment-file-remove";

        removeBtn.textContent = "✖";

        removeBtn.title =
            "Remove this file";

        removeBtn.onclick = event => {

            event.stopPropagation();

            selectedFiles.splice(
                index,
                1
            );

            updateAttachmentPreview();
        };

        row.appendChild(name);

        row.appendChild(removeBtn);

        attachmentList.appendChild(row);
    });
}

attachmentToggle.onclick = () => {

    const isOpen =
        attachmentToggle.getAttribute(
            "aria-expanded"
        ) === "true";

    if (isOpen) {

        attachmentList.style.display =
            "none";

        attachmentArrow.textContent =
            "▴";

        attachmentToggle.setAttribute(
            "aria-expanded",
            "false"
        );

    } else {

        attachmentList.style.display =
            "flex";

        attachmentArrow.textContent = "▾";

        attachmentToggle.setAttribute(
            "aria-expanded",
            "true"
        );
    }
};

/* 
   CTRL + V / CLIPBOARD SCREENSHOT PASTE
 */
document.addEventListener("paste", event => {
    const clipboardItems = Array.from(event.clipboardData?.items || []);
    const imageItems = clipboardItems.filter(item =>
        item.kind === "file" && item.type.startsWith("image/")
    );

    if (!imageItems.length) return;

    event.preventDefault();

    imageItems.forEach((item, index) => {
        const blob = item.getAsFile();
        if (!blob) return;

        const extension = blob.type.split("/")[1] || "png";
        const file = new File(
            [blob],
            `Screenshot-${new Date().toISOString().replace(/[:.]/g, "-")}-${index + 1}.${extension}`,
            { type: blob.type, lastModified: Date.now() }
        );

        selectedFiles.push(file);
    });

    updateAttachmentPreview();
});

removeAttachment.onclick = () => {

    fileInput.value = "";

    selectedFiles = [];

    updateAttachmentPreview();
};
