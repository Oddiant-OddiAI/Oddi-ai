(function installOddiMobileExperience() {
    "use strict";

    const mobileQuery = window.matchMedia("(max-width: 768px) and (pointer: coarse)");
    const chat = document.getElementById("chatbox");
    const composer = document.getElementById("oddiComposerShell");
    const input = document.getElementById("userInput");
    const voiceButton = document.getElementById("voice-btn");

    let lastHapticAt = 0;
    let swipe = null;
    let suppressSwipeClickUntil = 0;
    let suppressSwipeClickBubble = null;
    let viewportFrame = 0;
    let codeFrame = 0;
    let toastTimer = 0;
    let mobileFeaturesInstalled = false;

    function vibrate(duration = 9) {
        if (!mobileQuery.matches || !navigator.vibrate) return;
        const now = Date.now();
        if (now - lastHapticAt < 65) return;
        lastHapticAt = now;
        try { navigator.vibrate(duration); } catch (_) {}
    }

    function installHaptics() {
        document.addEventListener("pointerup", event => {
            if (!mobileQuery.matches || !["touch", "pen"].includes(event.pointerType)) return;
            const control = event.target?.closest?.("button, [role='button'], input[type='checkbox'], summary");
            if (!control || control.disabled || control.getAttribute("aria-disabled") === "true") return;
            vibrate(control.id === "send-btn" || control.id === "voice-btn" || control.id === "dictation-btn" ? 12 : 8);
        }, {capture: true, passive: true});

        document.addEventListener("click", event => {
            const button = event.target?.closest?.("#voice-btn");
            if (!button) return;
            requestAnimationFrame(() => {
                const active = button.classList.contains("listening");
                button.classList.toggle("mobile-voice-active", active);
                button.setAttribute("aria-pressed", String(active));
            });
        });

        if (voiceButton) {
            new MutationObserver(() => {
                const active = voiceButton.classList.contains("listening");
                voiceButton.classList.toggle("mobile-voice-active", active);
                voiceButton.setAttribute("aria-pressed", String(active));
            }).observe(voiceButton, {attributes: true, attributeFilter: ["class"]});
        }
    }

    function installKeyboardAndViewportHandling() {
        if (!mobileQuery.matches || !composer || !chat) return;

        const root = document.documentElement;
        const viewport = window.visualViewport;

        const updateViewport = () => {
            if (!mobileQuery.matches) {
                root.style.removeProperty("--oddi-mobile-keyboard-inset");
                document.body.classList.remove("oddi-mobile-keyboard-open");
                document.body.classList.remove("mobile-keyboard-open");
                return;
            }
            if (viewportFrame) cancelAnimationFrame(viewportFrame);
            viewportFrame = requestAnimationFrame(() => {
                viewportFrame = 0;
                const focused = document.activeElement === input;
                const layoutHeight = window.innerHeight || root.clientHeight;
                const visibleHeight = viewport?.height || layoutHeight;
                const visibleBottom = Math.min(layoutHeight, Math.max(0, (viewport?.offsetTop || 0) + visibleHeight));
                const rawInset = focused && layoutHeight - visibleBottom > 120
                    ? Math.max(0, layoutHeight - visibleBottom)
                    : 0;
                const keyboardInset = Math.min(rawInset, layoutHeight * 0.6);

                if (keyboardInset > 0) {
                    root.style.setProperty("--oddi-mobile-keyboard-inset", `${keyboardInset}px`);
                } else {
                    root.style.removeProperty("--oddi-mobile-keyboard-inset");
                }
                document.body.classList.toggle("oddi-mobile-keyboard-open", keyboardInset > 0);
                document.body.classList.toggle("mobile-keyboard-open", keyboardInset > 0);
                window.dispatchEvent(new Event("oddi:mobile-viewport-adjusted"));
            });
        };

        viewport?.addEventListener("resize", updateViewport, {passive: true});
        viewport?.addEventListener("scroll", updateViewport, {passive: true});
        window.addEventListener("resize", updateViewport, {passive: true});
        window.addEventListener("orientationchange", updateViewport, {passive: true});
        input?.addEventListener("focus", updateViewport, {passive: true});
        input?.addEventListener("blur", () => window.setTimeout(updateViewport, 80), {passive: true});
        updateViewport();
    }

    function showGestureToast(message) {
        let toast = document.getElementById("oddiMobileGestureToast");
        if (!toast) {
            toast = document.createElement("div");
            toast.id = "oddiMobileGestureToast";
            toast.setAttribute("role", "status");
            toast.setAttribute("aria-live", "polite");
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        toast.classList.add("is-visible");
        window.clearTimeout(toastTimer);
        toastTimer = window.setTimeout(() => toast.classList.remove("is-visible"), 1500);
    }

    function bubbleFromTarget(target) {
        return target?.closest?.("#chatbox .user-message, #chatbox .bot-message") || null;
    }

    function isGestureExcluded(target) {
        return !!target?.closest?.("button, a, input, textarea, select, pre, code, .user-attachments, .ai-code-wrap, .ai-table-wrap, .user-message-edit-input, [contenteditable='true']");
    }

    function clearSwipePreview() {
        if (!swipe?.bubble) return;
        swipe.bubble.classList.remove("oddi-mobile-swipe-hint", "oddi-mobile-swipe-reply", "oddi-mobile-swipe-pin");
    }

    function replyToBubble(bubble) {
        if (!input || document.body.classList.contains("oddi-generation-active")) return false;
        const source = bubble.querySelector(".user-text, .ai-content")?.innerText?.replace(/\s+/g, " ").trim();
        if (!source) return false;
        const speaker = bubble.classList.contains("user-message") ? "your message" : "ODDI-AI";
        const quote = source.length > 420 ? `${source.slice(0, 417).trimEnd()}…` : source;
        input.value = `Replying to ${speaker}:\n> ${quote}\n\n${input.value}`;
        input.dispatchEvent(new Event("input", {bubbles: true}));
        input.focus({preventScroll: true});
        requestAnimationFrame(() => input.setSelectionRange(input.value.length, input.value.length));
        showGestureToast("Message quoted in the composer");
        vibrate(12);
        return true;
    }

    function pinBubble(bubble) {
        const pinButton = bubble.querySelector(".user-pin-btn, .bot-pin-btn");
        if (!pinButton) return false;
        const willPin = !pinButton.classList.contains("active");
        if (typeof window.togglePinMessage === "function") {
            void window.togglePinMessage(pinButton);
        } else {
            pinButton.click();
        }
        showGestureToast(willPin ? "Message pinned" : "Message unpinned");
        vibrate(12);
        return true;
    }

    function installMessageGestures() {
        if (!mobileQuery.matches || !chat) return;

        document.addEventListener("pointerdown", event => {
            if (!mobileQuery.matches || event.pointerType !== "touch" || event.button !== 0 || isGestureExcluded(event.target)) return;
            const bubble = bubbleFromTarget(event.target);
            if (!bubble || document.body.classList.contains("oddi-generation-active")) return;
            swipe = {bubble, pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, dx: 0, dy: 0, horizontal: false};
        }, {capture: true, passive: true});

        document.addEventListener("pointermove", event => {
            if (!swipe || event.pointerId !== swipe.pointerId) return;
            swipe.dx = event.clientX - swipe.startX;
            swipe.dy = event.clientY - swipe.startY;
            if (Math.abs(swipe.dy) > 24 && Math.abs(swipe.dy) > Math.abs(swipe.dx) * 1.1) {
                clearSwipePreview();
                swipe = null;
                return;
            }
            if (Math.abs(swipe.dx) < 14 || Math.abs(swipe.dx) < Math.abs(swipe.dy) * 1.25) return;
            swipe.horizontal = true;
            event.preventDefault();
            swipe.bubble.classList.add("oddi-mobile-swipe-hint");
            swipe.bubble.classList.toggle("oddi-mobile-swipe-reply", swipe.dx > 0);
            swipe.bubble.classList.toggle("oddi-mobile-swipe-pin", swipe.dx < 0);
        }, {capture: true, passive: false});

        document.addEventListener("pointerup", event => {
            if (!swipe || event.pointerId !== swipe.pointerId) return;
            const current = swipe;
            clearSwipePreview();
            swipe = null;
            if (!current.horizontal || Math.abs(current.dx) < 76 || Math.abs(current.dx) < Math.abs(current.dy) * 1.35) return;
            event.preventDefault();
            event.stopPropagation();
            suppressSwipeClickBubble = current.bubble;
            suppressSwipeClickUntil = Date.now() + 450;
            if (current.dx > 0) replyToBubble(current.bubble);
            else pinBubble(current.bubble);
        }, {capture: true, passive: false});

        document.addEventListener("pointercancel", event => {
            if (!swipe || event.pointerId !== swipe.pointerId) return;
            clearSwipePreview();
            swipe = null;
        }, {capture: true, passive: true});

        document.addEventListener("click", event => {
            if (Date.now() > suppressSwipeClickUntil || !suppressSwipeClickBubble) return;
            if (bubbleFromTarget(event.target) !== suppressSwipeClickBubble) return;
            event.preventDefault();
            event.stopImmediatePropagation();
            suppressSwipeClickBubble = null;
        }, true);
    }

    function collapseLongCodeBlocks() {
        if (!mobileQuery.matches || document.body.classList.contains("oddi-generation-active") || !chat) return;
        chat.querySelectorAll(".ai-content .ai-code-wrap").forEach(wrapper => {
            if (wrapper.dataset.oddiCollapsibleCode === "true") return;
            const pre = wrapper.querySelector(":scope > pre");
            const code = pre?.querySelector("code");
            if (!pre || !code) return;
            const lines = String(code.textContent || "").split("\n").length;
            if (lines < 24) return;

            const details = document.createElement("details");
            details.className = "oddi-code-details";
            const summary = document.createElement("summary");
            const language = Array.from(code.classList).find(name => name.startsWith("language-"))?.slice(9) || "Code";
            summary.textContent = `${language} · ${lines} lines · tap to expand`;
            wrapper.insertBefore(details, pre);
            details.appendChild(summary);
            details.appendChild(pre);
            wrapper.dataset.oddiCollapsibleCode = "true";
        });
    }

    function scheduleCodeDisclosure() {
        if (codeFrame) return;
        codeFrame = requestAnimationFrame(() => {
            codeFrame = 0;
            collapseLongCodeBlocks();
        });
    }

    function installRichContentEnhancements() {
        if (!mobileQuery.matches || !chat) return;
        const observer = new MutationObserver(scheduleCodeDisclosure);
        observer.observe(chat, {childList: true, subtree: true});
        new MutationObserver(records => {
            if (records.some(record => record.attributeName === "class")) scheduleCodeDisclosure();
        }).observe(document.body, {attributes: true, attributeFilter: ["class"]});
        window.addEventListener("oddi:conversation-opened", scheduleCodeDisclosure);
        scheduleCodeDisclosure();
    }

    function installDynamicMobileSupport() {
        if (!mobileQuery.matches || mobileFeaturesInstalled) return;
        mobileFeaturesInstalled = true;
        installHaptics();
        installKeyboardAndViewportHandling();
        installMessageGestures();
        installRichContentEnhancements();
    }

    installDynamicMobileSupport();
    mobileQuery.addEventListener?.("change", () => {
        if (!mobileQuery.matches) {
            document.documentElement.style.removeProperty("--oddi-mobile-keyboard-inset");
            document.body.classList.remove("oddi-mobile-keyboard-open");
            document.body.classList.remove("mobile-keyboard-open");
            return;
        }
        installDynamicMobileSupport();
    });
})();
