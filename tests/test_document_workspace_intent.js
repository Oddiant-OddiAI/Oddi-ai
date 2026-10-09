const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(
    path.join(__dirname, "..", "static", "oddi-document-intent.js"),
    "utf8"
);
const workspaceSource = fs.readFileSync(
    path.join(__dirname, "..", "static", "oddi-document-workspace.js"),
    "utf8"
);
const context = {window: {}};
vm.runInNewContext(source, context, {filename: "oddi-document-intent.js"});
const intent = context.window.OddiDocumentIntent;

test("routes common downloadable document requests into the editor", () => {
    const prompts = [
        "Create a professional resume for a software engineer.",
        "Write a cover letter for a frontend developer.",
        "Create a long business proposal.",
        "Make a downloadable report.",
        "Create a document with headings, bold text, bullets and tables.",
        "Give me this as a PDF.",
        "Create a huge document.",
        "Write detailed notes about my project.",
        "Create a table from this data."
    ];
    for (const prompt of prompts) assert.equal(intent.isDocumentGenerationIntent(prompt), true, prompt);
});

test("ordinary information and coding questions remain in chat", () => {
    assert.equal(intent.isDocumentGenerationIntent("What is 2+2?"), false);
    assert.equal(intent.isDocumentGenerationIntent("What is the capital of France?"), false);
    assert.equal(intent.isDocumentGenerationIntent("Explain recursion."), false);
    assert.equal(intent.isDocumentGenerationIntent("Write a JavaScript function to sort numbers."), false);
    assert.equal(intent.isDocumentGenerationIntent("Explain how to write a resume."), false);
    assert.equal(intent.isDocumentGenerationIntent("How do I export a PDF?"), false);
    assert.equal(intent.isDocumentGenerationIntent("What formats can I export as PDF?"), false);
    assert.equal(intent.isDocumentGenerationIntent("How to write a cover letter?"), false);
});

test("export follow-ups select a local format without turning new document requests into exports", () => {
    assert.equal(intent.isDocumentExportFollowup("Give me this as a PDF."), true);
    assert.equal(intent.isDocumentExportFollowup("Export that as a Word document."), true);
    assert.equal(intent.isDocumentExportFollowup("Write a new cover letter as a PDF."), false);
    assert.equal(intent.documentFormatFromPrompt("Please save this as a Word file."), "docx");
    assert.equal(intent.documentFormatFromPrompt("Export this as HTML."), "html");
    assert.equal(intent.documentFormatFromPrompt("Give me a Markdown copy."), "md");
    assert.equal(intent.documentFormatFromPrompt("Give me plain text."), "txt");
    assert.equal(intent.documentFormatFromPrompt("Give me this as a PNG."), "png");
    assert.equal(intent.documentFormatFromPrompt("Give me this as a PDF."), "pdf");
});

test("document context is compact unless a follow-up asks to edit the source", () => {
    assert.equal(intent.shouldIncludeDocumentInModelHistory("What did you prepare?"), false);
    assert.equal(intent.shouldIncludeDocumentInModelHistory("Give me this as a PDF."), false);
    assert.equal(intent.shouldIncludeDocumentInModelHistory("Make the resume more detailed."), true);
    assert.equal(intent.shouldIncludeDocumentInModelHistory("Make it shorter."), true);
});

test("sequential document requests get independent titles and remain document requests", () => {
    const prompts = [
        ["Write a cover letter for a frontend developer.", "Cover Letter"],
        ["Create a business proposal for a mobile app.", "Business Proposal"],
        ["Prepare a report on quarterly sales.", "Report"]
    ];
    for (const [prompt, title] of prompts) {
        assert.equal(intent.isDocumentGenerationIntent(prompt), true);
        assert.equal(intent.documentTitleFromPrompt(prompt), title);
    }
});

test("the editor exposes all supported local export formats", () => {
    for (const format of ["pdf", "docx", "html", "txt", "md", "png"]) {
        assert.ok(workspaceSource.includes(`option value="${format}"`), `${format} is available in the selector`);
        assert.ok(workspaceSource.includes(`${format}:`), `${format} has a display label`);
    }
});
