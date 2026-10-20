(function () {
  "use strict";

  const setupPanel = document.getElementById("setupPanel");
  const practiceSessionsSection = document.getElementById("practiceSessionsSection");
  const practiceSessionList = document.getElementById("practiceSessionList");
  const practiceSessionCount = document.getElementById("practiceSessionCount");
  const clarificationPanel = document.getElementById("clarificationPanel");
  const questionsPanel = document.getElementById("questionsPanel");
  const professionForm = document.getElementById("professionForm");
  const clarificationForm = document.getElementById("clarificationForm");
  const professionInput = document.getElementById("professionInput");
  const roleDetailsInput = document.getElementById("roleDetailsInput");
  const roleDisplay = document.getElementById("selectedProfession");
  const questionList = document.getElementById("questionList");
  const statusNode = document.getElementById("studioStatus");
  const generateButton = document.getElementById("generateButton");
  const continueButton = document.getElementById("continueButton");
  const submitButton = document.getElementById("submitAnswersButton");
  const answerAllQuestionsButton = document.getElementById("answerAllQuestionsButton");
  const answerSheetSection = document.getElementById("answerSheetSection");
  const answerSheetContent = document.getElementById("answerSheetContent");
  const answerFollowups = document.getElementById("answerFollowups");
  const hideAnswerSheetButton = document.getElementById("hideAnswerSheetButton");
  const answerAllToggle = document.getElementById("answerAllToggle");
  const sessionSaveState = document.getElementById("sessionSaveState");
  const feedbackSection = document.getElementById("feedbackSection");
  const feedbackText = document.getElementById("feedbackText");
  const feedbackActionButtons = Array.from(document.querySelectorAll("[data-follow-up]"));
  const showPreviousAnswersButton = document.getElementById("showPreviousAnswersButton");
  const previousAnswersSection = document.getElementById("previousAnswersSection");
  const previousAnswersTitle = document.getElementById("previousAnswersTitle");
  const previousAnswersContent = document.getElementById("previousAnswersContent");
  const hidePreviousAnswersButton = document.getElementById("hidePreviousAnswersButton");
  const answeredCount = document.getElementById("answeredCount");
  const totalCount = document.getElementById("totalCount");
  const progressTrack = document.querySelector(".progress-track");
  const progressFill = document.getElementById("progressFill");
  const submitHint = document.getElementById("submitHint");

  let profession = "";
  let roleContext = "";
  let questions = [];
  let answers = [];
  let questionSampleAnswers = [];
  let answerSources = [];
  let sessionId = "";
  let sessionServerAvailable = true;
  let sessionCreatedAt = "";
  let sessionReviewText = "";
  let sessionFormattedAnswers = "";
  let statusTimeout = 0;
  let saveTimeout = 0;
  let saveQueue = Promise.resolve();
  let restoringSession = false;
  let answerSheetRequestToken = 0;
  let previousAnswersRequestToken = 0;
  let previousAnswersCache = null;
  let sessionReviewed = false;
  let activeRecognition = null;
  let activeSpeakButton = null;
  const userKey = document.querySelector(".studio-shell").dataset.userKey || "guest";
  const localFallbackKey = "oddi-interview-studio-local-v1:" + userKey;
  let localDatabasePromise = null;

  function openLocalSessionDatabase() {
    if (!window.indexedDB) return Promise.resolve(null);
    if (localDatabasePromise) return localDatabasePromise;
    localDatabasePromise = new Promise(function (resolve) {
      let request;
      try {
        request = window.indexedDB.open("oddi-interview-studio", 1);
      } catch (_) {
        resolve(null);
        return;
      }
      request.onupgradeneeded = function () {
        const db = request.result;
        if (!db.objectStoreNames.contains("sessions")) {
          const store = db.createObjectStore("sessions", { keyPath: "id" });
          store.createIndex("user_key", "user_key", { unique: false });
        }
      };
      request.onsuccess = function () { resolve(request.result); };
      request.onerror = function () { resolve(null); };
      request.onblocked = function () { resolve(null); };
    });
    return localDatabasePromise;
  }

  function localStorageSessions() {
    try {
      const value = JSON.parse(window.localStorage.getItem(localFallbackKey) || "[]");
      return Array.isArray(value) ? value.filter(function (item) { return item && item.id; }) : [];
    } catch (_) {
      return [];
    }
  }

  async function readLocalSessions() {
    const db = await openLocalSessionDatabase();
    if (!db) return localStorageSessions();
    return new Promise(function (resolve) {
      try {
        const request = db.transaction("sessions", "readonly").objectStore("sessions").index("user_key").getAll(userKey);
        request.onsuccess = function () {
          resolve(Array.isArray(request.result) && request.result.length ? request.result : localStorageSessions());
        };
        request.onerror = function () { resolve(localStorageSessions()); };
      } catch (_) {
        resolve(localStorageSessions());
      }
    });
  }

  async function readLocalSession(id) {
    const db = await openLocalSessionDatabase();
    if (!db) return localStorageSessions().find(function (item) { return String(item.id) === String(id); }) || null;
    return new Promise(function (resolve) {
      try {
        const request = db.transaction("sessions", "readonly").objectStore("sessions").get(String(id));
        request.onsuccess = function () {
          const value = request.result;
          resolve(value && value.user_key === userKey ? value : (localStorageSessions().find(function (item) { return String(item.id) === String(id); }) || null));
        };
        request.onerror = function () { resolve(localStorageSessions().find(function (item) { return String(item.id) === String(id); }) || null); };
      } catch (_) {
        resolve(localStorageSessions().find(function (item) { return String(item.id) === String(id); }) || null);
      }
    });
  }

  async function writeLocalSession(session) {
    const record = Object.assign({}, session, { user_key: userKey });
    const db = await openLocalSessionDatabase();
    if (db) {
      const saved = await new Promise(function (resolve) {
        try {
          const transaction = db.transaction("sessions", "readwrite");
          transaction.objectStore("sessions").put(record);
          transaction.oncomplete = function () { resolve(true); };
          transaction.onerror = function () { resolve(false); };
          transaction.onabort = function () { resolve(false); };
        } catch (_) {
          resolve(false);
        }
      });
      if (saved) return true;
    }
    try {
      const sessions = localStorageSessions().filter(function (item) { return String(item.id) !== String(record.id); });
      sessions.push(record);
      sessions.sort(function (left, right) { return String(right.updated_at || "").localeCompare(String(left.updated_at || "")); });
      window.localStorage.setItem(localFallbackKey, JSON.stringify(sessions));
      return true;
    } catch (_) {
      return false;
    }
  }

  function makeLocalSessionId() {
    const suffix = window.crypto && typeof window.crypto.randomUUID === "function"
      ? window.crypto.randomUUID()
      : Date.now().toString(36) + Math.random().toString(36).slice(2);
    return "local-" + suffix;
  }

  function buildLocalSessionRecord() {
    const snapshot = currentSessionSnapshot();
    const now = new Date().toISOString();
    return {
      id: sessionId,
      profession: profession,
      context: roleContext,
      questions: snapshot.questions,
      answers: snapshot.answers,
      question_sample_answers: snapshot.question_sample_answers,
      answer_sources: snapshot.answer_sources,
      status: sessionReviewed ? "completed" : "in_progress",
      formatted_answers: sessionFormattedAnswers,
      review: sessionReviewText,
      created_at: sessionCreatedAt || now,
      updated_at: now
    };
  }

  async function persistLocalSession() {
    if (!sessionId || ![5, 10].includes(questions.length)) return false;
    return writeLocalSession(buildLocalSessionRecord());
  }

  function setStatus(message, kind) {
    window.clearTimeout(statusTimeout);
    statusNode.textContent = message;
    statusNode.className = "studio-status" + (kind ? " is-" + kind : "");
    statusNode.hidden = false;
    if (kind !== "error") {
      statusTimeout = window.setTimeout(function () { statusNode.hidden = true; }, 7000);
    }
  }

  function clearStatus() {
    window.clearTimeout(statusTimeout);
    statusNode.hidden = true;
    statusNode.textContent = "";
    statusNode.className = "studio-status";
  }

  function setSaveState(message, kind) {
    if (!sessionSaveState) return;
    sessionSaveState.textContent = message || "";
    sessionSaveState.className = "session-save-state" + (kind ? " is-" + kind : "");
  }

  function setButtonBusy(button, busy, busyText) {
    const label = button.querySelector(".button-label");
    if (!label) return;
    if (busy) {
      button.dataset.idleLabel = label.textContent;
      button.disabled = true;
      label.textContent = busyText;
    } else {
      button.disabled = false;
      label.textContent = button.dataset.idleLabel || label.textContent;
      delete button.dataset.idleLabel;
    }
  }

  async function requestJson(path, method, body, keepalive) {
    let response;
    const options = {
      method: method || "GET",
      credentials: "same-origin",
      headers: { "Accept": "application/json" },
      cache: "no-store"
    };
    if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    if (keepalive) options.keepalive = true;
    try {
      response = await fetch(path, options);
    } catch (_) {
      throw new Error("Couldn't reach ODDI. Check your connection and try again.");
    }
    const result = await response.json().catch(function () { return {}; });
    if (!response.ok) {
      if (response.status === 401) throw new Error("Your session ended. Sign in again, then reopen Interview Studio.");
      throw new Error(result.error || result.detail || "ODDI couldn't complete this step. Please try again.");
    }
    return result;
  }

  function postJson(path, body) {
    return requestJson(path, "POST", body);
  }

  function setSessionUrl(id) {
    const url = new URL(window.location.href);
    if (id) url.searchParams.set("session", id);
    else url.searchParams.delete("session");
    window.history.replaceState(null, "", url.pathname + url.search + url.hash);
  }

  function setAnswerAllMode(enabled) {
    questionList.classList.toggle("is-answer-all-mode", enabled);
    answerAllToggle.setAttribute("aria-pressed", String(enabled));
    answerAllToggle.querySelector(".answer-all-toggle-label").textContent =
      enabled ? "Return to question cards" : "Answer all at once";
  }

  function showClarification(message) {
    setupPanel.hidden = true;
    practiceSessionsSection.hidden = true;
    questionsPanel.hidden = true;
    clarificationPanel.hidden = false;
    document.getElementById("clarificationText").textContent = message;
    roleDetailsInput.value = roleContext;
    window.setTimeout(function () { roleDetailsInput.focus(); }, 30);
  }

  function currentSessionSnapshot() {
    const cards = Array.from(questionList.querySelectorAll(".question-card"));
    const currentAnswers = cards.map(getAnswer);
    answers = currentAnswers;
    answerSources = currentAnswers.map(function (answer, index) {
      if (answer) return "candidate";
      return questionSampleAnswers[index] ? "oddi_sample" : "unanswered";
    });
    return {
      questions: questions,
      answers: currentAnswers,
      question_sample_answers: questionSampleAnswers,
      answer_sources: answerSources
    };
  }

  function saveSessionNow(keepalive) {
    window.clearTimeout(saveTimeout);
    saveTimeout = 0;
    if (!sessionId || ![5, 10].includes(questions.length)) return Promise.resolve();

    const savingId = sessionId;
    const snapshot = currentSessionSnapshot();
    if (sessionReviewed) {
      void persistLocalSession();
      return Promise.resolve({ local: true });
    }
    if (!sessionServerAvailable) {
      return persistLocalSession().then(function (saved) {
        setSaveState(saved ? "Saved on this device." : "This device couldn't save the practice.", saved ? "" : "error");
        return { local: true };
      });
    }
    setSaveState("Saving your progress...", "saving");
    const task = saveQueue.catch(function () {}).then(function () {
      return persistLocalSession();
    }).then(function (savedLocally) {
      return requestJson(
        "/api/interview/sessions/" + encodeURIComponent(savingId),
        "PATCH",
        snapshot,
        keepalive
      ).then(function (result) {
        result.local_backup_saved = Boolean(savedLocally);
        return result;
      });
    }).then(function (result) {
      if (sessionId === savingId) {
        setSaveState(result.local_backup_saved ? "Saved to your account and this device." : "Saved to your account; this device couldn't make a backup.", result.local_backup_saved ? "" : "error");
      }
      return result;
    }).catch(function (error) {
      if (sessionId === savingId) setSaveState("Saved on this device; account sync failed. Try again.", "error");
      throw error;
    });
    saveQueue = task;
    return task;
  }

  function scheduleSessionSave() {
    if (!sessionId || restoringSession) return;
    window.clearTimeout(saveTimeout);
    setSaveState("Saving your progress...", "saving");
    saveTimeout = window.setTimeout(function () {
      void saveSessionNow().catch(function () {});
    }, 650);
  }

  function showQuestions() {
    roleDisplay.textContent = profession;
    setupPanel.hidden = true;
    practiceSessionsSection.hidden = true;
    clarificationPanel.hidden = true;
    questionsPanel.hidden = false;
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function createQuestions(button) {
    clearStatus();
    setButtonBusy(button, true, "ODDI is preparing your questions...");
    try {
      const result = await postJson("/api/interview/questions", {
        profession: profession,
        context: roleContext
      });
      if (result.clarification) {
        showClarification(result.clarification);
        return;
      }
      if (!Array.isArray(result.questions) || result.questions.length !== 10) {
        throw new Error("ODDI didn't return a complete set. Please try again.");
      }
      questions = result.questions;
      answers = Array(questions.length).fill("");
      questionSampleAnswers = Array(questions.length).fill("");
      answerSources = Array(questions.length).fill("unanswered");
      sessionServerAvailable = Boolean(result.session_id);
      sessionId = String(result.session_id || makeLocalSessionId());
      sessionCreatedAt = new Date().toISOString();
      sessionReviewText = "";
      sessionFormattedAnswers = "";
      sessionReviewed = false;
      setSessionUrl(sessionId);
      feedbackText.textContent = "";
      clearPreviousAnswers();
      feedbackSection.hidden = true;
      feedbackSection.dataset.visible = "false";
      setAnswerAllMode(false);
      showQuestions();

      restoringSession = true;
      renderQuestions();
      updateProgress();
      restoringSession = false;

      if (sessionId) {
        void persistLocalSession();
        setSaveState(sessionServerAvailable ? "Practice saved to your account and this device." : "Practice saved on this device.");
        void loadSavedSessions(false);
        setStatus("Your 10 questions are ready. Take them one at a time.", "success");
        if (!sessionServerAvailable) {
          setStatus(result.session_error || "This practice is saved on this device. It couldn't be synced to your account yet.", "error");
        }
      }
    } catch (error) {
      restoringSession = false;
      setStatus(error.message || "ODDI couldn't prepare these questions. Please try again.", "error");
    } finally {
      setButtonBusy(button, false);
    }
  }

  professionForm.addEventListener("submit", function (event) {
    event.preventDefault();
    profession = professionInput.value.trim();
    roleContext = "";
    sessionId = "";
    if (!profession) {
      professionInput.focus();
      return;
    }
    roleDisplay.textContent = profession;
    void createQuestions(generateButton);
  });

  clarificationForm.addEventListener("submit", function (event) {
    event.preventDefault();
    roleContext = roleDetailsInput.value.trim();
    if (!roleContext) {
      roleDetailsInput.focus();
      return;
    }
    clarificationPanel.hidden = true;
    setupPanel.hidden = true;
    practiceSessionsSection.hidden = true;
    questionsPanel.hidden = true;
    roleDisplay.textContent = profession;
    void createQuestions(continueButton);
  });

  function getAnswer(card) {
    const textArea = card.querySelector("textarea");
    const spokenText = textArea ? textArea.value.trim() : "";
    const checked = card.querySelector('input[type="radio"]:checked');
    if (checked && spokenText) return checked.value + "\nSpoken response: " + spokenText;
    return checked ? checked.value : spokenText;
  }

  function updateProgress() {
    const cards = Array.from(questionList.querySelectorAll(".question-card"));
    const currentAnswers = cards.map(getAnswer);
    answers = currentAnswers;
    answerSources = currentAnswers.map(function (answer, index) {
      if (answer) return "candidate";
      return questionSampleAnswers[index] ? "oddi_sample" : "unanswered";
    });
    const answered = currentAnswers.filter(Boolean).length + currentAnswers.reduce(function (count, answer, index) {
      return count + (!answer && answerSources[index] === "oddi_sample" ? 1 : 0);
    }, 0);
    const total = cards.length || 10;
    answeredCount.textContent = String(answered);
    totalCount.textContent = String(total);
    progressTrack.setAttribute("aria-valuemax", String(total));
    progressTrack.setAttribute("aria-valuenow", String(answered));
    progressFill.style.width = (total ? (answered / total) * 100 : 0) + "%";
    submitHint.textContent = answered === total
      ? "Your responses and ODDI's samples are ready for an oral-style review."
      : "Answer every question or ask ODDI for a sample answer first.";
    scheduleSessionSave();
  }

  function makeElement(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function dispatchAnswerInput(textarea) {
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    textarea.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function startAnswerRecognition(textarea, button, status) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      status.textContent = "Voice input isn't available in this browser.";
      status.classList.add("is-error");
      return;
    }
    if (activeRecognition) {
      try { activeRecognition.stop(); } catch (_) { /* recognition may already be stopping */ }
    }

    const recognition = new SpeechRecognition();
    activeRecognition = recognition;
    const baseText = textarea.value.trim();
    recognition.lang = "en-IN";
    recognition.interimResults = true;
    recognition.continuous = false;
    button.classList.add("is-listening");
    button.setAttribute("aria-pressed", "true");
    button.querySelector(".answer-mic-label").textContent = "Listening... click to stop";
    status.classList.remove("is-error");
    status.textContent = "Speak naturally. Your words will appear here.";

    recognition.onresult = function (event) {
      const transcript = Array.from(event.results).map(function (result) {
        return result[0] && result[0].transcript ? result[0].transcript.trim() : "";
      }).filter(Boolean).join(" ");
      textarea.value = [baseText, transcript].filter(Boolean).join(" ");
      const card = textarea.closest(".question-card");
      if (card && card.dataset.questionType === "multiple_choice") {
        const choiceMatch = transcript.match(/^(?:option|choice|answer)?\s*([a-d])(?:\b|\s|[.,])/i);
        const options = Array.from(card.querySelectorAll('input[type="radio"]'));
        if (choiceMatch && options[choiceMatch[1].toUpperCase().charCodeAt(0) - 65]) {
          options[choiceMatch[1].toUpperCase().charCodeAt(0) - 65].checked = true;
        } else {
          const optionIndex = options.findIndex(function (input) {
            const label = input.closest("label");
            return label && label.querySelector(".choice-copy").textContent.trim().toLocaleLowerCase() === transcript.toLocaleLowerCase();
          });
          if (optionIndex >= 0) options[optionIndex].checked = true;
        }
      }
      dispatchAnswerInput(textarea);
    };
    recognition.onerror = function (event) {
      const messages = {
        "not-allowed": "Allow microphone access in your browser to use voice input.",
        "service-not-allowed": "Voice input is blocked by this browser or device.",
        "no-speech": "No speech was detected. Try again when you're ready.",
        "audio-capture": "No microphone was found. Check your microphone connection."
      };
      status.textContent = messages[event.error] || "Voice input stopped. Please try again.";
      status.classList.add("is-error");
    };
    recognition.onend = function () {
      if (activeRecognition === recognition) activeRecognition = null;
      button.classList.remove("is-listening");
      button.setAttribute("aria-pressed", "false");
      button.querySelector(".answer-mic-label").textContent = "Speak your answer";
      if (!status.classList.contains("is-error")) status.textContent = textarea.value.trim() ? "Transcript added to your answer." : "";
    };
    try {
      recognition.start();
    } catch (_) {
      if (activeRecognition === recognition) activeRecognition = null;
      button.classList.remove("is-listening");
      button.setAttribute("aria-pressed", "false");
      button.querySelector(".answer-mic-label").textContent = "Speak your answer";
      status.textContent = "Microphone couldn't start. Please try again.";
      status.classList.add("is-error");
    }
  }

  function makeAnswerInput(index, previousAnswer, multipleChoice) {
    const block = makeElement("div", "answer-input-block");
    const label = makeElement("label", "answer-field-label", multipleChoice ? "Optional spoken response or explanation" : "Your spoken or written answer");
    const textarea = document.createElement("textarea");
    const textareaId = "interview-answer-text-" + index;
    textarea.id = textareaId;
    label.htmlFor = textareaId;
    textarea.className = "written-answer";
    textarea.rows = 3;
    textarea.maxLength = 10000;
    textarea.placeholder = multipleChoice ? "Say or explain your selected option..." : "Write your answer or use the microphone...";
    textarea.setAttribute("aria-label", (multipleChoice ? "Optional spoken response" : "Your answer") + " to question " + (index + 1));
    textarea.value = previousAnswer || "";

    const tools = makeElement("div", "answer-input-tools");
    const micButton = makeElement("button", "answer-mic-button");
    micButton.type = "button";
    micButton.setAttribute("aria-pressed", "false");
    micButton.innerHTML = '<svg class="answer-mic-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.93V21h2v-3.07A7 7 0 0 0 19 11h-2Z"/></svg><span class="answer-mic-label">Speak your answer</span>';
    const voiceStatus = makeElement("span", "answer-voice-status");
    if (!(window.SpeechRecognition || window.webkitSpeechRecognition)) {
      micButton.disabled = true;
      voiceStatus.textContent = "Voice input isn't available in this browser.";
    } else {
      micButton.addEventListener("click", function () {
        if (micButton.getAttribute("aria-pressed") === "true" && activeRecognition) {
          try { activeRecognition.stop(); } catch (_) { /* recognition may already be stopping */ }
          return;
        }
        startAnswerRecognition(textarea, micButton, voiceStatus);
      });
    }
    tools.append(micButton, voiceStatus);
    block.append(label, textarea, tools);
    return block;
  }

  function speakAnswer(text, button) {
    if (!window.speechSynthesis || typeof window.SpeechSynthesisUtterance !== "function") {
      setStatus("Spoken answers aren't available in this browser. You can still read the sample answer.", "error");
      return;
    }
    if (window.speechSynthesis.speaking && activeSpeakButton === button) {
      window.speechSynthesis.cancel();
      activeSpeakButton = null;
      button.textContent = "Listen to answer";
      return;
    }
    if (window.speechSynthesis.speaking) window.speechSynthesis.cancel();
    if (activeSpeakButton) activeSpeakButton.textContent = "Listen to answer";
    const utterance = new window.SpeechSynthesisUtterance(text);
    utterance.lang = "en-IN";
    utterance.onend = utterance.onerror = function () {
      if (activeSpeakButton === button) {
        activeSpeakButton = null;
        button.textContent = "Listen to answer";
      }
    };
    activeSpeakButton = button;
    button.textContent = "Stop speaking";
    window.speechSynthesis.speak(utterance);
  }

  function appendReviewText(container, text) {
    const parts = String(text || "").split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
    parts.forEach(function (part) {
      if (part.startsWith("**") && part.endsWith("**")) {
        container.appendChild(makeElement("strong", "", part.slice(2, -2)));
      } else if (part.startsWith("*") && part.endsWith("*")) {
        container.appendChild(makeElement("em", "", part.slice(1, -1)));
      } else if (part) {
        container.appendChild(document.createTextNode(part));
      }
    });
  }

  function renderFeedback(text) {
    feedbackText.replaceChildren();
    const lines = String(text || "ODDI received your answers but did not return feedback.").split(/\r?\n/);
    let paragraph = [];
    let list = null;
    let listKind = "";

    function flushParagraph() {
      if (!paragraph.length) return;
      const node = makeElement("p");
      appendReviewText(node, paragraph.join(" "));
      feedbackText.appendChild(node);
      paragraph = [];
    }

    lines.forEach(function (rawLine) {
      const line = rawLine.trim();
      if (!line || /^-{3,}$/.test(line)) {
        flushParagraph();
        list = null;
        listKind = "";
        return;
      }

      const heading = line.match(/^#{1,4}\s+(.+)$/);
      if (heading) {
        flushParagraph();
        list = null;
        listKind = "";
        const node = makeElement("h3", "feedback-subheading");
        appendReviewText(node, heading[1]);
        feedbackText.appendChild(node);
        return;
      }

      const ordered = line.match(/^\d+[.)]\s+(.+)$/);
      const unordered = line.match(/^(?:[-*•])\s+(.+)$/);
      if (ordered || unordered) {
        flushParagraph();
        const kind = ordered ? "ol" : "ul";
        if (!list || listKind !== kind) {
          list = makeElement(kind, "feedback-list");
          listKind = kind;
          feedbackText.appendChild(list);
        }
        const item = makeElement("li");
        appendReviewText(item, (ordered || unordered)[1]);
        list.appendChild(item);
        return;
      }

      list = null;
      listKind = "";
      paragraph.push(line);
    });
    flushParagraph();
  }

  function buildQuestionCard(question, index, previousAnswer) {
    const card = makeElement("article", "question-card");
    card.dataset.questionIndex = String(index);
    card.dataset.questionType = question.type === "multiple_choice" ? "multiple_choice" : "written";
    card.style.animationDelay = Math.min(index * 35, 280) + "ms";

    const meta = makeElement("div", "question-meta");
    meta.appendChild(makeElement("span", "question-number", String(index + 1).padStart(2, "0")));
    const multipleChoice = question.type === "multiple_choice";
    meta.appendChild(makeElement("span", "question-type", multipleChoice ? "Multiple choice" : "Written answer"));
    card.appendChild(meta);

    const title = makeElement("h2", "", "Q" + (index + 1) + ". " + question.question);
    title.id = "interview-question-" + index;
    card.appendChild(title);

    if (multipleChoice) {
      const choices = makeElement("div", "choice-list");
      choices.setAttribute("role", "radiogroup");
      choices.setAttribute("aria-labelledby", title.id);
      (question.options || []).forEach(function (option, optionIndex) {
        const letter = String.fromCharCode(65 + optionIndex);
        const label = makeElement("label", "choice-option");
        const radio = document.createElement("input");
        radio.type = "radio";
        radio.name = "interview-answer-" + index;
        radio.value = letter + ". " + option;
        radio.checked = previousAnswer === radio.value || previousAnswer.indexOf(radio.value + "\nSpoken response:") === 0;
        const badge = makeElement("span", "choice-letter", letter);
        const copy = makeElement("span", "choice-copy", option);
        label.append(radio, badge, copy);
        choices.appendChild(label);
      });
      card.appendChild(choices);
    }
    const savedSpokenAnswer = question.type === "multiple_choice"
      ? (String(previousAnswer || "").match(/\nSpoken response:\s*([\s\S]*)$/) || [])[1] || ""
      : previousAnswer;
    card.appendChild(makeAnswerInput(index, savedSpokenAnswer, question.type === "multiple_choice"));

    const actions = makeElement("div", "question-actions");
    const answerButton = makeElement("button", "question-action answer-action");
    answerButton.type = "button";
    answerButton.setAttribute("aria-expanded", "false");
    answerButton.innerHTML = '<span class="question-action-icon" aria-hidden="true">↳</span><span>Answer it</span>';
    answerButton.addEventListener("click", function () {
      void answerQuestion(question, index, card, answerButton);
    });

    const differentButton = makeElement("button", "question-action different-action");
    differentButton.type = "button";
    differentButton.innerHTML = '<span class="question-action-icon" aria-hidden="true">⟳</span><span>Need a different question?</span>';
    differentButton.addEventListener("click", function () {
      void replaceQuestion(card, index, differentButton);
    });
    actions.append(answerButton, differentButton);
    card.appendChild(actions);
    const cardStatus = makeElement("div", "card-status");
    cardStatus.setAttribute("role", "status");
    card.appendChild(cardStatus);
    if (questionSampleAnswers[index]) renderQuestionSampleAnswer(card, index, questionSampleAnswers[index], false);
    return card;
  }

  function renderQuestionSampleAnswer(card, index, answer, speakOnDisplay) {
    let answerPanel = card.querySelector(".sample-answer");
    if (!answerPanel) {
      answerPanel = makeElement("section", "sample-answer");
      answerPanel.id = "interview-sample-answer-" + index;
      answerPanel.setAttribute("aria-live", "polite");
      card.insertBefore(answerPanel, card.querySelector(".card-status"));
    }
    answerPanel.replaceChildren(
      makeElement("strong", "sample-answer-title", "ODDI's sample answer"),
      makeElement("div", "sample-answer-copy", answer)
    );
    answerPanel.dataset.answer = answer;
    const listen = makeElement("button", "answer-speak-button", "Listen to answer");
    listen.type = "button";
    listen.addEventListener("click", function () { speakAnswer(answer, listen); });
    answerPanel.appendChild(listen);
    const answerButton = card.querySelector(".answer-action");
    if (answerButton) {
      answerButton.setAttribute("aria-controls", answerPanel.id);
      answerButton.setAttribute("aria-expanded", "true");
    }
    questionSampleAnswers[index] = answer;
    const currentAnswer = getAnswer(card);
    answerSources[index] = currentAnswer ? "candidate" : "oddi_sample";
    if (!answerSheetSection.hidden) renderAnswerSheet(questionSampleAnswers, questions);
    if (speakOnDisplay) speakAnswer(answer, listen);
    return listen;
  }

  async function answerQuestion(question, index, card, button) {
    if (button.disabled) return;
    const cardStatus = card.querySelector(".card-status");
    const label = button.querySelector("span:last-child");
    const originalLabel = label.textContent;
    button.disabled = true;
    button.setAttribute("aria-expanded", "true");
    label.textContent = "ODDI is answering...";
    const previousAnswer = questionSampleAnswers[index] || "";
    cardStatus.textContent = "ODDI is preparing a spoken sample answer...";
    cardStatus.classList.remove("is-error");

    try {
      currentSessionSnapshot();
      if (sessionServerAvailable) await saveSessionNow();
      else await persistLocalSession();
      const result = await postJson("/api/interview/answer", {
        profession: profession,
        context: roleContext,
        session_id: sessionServerAvailable ? sessionId : "",
        question_index: index,
        question: question.question,
        question_type: question.type === "multiple_choice" ? "multiple_choice" : "written",
        options: question.type === "multiple_choice" ? (question.options || []) : []
      });
      if (!result.answer || typeof result.answer !== "string") throw new Error("ODDI didn't return a sample answer.");
      if (!questions[index] || questions[index].question !== question.question) return;
      cardStatus.textContent = "";
      renderQuestionSampleAnswer(card, index, result.answer, true);
      await persistLocalSession();
      if (sessionServerAvailable) await saveSessionNow();
      answerFollowups.hidden = false;
      updateProgress();
      card.querySelector(".sample-answer").scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (error) {
      if (previousAnswer && questions[index] && questions[index].question === question.question) {
        renderQuestionSampleAnswer(card, index, previousAnswer, false);
      }
      cardStatus.textContent = error.message || "ODDI couldn't answer this question. Please try again.";
      cardStatus.classList.add("is-error");
    } finally {
      button.disabled = false;
      label.textContent = originalLabel;
    }
  }

  function renderQuestions() {
    clearAnswerSheet();
    const count = questions.length || 10;
    const existingSampleCount = questionSampleAnswers.filter(Boolean).length;
    document.getElementById("answerSheetTitle").textContent = existingSampleCount && existingSampleCount < count
      ? existingSampleCount + " saved model answer" + (existingSampleCount === 1 ? "" : "s")
      : "All " + count + " answers";
    answerAllQuestionsButton.querySelector(".button-label").textContent = "Get model answers for all " + count + " questions";
    questionList.replaceChildren();
    questions.forEach(function (question, index) {
      questionList.appendChild(buildQuestionCard(question, index, answers[index] || ""));
    });
    const hasSamples = questionSampleAnswers.some(Boolean);
    if (hasSamples) {
      renderAnswerSheet(questionSampleAnswers, questions);
      answerSheetSection.hidden = false;
      answerFollowups.hidden = false;
    }
  }

  function clearAnswerSheet() {
    answerSheetRequestToken += 1;
    answerSheetSection.hidden = true;
    answerFollowups.hidden = true;
    answerAllQuestionsButton.setAttribute("aria-expanded", "false");
    answerSheetContent.replaceChildren();
    if (answerAllQuestionsButton.disabled) setButtonBusy(answerAllQuestionsButton, false);
  }

  function previousAnswersLabel(action) {
    const count = questions.length || 10;
    return action + " model answers for the previous " + count + " questions";
  }

  function clearPreviousAnswers() {
    previousAnswersRequestToken += 1;
    previousAnswersSection.hidden = true;
    previousAnswersContent.replaceChildren();
    previousAnswersCache = null;
    showPreviousAnswersButton.disabled = false;
    showPreviousAnswersButton.setAttribute("aria-expanded", "false");
    showPreviousAnswersButton.textContent = previousAnswersLabel("Show");
  }

  function renderAnswerSheet(sampleAnswers, questionSet) {
    const count = sampleAnswers.filter(Boolean).length;
    document.getElementById("answerSheetTitle").textContent = count === questionSet.length
      ? "All " + questionSet.length + " answers"
      : count + " saved model answer" + (count === 1 ? "" : "s");
    return renderAnswerCards(answerSheetContent, sampleAnswers, questionSet);
  }

  function renderAnswerCards(container, sampleAnswers, questionSet) {
    container.replaceChildren();
    sampleAnswers.forEach(function (answer, index) {
      if (!answer || !questionSet[index]) return;
      const item = makeElement("article", "answer-sheet-item");
      item.appendChild(makeElement("h3", "answer-sheet-question", "Q" + (index + 1) + ". " + questionSet[index].question));
      item.appendChild(makeElement("span", "answer-sheet-label", "ODDI sample answer"));
      item.appendChild(makeElement("p", "answer-sheet-response", answer));
      const listen = makeElement("button", "answer-speak-button", "Listen to answer");
      listen.type = "button";
      listen.addEventListener("click", function () { speakAnswer(answer, listen); });
      item.appendChild(listen);
      container.appendChild(item);
    });
  }

  async function replaceQuestion(card, index, button) {
    const answer = getAnswer(card);
    if (answer && !window.confirm("Replace this question? Your current answer to it will be cleared.")) return;

    const hadReview = !feedbackSection.hidden;
    feedbackSection.hidden = true;
    feedbackSection.dataset.visible = "false";
    const cardStatus = card.querySelector(".card-status");
    const originalLabel = "Need a different question?";
    button.disabled = true;
    button.querySelector("span:last-child").textContent = "Creating another...";
    card.classList.add("is-changing");
    cardStatus.textContent = "ODDI is preparing a new question for this role.";
    try {
      const result = await postJson("/api/interview/question", {
        profession: profession,
        context: roleContext,
        existing_questions: questions.map(function (item) { return item.question; })
      });
      if (!result.question || !result.question.question) throw new Error("ODDI didn't return a replacement question.");
      sessionReviewed = false;
      sessionReviewText = "";
      sessionFormattedAnswers = "";
      clearPreviousAnswers();
      questions[index] = result.question;
      answers[index] = "";
      questionSampleAnswers[index] = "";
      answerSources[index] = "unanswered";
      clearAnswerSheet();
      const replacement = buildQuestionCard(result.question, index, "");
      card.replaceWith(replacement);
      updateProgress();
      setStatus("Question " + (index + 1) + " has been refreshed.", "success");
    } catch (error) {
      card.classList.remove("is-changing");
      button.disabled = false;
      button.querySelector("span:last-child").textContent = originalLabel;
      cardStatus.textContent = error.message || "ODDI couldn't create a different question.";
      cardStatus.classList.add("is-error");
      if (hadReview) {
        feedbackSection.hidden = false;
        feedbackSection.dataset.visible = "true";
      }
    }
  }

  function formatSessionDate(value) {
    if (!value) return "Saved practice";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return "Saved practice";
    return "Updated " + new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit"
    }).format(parsed);
  }

  function renderPracticeSessions(sessions) {
    const items = Array.isArray(sessions) ? sessions : [];
    practiceSessionList.replaceChildren();
    practiceSessionsSection.hidden = items.length === 0 || setupPanel.hidden;

    const byProfession = new Map();
    items.forEach(function (item) {
      const key = String(item.profession || "Interview practice").trim().toLocaleLowerCase();
      if (!byProfession.has(key)) byProfession.set(key, []);
      byProfession.get(key).push(item);
    });
    const practiceNumbers = new Map();
    byProfession.forEach(function (group) {
      group.slice().sort(function (left, right) {
        return String(left.created_at || "").localeCompare(String(right.created_at || ""));
      }).forEach(function (item, index) {
        practiceNumbers.set(String(item.id), index + 1);
      });
    });

    items.forEach(function (session) {
      const role = String(session.profession || "Interview practice");
      const ordinal = practiceNumbers.get(String(session.id)) || 1;

      const card = makeElement("article", "practice-session-card");
      const copy = makeElement("div", "practice-session-copy");
      copy.appendChild(makeElement("strong", "", "Continue with " + role));
      const progress = Number(session.answered_count || 0) + " / " + Number(session.question_count || 10) + " answered";
      const label = session.has_review ? "Review ready" : "In progress";
      copy.appendChild(makeElement("span", "", "Practice " + ordinal + " · " + label + " · " + formatSessionDate(session.updated_at)));

      const actions = makeElement("div", "practice-session-actions");
      actions.appendChild(makeElement("span", "practice-session-progress", progress));
      const openButton = makeElement("button", "practice-session-open", session.has_review ? "Open review" : "Continue");
      openButton.type = "button";
      openButton.addEventListener("click", function () {
        void openSavedSession(session.id, openButton);
      });
      actions.appendChild(openButton);
      card.append(copy, actions);
      practiceSessionList.appendChild(card);
    });
    practiceSessionCount.textContent = items.length + (items.length === 1 ? " session saved" : " sessions saved");
  }

  function mergeSavedSessions(serverSessions, localSessions) {
    const merged = new Map();
    (Array.isArray(serverSessions) ? serverSessions : []).forEach(function (session) {
      if (session && session.id) merged.set(String(session.id), session);
    });
    (Array.isArray(localSessions) ? localSessions : []).forEach(function (session) {
      if (!session || !session.id || session.user_key !== userKey) return;
      const id = String(session.id);
      const current = merged.get(id);
      if (!current || String(session.updated_at || "") >= String(current.updated_at || "")) {
        const storedAnswers = Array.isArray(session.answers) ? session.answers : [];
        const storedSamples = Array.isArray(session.question_sample_answers) ? session.question_sample_answers : [];
        const sources = Array.isArray(session.answer_sources) ? session.answer_sources : [];
        const answered = storedAnswers.reduce(function (count, answer, index) {
          return count + (String(answer || "").trim() || (
            sources[index] === "oddi_sample" && String(storedSamples[index] || "").trim()
          ) ? 1 : 0);
        }, 0);
        merged.set(id, {
          id: id,
          profession: session.profession || "Interview practice",
          status: session.status || (session.review ? "completed" : "in_progress"),
          has_review: Boolean(session.review),
          answered_count: answered,
          question_count: Array.isArray(session.questions) ? session.questions.length : 0,
          created_at: session.created_at,
          updated_at: session.updated_at
        });
      }
    });
    return Array.from(merged.values()).sort(function (left, right) {
      return String(right.updated_at || "").localeCompare(String(left.updated_at || ""));
    });
  }

  async function loadSavedSessions(showErrors) {
    const localSessions = await readLocalSessions();
    try {
      const result = await requestJson("/api/interview/sessions", "GET");
      renderPracticeSessions(mergeSavedSessions(result.sessions, localSessions));
    } catch (error) {
      renderPracticeSessions(mergeSavedSessions([], localSessions));
      if (showErrors && !localSessions.length) setStatus(error.message || "Saved practices couldn't be loaded.", "error");
    }
  }

  async function openSavedSession(id, button) {
    if (button) button.disabled = true;
    clearStatus();
    setStatus("Opening your saved practice...", "success");
    try {
      let saved = null;
      let serverSession = null;
      if (String(id).indexOf("local-") !== 0) {
        try {
          const result = await requestJson("/api/interview/sessions/" + encodeURIComponent(id), "GET");
          serverSession = result.session;
        } catch (_) {
          serverSession = null;
        }
      }
      const localSession = await readLocalSession(id);
      if (serverSession && localSession && String(localSession.updated_at || "") > String(serverSession.updated_at || "")) {
        saved = localSession;
      } else if (serverSession) {
        saved = serverSession;
      } else if (localSession) {
        saved = localSession;
      } else {
        throw new Error("That practice could not be found on your account or this device.");
      }
      if (!saved || !Array.isArray(saved.questions) || ![5, 10].includes(saved.questions.length)) {
        throw new Error("This saved practice doesn't have a complete question set.");
      }

      sessionId = String(saved.id);
      sessionServerAvailable = Boolean(serverSession);
      sessionCreatedAt = String(saved.created_at || "");
      profession = String(saved.profession || "");
      roleContext = String(saved.context || "");
      questions = saved.questions;
      sessionReviewed = Boolean(saved.review);
      answers = Array.isArray(saved.answers) ? saved.answers.slice(0, questions.length) : Array(questions.length).fill("");
      while (answers.length < questions.length) answers.push("");
      questionSampleAnswers = Array.isArray(saved.question_sample_answers)
        ? saved.question_sample_answers.slice(0, questions.length)
        : Array(questions.length).fill("");
      while (questionSampleAnswers.length < questions.length) questionSampleAnswers.push("");
      answerSources = Array.isArray(saved.answer_sources) ? saved.answer_sources.slice(0, questions.length) : Array(questions.length).fill("unanswered");
      while (answerSources.length < questions.length) answerSources.push("unanswered");
      sessionReviewText = String(saved.review || "");
      sessionFormattedAnswers = String(saved.formatted_answers || "");
      professionInput.value = profession;
      roleDetailsInput.value = roleContext;
      renderFeedback(String(saved.review || ""));
      clearPreviousAnswers();
      feedbackSection.hidden = !saved.review;
      feedbackSection.dataset.visible = saved.review ? "true" : "false";
      answerFollowups.hidden = !(saved.review || questionSampleAnswers.some(Boolean));
      setAnswerAllMode(false);
      setSessionUrl(sessionId);
      showQuestions();

      restoringSession = true;
      renderQuestions();
      updateProgress();
      restoringSession = false;
      setSaveState(serverSession ? "Saved to your account and this device." : "Saved on this device.");
      void persistLocalSession();
      if (saved.review) {
        window.setTimeout(function () { feedbackSection.scrollIntoView({ behavior: "smooth", block: "start" }); }, 150);
      }
    } catch (error) {
      restoringSession = false;
      setStatus(error.message || "This saved practice couldn't be opened.", "error");
    } finally {
      if (button) button.disabled = false;
    }
  }

  answerAllToggle.addEventListener("click", function () {
    const enabled = answerAllToggle.getAttribute("aria-pressed") !== "true";
    setAnswerAllMode(enabled);
    if (enabled) {
      const cards = Array.from(questionList.querySelectorAll(".question-card"));
      const firstUnanswered = cards.find(function (card) {
        return !getAnswer(card) && !questionSampleAnswers[Number(card.dataset.questionIndex)];
      }) || cards[0];
      if (firstUnanswered) firstUnanswered.scrollIntoView({ behavior: "smooth", block: "start" });
      const target = firstUnanswered && firstUnanswered.querySelector("textarea, input[type=radio]");
      if (target) window.setTimeout(function () { target.focus({ preventScroll: true }); }, 220);
    } else {
      document.querySelector(".questions-intro").scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });

  function handleAnswerChange() {
    if (!feedbackSection.hidden) {
      feedbackSection.hidden = true;
      feedbackSection.dataset.visible = "false";
    }
    sessionReviewed = false;
    sessionReviewText = "";
    sessionFormattedAnswers = "";
    updateProgress();
  }

  questionList.addEventListener("input", handleAnswerChange);
  questionList.addEventListener("change", handleAnswerChange);

  answerAllQuestionsButton.addEventListener("click", async function () {
    if (answerAllQuestionsButton.disabled) return;
    if (![5, 10].includes(questions.length)) {
      setStatus("ODDI needs a complete practice round before it can prepare model answers.", "error");
      return;
    }
    const count = questions.length;

    const questionSet = questions.map(function (question) {
      return {
        type: question.type === "multiple_choice" ? "multiple_choice" : "written",
        question: question.question,
        options: question.type === "multiple_choice" ? (question.options || []).slice() : []
      };
    });
    const requestToken = ++answerSheetRequestToken;
    clearStatus();
    setButtonBusy(answerAllQuestionsButton, true, "ODDI is answering all " + count + "...");
    answerSheetSection.hidden = false;
    answerAllQuestionsButton.setAttribute("aria-expanded", "true");
    answerSheetContent.replaceChildren(
        makeElement("div", "answer-sheet-loading", "ODDI is preparing a sample answer for each of the " + count + " questions...")
    );

    try {
      currentSessionSnapshot();
      if (sessionServerAvailable) await saveSessionNow();
      else await persistLocalSession();
      const result = await postJson("/api/interview/answers", {
        profession: profession,
        context: roleContext,
        session_id: sessionServerAvailable ? sessionId : "",
        questions: questionSet
      });
      if (requestToken !== answerSheetRequestToken) return;
      if (!Array.isArray(result.answers) || result.answers.length !== questionSet.length || result.answers.some(function (answer) {
        return typeof answer !== "string" || !answer.trim();
      })) {
        throw new Error("ODDI didn't return a complete set of " + count + " sample answers.");
      }
      questionSampleAnswers = result.answers.slice();
      answerSources = answers.map(function (answer) { return answer ? "candidate" : "oddi_sample"; });
      renderAnswerSheet(result.answers, questionSet);
      answerFollowups.hidden = false;
      await persistLocalSession();
      if (sessionServerAvailable) await saveSessionNow();
      updateProgress();
      answerSheetSection.scrollIntoView({ behavior: "smooth", block: "start" });
      setStatus("ODDI's sample answers for all " + count + " questions are ready.", "success");
    } catch (error) {
      if (requestToken !== answerSheetRequestToken) return;
      answerSheetContent.replaceChildren(
        makeElement("div", "answer-sheet-loading answer-sheet-error", error.message || "ODDI couldn't answer all " + count + " questions. Please try again.")
      );
      setStatus(error.message || "ODDI couldn't answer all " + count + " questions. Please try again.", "error");
    } finally {
      if (requestToken === answerSheetRequestToken) setButtonBusy(answerAllQuestionsButton, false);
    }
  });

  hideAnswerSheetButton.addEventListener("click", function () {
    answerSheetSection.hidden = true;
    answerAllQuestionsButton.setAttribute("aria-expanded", "false");
  });

  function openPreviousAnswers() {
    previousAnswersSection.hidden = false;
    showPreviousAnswersButton.setAttribute("aria-expanded", "true");
    showPreviousAnswersButton.textContent = "Hide model answers";
    previousAnswersSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  showPreviousAnswersButton.addEventListener("click", async function () {
    if (showPreviousAnswersButton.disabled) return;
    if (!previousAnswersSection.hidden) {
      previousAnswersSection.hidden = true;
      showPreviousAnswersButton.setAttribute("aria-expanded", "false");
      showPreviousAnswersButton.textContent = previousAnswersLabel("Show");
      return;
    }
    if (previousAnswersCache) {
      renderAnswerCards(previousAnswersContent, previousAnswersCache.answers, previousAnswersCache.questions);
      openPreviousAnswers();
      return;
    }

    const questionSet = questions.map(function (question) {
      return {
        type: question.type === "multiple_choice" ? "multiple_choice" : "written",
        question: question.question,
        options: question.type === "multiple_choice" ? (question.options || []).slice() : []
      };
    });
    const requestToken = ++previousAnswersRequestToken;
    clearStatus();
    showPreviousAnswersButton.disabled = true;
    showPreviousAnswersButton.textContent = "ODDI is preparing model answers...";
    previousAnswersSection.hidden = false;
    previousAnswersContent.replaceChildren(
      makeElement("div", "answer-sheet-loading", "ODDI is preparing model answers for your previous " + questionSet.length + " questions...")
    );

    try {
      currentSessionSnapshot();
      if (sessionServerAvailable) await saveSessionNow();
      else await persistLocalSession();
      const result = await postJson("/api/interview/answers", {
        profession: profession,
        context: roleContext,
        session_id: sessionServerAvailable ? sessionId : "",
        questions: questionSet
      });
      if (requestToken !== previousAnswersRequestToken) return;
      if (!Array.isArray(result.answers) || result.answers.length !== questionSet.length || result.answers.some(function (answer) {
        return typeof answer !== "string" || !answer.trim();
      })) {
        throw new Error("ODDI didn't return model answers for every question.");
      }
      previousAnswersCache = { answers: result.answers, questions: questionSet };
      questionSampleAnswers = result.answers.slice();
      answerSources = answers.map(function (answer) { return answer ? "candidate" : "oddi_sample"; });
      await persistLocalSession();
      previousAnswersTitle.textContent = "Model answers for your previous " + questionSet.length + " questions";
      renderAnswerCards(previousAnswersContent, result.answers, questionSet);
      openPreviousAnswers();
      setStatus("ODDI's model answers are ready.", "success");
    } catch (error) {
      if (requestToken !== previousAnswersRequestToken) return;
      previousAnswersSection.hidden = false;
      previousAnswersContent.replaceChildren(
        makeElement("div", "answer-sheet-loading answer-sheet-error", error.message || "ODDI couldn't prepare the model answers. Please try again.")
      );
      showPreviousAnswersButton.setAttribute("aria-expanded", "true");
      showPreviousAnswersButton.textContent = "Hide model answers";
      setStatus(error.message || "ODDI couldn't prepare the model answers. Please try again.", "error");
    } finally {
      if (requestToken === previousAnswersRequestToken) showPreviousAnswersButton.disabled = false;
    }
  });

  hidePreviousAnswersButton.addEventListener("click", function () {
    previousAnswersSection.hidden = true;
    showPreviousAnswersButton.setAttribute("aria-expanded", "false");
    showPreviousAnswersButton.textContent = previousAnswersLabel("Show");
  });

  async function createFollowupQuestions(button) {
    if (button.disabled) return;
    const action = button.dataset.followUp;
    const request = { count: 10, question_mode: "mixed", difficulty: "standard" };
    if (action === "more-5") request.count = 5;
    if (action === "written") request.question_mode = "written";
    if (action === "multiple-choice") request.question_mode = "multiple_choice";
    if (action === "easier") request.difficulty = "easier";
    if (action === "challenging") request.difficulty = "challenging";

    const originalLabel = button.textContent;
    feedbackActionButtons.forEach(function (item) { item.disabled = true; });
    showPreviousAnswersButton.disabled = true;
    button.textContent = "ODDI is preparing your questions...";
    clearStatus();
    try {
      const result = await postJson("/api/interview/questions", {
        profession: profession,
        context: roleContext,
        count: request.count,
        question_mode: request.question_mode,
        difficulty: request.difficulty,
        existing_questions: questions.map(function (item) { return item.question; })
      });
      if (result.clarification) throw new Error(result.clarification);
      if (!Array.isArray(result.questions) || result.questions.length !== request.count) {
        throw new Error("ODDI didn't return the complete new question set. Please try again.");
      }

      questions = result.questions;
      answers = Array(questions.length).fill("");
      questionSampleAnswers = Array(questions.length).fill("");
      answerSources = Array(questions.length).fill("unanswered");
      sessionServerAvailable = Boolean(result.session_id);
      sessionId = String(result.session_id || makeLocalSessionId());
      sessionCreatedAt = new Date().toISOString();
      sessionReviewText = "";
      sessionFormattedAnswers = "";
      sessionReviewed = false;
      setSessionUrl(sessionId);
      feedbackText.replaceChildren();
      clearPreviousAnswers();
      feedbackSection.hidden = true;
      feedbackSection.dataset.visible = "false";
      setAnswerAllMode(false);
      showQuestions();
      restoringSession = true;
      renderQuestions();
      updateProgress();
      restoringSession = false;

      if (sessionId) {
        void persistLocalSession();
        setSaveState(sessionServerAvailable ? "New practice saved to your account and this device." : "New practice saved on this device.");
        void loadSavedSessions(false);
        setStatus("Your next " + questions.length + " questions are ready for " + profession + ".", "success");
        if (!sessionServerAvailable) {
          setStatus(result.session_error || "This practice is saved on this device. It couldn't be synced to your account yet.", "error");
        }
      }
    } catch (error) {
      restoringSession = false;
      setStatus(error.message || "ODDI couldn't prepare the next questions. Please try again.", "error");
    } finally {
      feedbackActionButtons.forEach(function (item) { item.disabled = false; });
      showPreviousAnswersButton.disabled = false;
      button.textContent = originalLabel;
    }
  }

  feedbackActionButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      void createFollowupQuestions(button);
    });
  });

  submitButton.addEventListener("click", async function () {
    const cards = Array.from(questionList.querySelectorAll(".question-card"));
    const currentAnswers = cards.map(function (card) { return getAnswer(card); });
    answers = currentAnswers;
    answerSources = currentAnswers.map(function (answer, index) {
      return answer ? "candidate" : (questionSampleAnswers[index] ? "oddi_sample" : "unanswered");
    });
    const firstUnanswered = cards.findIndex(function (card, index) {
      return !getAnswer(card) && !(answerSources[index] === "oddi_sample" && questionSampleAnswers[index]);
    });
    if (firstUnanswered >= 0) {
      setStatus("Answer every question before submitting your interview.", "error");
      cards[firstUnanswered].scrollIntoView({ behavior: "smooth", block: "center" });
      const target = cards[firstUnanswered].querySelector("textarea, input[type=radio]");
      if (target) window.setTimeout(function () { target.focus({ preventScroll: true }); }, 220);
      return;
    }

    clearStatus();
    submitButton.disabled = true;
    submitButton.querySelector(".button-label").textContent = "ODDI is reviewing your answers...";
    submitHint.textContent = "Your answers are being sent to ODDI for feedback.";
    try {
      if (sessionId) await saveSessionNow();
      const result = await postJson("/api/interview/review", {
        profession: profession,
        session_id: sessionServerAvailable ? sessionId : "",
        answers: cards.map(function (card, index) {
          const answer = getAnswer(card);
          return {
            question: questions[index].question,
            answer: answer,
            sample_answer: questionSampleAnswers[index] || "",
            answer_source: answer ? "candidate" : "oddi_sample"
          };
        })
      });
      renderFeedback(result.review || "ODDI received your answers but did not return feedback.");
      sessionFormattedAnswers = String(result.formatted_answers || "");
      sessionReviewText = String(result.review || "");
      clearPreviousAnswers();
      answerFollowups.hidden = false;
      feedbackSection.hidden = false;
      feedbackSection.dataset.visible = "true";
      sessionReviewed = true;
      await persistLocalSession();
      setSaveState(sessionServerAvailable ? "Review saved to your account and this device." : "Review saved on this device.");
      feedbackSection.scrollIntoView({ behavior: "smooth", block: "start" });
      setStatus("Your interview review is ready.", "success");
    } catch (error) {
      submitHint.textContent = error.message || "ODDI couldn't review these answers.";
      setStatus(error.message || "ODDI couldn't review these answers. Please try again.", "error");
    } finally {
      submitButton.disabled = false;
      submitButton.querySelector(".button-label").textContent = "Submit answers to ODDI";
    }
  });

  window.addEventListener("pagehide", function () {
    if (activeRecognition) {
      try { activeRecognition.stop(); } catch (_) { /* recognition may already be stopping */ }
      activeRecognition = null;
    }
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    if (sessionId && [5, 10].includes(questions.length)) {
      void saveSessionNow(true).catch(function () {});
    }
  });

  void loadSavedSessions(false);
  const requestedSession = new URLSearchParams(window.location.search).get("session");
  if (requestedSession) void openSavedSession(requestedSession, null);
})();
