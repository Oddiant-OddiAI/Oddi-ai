/* 
   VOICE CONVERSATION
 */

let voiceModeActive = false;
let voiceResponseSpeaking = false;
let recognition = null;

// Voice recognition failure tracking
let voiceMissCount = 0;
let voiceReceivedResult = false;
let voiceErrorHandled = false;

const MAX_VOICE_MISSES = 3;

let voicePanel = null;
let voiceStatus = null;

function createVoicePanel() {

    if (voicePanel) return;

    voicePanel =
        document.createElement("div");

    voicePanel.id =
        "voice-mode-panel";

    voicePanel.innerHTML = `
        <div class="voice-mode-card">

            <button
                id="voice-close-btn"
                class="voice-close-btn"
                aria-label="Close voice mode">
                ✕
            </button>

            <div class="voice-orb">
                <div class="voice-orb-inner"></div>
            </div>

            <h2>Oddi AI</h2>

            <p id="voice-status">
                Listening...
            </p>

            <div
                id="voice-transcript"
                class="voice-transcript">
                Say something...
            </div>

            <button
                id="voice-stop-btn"
                class="voice-stop-btn">
                Stop voice chat
            </button>

        </div>
    `;

    document.body.appendChild(voicePanel);

    voiceStatus =
        document.getElementById(
            "voice-status"
        );

    document.getElementById(
        "voice-close-btn"
    ).onclick = stopVoiceMode;

    document.getElementById(
        "voice-stop-btn"
    ).onclick = stopVoiceMode;
}

function cleanSpeechText(text) {

    return String(text)

        /*
         * Remove emoji / pictographic characters.
         */
        .replace(
            /[\p{Extended_Pictographic}\p{Regional_Indicator}]/gu,
            ""
        )

        /*
         * Remove emoji variation selectors,
         * zero-width joiners and keycap markers.
         */
        .replace(
            /[\uFE0E\uFE0F\u200D\u20E3]/gu,
            ""
        )

        /*
         * Remove remaining emoji modifiers.
         */
        .replace(
            /[\u{1F3FB}-\u{1F3FF}]/gu,
            ""
        )

        /*
         * Remove fenced code blocks completely.
         * We don't want code formatting read aloud.
         */
        .replace(
            /```[\s\S]*?```/g,
            " "
        )

        /*
         * Remove Markdown headings.
         *
         * ### Heading
         * becomes:
         * Heading
         */
        .replace(
            /^\s{0,3}#{1,6}\s*/gm,
            ""
        )

        /*
         * Remove Markdown bullet points.
         *
         * - item
         * * item
         * + item
         */
        .replace(
            /^\s*[-*+]\s+/gm,
            ""
        )

        /*
         * Remove numbered-list formatting.
         *
         * 1. Tell me about yourself?
         * becomes:
         * Tell me about yourself?
         */
        .replace(
            /^\s*\d+[\.\)]\s+/gm,
            ""
        )

        /*
         * Remove Markdown blockquotes.
         */
        .replace(
            /^\s*>\s?/gm,
            ""
        )

        /*
         * Remove Markdown horizontal rules.
         */
        .replace(
            /^\s*([-*_])(?:\s*\1){2,}\s*$/gm,
            ""
        )

        /*
         * Remove Markdown bold / italic markers.
         *
         * **important**
         * *important*
         * becomes:
         * important
         */
        .replace(
            /(\*\*|__|\*|_)/g,
            ""
        )

        /*
         * Remove inline code markers.
         */
        .replace(
            /`([^`]+)`/g,
            "$1"
        )

        /*
         * Convert Markdown links to their visible text.
         *
         * [OpenAI](https://openai.com)
         * becomes:
         * OpenAI
         */
        .replace(
            /\[([^\]]+)\]\([^)]+\)/g,
            "$1"
        )

        /*
         * Remove remaining Markdown link brackets.
         */
        .replace(
            /[\[\]]/g,
            ""
        )

        /*
         * Remove table separators and pipes.
         *
         * | Question | Answer |
         * becomes natural speech.
         */
        .replace(
            /\|/g,
            " "
        )

        /*
         * Remove unnecessary slash characters.
         *
         * This prevents speech such as:
         * "slash"
         */
        .replace(
            /\s*\/\s*/g,
            " "
        )

        /*
         * Remove decorative symbols that can be spoken strangely.
         */
        .replace(
            /[~^]+/g,
            " "
        )

        /*
         * Normalize punctuation spacing.
         */
        .replace(
            /\s+([,.!?;:])/g,
            "$1"
        )

        /*
         * Clean excessive whitespace.
         */
        .replace(
            /\s{2,}/g,
            " "
        )

        .trim();
}

function updateVoiceStatus(
    text,
    transcript = ""
) {

    if (voiceStatus) {
        voiceStatus.textContent = text;
    }

    const transcriptBox =
        document.getElementById(
            "voice-transcript"
        );

    if (
        transcriptBox &&
        transcript
    ) {
        transcriptBox.textContent =
            transcript;
    }
}

function startVoiceRecognition() {

    if (
        !recognition ||
        !voiceModeActive ||
        voiceResponseSpeaking
    ) {
        return;
    }

    try {
        recognition.start();
    } catch (error) {

        if (
            error.name !==
            "InvalidStateError"
        ) {
            console.error(
                "Could not start voice recognition:",
                error
            );
        }
    }
}

function startVoiceMode() {

    if (!SpeechRecognition) {

        alert(
            "Voice conversation is not supported by this browser. Try Chrome or Edge."
        );

        return;
    }

    createVoicePanel();
    input.blur();
    voiceModeActive = true;

    voicePanel.classList.add("show");

    updateVoiceStatus(
        "Listening...",
        "Say something..."
    );

    startVoiceRecognition();
}

function stopVoiceMode() {

    voiceModeActive = false;
    voiceResponseSpeaking = false;

    if (recognition) {

        try {
            recognition.stop();
        } catch (e) {}
    }

    if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
    }

    voiceBtn.classList.remove(
        "listening"
    );

    voiceBtn.innerHTML = `
        <svg
            width="26"
            height="26"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round">
            <path d="M3 18v-6a9 9 0 0 1 18 0v6" />
            <path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3z" />
            <path d="M3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z" />
        </svg>
    `;

    voiceBtn.title =
        "Talk to Oddi";

    if (voicePanel) {
        voicePanel.classList.remove(
            "show"
        );
    }

    updateActionButton();
}

function getSelectedLanguage() {
    const languageSetting =
        document.getElementById("languageSetting");

    return languageSetting?.value || "en";
}

const speechLanguageMap = {
    en: "en-IN",
    hi: "hi-IN",
    bn: "bn-IN",
    mr: "mr-IN",
    gu: "gu-IN",
    ta: "ta-IN",
    te: "te-IN",
    kn: "kn-IN",
    ml: "ml-IN",
    pa: "pa-IN"
};

/* 
   AI VOICE SELECTION
 */

/* 
   AI VOICE SELECTION
 */

let availableSpeechVoices = [];
let selectedVoiceIndex =
    Number(localStorage.getItem("oddiVoiceIndex")) || 0;

function loadSpeechVoices() {

    if (!("speechSynthesis" in window)) {
        availableSpeechVoices = [];
        renderVoiceOptions();
        return;
    }

    const voices = window.speechSynthesis.getVoices();

    if (Array.isArray(voices) && voices.length) {
        availableSpeechVoices = voices;
        renderVoiceOptions();
        return;
    }

    /*
     * Some browsers (especially mobile Chrome/Android) populate the
     * speech-voice list asynchronously. Ask again a few times instead of
     * permanently showing “No voices available”. The onvoiceschanged event
     * below remains the primary update mechanism.
     */
    renderVoiceOptions();
}


if ("speechSynthesis" in window) {

    loadSpeechVoices();

    window.speechSynthesis.onvoiceschanged =
        loadSpeechVoices;

    /* Fallback polling for browsers that do not reliably fire
       onvoiceschanged. Stop as soon as voices become available. */
    let voiceLoadAttempts = 0;
    const voiceLoadTimer = setInterval(() => {
        voiceLoadAttempts += 1;
        loadSpeechVoices();
        if (availableSpeechVoices.length || voiceLoadAttempts >= 20) {
            clearInterval(voiceLoadTimer);
        }
    }, 250);
}


/* 
   VOICE OPTIONS UI
 */

function renderVoiceOptions() {

    const container =
        document.getElementById("voiceOptions");

    if (!container) return;

    if (!availableSpeechVoices.length) {

        container.innerHTML =
            `<p class="voice-loading">
                Loading voices...
             </p>`;

        return;
    }

    
    /*
     * Prefer voices matching the language selected in Settings.
     * Use the language map here rather than the old undefined
     * `selectedLanguage` variable (which caused a ReferenceError when
     * voices finally loaded).
     */
    const selectedSpeechLanguage =
        speechLanguageMap[getSelectedLanguage()] || "en-IN";

    let languageVoices =
        availableSpeechVoices.filter(voice =>
            String(voice.lang || "")
                .toLowerCase()
                .startsWith(
                    selectedSpeechLanguage
                        .toLowerCase()
                        .split("-")[0]
                )
        );


    /*
     * If the device doesn't have
     * voices for that language,
     * use available voices.
     */

    if (!languageVoices.length) {
        languageVoices =
            availableSpeechVoices;
    }


    /*
     * Show maximum 4 voices.
     */

    const voicesToShow =
        languageVoices.slice(0, 4);


    container.innerHTML = "";


    voicesToShow.forEach(
        (voice, index) => {

            const option =
                document.createElement("div");

            option.className =
                "voice-option";


            if (index === selectedVoiceIndex) {
                option.classList.add(
                    "selected"
                );
            }


            option.innerHTML = `
                <span class="voice-name">
                    Voice ${index + 1}
                </span>

                <button
                    type="button"
                    class="voice-preview-btn"
                    data-index="${index}">
                    ▶ Play
                </button>
            `;


            /*
             * Selecting the voice.
             */

            option.addEventListener(
                "click",
                () => {

                    selectedVoiceIndex =
                        index;

                    localStorage.setItem(
                        "oddiVoiceIndex",
                        index
                    );

                    renderVoiceOptions();
                }
            );


            /*
             * Preview button.
             */

            const previewButton =
                option.querySelector(
                    ".voice-preview-btn"
                );


            previewButton.addEventListener(
                "click",
                (event) => {

                    event.stopPropagation();

                    previewVoice(
                        voice,
                        previewButton
                    );
                }
            );


            container.appendChild(option);
        }
    );
}


/* 
   VOICE PREVIEW
 */

function previewVoice(
    voice,
    button
) {

    if (
        !("speechSynthesis" in window)
    ) {
        return;
    }


    /*
     * Stop any previous preview.
     */

    window.speechSynthesis.cancel();


    const previewText =
        "Hello! I am Oddi AI. This is a preview of my voice.";


    const utterance =
        new SpeechSynthesisUtterance(
            previewText
        );


    utterance.voice =
        voice;

    utterance.lang =
        voice.lang;

    utterance.rate = 1;
    utterance.pitch = 1;
    utterance.volume = 1;


    button.textContent =
        "⏹ Stop";


    utterance.onend = () => {

        button.textContent =
            "▶ Play";
    };


    utterance.onerror = () => {

        button.textContent =
            "▶ Play";
    };


    window.speechSynthesis.speak(
        utterance
    );
}


/* 
   GET SELECTED VOICE
 */

function getSelectedVoice() {

    if (!availableSpeechVoices.length) {
        loadSpeechVoices();
    }


    const selectedLanguage =
        speechLanguageMap[
            getSelectedLanguage()
        ] || "en-IN";


    let languageVoices =
        availableSpeechVoices.filter(
            voice =>
                voice.lang
                    .toLowerCase()
                    .startsWith(
                        selectedLanguage
                            .toLowerCase()
                            .split("-")[0]
                    )
        );


    if (!languageVoices.length) {
        languageVoices =
            availableSpeechVoices;
    }


    return (
        languageVoices[
            selectedVoiceIndex
        ] ||
        languageVoices[0] ||
        null
    );
}


/* Find the best available voice */

function getBestSpeechVoice(language, voiceType) {

    if (!availableSpeechVoices.length) {
        loadSpeechVoices();
    }

    const voices = availableSpeechVoices;

    if (!voices.length) {
        return null;
    }

    const languageCode =
        language.toLowerCase().split("-")[0];

    const languageVoices = voices.filter(voice =>
        voice.lang
            .toLowerCase()
            .startsWith(languageCode)
    );

    /*
     * Prefer voices matching the selected language.
     * If none exist, use all available voices.
     */
    const candidates =
        languageVoices.length
            ? languageVoices
            : voices;

    const femaleWords = [
        "female",
        "woman",
        "zira",
        "samantha",
        "susan",
        "karen",
        "victoria",
        "hazel",
        "google hindi",
        "google español",
        "google français"
    ];

    const maleWords = [
        "male",
        "man",
        "david",
        "mark",
        "alex",
        "daniel",
        "george",
        "james",
        "ravi"
    ];

    function scoreVoice(voice) {

        const name =
            voice.name.toLowerCase();

        let score = 0;

        /* Language match */
        if (
            voice.lang
                .toLowerCase()
                .startsWith(languageCode)
        ) {
            score += 100;
        }

        /* Prefer local/system voices */
        if (voice.localService) {
            score += 10;
        }

        /* Male */
        if (voiceType === "male") {

            if (
                maleWords.some(word =>
                    name.includes(word)
                )
            ) {
                score += 100;
            }

            if (
                femaleWords.some(word =>
                    name.includes(word)
                )
            ) {
                score -= 80;
            }
        }

        /* Female */
        if (voiceType === "female") {

            if (
                femaleWords.some(word =>
                    name.includes(word)
                )
            ) {
                score += 100;
            }

            if (
                maleWords.some(word =>
                    name.includes(word)
                )
            ) {
                score -= 80;
            }
        }

       

        return score;
    }

    return candidates
        .map(voice => ({
            voice,
            score: scoreVoice(voice)
        }))
        .sort(
            (a, b) =>
                b.score - a.score
        )[0]?.voice || null;
}

const languageSetting =
    document.getElementById("languageSetting");

if (languageSetting) {

    languageSetting.value =
        localStorage.getItem("oddiLanguage") || "en";

    languageSetting.addEventListener("change", () => {

        localStorage.setItem(
            "oddiLanguage",
            languageSetting.value
        );

        if (recognition) {
            recognition.lang =
                speechLanguageMap[languageSetting.value] || "en-IN";
        }

        /* Refresh the visible voice choices for the new language. */
        loadSpeechVoices();
    });
}

function speakVoiceReply(text) {

    if (
        !voiceModeActive ||
        !("speechSynthesis" in window)
    ) {
        return;
    }

    const cleanText =
        cleanSpeechText(text);

    if (!cleanText) return;

    voiceResponseSpeaking = true;

    updateVoiceStatus(
        "Oddi is speaking..."
    );

    if (recognition) {

        try {
            recognition.stop();
        } catch (e) {}
    }

    window.speechSynthesis.cancel();

    const utterance =
        new SpeechSynthesisUtterance(
            cleanText
        );

    utterance.lang =
        speechLanguageMap[getSelectedLanguage()] || "en-IN";
    
    const selectedVoice = getSelectedVoice();

    if (selectedVoice) {
        utterance.voice = selectedVoice;
        utterance.lang = selectedVoice.lang;
    } else {
        utterance.lang =
            speechLanguageMap[getSelectedLanguage()] || "en-IN";
    }

    utterance.rate = 1;
    utterance.pitch = 1;
    utterance.volume = 1;

    utterance.onend = () => {

        voiceResponseSpeaking = false;

        if (voiceModeActive) {

            updateVoiceStatus(
                "Listening...",
                "Say something..."
            );

            setTimeout(
                startVoiceRecognition,
                250
            );
        }
    };

    utterance.onerror = () => {

        voiceResponseSpeaking = false;

        if (voiceModeActive) {

            updateVoiceStatus(
                "Listening...",
                "Say something..."
            );

            setTimeout(
                startVoiceRecognition,
                250
            );
        }
    };

    window.speechSynthesis.speak(
        utterance
    );
}

if (SpeechRecognition) {

    recognition =
        new SpeechRecognition();

    recognition.lang =
        speechLanguageMap[getSelectedLanguage()] || "en-IN";
    recognition.continuous = false;
    recognition.interimResults = false;

    voiceBtn.onclick = () => {

        if (voiceModeActive) {
            stopVoiceMode();
        } else {
            startVoiceMode();
        }
    };

    recognition.onstart = () => {

        if (!voiceModeActive) return;

        // This is a fresh listening attempt.
        voiceReceivedResult = false;
        voiceErrorHandled = false;

        voiceBtn.classList.add(
            "listening"
        );

        voiceBtn.innerHTML = "🔴";

        voiceBtn.title =
            "Listening...";

        updateVoiceStatus(
            "Listening...",
            "I'm listening..."
        );
    };

    recognition.onresult = event => {

        if (!voiceModeActive) return;

        const transcript =
            event.results[0][0]
                .transcript
                .trim();

        // We successfully heard the user.
        voiceReceivedResult = true;
        voiceErrorHandled = false;

        // Reset consecutive failure counter.
        voiceMissCount = 0;

        if (!transcript) return;

        updateVoiceStatus(
            "Thinking...",
            `You said: "${transcript}"`
        );

        input.value = transcript;

        sendMessage(
            null,
            true
        );
    };
    
    function handleVoiceMiss() {

        if (
            !voiceModeActive ||
            voiceResponseSpeaking
        ) {
            return;
        }

        // Prevent the same recognition attempt
        // from being counted twice.
        if (voiceErrorHandled) {
            return;
        }

        voiceErrorHandled = true;
        voiceMissCount++;

        console.log(
            "Voice recognition miss:",
            voiceMissCount,
            "/",
            MAX_VOICE_MISSES
        );

        if (
            voiceMissCount >=
            MAX_VOICE_MISSES
        ) {

            updateVoiceStatus(
                "Voice chat ended",
                "Sorry, I couldn't hear you."
            );

            setTimeout(() => {

                if (voiceModeActive) {
                    stopVoiceMode();
                }

            }, 1200);

            return;
        }

        const retryMessage =
            "Sorry, I couldn't hear what you said. Please try again.";

        updateVoiceStatus(
            "I couldn't hear you",
            retryMessage
        );

        // Speak the retry message.
        speakVoiceReply(
            retryMessage
        );
    }


    recognition.onend = () => {

        voiceBtn.classList.remove(
            "listening"
        );

        if (!voiceModeActive) {
            return;
        }

        /*
        * Chrome can sometimes finish recognition because
        * no speech was detected without firing onerror.
        *
        * If we received no result, treat it as a missed attempt.
        */
        if (
            !voiceReceivedResult &&
            !voiceErrorHandled &&
            !voiceResponseSpeaking
        ) {
            handleVoiceMiss();
            return;
        }

        if (!voiceResponseSpeaking) {

            voiceBtn.innerHTML = "🎤";

            voiceBtn.title =
                "Listening...";
        }
    };

    recognition.onerror = event => {

        console.error(
            "Speech recognition error:",
            event.error
        );

        voiceBtn.classList.remove(
            "listening"
        );

        if (!voiceModeActive) {
            return;
        }

        // Permission problems are different from
        // simply not hearing the user.
        if (
            event.error ===
            "not-allowed"
        ) {

            updateVoiceStatus(
                "Microphone permission is required.",
                "Please allow microphone access and try again."
            );

            return;
        }

        // These errors generally mean that
        // the user's speech was not successfully captured.
        if (
            event.error === "no-speech" ||
            event.error === "audio-capture" ||
            event.error === "network" ||
            event.error === "aborted"
        ) {

            handleVoiceMiss();

            return;
        }

        // Any other recognition failure.
        handleVoiceMiss();
    };

} else {

    voiceBtn.onclick = () => {

        alert(
            "Voice conversation is not supported by this browser. Try Chrome or Edge."
        );
    };
}


(function () {
    function retryVoiceLoad() {
        try {
            if ("speechSynthesis" in window && typeof loadSpeechVoices === "function") {
                loadSpeechVoices();
            }
        } catch (_) {}
    }
    document.addEventListener("DOMContentLoaded", function () {
        retryVoiceLoad();
        [250, 750, 1500, 2500].forEach(function (delay) {
            setTimeout(retryVoiceLoad, delay);
        });
    });
    if ("speechSynthesis" in window) {
        window.speechSynthesis.addEventListener?.("voiceschanged", retryVoiceLoad);
    }
})();
