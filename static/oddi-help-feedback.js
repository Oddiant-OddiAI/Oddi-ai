(function () {
  "use strict";

  const QUESTIONS = [
    "How satisfied are you with ODDI overall?",
    "How helpful were ODDI's answers for your needs?",
    "How relevant and accurate did the answers feel?",
    "How easy was it to start and continue a chat?",
    "How reliably were your chats saved and available later?",
    "How easy was it to find the feature you needed?",
    "How helpful was the Help section and website tutorial?",
    "How would you rate the interface design and readability?",
    "How satisfied were you with ODDI's response speed?",
    "How likely are you to recommend ODDI to someone?"
  ];

  const FAQS = [
    { category: "Getting started", q: "How do I start a new chat?", a: "Choose New Chat in the left sidebar. ODDI opens a fresh conversation screen; type in the message box at the bottom and send your message." },
    { category: "Getting started", q: "Do I need an account to chat?", a: "You can explore ODDI while signed out where guest access is available. Sign in to submit feedback and receive a team reply. If you use a browser-local account, its feedback history and replies stay with that browser session." },
    { category: "Chats", q: "Where are my conversations saved?", a: "Chats are saved to your ODDI account's chat history as you use them. Open a conversation from the sidebar to continue it." },
    { category: "Chats", q: "How do I find an older chat?", a: "Use Search conversations in the sidebar and enter a word from the chat title." },
    { category: "Chats", q: "How do I pin, rename, or archive a chat?", a: "Use the pin icon on the chat row to pin or unpin it. Open the row's actions menu for Rename, Archive or Unarchive, and Delete. Delete moves the conversation to Bin." },
    { category: "Chats", q: "Where did my archived chats go?", a: "Open Settings, choose Data, then find Archived chats. Restore a conversation there to return it to your history." },
    { category: "Chats", q: "Can I restore a deleted chat?", a: "Open Recently Deleted from the profile menu, or press Ctrl/⌘ + Shift + D. Choose Restore on the conversation before it is permanently removed." },
    { category: "Projects", q: "How do I create a project?", a: "Open Projects from the sidebar. Enter a project name, choose a type, and select Add project. Open its project card to view its chats." },
    { category: "Projects", q: "How do I start a chat inside a project?", a: "Open Projects, select the project, then choose New chat. The project chat is listed inside that project so you can reopen it there." },
    { category: "Projects", q: "Will a project chat also appear in normal chat history?", a: "Project chats are managed from the selected project's Chats section. Open the project and use its chat row to continue the conversation." },
    { category: "Library", q: "What is the Library for?", a: "The Library is where you manage files you have added to ODDI. Open Library from the sidebar to review and manage available files." },
    { category: "Library", q: "How do I use a file in a chat?", a: "Start or open a chat, use the attachment control beside the message box to add a file, then include your question when you send it." },
    { category: "Interview Studio", q: "How do I make an interview practice set?", a: "Open Interview Studio from the sidebar, enter any profession or role, and choose Build my 10 questions. ODDI creates a mix of written and multiple-choice questions." },
    { category: "Interview Studio", q: "What does Answer it do in Interview Studio?", a: "Answer it asks ODDI to draft a sample answer for that specific question. It does not fill in your own answer box." },
    { category: "Interview Studio", q: "What does Answer all at once do?", a: "It asks ODDI for a sample answer to every question and displays them together with their question text. Your own answers remain separate." },
    { category: "Interview Studio", q: "How do I get feedback on my interview answers?", a: "Fill in all 10 answer fields, then choose Submit answers to ODDI. ODDI reviews the set and gives feedback." },
    { category: "Settings", q: "How do I change the theme or language?", a: "Open Settings from the sidebar. Appearance contains Light, Dark, System, language, font size, and display preferences." },
    { category: "Settings", q: "Where can I manage notification and voice settings?", a: "Open Settings and choose Voice & Response. That section contains voice, typing animation, and response notification controls." },
    { category: "Settings", q: "How do I manage saved memories?", a: "Open Settings and choose Memory. You can review, add, edit, or remove facts ODDI remembers for your account." },
    { category: "Settings", q: "How do I export my data or manage sync?", a: "Open Settings and choose Data. Storage & Sync shows the current storage state, and the export action is in Settings under Privacy." },
    { category: "Account & privacy", q: "How do I sign in or create an account?", a: "Choose Sign In from the account area. The sign-in screen also lets you create an account or continue with Google when available." },
    { category: "Account & privacy", q: "How do I send feedback and receive a reply?", a: "Open Settings, choose Help & Feedback, then Feedback. Sign in with your ODDI account, complete all ratings, and submit. Replies appear in your feedback history in ODDI." },
    { category: "Troubleshooting", q: "A page or button is not responding. What should I try?", a: "Check your connection, return to the home screen, and reopen the feature. If it continues, use Help & Feedback to report which screen you were on and what happened." },
    { category: "Troubleshooting", q: "Why can't I submit another feedback survey yet?", a: "ODDI allows one feedback submission per account every 24 hours. The Feedback section shows the remaining cooldown and your latest submission." }
  ];

  const tourSteps = [
    { chapter: "Welcome", title: "A guided tour of ODDI", body: "Take a read-only look at the main parts of ODDI. Use Next and Back to move around. Skip tour or press Escape whenever you like. The tour will not send a message, create or delete content, or change a setting." },
    { chapter: "Getting around", title: "Your account", body: "The profile area shows the signed-in account or sign-in entry point. Account actions and sign-out are available here; profile and session settings are in Settings > Account.", target: ".oddi-rs-profile", prepare: prepareTourSidebar },
    { chapter: "Getting around", title: "Sidebar shortcuts", body: "Use these shortcuts to open Interview Studio, Projects, Library, and Settings. The sidebar can be collapsed on desktop; on a phone, open it from the sidebar button.", target: ".oddi-rs-nav", prepare: prepareTourSidebar },
    { chapter: "Chats", title: "Start a fresh chat", body: "New Chat opens ODDI's standard chat screen. A fresh-chat home has starter prompts, and Recent Work appears when there is a conversation to continue.", target: ".oddi-rs-new", prepare: prepareTourSidebar },
    { chapter: "Chats", title: "Find a conversation", body: "Search by a word from a chat title. Clear the search to see the full conversation list again.", target: ".oddi-rs-search", prepare: prepareTourSidebar },
    { chapter: "Chats", title: "Pinned and recent chats", body: "Pinned chats stay in their own group; the newest conversations appear under Recent. A chat's menu can rename, archive, or delete it. Deleted chats go to Recently Deleted, where they can be restored.", target: ".oddi-rs-history", prepare: prepareTourSidebar },
    { chapter: "Chats", title: "Share a conversation", body: "For the open chat, choose More, then Export & Share Current Chat. To share from history, press and hold a conversation to select it, then hold any other chats you want to include. Choose Share selected chats to open Export & share, pick a format, then share the file. If your device cannot share files, ODDI downloads it instead; Copy chat text is also available.", target: ".oddi-rs-history", prepare: prepareTourSidebar },
    { chapter: "Chat tools", title: "Write, attach, or talk", body: "Type in the composer and use Send when ready. The plus attaches files, the microphone types spoken words, and the headset starts a voice conversation. This tour will not press them or send anything.", target: "#oddiComposerShell", prepare: prepareTourMain },
    { chapter: "Projects", title: "Create a project", body: "In Projects, enter a name, choose a type, and select Add project. Projects keep related work together so you can return to it later.", target: ".oddi-project-create-form", prepare: prepareTourProjects },
    { chapter: "Projects", title: "Keep project chats together", body: "Open a project card to see its Chats section. Create a chat there for an automatic title like Project Name Chat 1, then use Open or Delete from that list. Project chats stay out of normal sidebar history. The tour will not create anything.", target: ".oddi-project-list", prepare: prepareTourProjects },
    { chapter: "Your files", title: "Manage files in Library", body: "Add files to your Library, then search or filter the list. In a chat, attach a supported file when you want ODDI to use it in a request.", target: "#oddiLibraryModal .oddi-library-toolbar", prepare: prepareTourLibrary },
    { chapter: "Practice", title: "Interview Studio", body: "Enter any profession or role to build a 10-question practice set. Ask ODDI for one sample answer or answers to all questions, request a different question, then submit your own answers for review.", target: 'button[title="Interview Studio"]', link: "/interview-studio", linkLabel: "Open Interview Studio in a new tab", prepare: prepareTourSidebar },
    { chapter: "Make ODDI yours", title: "Appearance", body: "Choose Light, Dark, or System, then adjust language, font size, and display options. These controls only change when you choose them; the tour leaves them alone.", target: ".oddi-theme-grid", prepare: () => prepareTourSettings("appearance") },
    { chapter: "Make ODDI yours", title: "Personalize the chat", body: "Personalize lets you adjust the colors used for your messages, thinking dots, and the send button.", target: "[data-settings-panel=\"personalize\"] .oddi-settings-content-heading", prepare: () => prepareTourSettings("personalize") },
    { chapter: "Make ODDI yours", title: "Voice and response controls", body: "Choose a read-aloud voice and review the typing animation and response-notification controls here.", target: "[data-settings-panel=\"voice\"] .oddi-settings-group", prepare: () => prepareTourSettings("voice") },
    { chapter: "Make ODDI yours", title: "Chat preferences", body: "Choose how Enter sends messages, whether replies stream, which response details appear, and how much chat history ODDI can use for context.", target: "#oddiChatPrefRows", prepare: () => prepareTourSettings("chat-preferences") },
    { chapter: "Data and privacy", title: "Sync and archived chats", body: "Data shows where chats are stored, sync status, and Archived chats. Restore an archived conversation here when you want it back in your history.", target: "#oddiArchivedChatsCard", prepare: () => prepareTourSettings("data") },
    { chapter: "Data and privacy", title: "Privacy and data export", body: "Review privacy choices, conversation-retention preference, and the data-export action here. Read the notes on this page for options that depend on this ODDI deployment.", target: "#oddiPrivacyRows", prepare: () => prepareTourSettings("privacy") },
    { chapter: "Personal context", title: "Memory", body: "Choose whether ODDI can use saved facts to personalize replies, and review or manage the memories attached to your account. The tour will not change them.", target: "#oddiMemoryToggles", prepare: () => prepareTourSettings("memory") },
    { chapter: "Help and feedback", title: "Find help or contact the team", body: "Search Help or expand a question to read its answer. Sign in to send feedback; one survey can be submitted every 24 hours, and team replies appear in your feedback history. The host inbox is only shown to the host account.", target: ".oddi-hfb-view-switch", prepare: () => prepareTourSettings("help-feedback") }
  ];

  const $ = (selector, root) => (root || document).querySelector(selector);
  const $$ = (selector, root) => Array.from((root || document).querySelectorAll(selector));
  const escapeQuestionKey = index => "q" + (index + 1);
  const state = { ratings: {}, reasons: {}, user: null, selectedCategory: "All topics", cooldownUntil: null, submissions: [], adminOverview: null, inAppNotifiedReplyIds: new Set(), nativeNotifiedReplyIds: new Set(), pendingInAppReplies: new Map(), tourSidebarWasOpen: false, tourSidebarWasCollapsed: false, tourReturnFocus: null };
  let tourIndex = 0;
  let tourRenderId = 0;
  let tourRoot = null;
  let tourTarget = null;

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  async function api(url, options) {
    const response = await fetch(url, Object.assign({ credentials: "same-origin", cache: "no-store" }, options || {}));
    let body = {};
    try { body = await response.json(); } catch (_) {}
    if (!response.ok) {
      const error = new Error(body.detail || body.error || "ODDI could not complete that request.");
      error.status = response.status;
      error.payload = body;
      throw error;
    }
    return body;
  }

  function renderFaqs() {
    const categoryRoot = $("#oddiHfbFaqCategories");
    const listRoot = $("#oddiHfbFaqList");
    const search = String($("#oddiHfbFaqSearch")?.value || "").trim().toLowerCase();
    if (!categoryRoot || !listRoot) return;
    const categories = ["All topics", ...new Set(FAQS.map(item => item.category))];
    categoryRoot.replaceChildren();
    categories.forEach(category => {
      const button = element("button", "oddi-hfb-category", category);
      button.type = "button";
      button.setAttribute("aria-pressed", String(state.selectedCategory === category));
      if (state.selectedCategory === category) button.classList.add("is-active");
      button.addEventListener("click", () => { state.selectedCategory = category; renderFaqs(); });
      categoryRoot.appendChild(button);
    });

    const matches = FAQS.filter(item => {
      const categoryMatch = state.selectedCategory === "All topics" || item.category === state.selectedCategory;
      const textMatch = !search || `${item.category} ${item.q} ${item.a}`.toLowerCase().includes(search);
      return categoryMatch && textMatch;
    });
    listRoot.replaceChildren();
    if (!matches.length) {
      listRoot.appendChild(element("div", "oddi-hfb-empty", "No matching help questions. Try a different search or send us feedback."));
      return;
    }
    matches.forEach(item => {
      const details = element("details", "oddi-hfb-faq-item");
      const summary = element("summary", "", item.q);
      const answer = element("p", "oddi-hfb-faq-answer", item.a);
      const category = element("span", "oddi-hfb-faq-tag", item.category);
      details.append(summary, answer, category);
      listRoot.appendChild(details);
    });
  }

  function renderSurvey() {
    const root = $("#oddiHfbQuestionList");
    if (!root || root.dataset.ready === "1") return;
    root.dataset.ready = "1";
    QUESTIONS.forEach((question, index) => {
      const key = escapeQuestionKey(index);
      const card = element("fieldset", "oddi-hfb-question-card");
      const legend = element("legend", "oddi-hfb-question-title");
      legend.append(element("span", "oddi-hfb-question-number", String(index + 1).padStart(2, "0")));
      legend.append(element("span", "", question));
      const rating = element("div", "oddi-hfb-rating");
      rating.setAttribute("role", "radiogroup");
      rating.setAttribute("aria-label", question);
      for (let value = 1; value <= 5; value++) {
        const star = element("button", "oddi-hfb-star", "★");
        star.type = "button";
        star.dataset.question = key;
        star.dataset.rating = String(value);
        star.setAttribute("aria-label", `${value} out of 5 stars`);
        star.setAttribute("aria-pressed", "false");
        star.addEventListener("click", () => setRating(key, value, card));
        rating.appendChild(star);
      }
      const ratingCaption = element("span", "oddi-hfb-rating-caption", "Choose a rating");
      const reasonMount = element("div", "oddi-hfb-reason-mount");
      card.append(legend, rating, ratingCaption, reasonMount);
      root.appendChild(card);
    });
  }

  function setRating(key, value, card) {
    state.ratings[key] = value;
    const stars = $$("[data-question='" + key + "']", card);
    stars.forEach(button => {
      const starValue = Number(button.dataset.rating);
      button.classList.toggle("is-selected", starValue <= value);
      button.setAttribute("aria-pressed", String(starValue === value));
    });
    const caption = $(".oddi-hfb-rating-caption", card);
    if (caption) caption.textContent = ["", "Needs work", "Could be better", "It's okay", "Good", "Excellent"][value];
    const mount = $(".oddi-hfb-reason-mount", card);
    if (value <= 3) {
      if (!$("textarea", mount)) {
        const label = element("label", "oddi-hfb-reason-field");
        const title = element("span", "oddi-hfb-reason-label", "Tell us why or how we can improve");
        const input = element("textarea");
        input.rows = 3;
        input.maxLength = 600;
        input.required = true;
        input.placeholder = "What could we do better for this part of ODDI?";
        input.setAttribute("aria-label", `Reason for rating: ${questionForKey(key)}`);
        input.value = state.reasons[key] || "";
        input.addEventListener("input", () => { state.reasons[key] = input.value; updateSurveySubmitState(); });
        label.append(title, input);
        mount.replaceChildren(label);
      }
      card.classList.add("has-reason");
    } else {
      delete state.reasons[key];
      mount.replaceChildren();
      card.classList.remove("has-reason");
    }
    const count = Object.keys(state.ratings).length;
    const summary = $(".oddi-hfb-survey-intro span");
    if (summary) summary.textContent = `${count} of 10 rated · 1–5 stars · 3 or less needs a reason`;
    updateSurveySubmitState();
  }

  function updateSurveySubmitState() {
    const button = $("#oddiHfbSubmit");
    if (!button) return;
    const missingIndex = QUESTIONS.findIndex((_, index) => !state.ratings[escapeQuestionKey(index)]);
    const reasonIndex = QUESTIONS.findIndex((_, index) => {
      const key = escapeQuestionKey(index);
      return Number(state.ratings[key]) >= 1 && Number(state.ratings[key]) <= 3 && !String(state.reasons[key] || "").trim();
    });
    const complete = missingIndex < 0 && reasonIndex < 0;
    button.disabled = !state.user?.can_submit || !complete;
    const hint = $("#oddiHfbSubmitHint");
    if (!hint) return;
    if (!state.user?.can_submit) hint.textContent = "Sign in to an ODDI account to submit feedback.";
    else if (missingIndex >= 0) hint.textContent = `Rate question ${missingIndex + 1} to enable submit.`;
    else if (reasonIndex >= 0) hint.textContent = `Add a reason for question ${reasonIndex + 1} (3 stars or less).`;
    else hint.textContent = "All set. Your feedback is ready to submit.";
  }

  function questionForKey(key) {
    const index = Number(String(key).slice(1)) - 1;
    return QUESTIONS[index] || "this question";
  }

  function setStatus(selector, message, kind) {
    const node = $(selector);
    if (!node) return;
    node.textContent = message || "";
    node.className = "oddi-hfb-status" + (kind ? ` is-${kind}` : "");
  }

  function formatDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Recently";
    return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  }

  function formatCountdown(value) {
    const left = Math.max(0, new Date(value).getTime() - Date.now());
    const seconds = Math.floor(left / 1000);
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${String(hours).padStart(2, "0")}h ${String(minutes).padStart(2, "0")}m ${String(secs).padStart(2, "0")}s`;
  }

  function replyThread(submission, targetKey, hostView) {
    const replies = (submission.replies || []).filter(reply => reply.target_key === targetKey);
    const wrap = element("div", "oddi-hfb-replies");
    replies.forEach(reply => {
      const card = element("div", "oddi-hfb-reply");
      card.append(element("strong", "", "ODDI team replied"));
      card.append(element("p", "", reply.body));
      card.append(element("time", "", formatDate(reply.created_at)));
      wrap.appendChild(card);
    });
    if (hostView) {
      const form = element("form", "oddi-hfb-reply-form");
      form.dataset.submissionId = submission.id;
      form.dataset.targetKey = targetKey;
      const textarea = element("textarea");
      textarea.maxLength = 2000;
      textarea.rows = 2;
      textarea.required = true;
      textarea.placeholder = "Write a private reply to this user...";
      const button = element("button", "oddi-pref-action", "Send reply");
      button.type = "submit";
      form.append(textarea, button);
      wrap.appendChild(form);
    }
    return wrap;
  }

  function commentBlock(submission, targetKey, label, text, hostView) {
    const block = element("div", "oddi-hfb-comment-block");
    const title = element("div", "oddi-hfb-comment-title");
    title.append(element("strong", "", label));
    if (targetKey !== "overall") {
      const rating = Number((submission.ratings || {})[targetKey] || 0);
      title.append(element("span", "oddi-hfb-low-rating", `${rating} / 5 ★`));
    }
    block.append(title, element("p", "oddi-hfb-comment-text", text));
    block.appendChild(replyThread(submission, targetKey, hostView));
    return block;
  }

  function renderHistory(submissions, cooldownUntil) {
    const root = $("#oddiHfbHistory");
    if (!root) return;
    root.replaceChildren();
    if (!submissions?.length) return;
    root.appendChild(element("h5", "oddi-hfb-history-title", "Your feedback history"));
    submissions.forEach((submission, index) => {
      const details = element("details", "oddi-hfb-history-item");
      if (index === 0 && cooldownUntil) details.open = true;
      const average = QUESTIONS.length
        ? (Object.values(submission.ratings || {}).reduce((sum, n) => sum + Number(n || 0), 0) / QUESTIONS.length).toFixed(1)
        : "0.0";
      const summary = element("summary", "oddi-hfb-history-summary");
      summary.append(element("strong", "", index === 0 && cooldownUntil ? "Latest feedback" : "Feedback sent"));
      summary.append(element("span", "", `${average} / 5 average · ${formatDate(submission.submitted_at)}`));
      details.appendChild(summary);
      const body = element("div", "oddi-hfb-history-body");
      QUESTIONS.forEach((question, i) => {
        const key = escapeQuestionKey(i);
        const item = element("div", "oddi-hfb-history-question");
        item.append(element("strong", "", `Q${i + 1}. ${question}`));
        const value = Number((submission.ratings || {})[key] || 0);
        item.append(element("span", "oddi-hfb-history-rating", `${"★".repeat(value)}${"☆".repeat(5 - value)} (${value}/5)`));
        if ((submission.reasons || {})[key]) {
          item.append(element("p", "oddi-hfb-history-reason", submission.reasons[key]));
          item.appendChild(replyThread(submission, key, false));
        }
        body.appendChild(item);
      });
      if (submission.overall_feedback) {
        body.appendChild(commentBlock(submission, "overall", "Your written feedback", submission.overall_feedback, false));
      }
      details.appendChild(body);
      root.appendChild(details);
    });
  }

  function applyCooldown(until) {
    const badge = $("#oddiHfbCooldownBadge");
    const formWrap = $("#oddiHfbFeedbackFormWrap");
    const gate = $("#oddiHfbSignInGate");
    if (!badge || !formWrap) return;
    const activeUntil = until && new Date(until).getTime() > Date.now() ? until : null;
    state.cooldownUntil = activeUntil;
    badge.hidden = !activeUntil;
    if (!activeUntil) {
      badge.textContent = "";
      if (state.user?.can_submit) formWrap.hidden = false;
      return;
    }
    formWrap.hidden = true;
    badge.textContent = `Next survey in ${formatCountdown(activeUntil)}`;
    if (gate) gate.hidden = true;
  }

  async function loadFeedbackState() {
    try {
      const result = await api("/api/help-feedback/state");
      state.user = result;
      state.submissions = Array.isArray(result.submissions) ? result.submissions : [];
      $("#oddiHfbSignInGate").hidden = !!result.can_submit;
      $("#oddiHfbFeedbackFormWrap").hidden = !result.can_submit || !!(result.cooldown_until && new Date(result.cooldown_until).getTime() > Date.now());
      if (!result.can_submit && result.authenticated) {
        const gate = $("#oddiHfbSignInGate");
        if (gate) {
          const p = $("p", gate);
          if (p && result.account_message) p.textContent = result.account_message;
          const link = $("a", gate);
          if (link) link.href = "/login";
        }
      }
      const hostTab = $('[data-hfb-view="admin"]');
      if (hostTab) hostTab.hidden = !result.is_admin;
      applyCooldown(result.cooldown_until);
      renderHistory(state.submissions, state.cooldownUntil);
      updateSurveySubmitState();
      if ($("[data-hfb-panel='feedback']:not([hidden])") && result.unread_replies?.length) {
        $("#oddiHfbReplyToast")?.remove();
        void markRepliesRead(result.unread_replies);
      }
      if (!result.authenticated) setStatus("#oddiHfbFeedbackStatus", "Sign in to send feedback and get a reply in ODDI.", "info");
      else if (result.account_message) setStatus("#oddiHfbFeedbackStatus", result.account_message, "info");
      else setStatus("#oddiHfbFeedbackStatus", "", "");
      if (result.is_admin && $("[data-hfb-panel='admin']:not([hidden])")) void loadAdminInbox();
      return result;
    } catch (error) {
      let authResponse = null;
      let auth = null;
      try {
        authResponse = await fetch("/api/auth/me", { credentials: "same-origin", cache: "no-store" });
        auth = await authResponse.json();
      } catch (_) {}

      const authenticated = !!(authResponse?.ok && auth?.authenticated);
      const knownSignedOut = authResponse?.status === 401 || (authResponse?.ok && auth?.authenticated === false);
      const user = auth?.user || {};
      const isAdmin = String(user.email || "").trim().toLowerCase() === "vedansshrajsinha@gmail.com";
      state.user = {
        authenticated,
        can_submit: authenticated && auth?.can_submit_feedback !== false,
        is_admin: authenticated && isAdmin
      };
      const gate = $("#oddiHfbSignInGate");
      const formWrap = $("#oddiHfbFeedbackFormWrap");
      const authUnavailable = !knownSignedOut && !authenticated;
      if (gate) gate.hidden = authUnavailable || knownSignedOut || (authenticated && state.user.can_submit);
      if (formWrap) formWrap.hidden = knownSignedOut || (authenticated && !state.user.can_submit);
      const hostTab = $('[data-hfb-view="admin"]');
      if (hostTab) hostTab.hidden = !state.user.is_admin;
      updateSurveySubmitState();

      if (authenticated && state.user.can_submit) {
        setStatus("#oddiHfbFeedbackStatus", "Your feedback form is ready, but ODDI couldn't load your saved feedback or cooldown. The server will check the 24-hour limit when you submit.", "error");
      } else if (authenticated) {
        setStatus("#oddiHfbFeedbackStatus", "Sign in to an ODDI account to submit feedback and receive replies.", "info");
      } else if (knownSignedOut) {
        setStatus("#oddiHfbFeedbackStatus", "Sign in to send feedback and get a reply in ODDI.", "info");
      } else {
        // Keep the survey visible during a temporary auth or network outage, but
        // leave submission disabled until ODDI can verify the account.
        if (gate) gate.hidden = false;
        if (formWrap) formWrap.hidden = false;
        setStatus("#oddiHfbFeedbackStatus", "ODDI couldn't verify your account or load feedback right now. Your answers won't be sent until the connection is restored.", "error");
      }
      return null;
    }
  }

  async function submitSurvey(event) {
    event.preventDefault();
    if (!state.user?.can_submit) return;
    const missing = QUESTIONS.findIndex((_, index) => !state.ratings[escapeQuestionKey(index)]);
    if (missing >= 0) {
      setStatus("#oddiHfbFeedbackStatus", `Please rate question ${missing + 1} before submitting.`, "error");
      $$(".oddi-hfb-question-card")[missing]?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    for (let i = 0; i < QUESTIONS.length; i++) {
      const key = escapeQuestionKey(i);
      if (state.ratings[key] <= 3 && !String(state.reasons[key] || "").trim()) {
        setStatus("#oddiHfbFeedbackStatus", `Tell us why you gave question ${i + 1} ${state.ratings[key]} stars or less.`, "error");
        $(".oddi-hfb-question-card:nth-child(" + (i + 1) + ") textarea")?.focus();
        return;
      }
    }
    const button = $("#oddiHfbSubmit");
    button.disabled = true;
    button.textContent = "Submitting...";
    setStatus("#oddiHfbFeedbackStatus", "Saving your feedback securely to your ODDI account...", "info");
    try {
      const result = await api("/api/help-feedback/submissions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ratings: state.ratings, reasons: state.reasons, overall_feedback: $("#oddiHfbOverall").value })
      });
      const saved = result.submission;
      state.ratings = {};
      state.reasons = {};
      $("#oddiHfbOverall").value = "";
      const cards = $$(".oddi-hfb-question-card");
      cards.forEach(card => {
        card.querySelectorAll(".oddi-hfb-star").forEach(star => { star.classList.remove("is-selected"); star.setAttribute("aria-pressed", "false"); });
        const caption = $(".oddi-hfb-rating-caption", card);
        if (caption) caption.textContent = "Choose a rating";
        $(".oddi-hfb-reason-mount", card)?.replaceChildren();
        card.classList.remove("has-reason");
      });
      const count = $(".oddi-hfb-survey-intro span");
      if (saved) {
        state.submissions = [saved, ...state.submissions.filter(item => String(item.id) !== String(saved.id))];
        const submittedAt = new Date(saved.submitted_at || Date.now()).getTime();
        state.cooldownUntil = new Date((Number.isFinite(submittedAt) ? submittedAt : Date.now()) + 24 * 60 * 60 * 1000).toISOString();
        applyCooldown(state.cooldownUntil);
        renderHistory(state.submissions, state.cooldownUntil);
      }
      if (count) count.textContent = "Rate all 10 · 1–5 stars · 3 or less needs a reason";
      setStatus("#oddiHfbFeedbackStatus", "Thanks—your feedback is saved. You can submit again after the 24-hour cooldown. If the ODDI team replies, you'll see it here and in an in-app notification.", "success");
      if (state.user?.is_admin) await loadAdminInbox();
      return result;
    } catch (error) {
      if (error.status === 429 && error.payload?.cooldown_until) {
        state.cooldownUntil = error.payload.cooldown_until;
        applyCooldown(state.cooldownUntil);
        setStatus("#oddiHfbFeedbackStatus", "Your account is still in its 24-hour feedback cooldown.", "info");
      } else {
        setStatus("#oddiHfbFeedbackStatus", error.message, "error");
      }
    } finally {
      button.disabled = false;
      button.textContent = "Submit feedback";
      updateSurveySubmitState();
    }
  }

  function appendAdminComment(container, submission, targetKey, label, text) {
    const block = commentBlock(submission, targetKey, label, text, true);
    container.appendChild(block);
  }

  function renderAdminInbox(data) {
    const averages = $("#oddiHfbAverages");
    const inbox = $("#oddiHfbInbox");
    if (!averages || !inbox) return;
    averages.replaceChildren();
    inbox.replaceChildren();
    QUESTIONS.forEach((question, index) => {
      const item = (data.averages || {})[escapeQuestionKey(index)] || {};
      const card = element("div", "oddi-hfb-average-card");
      card.append(element("span", "oddi-hfb-question-number", String(index + 1).padStart(2, "0")));
      card.append(element("strong", "", item.average == null ? "— / 5" : `${Number(item.average).toFixed(1)} / 5 ★`));
      card.append(element("small", "", `${item.count || 0} ratings`));
      card.append(element("p", "", question));
      averages.appendChild(card);
    });
    const submissions = data.submissions || [];
    if (!submissions.length) {
      inbox.appendChild(element("div", "oddi-hfb-empty", "No feedback submissions yet."));
      return;
    }
    submissions.forEach(submission => {
      const card = element("article", "oddi-hfb-inbox-card");
      const heading = element("div", "oddi-hfb-inbox-card-head");
      const identity = element("div", "");
      identity.append(element("strong", "", submission.username || "ODDI user"));
      identity.append(element("small", "", submission.user_email || `Account ${submission.user_id}`));
      heading.append(identity, element("time", "", formatDate(submission.submitted_at)));
      card.appendChild(heading);
      const ratings = element("div", "oddi-hfb-rating-summary");
      QUESTIONS.forEach((question, index) => {
        const key = escapeQuestionKey(index);
        const score = Number((submission.ratings || {})[key] || 0);
        const row = element("div", "oddi-hfb-rating-summary-row");
        row.append(element("span", "", `Q${index + 1}. ${question}`));
        row.append(element("strong", score <= 3 ? "is-low" : "", `${score} / 5 ★`));
        ratings.appendChild(row);
      });
      card.appendChild(ratings);
      QUESTIONS.forEach((question, index) => {
        const key = escapeQuestionKey(index);
        const reason = String((submission.reasons || {})[key] || "").trim();
        if (reason && Number((submission.ratings || {})[key] || 5) <= 3) {
          appendAdminComment(card, submission, key, `Q${index + 1}. ${question}`, reason);
        }
      });
      if (String(submission.overall_feedback || "").trim()) {
        appendAdminComment(card, submission, "overall", "Overall written feedback", submission.overall_feedback);
      }
      inbox.appendChild(card);
    });
  }

  async function loadAdminInbox() {
    if (!state.user?.is_admin) return;
    setStatus("#oddiHfbAdminStatus", "Loading feedback from ODDI accounts...", "info");
    try {
      const data = await api("/api/help-feedback/admin");
      state.adminOverview = data;
      renderAdminInbox(data);
      setStatus("#oddiHfbAdminStatus", `${data.submission_count || 0} submissions · averages include all saved surveys.`, "success");
    } catch (error) {
      setStatus("#oddiHfbAdminStatus", error.message, "error");
    }
  }

  async function markRepliesRead(replies) {
    const replyIds = (replies || []).map(reply => reply?.id).filter(Boolean);
    if (!replyIds.length) return;
    try {
      await api("/api/help-feedback/replies/read", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reply_ids: replyIds })
      });
      replyIds.forEach(id => {
        state.inAppNotifiedReplyIds.delete(String(id));
        state.nativeNotifiedReplyIds.delete(String(id));
        state.pendingInAppReplies.delete(String(id));
      });
    } catch (_) {}
  }

  async function submitAdminReply(event) {
    const form = event.target.closest(".oddi-hfb-reply-form");
    if (!form) return;
    event.preventDefault();
    const textarea = $("textarea", form);
    const button = $("button", form);
    if (!textarea?.value.trim() || button.disabled) return;
    button.disabled = true;
    button.textContent = "Sending...";
    try {
      await api(`/api/help-feedback/admin/${encodeURIComponent(form.dataset.submissionId)}/replies`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_key: form.dataset.targetKey, body: textarea.value })
      });
      await loadAdminInbox();
    } catch (error) {
      setStatus("#oddiHfbAdminStatus", error.message, "error");
      button.disabled = false;
      button.textContent = "Send reply";
    }
  }

  function setHfbView(name) {
    const allowed = name === "admin" && !state.user?.is_admin ? "help" : name;
    $$('[data-hfb-view]').forEach(button => {
      const active = button.dataset.hfbView === allowed;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-selected", String(active));
    });
    $$('[data-hfb-panel]').forEach(panel => { panel.hidden = panel.dataset.hfbPanel !== allowed; });
    if (allowed === "feedback") void loadFeedbackState();
    if (allowed === "admin") void loadAdminInbox();
  }

  function closeTourScreens() {
    $("#oddiWorkspaceOverlay.is-open .oddi-workspace-close")?.click();
    if ($("#oddiLibraryModal.show")) $("#oddiLibraryClose")?.click();
    window.__oddiCloseSettings?.();
    window.dispatchEvent(new CustomEvent("oddi:sidebar-close"));
  }

  function prepareTourSidebar() {
    closeTourScreens();
    window.dispatchEvent(new CustomEvent("oddi:sidebar-open"));
    window.requestAnimationFrame(() => {
      if (document.body.classList.contains("oddi-react-sidebar-collapsed")) {
        document.querySelector(".oddi-rs-collapse")?.click();
      }
    });
  }

  function prepareTourMain() {
    closeTourScreens();
  }

  function prepareTourProjects() {
    closeTourScreens();
    window.dispatchEvent(new CustomEvent("oddi:open-projects"));
  }

  function prepareTourLibrary() {
    closeTourScreens();
    window.dispatchEvent(new CustomEvent("oddi:open-library"));
  }

  function prepareTourSettings(tab) {
    closeTourScreens();
    window.__oddiOpenSettings?.(tab);
  }

  function createTour() {
    if (tourRoot) return tourRoot;
    const root = element("div", "oddi-hfb-tour");
    root.setAttribute("role", "dialog");
    root.setAttribute("aria-modal", "true");
    root.setAttribute("aria-labelledby", "oddiHfbTourTitle");
    root.setAttribute("aria-describedby", "oddiHfbTourDescription");
    root.tabIndex = -1;
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("preserveAspectRatio", "none");
    const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    const mask = document.createElementNS("http://www.w3.org/2000/svg", "mask");
    mask.id = "oddiHfbTourMask";
    mask.setAttribute("maskUnits", "userSpaceOnUse");
    const whole = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    whole.setAttribute("id", "oddiHfbTourMaskWhole");
    whole.setAttribute("fill", "white");
    const hole = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    hole.id = "oddiHfbTourHole";
    hole.setAttribute("fill", "black");
    hole.setAttribute("rx", "14");
    mask.append(whole, hole);
    defs.appendChild(mask);
    const shade = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    shade.setAttribute("id", "oddiHfbTourShade");
    shade.setAttribute("fill", "rgba(0,0,0,.70)");
    shade.setAttribute("mask", "url(#oddiHfbTourMask)");
    const border = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    border.id = "oddiHfbTourBorder";
    border.setAttribute("fill", "none");
    border.setAttribute("stroke", "#31d28a");
    border.setAttribute("stroke-width", "3");
    border.setAttribute("rx", "14");
    svg.append(defs, shade, border);

    const card = element("section", "oddi-hfb-tour-card");
    const top = element("div", "oddi-hfb-tour-top");
    const progress = element("span", "oddi-hfb-tour-progress");
    progress.setAttribute("role", "status");
    progress.setAttribute("aria-live", "polite");
    const progressTrack = element("div", "oddi-hfb-tour-progress-track");
    progressTrack.setAttribute("role", "progressbar");
    progressTrack.setAttribute("aria-label", "Tutorial progress");
    progressTrack.setAttribute("aria-valuemin", "1");
    progressTrack.setAttribute("aria-valuemax", String(tourSteps.length));
    const progressFill = element("span", "oddi-hfb-tour-progress-fill");
    progressTrack.appendChild(progressFill);
    const actions = element("div", "oddi-hfb-tour-actions");
    const restart = element("button", "oddi-hfb-tour-restart", "Restart");
    restart.type = "button";
    restart.addEventListener("click", restartTour);
    const skip = element("button", "oddi-hfb-tour-skip", "Skip tour");
    skip.type = "button";
    skip.addEventListener("click", finishTour);
    actions.append(restart, skip);
    top.append(progress, actions);
    const title = element("h3", "", "");
    title.id = "oddiHfbTourTitle";
    const body = element("p", "");
    body.id = "oddiHfbTourDescription";
    body.setAttribute("aria-live", "polite");
    const targetNote = element("p", "oddi-hfb-tour-target-note", "This part of ODDI is not visible right now. Continue to the next step, or restart the tour once it is available.");
    targetNote.setAttribute("role", "status");
    targetNote.hidden = true;
    const openLink = element("button", "oddi-hfb-tour-link", "");
    openLink.type = "button";
    openLink.hidden = true;
    openLink.addEventListener("click", () => {
      const href = openLink.dataset.href;
      if (!href) return;
      window.open(new URL(href, window.location.origin).href, "_blank", "noopener,noreferrer");
    });
    const controls = element("div", "oddi-hfb-tour-controls");
    const back = element("button", "oddi-pref-action", "Back");
    const next = element("button", "oddi-pref-primary", "Next");
    back.type = next.type = "button";
    back.addEventListener("click", () => { if (tourIndex > 0) { tourIndex--; void showTourStep(); } });
    next.addEventListener("click", () => {
      advanceTour();
    });
    controls.append(back, next);
    card.append(top, progressTrack, title, body, targetNote, openLink, controls);
    const blocker = element("div", "oddi-hfb-tour-blocker");
    blocker.setAttribute("aria-hidden", "true");
    root.append(svg, blocker, card);
    root.addEventListener("keydown", event => {
      if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); finishTour(); return; }
      if (event.key === "ArrowLeft" && tourIndex > 0) { event.preventDefault(); tourIndex--; void showTourStep(); return; }
      if (event.key === "ArrowRight") { event.preventDefault(); advanceTour(); return; }
      if (event.key === "Tab") {
        const focusable = $$("button:not([disabled]):not([hidden])", root);
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (!root.contains(document.activeElement)) { event.preventDefault(); (event.shiftKey ? last : first).focus(); }
        else if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    });
    root._refs = { svg, whole, hole, shade, border, card, progress, progressTrack, progressFill, title, body, targetNote, openLink, back, next };
    tourRoot = root;
    return root;
  }

  function setTourMask(target) {
    if (!tourRoot) return;
    const refs = tourRoot._refs;
    const width = window.innerWidth;
    const height = window.innerHeight;
    refs.svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    [refs.whole, refs.shade].forEach(node => { node.setAttribute("x", "0"); node.setAttribute("y", "0"); node.setAttribute("width", String(width)); node.setAttribute("height", String(height)); });
    if (target?.isConnected) {
      const rect = target.getBoundingClientRect();
      const pad = 7;
      const left = Math.max(0, rect.left);
      const top = Math.max(0, rect.top);
      const right = Math.min(width, rect.right);
      const bottom = Math.min(height, rect.bottom);
      if (right > left && bottom > top) {
        const x = Math.max(5, left - pad);
        const y = Math.max(5, top - pad);
        const w = Math.min(width - x - 5, right - left + (left > pad ? pad : 0) + (right < width ? pad : 0));
        const h = Math.min(height - y - 5, bottom - top + (top > pad ? pad : 0) + (bottom < height ? pad : 0));
        [refs.hole, refs.border].forEach(node => { node.setAttribute("x", String(x)); node.setAttribute("y", String(y)); node.setAttribute("width", String(Math.max(0, w))); node.setAttribute("height", String(Math.max(0, h))); });
        tourTarget = target;
      } else {
        refs.hole.setAttribute("width", "0");
        refs.hole.setAttribute("height", "0");
        refs.border.setAttribute("width", "0");
        refs.border.setAttribute("height", "0");
        tourTarget = null;
      }
    } else {
      refs.hole.setAttribute("width", "0");
      refs.hole.setAttribute("height", "0");
      refs.border.setAttribute("width", "0");
      refs.border.setAttribute("height", "0");
      tourTarget = null;
    }
  }

  function placeTourCard(target) {
    if (!tourRoot) return;
    const card = tourRoot._refs.card;
    const margin = 18;
    const viewportHeight = window.visualViewport?.height || window.innerHeight;
    const maxWidth = Math.max(0, Math.min(440, window.innerWidth - margin * 2));
    card.style.width = `${maxWidth}px`;
    card.style.maxHeight = `${Math.max(120, viewportHeight - margin * 2)}px`;
    const rect = target?.getBoundingClientRect();
    const cardRect = card.getBoundingClientRect();
    let left = (window.innerWidth - maxWidth) / 2;
    let top = (viewportHeight - cardRect.height) / 2;
    if (rect) {
      left = Math.max(margin, Math.min(window.innerWidth - maxWidth - margin, rect.left + rect.width / 2 - maxWidth / 2));
      top = rect.bottom + 18;
      if (top + cardRect.height > viewportHeight - margin) top = rect.top - cardRect.height - 18;
      top = Math.max(margin, Math.min(viewportHeight - cardRect.height - margin, top));
    }
    card.style.left = `${left}px`;
    card.style.top = `${top}px`;
  }

  function advanceTour() {
    if (tourIndex >= tourSteps.length - 1) finishTour();
    else { tourIndex++; void showTourStep(); }
  }

  function restartTour() {
    tourIndex = 0;
    closeTourScreens();
    void showTourStep();
  }

  async function showTourStep() {
    const renderId = ++tourRenderId;
    const stepIndex = tourIndex;
    const step = tourSteps[stepIndex];
    const root = createTour();
    if (!root.isConnected) document.body.appendChild(root);
    const refs = root._refs;
    if (typeof step.prepare === "function") step.prepare();
    refs.progress.textContent = `STEP ${String(stepIndex + 1).padStart(2, "0")} OF ${tourSteps.length}  ·  ${step.chapter.toUpperCase()}`;
    refs.progressTrack.setAttribute("aria-valuenow", String(stepIndex + 1));
    refs.progressFill.style.width = `${((stepIndex + 1) / tourSteps.length) * 100}%`;
    refs.title.textContent = step.title;
    refs.body.textContent = step.body;
    refs.back.disabled = stepIndex === 0;
    refs.back.setAttribute("aria-label", stepIndex === 0 ? "Back, first tutorial step" : `Back to ${tourSteps[stepIndex - 1].title}`);
    refs.next.textContent = stepIndex === tourSteps.length - 1 ? "Finish tour" : "Next";
    refs.next.setAttribute("aria-label", stepIndex === tourSteps.length - 1 ? "Finish the website tutorial" : `Next: ${tourSteps[stepIndex + 1].title}`);
    refs.openLink.hidden = !step.link;
    refs.openLink.textContent = step.linkLabel || "Open this section in a new tab";
    if (step.link) refs.openLink.dataset.href = step.link;
    else delete refs.openLink.dataset.href;
    refs.targetNote.textContent = step.target ? "Finding this part of ODDI..." : "This section is not available right now. You can skip ahead or reopen the tour once it is available.";
    refs.targetNote.hidden = !step.target;
    setTourMask(null);
    placeTourCard(null);
    refs.next.focus({ preventScroll: true });
    let target = null;
    if (step.target) {
      for (let attempt = 0; attempt < 24; attempt++) {
        try { target = $(step.target); } catch (_) { target = null; }
        if (target?.isConnected) {
          const rect = target.getBoundingClientRect();
          const style = window.getComputedStyle(target);
          if (rect.width > 2 && rect.height > 2 && style.display !== "none" && style.visibility !== "hidden") break;
        }
        target = null;
        await new Promise(resolve => setTimeout(resolve, 100));
        if (renderId !== tourRenderId) return;
      }
      if (target) {
        const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
        target.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "center", inline: "nearest" });
        await new Promise(resolve => setTimeout(resolve, reduceMotion ? 0 : 320));
        if (renderId !== tourRenderId) return;
        const rect = target.getBoundingClientRect();
        if (rect.width < 2 || rect.height < 2) target = null;
      }
    }
    if (renderId !== tourRenderId || !root.isConnected) return;
    setTourMask(target);
    refs.targetNote.textContent = "This section is not available right now. You can skip ahead or reopen the tour once it is available.";
    refs.targetNote.hidden = !step.target || !!tourTarget;
    placeTourCard(tourTarget ? target : null);
    refs.next.focus({ preventScroll: true });
  }

  function startTour() {
    tourIndex = 0;
    state.tourReturnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    state.tourSidebarWasOpen = document.body.classList.contains("oddi-react-sidebar-open");
    state.tourSidebarWasCollapsed = document.body.classList.contains("oddi-react-sidebar-collapsed");
    closeTourScreens();
    void showTourStep();
  }

  function finishTour() {
    tourRenderId++;
    tourRoot?.remove();
    tourTarget = null;
    closeTourScreens();
    if (state.tourSidebarWasOpen) {
      window.dispatchEvent(new CustomEvent("oddi:sidebar-open"));
      if (state.tourSidebarWasCollapsed) window.setTimeout(() => document.querySelector(".oddi-rs-collapse")?.click(), 0);
    }
    window.__oddiOpenSettings?.("help-feedback");
    setHfbView("help");
    const returnFocus = state.tourReturnFocus;
    state.tourReturnFocus = null;
    window.setTimeout(() => {
      if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true });
      else $("#oddiHfbStartTour")?.focus({ preventScroll: true });
    }, 0);
  }

  function showReplyNotification(replies, useNative) {
    const notified = useNative ? state.nativeNotifiedReplyIds : state.inAppNotifiedReplyIds;
    const unique = replies.filter(reply => reply && reply.id && !notified.has(String(reply.id))).slice(0, 8);
    if (!unique.length) return;
    unique.forEach(reply => notified.add(String(reply.id)));
    if (!useNative) unique.forEach(reply => state.pendingInAppReplies.set(String(reply.id), reply));
    const displayReplies = useNative ? unique : Array.from(state.pendingInAppReplies.values()).slice(0, 100);
    const title = displayReplies.length === 1 ? "ODDI team replied to your feedback" : `You have ${displayReplies.length} new replies from ODDI`;
    const preview = String(displayReplies[displayReplies.length - 1]?.body || "Open Help & Feedback to read your reply.").slice(0, 150);
    const markRead = () => markRepliesRead(displayReplies);
    const openFeedback = () => {
      window.__oddiOpenSettings?.("help-feedback");
      setHfbView("feedback");
    };
    if (useNative) {
      try {
        const notification = new Notification(title, { body: preview, tag: "oddi-feedback-reply" });
        notification.onclick = async () => { await markRead(); window.focus(); openFeedback(); notification.close(); };
      } catch (_) {}
      return;
    }
    let toast = $("#oddiHfbReplyToast");
    if (!toast) {
      toast = element("div", "oddi-hfb-reply-toast");
      toast.id = "oddiHfbReplyToast";
      toast.setAttribute("role", "status");
      toast.setAttribute("aria-live", "polite");
      document.body.appendChild(toast);
    }
    toast.replaceChildren();
    const copy = element("div", "oddi-hfb-toast-copy");
    copy.append(element("strong", "", title), element("span", "", preview));
    const open = element("button", "", "View reply");
    open.type = "button";
    open.addEventListener("click", async () => { await markRead(); openFeedback(); toast.remove(); });
    const close = element("button", "oddi-hfb-toast-close", "×");
    close.type = "button";
    close.setAttribute("aria-label", "Dismiss notification");
    close.addEventListener("click", () => toast.remove());
    toast.append(copy, open, close);
  }

  async function checkReplyNotifications() {
    try {
      const result = await api("/api/help-feedback/notifications");
      if (!result.unread_replies?.length) return;
      if ($("[data-hfb-panel='feedback']:not([hidden])")) {
        await loadFeedbackState();
        return;
      }
      const nativeAllowed = document.hidden && "Notification" in window && Notification.permission === "granted" && window.__oddiNotificationsEnabled !== false;
      if (document.hidden && !nativeAllowed) return;
      showReplyNotification(result.unread_replies, nativeAllowed);
    } catch (_) {}
  }

  function initialize() {
    const panel = $("#oddiHelpFeedbackPanel");
    if (!panel) return;
    renderFaqs();
    renderSurvey();
    $("#oddiHfbFaqSearch")?.addEventListener("input", renderFaqs);
    $("#oddiHfbFeedbackForm")?.addEventListener("submit", submitSurvey);
    $("#oddiHfbStartTour")?.addEventListener("click", startTour);
    $("#oddiHfbRefreshInbox")?.addEventListener("click", loadAdminInbox);
    $("#oddiHfbInbox")?.addEventListener("submit", submitAdminReply);
    $$("[data-hfb-view]").forEach(button => button.addEventListener("click", () => setHfbView(button.dataset.hfbView)));
    panel.addEventListener("click", event => {
      const goFeedback = event.target.closest("[data-hfb-open-feedback]");
      if (goFeedback) setHfbView("feedback");
    });
    window.addEventListener("oddi:settings-tab-activated", event => {
      if (event.detail?.name === "help-feedback") void loadFeedbackState();
    });
    const repositionTour = () => { if (tourRoot?.isConnected) { setTourMask(tourTarget); placeTourCard(tourTarget); } };
    window.addEventListener("resize", repositionTour, { passive: true });
    window.addEventListener("scroll", repositionTour, { passive: true, capture: true });
    window.visualViewport?.addEventListener("resize", repositionTour, { passive: true });
    window.visualViewport?.addEventListener("scroll", repositionTour, { passive: true });
    document.addEventListener("visibilitychange", () => { if (!document.hidden) void checkReplyNotifications(); });
    window.setInterval(() => { if (state.cooldownUntil) applyCooldown(state.cooldownUntil); }, 1000);
    window.setInterval(() => { void checkReplyNotifications(); }, 60000);
    void checkReplyNotifications();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialize, { once: true });
  else initialize();
})();
