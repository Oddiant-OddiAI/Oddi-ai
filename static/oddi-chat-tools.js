(() => {
  "use strict";

  const attachButton = document.getElementById("attach-btn");
  const fileInput = document.getElementById("fileInput");
  const composer = document.getElementById("oddiComposerShell");
  const composerField = composer?.querySelector(".oddi-composer-field");
  const chatbox = document.getElementById("chatbox");
  const textarea = document.getElementById("userInput");
  const headerControls = document.querySelector(".header-controls");
  const appHeader = headerControls?.closest(".header") || document.querySelector(".app > .header");
  const moreButton = document.querySelector(".header-more");
  if (!attachButton || !fileInput || !composer || !composerField || !textarea || !headerControls) return;

  let agentMention = composerField.querySelector(".oddi-composer-agent-mention");
  if (!agentMention) {
    agentMention = document.createElement("span");
    agentMention.className = "oddi-composer-agent-mention";
    agentMention.hidden = true;
    agentMention.setAttribute("role", "status");
    agentMention.setAttribute("aria-live", "polite");
    composerField.insertBefore(agentMention, textarea);
  }

  let composerInputGroup = composerField.querySelector(".oddi-composer-input-group");
  if (!composerInputGroup) {
    composerInputGroup = document.createElement("div");
    composerInputGroup.className = "oddi-composer-input-group";
    composerField.insertBefore(composerInputGroup, agentMention);
    composerInputGroup.append(agentMention, textarea);
  }

  const AGENTS = [
    { id: "research", name: "Research Agent", detail: "Thorough research with cited sources", icon: "<path d=\"M10 3H3v18h18V11\"/><path d=\"M14 3h7v7\"/><path d=\"m21 3-11 11\"/><path d=\"M7 7h3M7 11h2M7 15h5\"/>" },
    { id: "search", name: "Search Agent", detail: "Find current information on the web", icon: "<circle cx=\"10.8\" cy=\"10.8\" r=\"6.8\"/><path d=\"m16 16 5 5\"/><path d=\"M8 11h5M10.5 8.5v5\"/>" },
    { id: "coding", name: "Coding Agent", detail: "Build, debug, and explain code", icon: "<path d=\"m8 8-4 4 4 4M16 8l4 4-4 4M14 5l-4 14\"/>" },
    { id: "document_search", name: "Document Search Agent", detail: "Find answers in attached Library files", icon: "<path d=\"M7 3h7l5 5v13H7z\"/><path d=\"M14 3v6h5M10 13h6M10 17h3\"/><circle cx=\"17.5\" cy=\"17.5\" r=\"2.5\"/><path d=\"m19.3 19.3 2 2\"/>" }
  ];
  const MAX_LIBRARY_SELECTION = 4;
  let selectedAgentId = "";
  let libraryFiles = [];
  const selectedLibraryIds = new Set();
  let libraryOpener = null;
  let libraryBusy = false;
  let incognitoEnabled = false;

  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
  }[char]));
  const icon = paths => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;
  const toast = (message, kind = "info") => window.showOddiToast?.(message, kind);

  const moreControlButton = document.getElementById("headerMoreBtn");
  const themeControlButton = document.getElementById("themeBtn");
  if (moreControlButton) {
    moreControlButton.innerHTML = `<svg class="oddi-header-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="5" r="1.45"/><circle cx="12" cy="12" r="1.45"/><circle cx="12" cy="19" r="1.45"/></svg>`;
  }
  const themeIconPaths = {
    light: `<path d="M20.2 15.1A8.2 8.2 0 0 1 8.9 3.8 8.7 8.7 0 1 0 20.2 15.1Z"/>`,
    dark: `<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"/>`,
    system: `<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8m-4-4v4"/><path d="M12 7v3l2 1"/>`
  };
  function syncThemeControlIcon() {
    if (!themeControlButton) return;
    const preference = localStorage.getItem("oddi_theme_v1") || "light";
    const mode = preference === "system" ? "system" : (preference === "dark" ? "dark" : "light");
    if (themeControlButton.dataset.oddiIconMode === mode && themeControlButton.querySelector("svg.oddi-header-icon")) return;
    themeControlButton.dataset.oddiIconMode = mode;
    themeControlButton.innerHTML = `<svg class="oddi-header-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${themeIconPaths[mode]}</svg>`;
  }
  syncThemeControlIcon();
  if (themeControlButton && window.MutationObserver) {
    new MutationObserver(syncThemeControlIcon).observe(themeControlButton, { childList: true, subtree: true });
  }
  window.addEventListener("oddi:theme-changed", syncThemeControlIcon);

  const incognitoButton = document.createElement("button");
  incognitoButton.id = "headerIncognitoBtn";
  incognitoButton.className = "incognito-toggle";
  incognitoButton.type = "button";
  incognitoButton.setAttribute("aria-pressed", "false");
  incognitoButton.setAttribute("aria-label", "Start an Incognito chat");
  incognitoButton.title = "Incognito chat · not saved to ODDI history or memory";
  const incognitoIcon = icon("<path d=\"M5.1 9.4 6.4 4.8a1.8 1.8 0 0 1 1.8-1.3h7.6a1.8 1.8 0 0 1 1.8 1.3l1.3 4.6H5.1Z\"/><path d=\"M3 9.8c2.1 1.1 5.1 1.7 9 1.7s6.9-.6 9-1.7\"/><path d=\"M4.3 13h6.2l-.4 3a2.8 2.8 0 0 1-5.5 0l-.3-3Zm9.2 0h6.2l-.4 3a2.8 2.8 0 0 1-5.5 0l-.3-3Z\"/><path d=\"M10.6 13.7c.8-.8 2-.8 2.8 0\"/>");
  incognitoButton.innerHTML = incognitoIcon;
  if (moreButton) headerControls.insertBefore(incognitoButton, moreButton);
  else headerControls.appendChild(incognitoButton);

  const incognitoHeaderNotice = document.createElement("div");
  incognitoHeaderNotice.id = "oddiIncognitoHeaderNotice";
  incognitoHeaderNotice.className = "oddi-incognito-header-notice";
  incognitoHeaderNotice.setAttribute("role", "status");
  incognitoHeaderNotice.setAttribute("aria-live", "polite");
  incognitoHeaderNotice.hidden = true;
  const incognitoHeaderTitle = document.createElement("span");
  incognitoHeaderTitle.className = "oddi-incognito-header-title";
  incognitoHeaderTitle.textContent = "Temporary Chats";
  const incognitoHeaderStatus = document.createElement("strong");
  incognitoHeaderStatus.className = "oddi-incognito-header-status";
  incognitoHeaderStatus.textContent = "Incognito \u00b7 not saved to ODDI history or memory";
  incognitoHeaderNotice.append(incognitoHeaderTitle, incognitoHeaderStatus);
  appHeader?.appendChild(incognitoHeaderNotice);

  const toolMenu = document.createElement("div");
  toolMenu.id = "oddiComposerToolMenu";
  toolMenu.setAttribute("role", "menu");
  toolMenu.setAttribute("aria-hidden", "true");
  toolMenu.setAttribute("aria-label", "Add to your message");
  const toolRows = [
    ["file", "Add photos & files", "Upload from your computer", "<path d=\"M20.5 11.5 12 20a6 6 0 0 1-8.5-8.5l9.2-9.2a4 4 0 0 1 5.7 5.7l-9.2 9.2a2 2 0 0 1-2.8-2.8l8.5-8.5\"/>"],
    ["library", "Add from library", "Browse and choose your files", "<path d=\"M4 5h16v14H4z\"/><path d=\"M8 9h8M8 12h5M8 15h8\"/><path d=\"M2 7v14h16\"/>"],
    ...AGENTS.map(agent => [agent.id, agent.name, agent.detail, agent.icon])
  ];
  toolMenu.innerHTML = `<div class="oddi-tool-menu-label">Add to your message</div>${toolRows.map(([id, name, detail, paths], index) => {
    const divider = index === 2 ? '<div class="oddi-tool-menu-divider" role="separator"></div><div class="oddi-tool-menu-label">Choose one agent</div>' : "";
    return `${divider}<button class="oddi-tool-item" type="button" role="menuitem" data-tool="${escapeHtml(id)}" aria-pressed="false"><span class="oddi-tool-icon">${icon(paths)}</span><span class="oddi-tool-copy"><span class="oddi-tool-title">${escapeHtml(name)}</span><span class="oddi-tool-subtitle">${escapeHtml(detail)}</span></span><span class="oddi-tool-check" aria-hidden="true"></span></button>`;
  }).join("")}`;
  document.body.appendChild(toolMenu);

  const libraryPicker = document.createElement("div");
  libraryPicker.id = "oddiChatLibraryPicker";
  libraryPicker.setAttribute("aria-hidden", "true");
  libraryPicker.innerHTML = `
    <section class="oddi-chat-library-panel" role="dialog" aria-modal="true" aria-labelledby="oddiChatLibraryTitle">
      <header class="oddi-chat-library-head">
        <div class="oddi-chat-library-heading"><h2 id="oddiChatLibraryTitle">Add from Library</h2><p>Choose up to ${MAX_LIBRARY_SELECTION} files to attach to this chat.</p></div>
        <button type="button" class="oddi-chat-library-close" data-library-close aria-label="Close Library picker">×</button>
      </header>
      <label class="oddi-chat-library-search-wrap">${icon("<circle cx=\"10.8\" cy=\"10.8\" r=\"6.8\"/><path d=\"m16 16 5 5\"/>")}<input id="oddiChatLibrarySearch" type="search" autocomplete="off" placeholder="Search Library" aria-label="Search Library"></label>
      <div id="oddiChatLibraryCount" class="oddi-chat-library-count" aria-live="polite">Loading your files…</div>
      <div id="oddiChatLibraryRows" role="group" aria-label="Library files"></div>
      <footer class="oddi-chat-library-foot"><span id="oddiChatLibrarySelection" class="oddi-chat-library-selection" aria-live="polite">0 selected</span><div class="oddi-chat-library-actions"><button type="button" data-library-close>Cancel</button><button type="button" id="oddiChatLibraryAdd" disabled>Add to chat</button></div></footer>
    </section>`;
  document.body.appendChild(libraryPicker);

  const librarySearch = libraryPicker.querySelector("#oddiChatLibrarySearch");
  const libraryRows = libraryPicker.querySelector("#oddiChatLibraryRows");
  const libraryCount = libraryPicker.querySelector("#oddiChatLibraryCount");
  const librarySelectionLabel = libraryPicker.querySelector("#oddiChatLibrarySelection");
  const addLibraryButton = libraryPicker.querySelector("#oddiChatLibraryAdd");

  function activeAgent() { return AGENTS.find(agent => agent.id === selectedAgentId) || null; }

  function syncAgentMention(agent) {
    const nextPrefix = agent ? `@${agent.name}` : "";
    agentMention.textContent = nextPrefix;
    agentMention.hidden = !nextPrefix;
    agentMention.setAttribute("aria-label", nextPrefix ? `${nextPrefix} selected` : "No specialist selected");
  }

  function syncIncognitoButtonVisibility() {
    const chatHasMessages = !!chatbox?.querySelector(".user-message, .bot-message");
    incognitoButton.hidden = chatHasMessages;
    incognitoButton.setAttribute("aria-hidden", chatHasMessages ? "true" : "false");
    if (chatHasMessages) incognitoButton.tabIndex = -1;
    else incognitoButton.removeAttribute("tabindex");
  }

  function updateToolAgentState() {
    toolMenu.querySelectorAll("[data-tool]").forEach(button => {
      const active = AGENTS.some(agent => agent.id === button.dataset.tool) && button.dataset.tool === selectedAgentId;
      button.setAttribute("aria-pressed", active ? "true" : "false");
      const check = button.querySelector(".oddi-tool-check");
      if (check) check.textContent = active ? "✓" : "";
    });
    incognitoButton.setAttribute("aria-pressed", incognitoEnabled ? "true" : "false");
    incognitoButton.setAttribute("aria-label", incognitoEnabled ? "End Incognito chat" : "Start an Incognito chat");
    incognitoButton.title = incognitoEnabled
      ? "Incognito is on · not saved to ODDI history or memory · click to end"
      : "Start an Incognito chat · not saved to ODDI history or memory";
    document.body.classList.toggle("oddi-incognito-active", incognitoEnabled);
    incognitoHeaderNotice.hidden = !incognitoEnabled;
    syncIncognitoButtonVisibility();

    const agent = activeAgent();
    composer.classList.toggle("has-specialist-agent", !!agent);
    syncAgentMention(agent);
  }

  function closeToolMenu({ focus = false } = {}) {
    toolMenu.classList.remove("open");
    toolMenu.setAttribute("aria-hidden", "true");
    attachButton.setAttribute("aria-expanded", "false");
    attachButton.setAttribute("aria-label", "Add photos, files, Library items, or an agent");
    attachButton.title = "Add photos, files, Library items, or an agent";
    if (focus) attachButton.focus({ preventScroll: true });
  }

  function positionToolMenu() {
    const rect = attachButton.getBoundingClientRect();
    const width = Math.min(376, window.innerWidth - 24);
    const left = Math.max(12, Math.min(rect.left, window.innerWidth - width - 12));
    toolMenu.style.left = `${left}px`;
    toolMenu.style.bottom = `${Math.max(12, window.innerHeight - rect.top + 8)}px`;
  }

  function openToolMenu() {
    positionToolMenu();
    toolMenu.classList.add("open");
    toolMenu.setAttribute("aria-hidden", "false");
    attachButton.setAttribute("aria-expanded", "true");
    attachButton.setAttribute("aria-label", "Close message tools");
    attachButton.title = "Close message tools";
    const first = toolMenu.querySelector("[data-tool='file']");
    first?.focus({ preventScroll: true });
  }

  function openLibraryPicker() {
    libraryOpener = attachButton;
    closeToolMenu();
    selectedLibraryIds.clear();
    libraryPicker.classList.add("open");
    libraryPicker.setAttribute("aria-hidden", "false");
    document.body.classList.add("oddi-chat-library-picker-open");
    librarySearch.value = "";
    libraryRows.innerHTML = '<div class="oddi-chat-library-empty"><strong>Loading your Library</strong><span>Fetching your saved files…</span></div>';
    libraryCount.textContent = "Loading your files…";
    librarySearch.focus({ preventScroll: true });
    refreshLibraryFiles();
  }

  function closeLibraryPicker({ restoreFocus = true } = {}) {
    libraryPicker.classList.remove("open");
    libraryPicker.setAttribute("aria-hidden", "true");
    document.body.classList.remove("oddi-chat-library-picker-open");
    if (restoreFocus && libraryOpener?.isConnected) libraryOpener.focus({ preventScroll: true });
  }

  async function refreshLibraryFiles() {
    libraryCount.textContent = "Loading your files…";
    try {
      const response = await fetch("/api/files", {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
        cache: "no-store"
      });
      if (response.status === 401 || response.status === 403) throw new Error("Sign in to use files from your Library.");
      if (!response.ok) throw new Error(`Library could not be loaded (HTTP ${response.status}).`);
      const payload = await response.json();
      libraryFiles = (Array.isArray(payload) ? payload : (Array.isArray(payload?.files) ? payload.files : []))
        .filter(file => file && file.id != null)
        .sort((a, b) => String(b.created_at || b.updated_at || "").localeCompare(String(a.created_at || a.updated_at || "")));
      renderLibraryRows();
    } catch (error) {
      libraryFiles = [];
      libraryRows.innerHTML = `<div class="oddi-chat-library-empty"><strong>Library unavailable</strong><span>${escapeHtml(error?.message || "Could not load your Library.")}</span></div>`;
      libraryCount.textContent = "";
      updateLibrarySelection();
      toast(error?.message || "Could not load your Library.", "error");
    }
  }

  function renderLibraryRows() {
    const query = String(librarySearch.value || "").trim().toLocaleLowerCase();
    const visible = libraryFiles.filter(file => `${file.filename || file.name || ""} ${file.mime_type || file.type || ""}`.toLocaleLowerCase().includes(query));
    libraryCount.textContent = `${visible.length} ${visible.length === 1 ? "file" : "files"}${query ? " found" : " in your Library"}`;
    if (!visible.length) {
      libraryRows.innerHTML = `<div class="oddi-chat-library-empty"><strong>${libraryFiles.length ? "No matches" : "Your Library is empty"}</strong><span>${libraryFiles.length ? "Try a different search." : "Use Add photos & files to upload a file first."}</span></div>`;
      updateLibrarySelection();
      return;
    }
    libraryRows.innerHTML = visible.map(file => {
      const id = String(file.id);
      const name = String(file.filename || file.name || "Unnamed file");
      const mime = String(file.mime_type || file.type || "File");
      const dateRaw = file.created_at || file.updated_at || "";
      const dateTime = Date.parse(dateRaw);
      const date = Number.isFinite(dateTime)
        ? new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(dateTime))
        : mime;
      const selected = selectedLibraryIds.has(id);
      return `<label class="oddi-chat-library-row${selected ? " is-selected" : ""}" data-file-id="${escapeHtml(id)}"><input class="oddi-chat-library-check" type="checkbox" value="${escapeHtml(id)}" aria-label="Select ${escapeHtml(name)}"${selected ? " checked" : ""}><span class="oddi-chat-library-file-icon">${icon(mime.startsWith("image/") ? "<rect x=\"3\" y=\"4\" width=\"18\" height=\"16\" rx=\"2\"/><circle cx=\"8.5\" cy=\"9\" r=\"1.5\"/><path d=\"m21 15-5-5L5 20\"/>" : "<path d=\"M6 3h8l5 5v13H6z\"/><path d=\"M14 3v6h5M9 13h7M9 17h5\"/>")}</span><span class="oddi-chat-library-file-copy"><span class="oddi-chat-library-file-name" title="${escapeHtml(name)}">${escapeHtml(name)}</span><span class="oddi-chat-library-file-meta">${escapeHtml(date)} · ${escapeHtml(mime)}</span></span></label>`;
    }).join("");
    updateLibrarySelection();
  }

  function updateLibrarySelection() {
    const count = selectedLibraryIds.size;
    librarySelectionLabel.textContent = `${count} selected${count ? ` · up to ${MAX_LIBRARY_SELECTION}` : ""}`;
    addLibraryButton.disabled = count === 0 || libraryBusy;
    libraryRows.querySelectorAll(".oddi-chat-library-row").forEach(row => {
      const checkbox = row.querySelector(".oddi-chat-library-check");
      row.classList.toggle("is-selected", !!checkbox?.checked);
    });
  }

  async function addSelectedLibraryFiles() {
    if (libraryBusy || !selectedLibraryIds.size) return;
    libraryBusy = true;
    addLibraryButton.disabled = true;
    addLibraryButton.textContent = "Adding…";
    const additions = [];
    try {
      const picked = libraryFiles.filter(file => selectedLibraryIds.has(String(file.id)));
      for (const record of picked) {
        if (typeof selectedFiles !== "undefined" && selectedFiles.some(file => String(file?.oddiLibrarySourceId || "") === String(record.id))) continue;
        const response = await fetch(`/api/files/${encodeURIComponent(record.id)}`, {
          credentials: "same-origin", headers: { Accept: "*/*" }, cache: "no-store"
        });
        if (!response.ok) throw new Error(`Could not load ${record.filename || record.name || "a Library file"} (HTTP ${response.status}).`);
        const blob = await response.blob();
        if (!blob.size) throw new Error(`${record.filename || record.name || "A Library file"} is empty or unavailable.`);
        const file = new File([blob], record.filename || record.name || "library-file", {
          type: record.mime_type || record.type || blob.type || "application/octet-stream",
          lastModified: Date.parse(record.updated_at || record.created_at || "") || Date.now()
        });
        Object.defineProperty(file, "oddiLibrarySourceId", { value: String(record.id), configurable: true });
        additions.push(file);
      }
      if (typeof selectedFiles === "undefined") throw new Error("The chat composer is not ready. Please try again.");
      selectedFiles.push(...additions);
      fileInput.value = "";
      if (typeof updateAttachmentPreview === "function") updateAttachmentPreview();
      composer.classList.toggle("has-attachments", selectedFiles.length > 0);
      window.dispatchEvent(new CustomEvent("oddi:publish-attachments"));
      closeLibraryPicker({ restoreFocus: false });
      if (additions.length) toast(`${additions.length} Library file${additions.length === 1 ? "" : "s"} added to this chat.`, "success");
    } catch (error) {
      toast(error?.message || "Could not add those Library files.", "error");
    } finally {
      libraryBusy = false;
      addLibraryButton.textContent = "Add to chat";
      updateLibrarySelection();
      attachButton.focus({ preventScroll: true });
    }
  }

  function setIncognito(enabled, { fromConversation = false } = {}) {
    if (enabled === incognitoEnabled && !fromConversation) return;
    if (typeof generationActive !== "undefined" && generationActive) {
      toast("Wait until ODDI finishes this reply before changing Incognito mode.", "info");
      return;
    }
    const wasEnabled = incognitoEnabled;
    incognitoEnabled = !!enabled;
    window.__oddiIncognitoMode = incognitoEnabled;
    if (!incognitoEnabled) {
      if (typeof conversations !== "undefined" && Array.isArray(conversations)) {
        conversations = conversations.filter(conversation => !conversation?.__oddiIncognito);
      }
      if (!fromConversation) {
        if (typeof currentConversation !== "undefined") currentConversation = null;
        window.__oddiActiveConversationId = null;
      }
    }
    updateToolAgentState();
    if (!fromConversation && typeof newChat === "function") {
      Promise.resolve(newChat()).then(() => {
        if (wasEnabled && !incognitoEnabled) toast("Incognito chat cleared. It was not added to your history.", "info");
      });
    }
    if (typeof renderHistory === "function") renderHistory();
  }

  function clearTransientChatsForNormalNavigation() {
    if (typeof conversations === "undefined" || !Array.isArray(conversations)) return;
    conversations = conversations.filter(conversation => !conversation?.__oddiIncognito);
    window.__oddiIncognitoMode = false;
    incognitoEnabled = false;
    updateToolAgentState();
    window.setTimeout(() => {
      const id = String(window.__oddiActiveConversationId || "");
      const index = conversations.findIndex(conversation => String(conversation?.id ?? "") === id);
      if (index >= 0 && typeof currentConversation !== "undefined") currentConversation = index;
      if (typeof renderHistory === "function") renderHistory();
    }, 0);
  }

  attachButton.onclick = event => {
    event.preventDefault();
    event.stopPropagation();
    if (typeof lockIsActive === "function" && lockIsActive()) return;
    if (toolMenu.classList.contains("open")) closeToolMenu();
    else openToolMenu();
  };
  attachButton.setAttribute("aria-haspopup", "menu");
  attachButton.setAttribute("aria-expanded", "false");
  attachButton.setAttribute("aria-label", "Add photos, files, Library items, or an agent");
  attachButton.title = "Add photos, files, Library items, or an agent";

  incognitoButton.addEventListener("click", () => setIncognito(!incognitoEnabled));
  window.addEventListener("oddi:agent-consumed", event => {
    const consumedId = String(event.detail?.id || "");
    if (consumedId && selectedAgentId && consumedId !== selectedAgentId) return;
    selectedAgentId = "";
    window.__oddiSelectedSpecialistAgent = "";
    updateToolAgentState();
  });
  window.addEventListener("oddi:attachments-changed", () => {
    const exposedAgentId = String(window.__oddiSelectedSpecialistAgent || "");
    if (AGENTS.some(agent => agent.id === exposedAgentId)) {
      selectedAgentId = exposedAgentId;
    } else if (AGENTS.some(agent => agent.id === selectedAgentId)) {
      // Some attachment helpers publish a reset while refreshing the file
      // preview. Keep the selected specialist as draft metadata in that case.
      window.__oddiSelectedSpecialistAgent = selectedAgentId;
    } else {
      selectedAgentId = "";
      window.__oddiSelectedSpecialistAgent = "";
    }
    updateToolAgentState();
  });
  toolMenu.addEventListener("click", event => {
    const button = event.target.closest("[data-tool]");
    if (!button) return;
    const action = button.dataset.tool;
    if (action === "file") {
      closeToolMenu();
      fileInput.removeAttribute("accept");
      fileInput.removeAttribute("capture");
      fileInput.value = "";
      fileInput.click();
      return;
    }
    if (action === "library") { openLibraryPicker(); return; }
    if (AGENTS.some(agent => agent.id === action)) {
      selectedAgentId = selectedAgentId === action ? "" : action;
      window.__oddiSelectedSpecialistAgent = selectedAgentId;
      updateToolAgentState();
      closeToolMenu();
      textarea.focus({ preventScroll: true });
    }
  });

  document.addEventListener("click", event => {
    if (toolMenu.classList.contains("open") && !toolMenu.contains(event.target) && !attachButton.contains(event.target)) closeToolMenu();
  });
  toolMenu.addEventListener("keydown", event => {
    if (event.key === "Escape") { event.preventDefault(); closeToolMenu({ focus: true }); }
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && libraryPicker.classList.contains("open")) {
      event.preventDefault();
      closeLibraryPicker();
    }
  }, true);
  libraryPicker.addEventListener("click", event => {
    if (event.target === libraryPicker || event.target.closest("[data-library-close]")) closeLibraryPicker();
  });
  librarySearch.addEventListener("input", renderLibraryRows);
  libraryRows.addEventListener("change", event => {
    const checkbox = event.target.closest(".oddi-chat-library-check");
    if (!checkbox) return;
    const id = String(checkbox.value);
    if (checkbox.checked) {
      if (selectedLibraryIds.size >= MAX_LIBRARY_SELECTION) {
        checkbox.checked = false;
        toast(`Choose up to ${MAX_LIBRARY_SELECTION} Library files at a time.`, "info");
      } else selectedLibraryIds.add(id);
    } else selectedLibraryIds.delete(id);
    renderLibraryRows();
  });
  addLibraryButton.addEventListener("click", addSelectedLibraryFiles);
  window.addEventListener("resize", () => { if (toolMenu.classList.contains("open")) positionToolMenu(); });
  window.addEventListener("scroll", () => { if (toolMenu.classList.contains("open")) positionToolMenu(); }, true);
  window.addEventListener("oddi:conversation-opened", event => {
    if (event.detail?.id !== null && event.detail?.id !== undefined && incognitoEnabled) {
      const activeId = String(event.detail.id);
      incognitoEnabled = false;
      window.__oddiIncognitoMode = false;
      window.__oddiActiveConversationId = activeId;
      updateToolAgentState();
      clearTransientChatsForNormalNavigation();
    }
  });

  if (chatbox && window.MutationObserver) {
    new MutationObserver(syncIncognitoButtonVisibility).observe(chatbox, { childList: true, subtree: true });
  }

  window.__oddiSelectedSpecialistAgent = "";
  window.__oddiIncognitoMode = false;
  window.__oddiChatToolAgents = AGENTS.map(({ id, name }) => ({ id, name }));
  updateToolAgentState();
})();
