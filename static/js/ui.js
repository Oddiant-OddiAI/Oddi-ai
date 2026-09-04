/* 
   OPEN UPLOADED FILES
 */
chat.addEventListener("click", event => {
    const fileElement = event.target.closest(".message-file[data-file-key]");
    if (!fileElement) return;
    openOddiUploadedFile(fileElement.dataset.fileKey);
});

chat.addEventListener("keydown", event => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const fileElement = event.target.closest(".message-file[data-file-key]");
    if (!fileElement) return;
    event.preventDefault();
    openOddiUploadedFile(fileElement.dataset.fileKey);
});

/* 
   NEW CHAT
 */

async function newChat() {

    const activeConversation =
        currentConversation !== null
            ? conversations[currentConversation]
            : null;

    if (
        activeConversation &&
        Array.isArray(activeConversation.messages) &&
        activeConversation.messages.length > 0
    ) {
        const confirmed =
            await showActionConfirmation(
                "Start a New Chat?",
                "Your current conversation will remain saved.",
                "Continue",
                false
            );

        if (!confirmed) {
            return;
        }
    }

    chat.innerHTML = "";

    input.value = "";

    if (chatSearchInput.value) {
        chatSearchInput.value = "";
        chatSearchQuery = "";
    }

    selectedFiles = [];

    if (isLoggedIn) {

        const serverConversation =
            await createServerConversation(
                "New Chat"
            );

        if (!serverConversation) {
            return;
        }

        conversations.unshift({
            id:
                serverConversation.id,
            title:
                serverConversation.title,
            messages: [],
            pinned: false
        });

        currentConversation = 0;

        renderHistory();

    } else {

        conversations = [{
            id: null,
            title: "New Chat",
            messages: [],
            pinned: false
        }];

        currentConversation = 0;
    }

    updateActionButton();

    input.focus();
}

/* 
   QUICK ACTIONS
 */

const quickActions =
    document.querySelectorAll(
        ".action-card"
    );

quickActions.forEach(card => {

    card.addEventListener(
        "click",
        function () {

            const message =
                this.getAttribute(
                    "data-message"
                );

            const prompt =
                this.getAttribute(
                    "data-prompt"
                );

            if (!message || !prompt) {
                return;
            }

            if (
                message ===
                "Analyze my resume"
            ) {

                input.value =
                    message;

                if (
                    selectedFiles.length
                ) {

                    sendMessage(
                        message
                    );

                } else {

                    fileInput.click();
                }

                return;
            }

            input.value =
                prompt;

            sendMessage(
                message
            );
        }
    );
});

/* 
   THEME
 */

/* 
   THEME
 */

const themeBtn =
    document.getElementById(
        "themeBtn"
    );

const logo =
    document.getElementById(
        "logo"
    );

themeBtn.onclick = () => {

    document.body.classList.toggle(
        "dark-mode"
    );

    if (
        document.body.classList.contains(
            "dark-mode"
        )
    ) {

        themeBtn.innerHTML =
            "☀️";

        themeBtn.title =
            "Switch to Light Mode";

        logo.src =
            "/static/logo-dark.png";

    } else {

        themeBtn.innerHTML =
            "🌙";

        themeBtn.title =
            "Switch to Dark Mode";

        logo.src =
            "/static/logo.png";
    }
};
/* 
   PWA INSTALL / ADD TO HOME SCREEN
 */

let deferredInstallPrompt = null;
const installBtn = document.getElementById("installBtn");

function isOddiStandalone() {
    return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
}

function updateInstallButton() {
    if (!installBtn) return;
    installBtn.style.display = deferredInstallPrompt && !isOddiStandalone() ? 'flex' : 'none';
}

window.addEventListener("beforeinstallprompt", event => {
    event.preventDefault();
    deferredInstallPrompt = event;
    updateInstallButton();
});

if (installBtn) {
    installBtn.addEventListener("click", async () => {
        if (!deferredInstallPrompt) {
            updateInstallButton();
            return;
        }
        const promptEvent = deferredInstallPrompt;
        deferredInstallPrompt = null;
        try {
            promptEvent.prompt();
            await promptEvent.userChoice;
        } catch (error) {
            console.warn("Install prompt result unavailable:", error);
        }
        updateInstallButton();
    });
}

window.addEventListener("appinstalled", () => {
    deferredInstallPrompt = null;
    updateInstallButton();
});

window.addEventListener('load', updateInstallButton);

/* 
   SIDEBAR
 */

const menuBtn =
    document.getElementById(
        "menuBtn"
    );

const sidebar =
    document.getElementById(
        "sidebar"
    );

const overlay =
    document.getElementById(
        "overlay"
    );
function closeSidebarForModal() {
    sidebar.classList.remove("open");
    overlay.classList.remove("show");
}
menuBtn.onclick = () => {

    sidebar.classList.add(
        "open"
    );

    overlay.classList.add(
        "show"
    );
};

overlay.onclick = () => {

    sidebar.classList.remove(
        "open"
    );

    overlay.classList.remove(
        "show"
    );
};

/* 
   SETTINGS / MODALS
 */

const newChatBtn =
    document.getElementById(
        "newChatBtn"
    );

newChatBtn.onclick =
    newChat;

const renameModal =
    document.getElementById(
        "renameModal"
    );

const renameInput =
    document.getElementById(
        "renameInput"
    );

const saveRename =
    document.getElementById(
        "saveRename"
    );

const cancelRename =
    document.getElementById(
        "cancelRename"
    );

let renameIndex = -1;

const deleteModal =
    document.getElementById(
        "deleteModal"
    );

const confirmDelete =
    document.getElementById(
        "confirmDelete"
    );

const cancelDelete =
    document.getElementById(
        "cancelDelete"
    );

let deleteIndex = -1;

const actionConfirmModal =
    document.getElementById(
        "actionConfirmModal"
    );

const actionConfirmTitle =
    document.getElementById(
        "actionConfirmTitle"
    );

const actionConfirmMessage =
    document.getElementById(
        "actionConfirmMessage"
    );

const actionConfirmCancel =
    document.getElementById(
        "actionConfirmCancel"
    );

const actionConfirmOk =
    document.getElementById(
        "actionConfirmOk"
    );

let actionConfirmResolve = null;

function showActionConfirmation(
    title,
    message,
    confirmText,
    danger = false
) {
    return new Promise(resolve => {
        actionConfirmResolve = resolve;

        actionConfirmTitle.innerText =
            title;

        actionConfirmMessage.innerText =
            message;

        actionConfirmOk.innerText =
            confirmText;

        actionConfirmOk.classList.toggle(
            "danger",
            danger
        );

        actionConfirmModal.classList.add(
            "show"
        );
    });
}

function closeActionConfirmation(
    confirmed
) {
    actionConfirmModal.classList.remove(
        "show"
    );

    if (actionConfirmResolve) {
        const resolve =
            actionConfirmResolve;

        actionConfirmResolve = null;
        resolve(confirmed);
    }
}

actionConfirmCancel.onclick = () => {
    closeActionConfirmation(false);
};

actionConfirmOk.onclick = () => {
    closeActionConfirmation(true);
};

const settingsBtn =
    document.getElementById(
        "settingsBtn"
    );

const settingsModal =
    document.getElementById(
        "settingsModal"
    );

const closeSettings =
    document.getElementById(
        "closeSettings"
    );

saveRename.onclick =
    async () => {

        const newName =
            renameInput.value.trim();

        if (!newName) return;

        conversations[
            renameIndex
        ].title = newName;

        await saveConversation(
            conversations[
                renameIndex
            ]
        );

        renameModal.classList.remove(
            "show"
        );

        renderHistory();
    };

cancelRename.onclick = () => {

    renameModal.classList.remove(
        "show"
    );
};

cancelDelete.onclick = () => {

    deleteModal.classList.remove(
        "show"
    );
};

const TRASH_KEY = "oddi_deleted_chats_v1";
function getTrash() {
    try {
        const value = JSON.parse(localStorage.getItem(TRASH_KEY) || "[]");
        return Array.isArray(value) ? value : [];
    } catch { return []; }
}
function setTrash(items) { localStorage.setItem(TRASH_KEY, JSON.stringify(items)); }
async function permanentlyDeleteAllBinChats() {
    const trash = getTrash();
    if (!trash.length) {
        renderBin();
        return;
    }

    const confirmed = await showActionConfirmation(
        "Delete All Chats Permanently?",
        "Every chat currently in the Bin will be permanently deleted and cannot be restored.",
        "Delete All",
        true
    );
    if (!confirmed) return;

    /* Remove every deleted conversation from the server when it has an id.
       Local Bin data is cleared even if one server request fails, because
       the user explicitly confirmed permanent deletion. */
    await Promise.all(trash.map(async conversation => {
        if (!conversation?.id) return;
        try {
            await fetch(`/api/conversations/${conversation.id}`, { method: "DELETE" });
        } catch (e) {
            console.warn("Permanent delete sync failed", e);
        }
    }));

    setTrash([]);
    renderBin();
}

function renderBin() {
    const list = document.getElementById("binList");
    if (!list) return;
    const trash = getTrash();
    list.innerHTML = "";
    if (!trash.length) {
        list.innerHTML = '<div class="utility-empty">🗑️ Bin is empty</div>';
        return;
    }
    trash.slice().reverse().forEach((conversation, reverseIndex) => {
        const realIndex = trash.length - 1 - reverseIndex;
        const row = document.createElement("div");
        row.className = "bin-item";
        const count = Array.isArray(conversation.messages) ? conversation.messages.length : 0;
        row.innerHTML = `<div class="bin-item-main"><div class="bin-item-title"></div><div class="bin-item-meta">${count} ${count === 1 ? "message" : "messages"}</div></div><div class="bin-actions"><button class="restore-trash" type="button">↩ Restore</button><button class="permanent-delete" type="button">Delete</button></div>`;
        row.querySelector(".bin-item-title").textContent = conversation.title || "New Chat";
        row.querySelector(".restore-trash").onclick = async () => {
            const item = getTrash();
            const restored = item.splice(realIndex, 1)[0];
            if (!restored) return;
            setTrash(item);
            conversations.push(restored);
            try { await saveConversation(restored); } catch (e) { console.warn("Could not sync restored chat", e); }
            renderHistory(); renderBin();
        };
        row.querySelector(".permanent-delete").onclick = async () => {
            const item = getTrash();
            const doomed = item[realIndex];
            if (!doomed) return;
            const ok = await showActionConfirmation("Delete Permanently?", "This chat will be permanently deleted and cannot be restored.", "Delete", true);
            if (!ok) return;
            if (doomed.id) {
                try { await fetch(`/api/conversations/${doomed.id}`, { method: "DELETE" }); } catch (e) { console.warn("Permanent delete sync failed", e); }
            }
            item.splice(realIndex, 1); setTrash(item); renderBin();
        };
        list.appendChild(row);
    });
}

const deleteAllBinBtn = document.getElementById("deleteAllBinBtn");
deleteAllBinBtn?.addEventListener("click", permanentlyDeleteAllBinChats);

confirmDelete.onclick = async () => {
    const conversation = conversations[deleteIndex];
    if (!conversation) return;
    const trash = getTrash();
    trash.push({ ...conversation, deletedAt: Date.now() });
    setTrash(trash);
    removePinnedConversation(conversation);
    conversations.splice(deleteIndex, 1);
    deleteModal.classList.remove("show");
    currentConversation = null;
    renderHistory();
    chat.innerHTML = "";
};

settingsBtn.onclick = () => {

    closeSidebarForModal();
    settingsModal.classList.add("show");
};

closeSettings.onclick = () => {

    settingsModal.classList.remove(
        "show"
    );
};

/* 
   SETTINGS
 */

const themeSettingBtn =
    document.getElementById(
        "themeSettingBtn"
    );

themeSettingBtn.onclick = () => {
    themeBtn.click();
};

const typingBtn =
    document.getElementById(
        "typingBtn"
    );

let typingEnabled = true;

typingBtn.onclick = () => {

    typingEnabled =
        !typingEnabled;

    typingBtn.innerText =
        typingEnabled
            ? "ON"
            : "OFF";
};

const notificationBtn =
    document.getElementById(
        "notificationBtn"
    );

let notificationEnabled = true;

notificationBtn.onclick = () => {

    notificationEnabled =
        !notificationEnabled;

    notificationBtn.innerText =
        notificationEnabled
            ? "ON"
            : "OFF";
};
/* KEYBOARD SHORTCUTS*/
document.addEventListener("keydown", event => {
    if (event.key === "Escape") {
        renameModal.classList.remove("show");
        deleteModal.classList.remove("show");
        settingsModal.classList.remove("show");
        closeActionConfirmation(false);
        sidebar.classList.remove("open");
        overlay.classList.remove("show");
        return;
    }
    if (
        (event.ctrlKey || event.metaKey) &&
        event.key.toLowerCase() === "k"
    ) {
        event.preventDefault();
        chatSearchInput.focus();
        chatSearchInput.select();
        return;
    }
    if (
        (event.ctrlKey || event.metaKey) &&
        event.shiftKey &&
        event.key.toLowerCase() === "n"
    ) {
        event.preventDefault();
        newChat();
    }
});
/* LOGOUT*/
const logoutBtn =
    document.getElementById(
        "logoutBtn"
    );
if (logoutBtn) {
    logoutBtn.onclick = () => {
        window.location.href =
            "/logout";
    };
}
/* MOVE ALL TO BIN*/
const clearChatBtn =
    document.getElementById(
        "clearChatBtn"
    );
clearChatBtn.onclick =
    async () => {
        if (!conversations.length) {
            return;
        }
        const confirmed =
            await showActionConfirmation(
                "Move All Conversations to Bin?",
                "Your chats will be moved to the Bin and can be restored later.",
                "Move All to Bin",
                true
            );
        if (!confirmed) {
            return;
        }
        const trash = getTrash();
        const existingIds = new Set(
            trash
                .map(item => item && item.id)
                .filter(Boolean)
                .map(String)
        );
        const now = Date.now();
        conversations.forEach(conversation => {
            // Avoid duplicate Bin entries if the same conversation is
            // ever encountered more than once.
            if (conversation.id && existingIds.has(String(conversation.id))) {
                return;
            }
            trash.push({
                ...conversation,
                deletedAt: now
            });
            if (conversation.id) {
                existingIds.add(String(conversation.id));
            }
            removePinnedConversation(conversation);
        });
        setTrash(trash);
        conversations = [];
        currentConversation = null;
        chat.innerHTML = "";

        renderHistory();
        renderBin();
        newChat();
    };
/* SPLASH SCREEN*/
document.addEventListener("DOMContentLoaded", () => {
    const isMobile = window.matchMedia(
        "(max-width: 768px)"
    ).matches;
    const splash = document.getElementById(
        isMobile ? "mobileSplash" : "splash-screen"
    );
    const splashSound =
        document.getElementById("splashSound");
    if (splashSound) {
        splashSound.play().catch(() => {});
    }
    if (splash) {
        setTimeout(() => {
            splash.classList.add("hide");
            setTimeout(() => {
                splash.remove();
            }, 1500);
        }, 3000);
    }
});
/* INITIALIZE*/
input.style.height =
    "auto";
input.style.height =
    input.scrollHeight + "px";
updateActionButton();
loadConversations();


(function () {
    const modal = document.getElementById("accountSettingsModal");
    const closeBtn = document.getElementById("closeAccountSettings");
    const fullSettingsBtn = document.getElementById("openFullSettingsBtn");
    const switchBtn = document.getElementById("switchAccountBtn");
    const logoutBtn = document.getElementById("accountLogoutBtn");
    const list = document.getElementById("rememberedAccountList");
    const clearBtn = document.getElementById("clearRememberedAccountsBtn");
    const appPasswordInput = document.getElementById("appPasswordInput");
    const togglePasswordBtn = document.getElementById("toggleAppPasswordBtn");
    const savePasswordBtn = document.getElementById("saveAppPasswordBtn");
    const passwordStatus = document.getElementById("appPasswordStatus");
    if (!modal) return;

    const ACCOUNT_KEY = "oddi_remembered_accounts_v1";
    const PASSWORD_KEY = "oddi_device_app_password_v1";
    const currentUsername = document.body?.dataset.username || "";

    function closeAccountModal() {
        modal.classList.remove("show");
        modal.setAttribute("aria-hidden", "true");
    }
    function readAccounts() {
        try {
            const data = JSON.parse(localStorage.getItem(ACCOUNT_KEY) || "[]");
            return Array.isArray(data) ? data.filter(Boolean).map(String) : [];
        } catch (_) { return []; }
    }
    function writeAccounts(accounts) {
        localStorage.setItem(ACCOUNT_KEY, JSON.stringify([...new Set(accounts)].slice(0, 12)));
    }
    function rememberCurrentAccount() {
        if (!currentUsername) return;
        writeAccounts([currentUsername, ...readAccounts()]);
    }
    function renderAccounts() {
        if (!list) return;
        const accounts = readAccounts();
        list.innerHTML = "";
        if (!accounts.length) {
            list.innerHTML = '<div class="account-empty">No remembered accounts yet.</div>';
            return;
        }
        accounts.forEach(name => {
            const row = document.createElement("div");
            row.className = "remembered-account";
            const label = document.createElement("span");
            label.className = "remembered-account-name";
            label.textContent = name + (name === currentUsername ? " (current)" : "");
            const remove = document.createElement("button");
            remove.className = "remembered-account-remove";
            remove.type = "button";
            remove.textContent = "×";
            remove.title = "Forget this account name";
            remove.addEventListener("click", () => {
                writeAccounts(readAccounts().filter(item => item !== name));
                renderAccounts();
            });
            row.append(label, remove);
            list.appendChild(row);
        });
    }
    function refreshPasswordStatus() {
        const configured = !!sessionStorage.getItem(PASSWORD_KEY);
        if (passwordStatus) passwordStatus.textContent = configured ? "Configured for this browser session" : "Not configured on this device";
    }

    rememberCurrentAccount();
    renderAccounts();
    refreshPasswordStatus();

    closeBtn?.addEventListener("click", closeAccountModal);
    modal.addEventListener("click", event => { if (event.target === modal) closeAccountModal(); });
    fullSettingsBtn?.addEventListener("click", () => {
        closeAccountModal();
        document.getElementById("settingsBtn")?.click();
    });
    switchBtn?.addEventListener("click", () => {
        closeAccountModal();
        window.location.href = "/login";
    });
    logoutBtn?.addEventListener("click", () => {
        closeAccountModal();
        window.location.href = "/logout";
    });
    clearBtn?.addEventListener("click", () => {
        writeAccounts([]);
        renderAccounts();
    });
    togglePasswordBtn?.addEventListener("click", () => {
        if (!appPasswordInput) return;
        const visible = appPasswordInput.type === "text";
        appPasswordInput.type = visible ? "password" : "text";
        togglePasswordBtn.textContent = visible ? "👁" : "🙈";
    });
    savePasswordBtn?.addEventListener("click", () => {
        const value = appPasswordInput?.value.trim() || "";
        if (!value) {
            sessionStorage.removeItem(PASSWORD_KEY);
            refreshPasswordStatus();
            return;
        }
        sessionStorage.setItem(PASSWORD_KEY, "configured");
        if (appPasswordInput) appPasswordInput.value = "";
        refreshPasswordStatus();
    });
    document.addEventListener("keydown", event => {
        if (event.key === "Escape" && modal.classList.contains("show")) {
            event.preventDefault();
            closeAccountModal();
        }
    }, true);
    window.addEventListener("pageshow", closeAccountModal);
})();

(function () {
    const moreBtn = document.getElementById("headerMoreBtn");
    const overlayEl = document.getElementById("headerMoreOverlay");
    const panel = document.getElementById("headerMorePanel");
    const closeBtn = document.getElementById("headerMoreClose");
    const exportBtn = document.getElementById("headerMoreExport");
    const accountBtn = document.getElementById("headerMoreAccount");
    if (!moreBtn || !overlayEl || !panel || !closeBtn) return;
    function closeHeaderMore() {
        overlayEl.classList.remove("show");
        overlayEl.setAttribute("aria-hidden", "true");
        moreBtn.setAttribute("aria-expanded", "false");
    }
    function openHeaderMore() {
        /* Always open from a clean state; nothing is persisted across refresh. */
        overlayEl.classList.add("show");
        overlayEl.setAttribute("aria-hidden", "false");
        moreBtn.setAttribute("aria-expanded", "true");
        requestAnimationFrame(() => closeBtn.focus());
    }
    closeHeaderMore();
    moreBtn.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        if (overlayEl.classList.contains("show")) closeHeaderMore();
        else openHeaderMore();
    });
    closeBtn.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        closeHeaderMore();
    });
    overlayEl.addEventListener("click", function (event) {
        if (event.target === overlayEl) closeHeaderMore();
    });
    panel.addEventListener("click", function (event) {
        event.stopPropagation();
    });
    document.addEventListener("click", function (event) {
        if (!overlayEl.classList.contains("show")) return;
        if (panel.contains(event.target) || moreBtn.contains(event.target)) return;
        closeHeaderMore();
    }, true);
    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && overlayEl.classList.contains("show")) {
            event.preventDefault();
            event.stopPropagation();
            closeHeaderMore();
        }
    }, true);
    exportBtn?.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        closeHeaderMore();
        const existingExport = document.getElementById("exportChatBtn");
        if (existingExport) existingExport.click();
    });
    accountBtn?.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        closeHeaderMore();
        const accountModal = document.getElementById("accountSettingsModal");
        if (accountModal) {
            accountModal.classList.add("show");
            accountModal.setAttribute("aria-hidden", "false");
            requestAnimationFrame(() => document.getElementById("closeAccountSettings")?.focus());
        }
    });
    window.addEventListener("pageshow", closeHeaderMore);
    window.addEventListener("pagehide", closeHeaderMore);
})();
/* 
   OPTIONAL APP LOCK & SETTINGS LOGIC
*/
(function () {
    const lockOverlay = document.getElementById("appLockOverlay");
    if (!lockOverlay) return;

    const ENABLED_KEY = "oddi_app_lock_enabled_v1";
    const PIN_KEY = "oddi_app_lock_pin_v1";

    const isEnabled = localStorage.getItem(ENABLED_KEY) === "true";
    const savedPin = localStorage.getItem(PIN_KEY) || "123456";

    // Only show lock overlay if the user explicitly enabled it
    if (!isEnabled) {
        lockOverlay.style.display = "none";
    }

    let enteredPin = "";
    const pinDots = document.querySelectorAll(".pin-dot");
    const statusText = document.getElementById("appLockStatus");
    const keys = document.querySelectorAll(".pin-key[data-value]");
    const backspaceBtn = document.getElementById("pinBackspace");

    function updateDots() {
        pinDots.forEach((dot, index) => {
            dot.classList.toggle("filled", index < enteredPin.length);
        });
    }

    function verifyPin() {
        if (enteredPin === savedPin) {
            statusText.textContent = "Unlocked";
            lockOverlay.classList.add("unlock-success");
            setTimeout(() => { lockOverlay.style.display = "none"; }, 400);
        } else {
            statusText.textContent = "Incorrect PIN. Try again.";
            lockOverlay.classList.add("shake-animation");
            setTimeout(() => {
                lockOverlay.classList.remove("shake-animation");
                enteredPin = "";
                updateDots();
                statusText.textContent = "Please Enter Your PIN";
            }, 600);
        }
    }

    keys.forEach(key => {
        key.addEventListener("click", () => {
            if (enteredPin.length < 6) {
                enteredPin += key.dataset.value;
                updateDots();
                if (enteredPin.length === 6) setTimeout(verifyPin, 150);
            }
        });
    });

    backspaceBtn?.addEventListener("click", () => {
        if (enteredPin.length > 0) {
            enteredPin = enteredPin.slice(0, -1);
            updateDots();
        }
    });

    // Account Settings Controls for App Lock
    const toggleOptBtn = document.getElementById("toggleAppLockOptBtn");
    const pinInput = document.getElementById("changePinInput");
    const savePinBtn = document.getElementById("savePinBtn");

    function updateOptButtonState() {
        if (!toggleOptBtn) return;
        const active = localStorage.getItem(ENABLED_KEY) === "true";
        toggleOptBtn.textContent = active ? "Disable" : "Enable";
        toggleOptBtn.style.backgroundColor = active ? "#ff3b30" : "#20c76b";
    }

    updateOptButtonState();

    toggleOptBtn?.addEventListener("click", () => {
        const active = localStorage.getItem(ENABLED_KEY) === "true";
        localStorage.setItem(ENABLED_KEY, active ? "false" : "true");
        updateOptButtonState();
        alert(active ? "App lock disabled." : "App lock enabled.");
    });

    savePinBtn?.addEventListener("click", () => {
        const val = pinInput?.value.trim();
        if (!val || val.length !== 6 || isNaN(val)) {
            alert("Please enter a valid 6-digit PIN.");
            return;
        }
        localStorage.setItem(PIN_KEY, val);
        localStorage.setItem(ENABLED_KEY, "true");
        if (pinInput) pinInput.value = "";
        updateOptButtonState();
        alert("New PIN saved and App Lock enabled!");
    });
})();
/* 
   BIN + KEYBOARD SHORTCUTS
*/

(function () {

    const binBtn = document.getElementById("binBtn");
    const binModal = document.getElementById("binModal");
    const closeBin = document.getElementById("closeBin");

    const shortcutsBtn = document.getElementById("shortcutsBtn");
    const shortcutsModal = document.getElementById("shortcutsModal");
    const closeShortcuts = document.getElementById("closeShortcuts");


    function openModal(modal) {

        if (!modal) return;

        modal.classList.add("show");
        modal.setAttribute("aria-hidden", "false");

    }


    function closeModal(modal) {

        if (!modal) return;

        modal.classList.remove("show");
        modal.setAttribute("aria-hidden", "true");

    }


    /* =========================
       RECENTLY DELETED / BIN
       ========================= */

    binBtn?.addEventListener("click", () => {

        // Refresh the Bin contents every time it is opened
        if (typeof renderBin === "function") {
            renderBin();
        }

        openModal(binModal);

    });


    closeBin?.addEventListener("click", () => {

        closeModal(binModal);

    });


    /* =========================
       KEYBOARD SHORTCUTS
       ========================= */

    shortcutsBtn?.addEventListener("click", () => {

        openModal(shortcutsModal);

    });


    closeShortcuts?.addEventListener("click", () => {

        closeModal(shortcutsModal);

    });


    /* =========================
       CLICK OUTSIDE TO CLOSE
       ========================= */

    [binModal, shortcutsModal].forEach(modal => {

        modal?.addEventListener("click", event => {

            if (event.target === modal) {
                closeModal(modal);
            }

        });

    });


    /* =========================
       ESC TO CLOSE
       ========================= */

    document.addEventListener("keydown", event => {

        if (event.key === "Escape") {

            closeModal(binModal);
            closeModal(shortcutsModal);

        }

    });

})();