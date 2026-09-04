/* 
   COPY
 */

function copyAIResponse(button) {

    const message =
        button
            .closest(".bot-message")
            ?.querySelector(".ai-content");

    if (!message) return;

    navigator.clipboard
        .writeText(message.innerText)
        .then(() => {

            button.innerText = "✅ Copied!";

            setTimeout(() => {
                button.innerText = "📋 Copy";
            }, 1500);
        });
}

function copyUserMessage(button) {
    const message =
        button
            .closest(".user-message")
            ?.querySelector(".user-text");

    if (!message) return;

    navigator.clipboard
        .writeText(message.innerText)
        .then(() => {
            button.innerText = "✅ Copied!";

            setTimeout(() => {
                button.innerText = "📋 Copy";
            }, 1500);
        });
}

function getMessageFromButton(button) {
    const bubble = button.closest(".user-message, .bot-message");
    if (!bubble || currentConversation === null) return null;

    const index = Number(bubble.dataset.messageIndex);
    if (!Number.isInteger(index)) return null;

    const conversation = conversations[currentConversation];
    if (!conversation || !conversation.messages[index]) return null;

    return {
        bubble,
        index,
        message: conversation.messages[index]
    };
}

async function togglePinMessage(button) {
    const result = getMessageFromButton(button);
    if (!result) return;

    result.message.pinned = !result.message.pinned;
    result.bubble.classList.toggle("pinned-message", result.message.pinned);
    button.classList.toggle("active", result.message.pinned);
    button.textContent = result.message.pinned ? "📌 Pinned" : "📌 Pin";
    button.title = result.message.pinned ? "Unpin message" : "Pin important message";

    await saveConversation(conversations[currentConversation]);
}

async function setMessageFeedback(button, type) {
    const result = getMessageFromButton(button);
    if (!result || result.message.role !== "assistant") return;

    result.message.feedback =
        result.message.feedback === type ? null : type;

    const actions = result.bubble.querySelector(".bot-actions");
    if (actions) {
        actions.querySelectorAll(".feedback-btn").forEach(btn => {
            btn.classList.remove("active");
        });

        if (result.message.feedback) {
            const active = actions.querySelector(
                `.feedback-btn[data-feedback="${result.message.feedback}"]`
            );
            if (active) active.classList.add("active");
        }
    }

    /* Feedback is stored with the message and sent through the existing
       conversation save endpoint, so the host can inspect it with chat data. */
    await saveConversation(conversations[currentConversation]);
}

async function regenerateResponse(button) {
    if (generationActive) return;
    if (currentConversation === null) return;

    const result = getMessageFromButton(button);
    if (!result || result.message.role !== "assistant") return;

    const messages = conversations[currentConversation].messages;

    if (result.index !== messages.length - 1) {
        alert("Regenerate is available for the latest AI response.");
        return;
    }

    let userIndex = result.index - 1;

    while (userIndex >= 0 && messages[userIndex].role !== "user") {
        userIndex--;
    }

    if (userIndex < 0) return;

    const userMessage = messages[userIndex].text;

    /* Regenerate the latest answer without duplicating the user's message. */
    messages.splice(result.index, 1);
    await saveConversation(conversations[currentConversation]);

    await sendMessage(null, false, {
        skipUserMessage: true,
        regenerate: true,
        messageOverride: userMessage
    });
}

/* 
   MESSAGE SOUND
 */

function speakAIMessage(button) {

    if (
        !("speechSynthesis" in window)
    ) {
        alert(
            "Text-to-speech is not supported by this browser."
        );
        return;
    }

    if (
        button.classList.contains(
            "speaking"
        )
    ) {

        window.speechSynthesis.cancel();

        button.textContent = "🔊";

        button.classList.remove(
            "speaking"
        );

        return;
    }

    window.speechSynthesis.cancel();

    document
        .querySelectorAll(
            ".message-sound-btn.speaking"
        )
        .forEach(btn => {

            btn.textContent = "🔊";

            btn.classList.remove(
                "speaking"
            );
        });

    const message =
        button.closest(".bot-message");

    const content =
        message?.querySelector(
            ".ai-content"
        );

    if (!content) return;

    const text =
        cleanSpeechText(
            content.innerText
        );

    if (!text) return;

    const utterance =
        new SpeechSynthesisUtterance(
            text
        );
    const selectedLanguage =
        speechLanguageMap[
            getSelectedLanguage()
        ] || "en-IN";
    // Get currently selected Voice
    const selectedVoice =
        getSelectedVoice();

    if (selectedVoice) {

        utterance.voice =
            selectedVoice;

        utterance.lang =
            selectedVoice.lang;

    } else {

        utterance.lang =
            selectedLanguage;
    }

    


    

    if (selectedVoice) {
        utterance.voice =
            selectedVoice;

        utterance.lang =
            selectedVoice.lang;
    } else {
        utterance.lang =
            selectedLanguage;
    }

    utterance.rate = 1;
    utterance.pitch = 1;
    utterance.volume = 1;

    utterance.onstart = () => {

        button.textContent =
            "⏹️";

        button.classList.add(
            "speaking"
        );
    };

    utterance.onend = () => {

        button.textContent =
            "🔊";

        button.classList.remove(
            "speaking"
        );
    };

    utterance.onerror = () => {

        button.textContent =
            "🔊";

        button.classList.remove(
            "speaking"
        );
    };

    window.speechSynthesis.speak(
        utterance
    );
}
