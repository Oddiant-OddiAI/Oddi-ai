/**
 * ODDI AI — Homepage Composer Wiring & Flow Management
 * Handles Attach, Settings, Options, Mic, Send buttons
 * Manages Home <-> Chat state transitions seamlessly.
 */
(() => {
  "use strict";

  const wireTools = () => {
    // 1. Attach Chip -> File Input
    const attachBtn = document.getElementById("oddiAttachChipBtn");
    if (attachBtn && !attachBtn.dataset.bound) {
      attachBtn.dataset.bound = "1";
      attachBtn.addEventListener("click", (e) => {
        e.preventDefault();
        const fileInput = document.getElementById("fileInput");
        if (fileInput) fileInput.click();
      });
    }

    // 2. Settings Chip -> Open Settings Modal
    const settingsBtn = document.getElementById("oddiSettingsChipBtn");
    if (settingsBtn && !settingsBtn.dataset.bound) {
      settingsBtn.dataset.bound = "1";
      settingsBtn.addEventListener("click", (e) => {
        e.preventDefault();
        if (typeof window.__oddiOpenSettings === "function") {
          window.__oddiOpenSettings("general");
        } else {
          document.getElementById("headerMoreBtn")?.click();
        }
      });
    }

    // 3. Options Chip -> More Menu / Options
    const optionsBtn = document.getElementById("oddiOptionsChipBtn");
    if (optionsBtn && !optionsBtn.dataset.bound) {
      optionsBtn.dataset.bound = "1";
      optionsBtn.addEventListener("click", (e) => {
        e.preventDefault();
        document.getElementById("headerMoreBtn")?.click();
      });
    }
  };

  const syncQuickActionAgents = () => {
    const selectedAgent = String(window.__oddiSelectedSpecialistAgent || "");
    document.querySelectorAll("#oddiHomeQuickActions .oddi-home-quick-action[data-home-agent]").forEach((button) => {
      const selected = button.dataset.homeAgent === selectedAgent;
      button.classList.toggle("is-selected", selected);
      button.setAttribute("aria-pressed", selected ? "true" : "false");
    });
  };

  const wireHomeQuickActions = () => {
    if (document.documentElement.dataset.oddiHomeQuickActionsBound === "1") {
      syncQuickActionAgents();
      return;
    }
    document.documentElement.dataset.oddiHomeQuickActionsBound = "1";

    document.addEventListener("click", (event) => {
      const button = event.target instanceof Element
        ? event.target.closest("#oddiHomeQuickActions .oddi-home-quick-action")
        : null;
      if (!button) return;

      event.preventDefault();
      const input = document.getElementById("userInput");
      if (!input) return;

      const agent = String(button.dataset.homeAgent || "").trim();
      if (agent) {
        const alreadySelectedByThisRow = window.__oddiHomeQuickActionAgent === agent &&
          String(window.__oddiSelectedSpecialistAgent || "") === agent;
        window.__oddiSelectedSpecialistAgent = alreadySelectedByThisRow ? "" : agent;
        window.__oddiHomeQuickActionAgent = alreadySelectedByThisRow ? "" : agent;
        window.dispatchEvent(new CustomEvent("oddi:attachments-changed", {
          detail: { source: "home-quick-action", id: window.__oddiSelectedSpecialistAgent }
        }));
      } else {
        const homeAgent = String(window.__oddiHomeQuickActionAgent || "");
        if (homeAgent && String(window.__oddiSelectedSpecialistAgent || "") === homeAgent) {
          window.__oddiSelectedSpecialistAgent = "";
          window.dispatchEvent(new CustomEvent("oddi:attachments-changed", {
            detail: { source: "home-quick-action", id: "" }
          }));
        }
        window.__oddiHomeQuickActionAgent = "";
      }

      const prompt = String(button.dataset.homePrompt || "");
      if (prompt && !input.value.trim()) {
        input.value = prompt;
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.setSelectionRange(input.value.length, input.value.length);
      }
      input.focus({ preventScroll: true });
      syncQuickActionAgents();
    });

    window.addEventListener("oddi:agent-consumed", (event) => {
      if (String(event.detail?.id || "") === String(window.__oddiHomeQuickActionAgent || "")) {
        window.__oddiHomeQuickActionAgent = "";
      }
      syncQuickActionAgents();
    });
    window.addEventListener("oddi:new-chat-ready", syncQuickActionAgents);
    syncQuickActionAgents();
  };

  const syncFlow = () => {
    const welcome = document.getElementById("welcomeContainer");
    const app = document.querySelector(".app") || document.body;
    const isHome = !!welcome && !app.classList.contains("chat-started");
    const composer = document.getElementById("oddiComposerShell");
    const slot = document.getElementById("oddiComposerSlot");
    const note = document.getElementById("oddiAccuracyNote");
    const input = document.getElementById("userInput");

    if (!composer) return;

    if (isHome) {
      // Home Screen mode
      if (slot && composer.parentElement !== slot) {
        slot.appendChild(composer);
      }
      composer.classList.add("oddi-home-composer-mode");

      if (input && (!input.value || input.placeholder.includes("career AI"))) {
        input.placeholder = "Ask Anything...";
      }

      // Ensure disclaimer is inside welcomeContainer below cards in flow
      if (note && welcome && note.parentElement !== welcome) {
        welcome.appendChild(note);
      }
      if (note) {
        note.classList.add("oddi-home-disclaimer");
        note.style.position = "";
        note.style.top = "";
        note.style.left = "";
        note.style.transform = "";
        note.style.visibility = "visible";
        note.hidden = false;
      }
    } else {
      // Chat mode
      if (composer.parentElement !== app) {
        app.appendChild(composer);
      }
      composer.classList.remove("oddi-home-composer-mode");

      if (note && note.parentElement !== app) {
        app.appendChild(note);
      }
      if (note) {
        note.classList.remove("oddi-home-disclaimer");
      }
    }

    wireTools();
  };

  const init = () => {
    wireTools();
    wireHomeQuickActions();
    syncFlow();

    // Listen to lifecycle events
    window.addEventListener("oddi:new-chat-ready", () => {
      wireTools();
      syncFlow();
    });
    window.addEventListener("oddi:conversation-opened", syncFlow);

    // Observer for chatbox child changes
    const chatbox = document.getElementById("chatbox");
    if (chatbox) {
      new MutationObserver(syncFlow).observe(chatbox, { childList: true });
    }
    const app = document.querySelector(".app") || document.body;
    new MutationObserver(syncFlow).observe(app, { attributes: true, attributeFilter: ["class"] });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
