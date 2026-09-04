/* =========================================================
   CURRENT ARROW
   ========================================================= */

function drawCurrentArrow(x1, y1, x2, y2, label = "") {
    const angle = Math.atan2(y2 - y1, x2 - x1);
    const size = 8;

    const p1x =
        x2 + size * Math.cos(angle + Math.PI * 0.82);

    const p1y =
        y2 + size * Math.sin(angle + Math.PI * 0.82);

    const p2x =
        x2 + size * Math.cos(angle - Math.PI * 0.82);

    const p2y =
        y2 + size * Math.sin(angle - Math.PI * 0.82);

    return `
        <line
            class="ai-circuit-current-arrow"
            x1="${x1}" y1="${y1}"
            x2="${x2}" y2="${y2}">
        </line>

        <polygon
            class="ai-circuit-current-arrow-head"
            points="
                ${x2},${y2}
                ${p1x},${p1y}
                ${p2x},${p2y}
            ">
        </polygon>

        ${label
            ? svgText(
                (x1 + x2) / 2,
                (y1 + y2) / 2 - 12,
                label,
                "ai-circuit-value"
            )
            : ""}
    `;
}

/* =========================================================
   SERIES CIRCUIT
   ========================================================= */

function renderSeriesCircuit(circuit) {
    const components = [];

    if (circuit.battery) {
        components.push(circuit.battery);
    }

    components.push(...circuit.components);

    if (circuit.switch) {
        components.push(circuit.switch);
    }

    if (!components.length) return null;

    const width = Math.max(
        820,
        240 + components.length * 150
    );

    const height = 390;
    const topY = 165;
    const bottomY = 300;
    const leftX = 90;
    const rightX = width - 90;

    const step =
        (rightX - leftX) /
        Math.max(1, components.length);

    let body = "";

    components.forEach((component, index) => {
        const x =
            leftX +
            step * index +
            step / 2;

        const left =
            index === 0
                ? leftX
                : x - step / 2;

        const right =
            index === components.length - 1
                ? rightX
                : x + step / 2;

        body += svgLine(left, topY, x - 65, topY);
        body += drawComponent(component, x, topY);
        body += svgLine(x + 65, topY, right, topY);
    });

    body += svgLine(rightX, topY, rightX, bottomY);
    body += svgLine(rightX, bottomY, leftX, bottomY);
    body += svgLine(leftX, bottomY, leftX, topY);

    if (circuit.current) {
        body += drawCurrentArrow(
            leftX + 15,
            topY - 38,
            leftX + 105,
            topY - 38,
            `I = ${circuit.current}`
        );
    }

    return {
        width,
        height,
        body
    };
}

/* =========================================================
   PARALLEL CIRCUIT
   ========================================================= */

function renderParallelCircuit(circuit) {
    let branches = circuit.branches;

    if (!branches.length && circuit.components.length) {
        branches = circuit.components.map(component => ({
            components: [component]
        }));
    }

    if (!branches.length) return null;

    const width = 900;
    const leftX = 130;
    const rightX = 770;
    const topY = 75;
    const gap = 105;

    const height =
        Math.max(
            420,
            topY + branches.length * gap + 180
        );

    let body = "";

    body += svgLine(
        leftX,
        topY,
        leftX,
        height - 80
    );

    body += svgLine(
        rightX,
        topY,
        rightX,
        height - 80
    );

    branches.forEach((branch, index) => {
        const y =
            topY +
            55 +
            index * gap;

        const list =
            branch.components || [];

        body += svgLine(
            leftX,
            y,
            leftX + 75,
            y
        );

        if (!list.length) {
            body += svgLine(
                leftX + 75,
                y,
                rightX - 75,
                y
            );
        } else {
            const available =
                rightX -
                leftX -
                150;

            const spacing =
                available /
                list.length;

            list.forEach((component, componentIndex) => {
                const x =
                    leftX +
                    75 +
                    spacing * componentIndex +
                    spacing / 2;

                const start =
                    componentIndex === 0
                        ? leftX + 75
                        : x - spacing / 2;

                const end =
                    componentIndex === list.length - 1
                        ? rightX - 75
                        : x + spacing / 2;

                body += svgLine(
                    start,
                    y,
                    x - 65,
                    y
                );

                body += drawComponent(
                    component,
                    x,
                    y
                );

                body += svgLine(
                    x + 65,
                    y,
                    end,
                    y
                );
            });
        }

        body += svgLine(
            rightX - 75,
            y,
            rightX,
            y
        );

        body += `
            <circle
                class="ai-circuit-junction"
                cx="${leftX}"
                cy="${y}"
                r="4">
            </circle>

            <circle
                class="ai-circuit-junction"
                cx="${rightX}"
                cy="${y}"
                r="4">
            </circle>
        `;

        if (circuit.current) {
            body += drawCurrentArrow(
                rightX / 2 - 35,
                y - 30,
                rightX / 2 + 35,
                y - 30,
                `I${index + 1}`
            );
        }
    });

    if (circuit.battery) {
        body += `
            <g transform="translate(${leftX}, ${height / 2}) rotate(90)">
                ${drawBattery(
                    0,
                    0,
                    circuit.battery.value
                )}
            </g>
        `;
    }

    body += svgText(
        leftX - 15,
        topY - 12,
        "X",
        "ai-circuit-label",
        "end"
    );

    body += svgText(
        rightX + 15,
        topY - 12,
        "Y",
        "ai-circuit-label",
        "start"
    );

    if (circuit.voltage) {
        body += svgText(
            width / 2,
            height - 30,
            `V = ${circuit.voltage}`,
            "ai-circuit-value"
        );
    }

    return {
        width,
        height,
        body
    };
}

/* =========================================================
   COMPLETE CIRCUIT CARD
   ========================================================= */

function buildCircuitSvg(circuit) {
    const rendered =
        circuit.layout === "parallel"
            ? renderParallelCircuit(circuit)
            : renderSeriesCircuit(circuit);

    if (!rendered) return "";

    return `
        <div class="ai-circuit-wrap">
            <div class="ai-circuit-card">

                <div class="ai-circuit-header">
                    <div class="ai-circuit-title">
                        <span class="ai-circuit-title-icon">
                            ⚡
                        </span>

                        <span>
                            ${escapeXml(
                                circuit.title ||
                                "Electrical Circuit"
                            )}
                        </span>
                    </div>
                </div>

                <div class="ai-circuit-canvas">

                    <svg
                        class="ai-circuit-svg"
                        viewBox="
                            0 0
                            ${rendered.width}
                            ${rendered.height}
                        "
                        preserveAspectRatio="xMidYMid meet"
                        role="img"
                        aria-label="${escapeXml(
                            circuit.title ||
                            "Electrical circuit diagram"
                        )}"
                    >
                        ${rendered.body}
                    </svg>

                </div>

                <div class="ai-circuit-controls">

                    <button
                        type="button"
                        class="ai-circuit-control ai-circuit-zoom-in"
                        title="Zoom in"
                        aria-label="Zoom in">
                        ＋
                    </button>

                    <button
                        type="button"
                        class="ai-circuit-control ai-circuit-zoom-out"
                        title="Zoom out"
                        aria-label="Zoom out">
                        −
                    </button>

                    <button
                        type="button"
                        class="ai-circuit-control ai-circuit-zoom-reset"
                        title="Reset zoom"
                        aria-label="Reset zoom">
                        ↺
                    </button>

                    <button
                        type="button"
                        class="ai-circuit-control ai-circuit-fullscreen"
                        title="Fullscreen"
                        aria-label="Fullscreen">
                        ⛶
                    </button>

                </div>

            </div>
        </div>
    `;
}

/* =========================================================
   CIRCUIT BLOCK PROTECTION
   ========================================================= */

function protectCircuitBlocks(text, circuitParts) {
    return String(text || "").replace(
        /```(?:circuit|schematic|electrical)\s*\n([\s\S]*?)```/gi,
        (whole, body) => {
            const circuit =
                parseCircuitSource(body);

            if (!validCircuit(circuit)) {
                return whole;
            }

            const key =
                `ODDICIRCUIT${circuitParts.length}X`;

            circuitParts.push({
                key,
                circuit
            });

            return key;
        }
    );
}

function restoreCircuitBlocks(html, circuitParts) {
    let output = String(html || "");

    circuitParts.forEach(({ key, circuit }) => {
        output = output
            .split(key)
            .join(buildCircuitSvg(circuit));
    });

    return output;
}

/* =========================================================
   MATH PROTECTION
   ========================================================= */

function prepareRichContent(source) {
    let text = String(source ?? "");

    const mathParts = [];
    const circuitParts = [];
    const codeParts = [];

    const protectMath = value => {
        const key =
            `ODDIMATH${mathParts.length}X`;

        mathParts.push({
            key,
            value
        });

        return key;
    };

    /*
     * Circuit MUST be protected before normal code blocks.
     */
    text =
        protectCircuitBlocks(
            text,
            circuitParts
        );

    /*
     * Protect ordinary fenced code.
     */
    text = text.replace(
        /```[\s\S]*?```/g,
        block => {
            const key =
                `ODDICODE${codeParts.length}X`;

            codeParts.push({
                key,
                value: block
            });

            return key;
        }
    );

    /*
     * Display math.
     */
    text = text.replace(
        /\$\$[\s\S]*?\$\$/g,
        protectMath
    );

    text = text.replace(
        /\\\[[\s\S]*?\\\]/g,
        protectMath
    );

    text = text.replace(
        /\\\([\s\S]*?\\\)/g,
        protectMath
    );

    /*
     * Inline dollar math.
     */
    text = text.replace(
        /(^|[^\\])\$([^$\n]+?)\$/g,
        (whole, prefix, body) =>
            `${prefix}${protectMath(`$${body}$`)}`
    );

    /*
     * Standalone LaTeX-looking [ ... ].
     */
    text = text.replace(
        /^\s*\[\s*((?:\\[a-zA-Z]+|[^\n])*?(?:\\frac|\\sqrt|\\boxed|\\begin|\\Delta|\\pm|\\le|\\ge|\^|_)[^\n]*?)\s*\]\s*$/gm,
        (whole, body) =>
            protectMath(`\\[${body}\\]`)
    );

    /*
     * LaTeX-looking expressions in parentheses.
     */
    text = text.replace(
        /\(([^()\n]*(?:\\(?:frac|sqrt|times|Delta|pm|le|ge|neq|quad|text|boxed|begin|cdot)|\^\{|\_\{|\^[A-Za-z0-9]|_[A-Za-z0-9])[^()\n]*)\)/g,
        (whole, body) =>
            protectMath(`\\(${body}\\)`)
    );

    /*
     * Plain superscript/subscript fallback.
     */
    text = text.replace(
        /\b([A-Za-z0-9])\^(\d{1,3})\b/g,
        "$1<sup>$2</sup>"
    );

    text = text.replace(
        /\b([A-Za-z])_(\d{1,3})\b/g,
        "$1<sub>$2</sub>"
    );

    /*
     * Restore normal code before Marked parses it.
     */
    codeParts.forEach(({ key, value }) => {
        text = text
            .split(key)
            .join(value);
    });

    return {
        markdown: text,
        mathParts,
        circuitParts
    };
}

function restoreMathInHtml(html, mathParts) {
    let output = String(html || "");

    mathParts.forEach(({ key, value }) => {
        output = output
            .split(key)
            .join(escapeHtml(value));
    });

    return output;
}

/* =========================================================
   KATEX
   ========================================================= */

function renderOddiMath(container, attempt = 0) {
    if (!container) return;

    if (
        window.renderMathInElement &&
        window.katex
    ) {
        try {
            renderMathInElement(
                container,
                {
                    delimiters: [
                        {
                            left: "$$",
                            right: "$$",
                            display: true
                        },
                        {
                            left: "\\[",
                            right: "\\]",
                            display: true
                        },
                        {
                            left: "\\(",
                            right: "\\)",
                            display: false
                        },
                        {
                            left: "$",
                            right: "$",
                            display: false
                        }
                    ],

                    throwOnError: false,
                    strict: "ignore",

                    ignoredTags: [
                        "script",
                        "noscript",
                        "style",
                        "textarea",
                        "pre",
                        "code",
                        "button"
                    ]
                }
            );

            container.dataset.oddimathRendered =
                "true";

            return;

        } catch (error) {
            console.warn(
                "Oddi math rendering failed:",
                error
            );
        }
    }

    if (attempt < 80) {
        setTimeout(
            () =>
                renderOddiMath(
                    container,
                    attempt + 1
                ),
            100
        );
    }
}

/* =========================================================
   CODE BLOCKS
   ========================================================= */

function enhanceCodeBlocks(container) {
    if (!container) return;

    container
        .querySelectorAll("pre code")
        .forEach(block => {

            if (
                window.hljs &&
                !block.dataset.oddihighlighted
            ) {
                try {
                    hljs.highlightElement(block);

                    block.dataset.oddihighlighted =
                        "true";

                } catch (error) {
                    console.warn(
                        "Oddi code highlighting failed:",
                        error
                    );
                }
            }
        });

    container
        .querySelectorAll("pre")
        .forEach(pre => {

            if (
                pre.parentElement
                    ?.classList
                    .contains("ai-code-wrap")
            ) {
                return;
            }

            const code =
                pre.querySelector("code");

            if (!code) return;

            const wrapper =
                document.createElement("div");

            wrapper.className =
                "ai-code-wrap";

            pre.parentNode.insertBefore(
                wrapper,
                pre
            );

            wrapper.appendChild(pre);

            const copyButton =
                document.createElement("button");

            copyButton.type = "button";
            copyButton.className =
                "ai-code-copy";

            copyButton.textContent =
                "📋 Copy";

            copyButton.title =
                "Copy this code";

            copyButton.setAttribute(
                "aria-label",
                "Copy this code block"
            );

            copyButton.addEventListener(
                "click",
                async () => {

                    try {
                        await navigator
                            .clipboard
                            .writeText(
                                code.textContent || ""
                            );

                        copyButton.textContent =
                            "✅ Copied!";

                    } catch (error) {

                        console.error(
                            "Could not copy code:",
                            error
                        );

                        copyButton.textContent =
                            "❌ Copy failed";
                    }

                    setTimeout(
                        () => {
                            copyButton.textContent =
                                "📋 Copy";
                        },
                        1400
                    );
                }
            );

            wrapper.appendChild(
                copyButton
            );
        });
}

/* =========================================================
   CIRCUIT CONTROLS
   ========================================================= */

function enhanceCircuitControls(container) {
    if (!container) return;

    container
        .querySelectorAll(".ai-circuit-card")
        .forEach(card => {

            if (
                card.dataset
                    .circuitEnhanced === "true"
            ) {
                return;
            }

            card.dataset
                .circuitEnhanced = "true";

            const svg =
                card.querySelector(
                    ".ai-circuit-svg"
                );

            const canvas =
                card.querySelector(
                    ".ai-circuit-canvas"
                );

            if (!svg || !canvas) return;

            let zoom = 1;

            function applyZoom() {
                svg.style.transform =
                    `scale(${zoom})`;

                svg.style.transformOrigin =
                    "center center";

                canvas.style.overflow =
                    zoom > 1
                        ? "auto"
                        : "hidden";
            }

            card
                .querySelector(
                    ".ai-circuit-zoom-in"
                )
                ?.addEventListener(
                    "click",
                    () => {
                        zoom =
                            Math.min(
                                2.5,
                                +(zoom + 0.15)
                                    .toFixed(2)
                            );

                        applyZoom();
                    }
                );

            card
                .querySelector(
                    ".ai-circuit-zoom-out"
                )
                ?.addEventListener(
                    "click",
                    () => {
                        zoom =
                            Math.max(
                                0.65,
                                +(zoom - 0.15)
                                    .toFixed(2)
                            );

                        applyZoom();
                    }
                );

            card
                .querySelector(
                    ".ai-circuit-zoom-reset"
                )
                ?.addEventListener(
                    "click",
                    () => {
                        zoom = 1;
                        applyZoom();
                    }
                );

            card
                .querySelector(
                    ".ai-circuit-fullscreen"
                )
                ?.addEventListener(
                    "click",
                    () => {

                        card.classList.toggle(
                            "circuit-fullscreen"
                        );

                        document.body.classList.toggle(
                            "oddi-circuit-fullscreen-open",
                            card.classList.contains(
                                "circuit-fullscreen"
                            )
                        );
                    }
                );
        });
}

/* =========================================================
   MAIN RENDERER
   ========================================================= */

function enhanceRichContent(container) {
    if (!container) return;

    enhanceCodeBlocks(container);
    enhanceCircuitControls(container);
    renderOddiMath(container);
}

function renderRichContentToHtml(source) {
    const prepared =
        prepareRichContent(source);

    let html =
        marked.parse(
            prepared.markdown
        );

    html =
        restoreMathInHtml(
            html,
            prepared.mathParts
        );

    html =
        restoreCircuitBlocks(
            html,
            prepared.circuitParts
        );

    return html;
}

function renderRichContent(
    element,
    source,
    options = {}
) {
    if (!element) return;

    const prepared =
        prepareRichContent(source);

    let html =
        marked.parse(
            prepared.markdown
        );

    html =
        restoreMathInHtml(
            html,
            prepared.mathParts
        );

    html =
        restoreCircuitBlocks(
            html,
            prepared.circuitParts
        );

    element.innerHTML = html;

    enhanceRichContent(element);
}