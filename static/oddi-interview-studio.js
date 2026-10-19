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
  let sessionId = "";
  let statusTimeout = 0;
  let saveTimeout = 0;
  let saveQueue = Promise.resolve();
  let restoringSession = false;
  let answerSheetRequestToken = 0;
  let previousAnswersRequestToken = 0;
  let previousAnswersCache = null;
  let sessionReviewed = false;

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
    return { questions: questions, answers: currentAnswers };
  }

  function saveSessionNow(keepalive) {
    window.clearTimeout(saveTimeout);
    saveTimeout = 0;
    if (!sessionId || sessionReviewed || ![5, 10].includes(questions.length)) return Promise.resolve();

    const savingId = sessionId;
    const snapshot = currentSessionSnapshot();
    setSaveState("Saving your progress...", "saving");
    const task = saveQueue.catch(function () {}).then(function () {
      return requestJson(
        "/api/interview/sessions/" + encodeURIComponent(savingId),
        "PATCH",
        snapshot,
        keepalive
      );
    }).then(function (result) {
      if (sessionId === savingId) setSaveState("Progress saved to this account.");
      return result;
    }).catch(function (error) {
      if (sessionId === savingId) setSaveState("Progress couldn't be saved. Try again.", "error");
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
      sessionId = String(result.session_id || "");
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
        setSaveState("Practice saved. Your answers save automatically.");
        void loadSavedSessions(true);
        setStatus("Your 10 questions are ready. Take them one at a time.", "success");
      } else {
        const saveError = result.session_error || "Questions are ready, but ODDI couldn't save this practice session.";
        setSaveState("This practice couldn't be saved. Please keep this page open.", "error");
        setStatus(saveError, "error");
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
    if (textArea) return textArea.value.trim();
    const checked = card.querySelector('input[type="radio"]:checked');
    return checked ? checked.value : "";
  }

  function updateProgress() {
    const cards = Array.from(questionList.querySelectorAll(".question-card"));
    const currentAnswers = cards.map(getAnswer);
    answers = currentAnswers;
    const answered = currentAnswers.filter(Boolean).length;
    const total = cards.length || 10;
    answeredCount.textContent = String(answered);
    totalCount.textContent = String(total);
    progressTrack.setAttribute("aria-valuemax", String(total));
    progressTrack.setAttribute("aria-valuenow", String(answered));
    progressFill.style.width = (total ? (answered / total) * 100 : 0) + "%";
    submitHint.textContent = answered === total
      ? "Your answers are ready for ODDI's review."
      : "Answer all " + total + " questions to get your ODDI review.";
    scheduleSessionSave();
  }

  function makeElement(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
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
        radio.checked = radio.value === previousAnswer;
        const badge = makeElement("span", "choice-letter", letter);
        const copy = makeElement("span", "choice-copy", option);
        label.append(radio, badge, copy);
        choices.appendChild(label);
      });
      card.appendChild(choices);
    } else {
      const answer = document.createElement("textarea");
      answer.className = "written-answer";
      answer.rows = 3;
      answer.maxLength = 10000;
      answer.placeholder = "Write your answer here...";
      answer.setAttribute("aria-label", "Your answer to question " + (index + 1));
      answer.value = previousAnswer || "";
      card.appendChild(answer);
    }

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
    return card;
  }

  async function answerQuestion(question, index, card, button) {
    if (button.disabled) return;
    const cardStatus = card.querySelector(".card-status");
    let answerPanel = card.querySelector(".sample-answer");
    if (!answerPanel) {
      answerPanel = makeElement("section", "sample-answer");
      answerPanel.id = "interview-sample-answer-" + index;
      answerPanel.setAttribute("aria-live", "polite");
      const heading = makeElement("strong", "sample-answer-title", "ODDI's sample answer");
      const copy = makeElement("div", "sample-answer-copy");
      answerPanel.append(heading, copy);
      card.insertBefore(answerPanel, cardStatus);
      button.setAttribute("aria-controls", answerPanel.id);
    }

    const label = button.querySelector("span:last-child");
    const originalLabel = label.textContent;
    button.disabled = true;
    button.setAttribute("aria-expanded", "true");
    label.textContent = "ODDI is answering...";
    const answerCopy = answerPanel.querySelector(".sample-answer-copy");
    const previousAnswer = answerPanel.dataset.answer || "";
    answerCopy.textContent = "ODDI is preparing a sample answer for this question...";
    answerPanel.classList.remove("is-error");
    answerPanel.hidden = false;
    cardStatus.textContent = "";
    cardStatus.classList.remove("is-error");

    try {
      const result = await postJson("/api/interview/answer", {
        profession: profession,
        context: roleContext,
        question: question.question,
        question_type: question.type === "multiple_choice" ? "multiple_choice" : "written",
        options: question.type === "multiple_choice" ? (question.options || []) : []
      });
      if (!result.answer || typeof result.answer !== "string") throw new Error("ODDI didn't return a sample answer.");
      answerPanel.dataset.answer = result.answer;
      answerCopy.textContent = result.answer;
      answerPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (error) {
      if (previousAnswer) {
        answerCopy.textContent = previousAnswer;
      } else {
        answerPanel.hidden = true;
        button.setAttribute("aria-expanded", "false");
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
    document.getElementById("answerSheetTitle").textContent = "All " + count + " answers";
    answerAllQuestionsButton.querySelector(".button-label").textContent = "Get model answers for all " + count + " questions";
    questionList.replaceChildren();
    questions.forEach(function (question, index) {
      questionList.appendChild(buildQuestionCard(question, index, answers[index] || ""));
    });
  }

  function clearAnswerSheet() {
    answerSheetRequestToken += 1;
    answerSheetSection.hidden = true;
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
    return renderAnswerCards(answerSheetContent, sampleAnswers, questionSet);
  }

  function renderAnswerCards(container, sampleAnswers, questionSet) {
    container.replaceChildren();
    sampleAnswers.forEach(function (answer, index) {
      const item = makeElement("article", "answer-sheet-item");
      item.appendChild(makeElement("h3", "answer-sheet-question", "Q" + (index + 1) + ". " + questionSet[index].question));
      item.appendChild(makeElement("span", "answer-sheet-label", "ODDI sample answer"));
      item.appendChild(makeElement("p", "answer-sheet-response", answer));
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
      clearPreviousAnswers();
      questions[index] = result.question;
      answers[index] = "";
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

  async function loadSavedSessions(showErrors) {
    try {
      const result = await requestJson("/api/interview/sessions", "GET");
      renderPracticeSessions(result.sessions);
    } catch (error) {
      if (showErrors) setStatus(error.message || "Saved practices couldn't be loaded.", "error");
    }
  }

  async function openSavedSession(id, button) {
    if (button) button.disabled = true;
    clearStatus();
    setStatus("Opening your saved practice...", "success");
    try {
      const result = await requestJson("/api/interview/sessions/" + encodeURIComponent(id), "GET");
      const saved = result.session;
      if (!saved || !Array.isArray(saved.questions) || ![5, 10].includes(saved.questions.length)) {
        throw new Error("This saved practice doesn't have a complete question set.");
      }

      sessionId = String(saved.id);
      profession = String(saved.profession || "");
      roleContext = String(saved.context || "");
      questions = saved.questions;
      sessionReviewed = Boolean(saved.review);
      answers = Array.isArray(saved.answers) ? saved.answers.slice(0, questions.length) : Array(questions.length).fill("");
      while (answers.length < questions.length) answers.push("");
      professionInput.value = profession;
      roleDetailsInput.value = roleContext;
      renderFeedback(String(saved.review || ""));
      clearPreviousAnswers();
      feedbackSection.hidden = !saved.review;
      feedbackSection.dataset.visible = saved.review ? "true" : "false";
      setAnswerAllMode(false);
      setSessionUrl(sessionId);
      showQuestions();

      restoringSession = true;
      renderQuestions();
      updateProgress();
      restoringSession = false;
      setSaveState(saved.review ? "Review and answers saved to this account." : "Progress saved to this account.");
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
      const firstUnanswered = cards.find(function (card) { return !getAnswer(card); }) || cards[0];
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
      const result = await postJson("/api/interview/answers", {
        profession: profession,
        context: roleContext,
        questions: questionSet
      });
      if (requestToken !== answerSheetRequestToken) return;
      if (!Array.isArray(result.answers) || result.answers.length !== questionSet.length || result.answers.some(function (answer) {
        return typeof answer !== "string" || !answer.trim();
      })) {
        throw new Error("ODDI didn't return a complete set of " + count + " sample answers.");
      }
      renderAnswerSheet(result.answers, questionSet);
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
      const result = await postJson("/api/interview/answers", {
        profession: profession,
        context: roleContext,
        questions: questionSet
      });
      if (requestToken !== previousAnswersRequestToken) return;
      if (!Array.isArray(result.answers) || result.answers.length !== questionSet.length || result.answers.some(function (answer) {
        return typeof answer !== "string" || !answer.trim();
      })) {
        throw new Error("ODDI didn't return model answers for every question.");
      }
      previousAnswersCache = { answers: result.answers, questions: questionSet };
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
      sessionId = String(result.session_id || "");
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
        setSaveState("New practice saved. Your answers save automatically.");
        void loadSavedSessions(false);
        setStatus("Your next " + questions.length + " questions are ready for " + profession + ".", "success");
      } else {
        setSaveState("This practice couldn't be saved. Please keep this page open.", "error");
        setStatus(result.session_error || "Your questions are ready, but ODDI couldn't save this practice.", "error");
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
    const firstUnanswered = cards.findIndex(function (card) { return !getAnswer(card); });
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
        session_id: sessionId,
        answers: cards.map(function (card, index) {
          return { question: questions[index].question, answer: getAnswer(card) };
        })
      });
      renderFeedback(result.review || "ODDI received your answers but did not return feedback.");
      clearPreviousAnswers();
      feedbackSection.hidden = false;
      feedbackSection.dataset.visible = "true";
      sessionReviewed = true;
      setSaveState("Review and answers saved to this account.");
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
    if (sessionId && [5, 10].includes(questions.length)) {
      void saveSessionNow(true).catch(function () {});
    }
  });

  void loadSavedSessions(false);
  const requestedSession = new URLSearchParams(window.location.search).get("session");
  if (requestedSession) void openSavedSession(requestedSession, null);
})();
