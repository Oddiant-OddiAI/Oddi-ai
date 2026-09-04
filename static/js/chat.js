/* 
   GENERATION CONTROL
 */
let generationActive = false;
let generationStopped = false;
let activeAbortController = null;
let activeTypingInterval = null;
let activeTypingResolve = null;
let activeTypingElement = null;
let activeGenerationConversation = null;

function setGenerationUI(active) {
    generationActive = active;

    if (active) {
        button.disabled = false;
        button.classList.add("stop-active");
        button.innerHTML = `<span class="stop-icon">■</span>`;
        button.title = "Stop generating";
        button.setAttribute("aria-label", "Stop generating");
    } else {
        button.disabled = false;
        button.classList.remove("stop-active");
        button.innerHTML = `<span class="send-icon">➤</span>`;
        button.title = "Send message";
        button.setAttribute("aria-label", "Send message");
    }
}

function stopGeneration() {
    if (!generationActive) return;

    generationStopped = true;

    if (activeAbortController) {
        activeAbortController.abort();
    }

    if (activeTypingInterval) {
        clearInterval(activeTypingInterval);
        activeTypingInterval = null;
    }

    if (activeTypingResolve) {
        activeTypingResolve();
        activeTypingResolve = null;
    }

    const conversationIndex = activeGenerationConversation;
    const botMessage = activeTypingElement?.closest('.bot-message');

    if (
        botMessage &&
        conversationIndex !== null &&
        conversationIndex !== undefined &&
        conversations[conversationIndex]
    ) {
        const conversation = conversations[conversationIndex];

        /* Store the stopped generation so it survives reloads. */
        const alreadySaved =
            botMessage.dataset.messageIndex !== undefined &&
            conversation.messages[Number(botMessage.dataset.messageIndex)]?.stopped;

        if (!alreadySaved) {
            activeTypingElement.innerHTML = 'Generation stopped.';

            const stoppedIndex = conversation.messages.length;

            conversation.messages.push({
                role: 'assistant',
                text: 'Generation stopped.',
                pinned: false,
                feedback: null,
                stopped: true
            });

            botMessage.dataset.messageIndex = stoppedIndex;
            botMessage.querySelector('.thinking-actions')?.remove();
            addBotMessageActions(botMessage, stoppedIndex, conversationIndex);

            saveConversation(conversation);
        }
    } else {
        const thinking = document.querySelector('.bot-message .thinking-indicator');
        if (thinking) {
            thinking.textContent = 'Generation stopped.';
        }
    }

    setGenerationUI(false);
}

/* 
   ACTION BUTTON
 */

/* 
   ACTION BUTTON
 */

function updateActionButton() {
    const hasText = input.value.trim().length > 0;

    const slot =
        document.querySelector(".action-button-slot");

    if (slot) {
        slot.classList.toggle("has-text", hasText);
    }

    if (!generationActive) {
        setGenerationUI(false);
    }
}

/* 
   SPEECH DICTATION
 */

const SpeechRecognition =
    window.SpeechRecognition ||
    window.webkitSpeechRecognition;

const dictationBtn =
    document.getElementById("dictation-btn");

let dictationRecognition = null;
let dictationActive = false;

function resizeInputAfterDictation() {
    input.style.height = "auto";
    input.style.height =
        Math.min(input.scrollHeight, 180) + "px";

    updateActionButton();
}

if (SpeechRecognition) {

    dictationRecognition =
        new SpeechRecognition();

    dictationRecognition.lang = "en-IN";
    dictationRecognition.continuous = false;
    dictationRecognition.interimResults = true;

    dictationBtn.onclick = () => {

        if (voiceModeActive) {
            stopVoiceMode();
        }

        if (dictationActive) {
            try {
                dictationRecognition.stop();
            } catch (e) {}
            return;
        }

        try {
            dictationRecognition.start();
        } catch (error) {
            if (error.name !== "InvalidStateError") {
                console.error(
                    "Could not start dictation:",
                    error
                );
            }
        }
    };

    dictationRecognition.onstart = () => {

        dictationActive = true;

        dictationBtn.classList.add("listening");

        dictationBtn.innerHTML = "⏺";

        dictationBtn.title =
            "Stop voice typing";

        dictationBtn.setAttribute(
            "aria-label",
            "Stop voice typing"
        );
    };

    dictationRecognition.onresult = (event) => {

        let finalText = "";
        let interimText = "";

        for (
            let i = event.resultIndex;
            i < event.results.length;
            i++
        ) {

            const text =
                event.results[i][0].transcript;

            if (event.results[i].isFinal) {
                finalText += text;
            } else {
                interimText += text;
            }
        }

        if (finalText.trim()) {

            const existing =
                input.value.trim();

            input.value = existing
                ? existing + " " + finalText.trim()
                : finalText.trim();

            resizeInputAfterDictation();
        }

        if (interimText.trim()) {
            input.placeholder =
                interimText.trim();
        }
    };

    dictationRecognition.onend = () => {

        dictationActive = false;

        dictationBtn.classList.remove(
            "listening"
        );

        dictationBtn.innerHTML = `
            <svg
                height="24"
                viewBox="0 0 24 24"
                width="24"
                xmlns="http://www.w3.org/2000/svg"
                fill="currentColor">
                <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1-9c0-.55.45-1 1-1s1 .45 1 1v6c0 .55-.45 1-1 1s-1-.45-1-1V5zm6 6c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39-6-6.92h-2z"/>
            </svg>
        `;

        dictationBtn.title =
            "Type with your voice";

        dictationBtn.setAttribute(
            "aria-label",
            "Type with your voice"
        );

        input.placeholder =
            "Ask Oddi anything...";

        resizeInputAfterDictation();
    };

    dictationRecognition.onerror = (event) => {

        console.error(
            "Speech dictation error:",
            event.error
        );

        dictationActive = false;

        dictationBtn.classList.remove(
            "listening"
        );

        input.placeholder =
            "Ask Oddi anything...";

        if (event.error === "not-allowed") {
            alert(
                "Microphone permission is required for voice typing."
            );
        }
    };

} else {

    dictationBtn.onclick = () => {
        alert(
            "Voice typing is not supported by this browser. Try Chrome or Edge."
        );
    };
}
/* 
   MAIN SEND FUNCTION
   THIS IS THE IMPORTANT FIX
 */

async function sendMessage(
    displayMessage = null,
    voiceReply = false,
    options = {}
) {

    if (generationActive) {
        stopGeneration();
        return;
    }

    const skipUserMessage = !!options.skipUserMessage;

    const message =
        options.messageOverride !== undefined
            ? String(options.messageOverride).trim()
            : input.value.trim();

    const userDisplayMessage =
        displayMessage || message;

    if (!message) return;

    generationStopped = false;

    /* -----------------------------------------
       CREATE CONVERSATION
    ----------------------------------------- */

    if (
        currentConversation === null
    ) {

        if (isLoggedIn) {

            const serverConversation =
                await createServerConversation(
                    message
                );

            if (!serverConversation) {
                return;
            }

            conversations.unshift({
                id:
                    serverConversation.id,
                title: message,
                messages: [],
                pinned: false
            });

            currentConversation = 0;
            touchConversation(conversations[0]);

            renderHistory();

        } else {

            conversations = [{
                id: null,
                title: message,
                messages: []
            }];

            currentConversation = 0;
        }
    }

    /* -----------------------------------------
       LOCK INPUT
    ----------------------------------------- */

    input.disabled = true;
    setGenerationUI(true);
    activeAbortController = new AbortController();

    const app =
        document.querySelector(
            ".app"
        );

    if (app) {
        app.classList.add(
            "chat-started"
        );
    }

    const welcome =
        document.getElementById(
            "welcomeContainer"
        );

    if (welcome) {
        welcome.remove();
    }

    /* -----------------------------------------
       USER MESSAGE
    ----------------------------------------- */

    if (!skipUserMessage) {
        let fileHTML = "";
        const fileRefs = [];

        if (selectedFiles.length) {
            for (const file of selectedFiles) {
                try {
                    const fileId = await storeOddiFile(file);
                    fileRefs.push({ id: fileId, name: file.name });
                    fileHTML += buildFileHTML(file.name, fileId);
                } catch (error) {
                    console.error("Could not store uploaded file:", error);
                    fileHTML += buildFileHTML(file.name);
                }
            }
        }

        const userMessageIndex =
            conversations[currentConversation].messages.length;

        chat.innerHTML += `
            <div class="user-message" data-message-index="${userMessageIndex}">
                ${fileHTML}

                <div class="user-message-header">
                    <b>You:</b>
                    <button
                        class="message-action-btn user-pin-btn"
                        onclick="togglePinMessage(this)"
                        title="Pin important message"
                        aria-label="Pin important message">
                        📌 Pin
                    </button>
                </div>

                <div class="user-text">${escapeUserText(userDisplayMessage)}</div>

                <div class="user-actions">
                    <button
                        class="message-action-btn user-copy-btn"
                        onclick="copyUserMessage(this)"
                        title="Copy your message">
                        📋 Copy
                    </button>
                </div>
            </div>
        `;

        chat.scrollTop =
            chat.scrollHeight;

        conversations[
            currentConversation
        ].messages.push({
            role: "user",
            text: message,
            files:
                selectedFiles.map(
                    file => file.name
                ),
            fileRefs,
            pinned: false
        });

        touchConversation(
            conversations[currentConversation]
        );

        await saveConversation(
            conversations[
                currentConversation
            ]
        );

        renderHistory();
    }

    /* -----------------------------------------
       ⭐ CREATE THINKING BUBBLE FIRST
       ⭐ BEFORE FETCH
    ----------------------------------------- */

    const typingId =
        "typing-" +
        Date.now();

    chat.innerHTML += `
        <div class="bot-message">

            <div class="bot-header">

                <button
                    class="message-sound-btn"
                    onclick="speakAIMessage(this)"
                    title="Read this AI message aloud"
                    aria-label="Read this AI message aloud">
                    🔊
                </button>

                <b>Oddi AI:</b>

            </div>

            <div
                class="ai-content"
                id="${typingId}">
                <span class="thinking-indicator">
                    Thinking...
                </span>
            </div>

            <div class="bot-actions thinking-actions">
                <button
                    class="message-action-btn stop-generation-btn"
                    onclick="stopGeneration()"
                    title="Stop generating"
                    aria-label="Stop generating">
                    ■ Stop
                </button>
            </div>

        </div>
    `;

    const typing =
        document.getElementById(
            typingId
        );

    activeTypingElement = typing;
    activeGenerationConversation = currentConversation;

    const activeConversation = conversations[currentConversation];

    const scrollKey = activeConversation
        ? `oddi_chat_scroll_${getConversationKey(activeConversation)}`
        : '';

    const savedScroll = scrollKey
        ? Number(localStorage.getItem(scrollKey) || 0)
        : 0;
    requestAnimationFrame(() => {
        if (savedScroll > 0) {
            chat.scrollTop = Math.min(savedScroll, chat.scrollHeight);
        } else {
            chat.scrollTop = chat.scrollHeight;
        }
    });

    /* -----------------------------------------
       SEND TO BACKEND
    ----------------------------------------- */

    const formData =
        new FormData();

    formData.append(
        "message",
        message
    );

    formData.append(
        "history",
        JSON.stringify(
            conversations[
                currentConversation
            ].messages.slice(-100)
        )
    );

    selectedFiles.forEach(file => {

        formData.append(
            "files",
            file
        );
    });

    /* -----------------------------------------
       WAIT FOR AI
    ----------------------------------------- */

    try {

        const response =
            await fetch(
                "/chat",
                {
                    method: "POST",
                    body: formData,
                    signal: activeAbortController?.signal
                }
            );

        if (!response.ok) {
            throw new Error(
                await response.text()
            );
        }

        const reply =
            await response.text();

        if (generationStopped) {
            return;
        }

        /* -----------------------------------------
           CLEAR INPUT
        ----------------------------------------- */

        input.value = "";

        input.style.height =
            "auto";

        selectedFiles = [];

        fileInput.value = "";

        attachmentPreview.style.display =
            "none";

        updateActionButton();

        /* -----------------------------------------
           TYPE INTO THE EXISTING BUBBLE
        ----------------------------------------- */

        typing.innerHTML = "";

        if (!typingEnabled) {

            renderRichContent(typing, reply, { final: true });

            if (generationStopped) {
                return;
            }

            finishAIMessage(
                reply,
                message,
                typing,
                voiceReply
            );

        } else {

            await typeAIResponse(
                reply,
                typing
            );

            if (generationStopped) {
                return;
            }

            finishAIMessage(
                reply,
                message,
                typing,
                voiceReply
            );
        }

    } catch (error) {

        if (generationStopped || error?.name === "AbortError") {
            if (typing) {
                typing.innerHTML = "Generation stopped.";
            }
            return;
        }

        console.error(
            "Chat error:",
            error
        );

        /* -----------------------------------------
           DO NOT CREATE ANOTHER BUBBLE
           REUSE THE THINKING BUBBLE
        ----------------------------------------- */

        if (typing) {

            typing.innerHTML = `
                ⚠️ Sorry! Something went wrong.
            `;
        }

    } finally {

        input.disabled = false;
        activeAbortController = null;
        activeTypingElement = null;
        activeGenerationConversation = null;
        setGenerationUI(false);
        generationStopped = false;

        updateActionButton();

        if (!voiceReply) {
            input.focus();
        }

        chat.scrollTop =
            chat.scrollHeight;
    }
}

/* 
   TYPING ANIMATION
 */

function typeAIResponse(
    text,
    element
) {

    return new Promise(resolve => {

        let i = 0;

        activeTypingResolve = resolve;

        const startTime = performance.now();

        /*
         * Time-based typing.
         *
         * Important:
         * We do NOT depend on one character per timer tick.
         * This prevents background-tab timer throttling from
         * making generation appear to stop.
         */
        activeTypingInterval = setInterval(() => {

            if (generationStopped) {

                clearInterval(
                    activeTypingInterval
                );

                activeTypingInterval = null;
                activeTypingResolve = null;

                resolve();

                return;
            }

            /*
             * Calculate where we SHOULD be based on real elapsed time.
             *
             * 12ms ~= previous typing speed.
             */
            const elapsed =
                performance.now() - startTime;

            const targetIndex =
                Math.min(
                    text.length,
                    Math.floor(elapsed / 12)
                );

            if (targetIndex !== i) {

                i = targetIndex;

                /*
                 * Render Markdown continuously instead of
                 * showing raw Markdown during typing.
                 */
                renderRichContent(
                    element,
                    text.substring(0, i),
                    { final: false }
                );

                /*
                 * Highlight code blocks whenever they
                 * become available.
                 */
                element
                    .querySelectorAll("pre code")
                    .forEach(block => {

                        if (window.hljs) {
                            hljs.highlightElement(block);
                        }

                    });

                chat.scrollTop =
                    chat.scrollHeight;
            }

            /*
             * Finished.
             */
            if (i >= text.length) {

                clearInterval(
                    activeTypingInterval
                );

                activeTypingInterval = null;
                activeTypingResolve = null;

                /*
                 * One final complete Markdown render.
                 */
                renderRichContent(element, text, { final: true });

                element
                    .querySelectorAll("pre code")
                    .forEach(block => {

                        if (window.hljs) {
                            hljs.highlightElement(block);
                        }

                    });

                chat.scrollTop =
                    chat.scrollHeight;

                resolve();
            }

        }, 30);
    });
}

function addBotMessageActions(botMessage, messageIndex, conversationIndex = currentConversation) {
    if (!botMessage) return;

    botMessage.querySelector('.thinking-actions')?.remove();
    botMessage.querySelector('.bot-actions:not(.thinking-actions)')?.remove();

    const message =
        conversations[conversationIndex]?.messages[messageIndex];

    const feedback = message?.feedback || '';
    const pinned = !!message?.pinned;

    const actions = document.createElement('div');
    actions.className = 'bot-actions';
    actions.innerHTML = `
        <button
            class="message-action-btn bot-pin-btn ${pinned ? 'active' : ''}"
            onclick="togglePinMessage(this)"
            title="${pinned ? 'Unpin message' : 'Pin important message'}"
            aria-label="${pinned ? 'Unpin message' : 'Pin important message'}">
            ${pinned ? '📌 Pinned' : '📌 Pin'}
        </button>
        <button
            class="message-action-btn feedback-btn ${feedback === 'like' ? 'active' : ''}"
            data-feedback="like"
            onclick="setMessageFeedback(this, 'like')"
            title="Like response"
            aria-label="Like response">
            👍
        </button>
        <button
            class="message-action-btn feedback-btn ${feedback === 'dislike' ? 'active' : ''}"
            data-feedback="dislike"
            onclick="setMessageFeedback(this, 'dislike')"
            title="Dislike response"
            aria-label="Dislike response">
            👎
        </button>
        <button
            class="message-action-btn regenerate-btn"
            onclick="regenerateResponse(this)"
            title="Regenerate response"
            aria-label="Regenerate response">
            ↻ Regenerate
        </button>
        <button
            class="message-action-btn copy-btn"
            onclick="copyAIResponse(this)"
            title="Copy AI response"
            aria-label="Copy AI response">
            📋 Copy
        </button>
    `;

    botMessage.appendChild(actions);
}

/* 
   FINISH AI MESSAGE
 */

async function finishAIMessage(
    reply,
    userMessage,
    typing,
    voiceReply
) {

    if (generationStopped) return;

    if (
        conversations[
            currentConversation
        ].messages.length === 1
    ) {

        conversations[
            currentConversation
        ].title =
            userMessage;

        renderHistory();
    }

    const assistantIndex =
        conversations[currentConversation].messages.length;

    conversations[
        currentConversation
    ].messages.push({
        role: "assistant",
        text: reply,
        pinned: false,
        feedback: null
    });

    const botMessage = typing?.closest(".bot-message");

    if (botMessage) {
        botMessage.dataset.messageIndex = assistantIndex;
        addBotMessageActions(
            botMessage,
            assistantIndex
        );
    }

    touchConversation(
        conversations[currentConversation]
    );

    await saveConversation(
        conversations[
            currentConversation
        ]
    );

    renderHistory();

    if (voiceReply) {
        speakVoiceReply(reply);
    }

    chat.scrollTop =
        chat.scrollHeight;
}

/* 
   INPUT
 */

button.addEventListener(
    "click",
    () => sendMessage()
);

input.addEventListener(
    "keydown",
    event => {

        if (
            event.key === "Enter" &&
            !event.shiftKey
        ) {

            event.preventDefault();

            sendMessage();
        }
    }
);

input.addEventListener(
    "input",
    () => {

        input.style.height =
            "auto";

        input.style.height =
            Math.min(
                input.scrollHeight,
                180
            ) + "px";

        updateActionButton();
    }
);
