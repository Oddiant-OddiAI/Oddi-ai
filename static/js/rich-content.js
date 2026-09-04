/* 
   RICH CONTENT RENDERER
 */

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function prepareRichContent(source) {
    /*
     * IMPORTANT RENDERING RULE:
     * Markdown must NEVER see LaTeX delimiters first. Marked treats the
     * backslash in \[ and \( as an escape and removes it, which leaves raw
     * [ ... ] / ( ... ) in the final DOM. We therefore protect math first,
     * let Markdown render everything else, then restore math afterwards.
     */
    let text = String(source ?? "");
    const mathParts = [];

    const protectMath = value => {
        const key = `ODDIMATH${mathParts.length}X`;
        mathParts.push({ key, value });
        return key;
    };

    /* Code is protected while applying plain-text ^ / _ fallback, but is
       restored BEFORE marked parses so fenced code remains real code blocks. */
    const codeParts = [];
    text = text.replace(/```[\s\S]*?```/g, block => {
        const key = `ODDICODE${codeParts.length}X`;
        codeParts.push({ key, value: block });
        return key;
    });

    /* Standard display / inline delimiters. Longest delimiters first. */
    text = text.replace(/\$\$[\s\S]*?\$\$/g, protectMath);
    text = text.replace(/\\\[[\s\S]*?\\\]/g, protectMath);
    text = text.replace(/\\\([\s\S]*?\\\)/g, protectMath);

    /* Single-dollar inline math. */
    text = text.replace(
        /(^|[^\\])\$([^$\n]+?)\$/g,
        (whole, prefix, body) => `${prefix}${protectMath(`$${body}$`)}`
    );

    /*
     * Some backend/model paths emit a display equation as:
     *     [\boxed{...}]
     * or:
     *     [\begin{aligned} ... \end{aligned}]
     * Convert only standalone LaTeX-looking lines. Normal Markdown links are
     * not touched.
     */
    text = text.replace(
        /^\s*\[\s*((?:\\[a-zA-Z]+|[^\n])*?(?:\\frac|\\sqrt|\\boxed|\\begin|\\Delta|\\pm|\\le|\\ge|\^|_)[^\n]*?)\s*\]\s*$/gm,
        (whole, body) => protectMath(`\\[${body}\\]`)
    );

    /*
     * A frequent model output is bare LaTeX inside normal parentheses, e.g.
     * (x^{2}), (\\frac{x_{n+1}}{x_n}=r), or (\\Delta=b^2-4ac).
     * Turn only LaTeX-looking parenthesized expressions into inline math.
     */
    text = text.replace(
        /\(([^()\n]*(?:\\(?:frac|sqrt|times|Delta|pm|le|ge|neq|quad|text|boxed|begin|cdot)|\^\{|_\{|\^[A-Za-z0-9]|_[A-Za-z0-9])[^()\n]*)\)/g,
        (whole, body) => protectMath(`\\(${body}\\)`)
    );

    /* Plain-text fallback ONLY outside code/math. */
    text = text.replace(
        /\b([A-Za-z0-9])\^(\d{1,3})\b/g,
        "$1<sup>$2</sup>"
    );
    text = text.replace(
        /\b([A-Za-z])_(\d{1,3})\b/g,
        "$1<sub>$2</sub>"
    );

    codeParts.forEach(({ key, value }) => {
        text = text.split(key).join(value);
    });

    return { markdown: text, mathParts };
}

function restoreMathInHtml(html, mathParts) {
    let output = String(html ?? "");

    /*
     * This happens AFTER marked.parse(). Escaping HTML-sensitive characters
     * keeps model-produced LaTeX from becoming HTML while still leaving the
     * LaTeX delimiters visible to KaTeX in the DOM text nodes.
     */
    mathParts.forEach(({ key, value }) => {
        output = output.split(key).join(escapeHtml(value));
    });

    return output;
}

function renderOddiMath(container, attempt = 0) {
    if (!container) return;

    if (window.renderMathInElement && window.katex) {
        try {
            renderMathInElement(container, {
                delimiters: [
                    { left: "$$", right: "$$", display: true },
                    { left: "\\[", right: "\\]", display: true },
                    { left: "\\(", right: "\\)", display: false },
                    { left: "$", right: "$", display: false }
                ],
                throwOnError: false,
                strict: "ignore",
                ignoredTags: [
                    "script", "noscript", "style", "textarea",
                    "pre", "code", "button"
                ]
            });
            container.dataset.oddimathRendered = "true";
            return;
        } catch (error) {
            console.warn("Oddi math rendering failed:", error);
        }
    }

    if (attempt < 80) {
        setTimeout(() => renderOddiMath(container, attempt + 1), 100);
    }
}

function enhanceRichContent(container) {
    if (!container) return;

    /* Syntax highlighting — exactly once per code block. */
    container.querySelectorAll("pre code").forEach(block => {
        if (window.hljs && !block.dataset.oddihighlighted) {
            try {
                hljs.highlightElement(block);
                block.dataset.oddihighlighted = "true";
            } catch (error) {
                console.warn("Oddi code highlighting failed:", error);
            }
        }
    });

    /* One dedicated copy button for every code block. */
    container.querySelectorAll("pre").forEach(pre => {
        if (pre.parentElement?.classList.contains("ai-code-wrap")) return;

        const code = pre.querySelector("code");
        if (!code) return;

        const wrapper = document.createElement("div");
        wrapper.className = "ai-code-wrap";
        pre.parentNode.insertBefore(wrapper, pre);
        wrapper.appendChild(pre);

        const copyButton = document.createElement("button");
        copyButton.type = "button";
        copyButton.className = "ai-code-copy";
        copyButton.textContent = "📋 Copy";
        copyButton.title = "Copy this code";
        copyButton.setAttribute("aria-label", "Copy this code block");

        copyButton.addEventListener("click", async () => {
            try {
                await navigator.clipboard.writeText(code.textContent || "");
                copyButton.textContent = "✅ Copied!";
            } catch (error) {
                console.error("Could not copy code:", error);
                copyButton.textContent = "❌ Copy failed";
            }

            setTimeout(() => {
                copyButton.textContent = "📋 Copy";
            }, 1400);
        });

        wrapper.appendChild(copyButton);
    });

    renderOddiMath(container);
}

function renderRichContentToHtml(source) {
    const prepared = prepareRichContent(source);
    return restoreMathInHtml(
        marked.parse(prepared.markdown),
        prepared.mathParts
    );
}

function renderRichContent(element, source, options = {}) {
    if (!element) return;

    const prepared = prepareRichContent(source);

    /* Marked runs exactly once. Math was protected before Markdown and is
       restored immediately after, so KaTeX receives the original delimiters. */
    element.innerHTML = restoreMathInHtml(
        marked.parse(prepared.markdown),
        prepared.mathParts
    );

    enhanceRichContent(element);
}