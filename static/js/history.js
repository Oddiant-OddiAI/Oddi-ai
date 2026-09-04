/* 
   HISTORY
 */

const PINNED_CHATS_KEY = 'oddi_pinned_chats_v1';

let chatSearchQuery = '';

const chatSearchInput =
    document.getElementById(
        "chatSearchInput"
    );

chatSearchInput.addEventListener(
    "input",
    () => {
        chatSearchQuery = chatSearchInput.value.trim().toLowerCase();
        renderHistory();
    }
);


function getPinnedChatIds() {
    try {
        const saved = JSON.parse(localStorage.getItem(PINNED_CHATS_KEY) || '[]');
        return Array.isArray(saved) ? saved.map(String) : [];
    } catch {
        return [];
    }
}

function savePinnedChatIds(ids) {
    localStorage.setItem(PINNED_CHATS_KEY, JSON.stringify([...new Set(ids.map(String))]));
}

function getConversationKey(conversation) {
    return conversation?.id ? `server:${conversation.id}` : '';
}

function isConversationPinned(conversation) {
    const key = getConversationKey(conversation);
    return !!key && getPinnedChatIds().includes(key);
}

function getConversationActivityKey(conversation) {
    const key = getConversationKey(conversation);
    return key ? `oddi_chat_activity_${key}` : '';
}

function touchConversation(conversation) {
    const now = Date.now();
    const key = getConversationActivityKey(conversation);
    if (key) localStorage.setItem(key, String(now));
    if (conversation) conversation.__localActivity = now;
}

function getConversationActivity(conversation) {
    const key = getConversationActivityKey(conversation);
    if (!key) return 0;
    const value = Number(localStorage.getItem(key) || 0);
    return Number.isFinite(value) ? value : 0;
}

function getConversationDate(conversation) {
    const raw = conversation?.updated_at || conversation?.updatedAt || conversation?.created_at || conversation?.createdAt;
    const parsed = raw ? new Date(raw).getTime() : 0;
    const activity = getConversationActivity(conversation);
    return Number.isFinite(parsed) && parsed > 0 ? Math.max(parsed, activity) : activity;
}

function formatChatTime(timestamp) {
    if (!timestamp) return '';
    const d = new Date(timestamp);
    if (Number.isNaN(d.getTime())) return '';
    return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

function getDateGroup(timestamp) {
    const d = new Date(timestamp || Date.now());
    const now = new Date();
    const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const startYesterday = startToday - 86400000;
    if (d.getTime() >= startToday) return 'Today';
    if (d.getTime() >= startYesterday) return 'Yesterday';
    return 'Earlier';
}

function getConversationPreview(conversation) {
    const messages = Array.isArray(conversation?.messages) ? conversation.messages : [];
    for (let i = messages.length - 1; i >= 0; i--) {
        const msg = messages[i];
        if (!msg) continue;
        let text = String(msg.text || msg.content || '').replace(/\s+/g, ' ').trim();
        if (text) return text;
    }
    return messages.length ? 'Conversation' : 'No messages yet';
}

function getConversationMeta(conversation, timestamp) {
    const count = Array.isArray(conversation?.messages) ? conversation.messages.length : 0;
    const time = formatChatTime(timestamp);
    return `${count} ${count === 1 ? 'message' : 'messages'}${time ? ` · ${time}` : ''}`;
}

function highlightText(text, query) {
    const safe = escapeUserText(String(text || ''));
    if (!query) return safe;
    const escapedQuery = escapeUserText(query).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    if (!escapedQuery) return safe;
    return safe.replace(new RegExp(`(${escapedQuery})`, 'ig'), '<mark class="history-highlight">$1</mark>');
}

function conversationMatchesQuery(conversation, query) {
    if (!query) return true;
    const title = String(conversation?.title || '');
    if (title.toLowerCase().includes(query)) return true;
    const messages = Array.isArray(conversation?.messages) ? conversation.messages : [];
    return messages.some(msg => {
        const text = String(msg?.text || msg?.content || '');
        return text.toLowerCase().includes(query);
    });
}

function isConversationArchived(conversation) {
    const key = getConversationKey(conversation);
    if (!key) return false;
    try {
        return JSON.parse(localStorage.getItem('oddi_archived_chats_v1') || '[]').map(String).includes(key);
    } catch { return false; }
}

function getArchivedChatIds() {
    try {
        const value = JSON.parse(localStorage.getItem('oddi_archived_chats_v1') || '[]');
        return Array.isArray(value) ? value.map(String) : [];
    } catch { return []; }
}

function setArchivedChatIds(ids) {
    localStorage.setItem('oddi_archived_chats_v1', JSON.stringify([...new Set(ids.map(String))]));
}

function toggleArchiveConversation(conversation) {
    const key = getConversationKey(conversation);
    if (!key) return;
    const ids = getArchivedChatIds();
    const index = ids.indexOf(key);
    if (index === -1) ids.push(key); else ids.splice(index, 1);
    setArchivedChatIds(ids);
    renderHistory();
}

function createHistoryItem(conversation, options = {}) {
    const { archived = false, searchQuery = '' } = options;
    const pinned = isConversationPinned(conversation);
    const active = conversations[currentConversation] === conversation;
    const timestamp = getConversationDate(conversation);
    const preview = getConversationPreview(conversation);
    const item = document.createElement('div');
    item.className = `history-item ${pinned ? 'pinned-chat' : ''} ${active ? 'active-chat' : ''}`;
    item.tabIndex = 0;
    item.setAttribute('role', 'button');
    item.dataset.conversationId = getConversationKey(conversation);
    item.dataset.index = String(conversations.indexOf(conversation));
    item.innerHTML = `
        <div class="history-main">
            <div class="history-topline">
                <span class="history-title">${pinned ? '📌 ' : ''}${highlightText(conversation.title || 'New Chat', searchQuery)}</span>
            </div>
            <div class="history-preview">${highlightText(preview, searchQuery)}</div>
            <div class="history-meta"><span>${getConversationMeta(conversation, timestamp)}</span>${archived ? '<span class="history-dot">·</span><span>Archived</span>' : ''}</div>
        </div>
        <div class="history-actions">
            ${!archived ? `<button class="chat-pin-btn ${pinned ? 'active' : ''}" title="${pinned ? 'Unpin chat' : 'Pin chat'}" aria-label="${pinned ? 'Unpin chat' : 'Pin chat'}">📌</button>` : ''}
            <button class="archive-btn" title="${archived ? 'Restore chat' : 'Archive chat'}" aria-label="${archived ? 'Restore chat' : 'Archive chat'}">${archived ? '↩️' : '🗄️'}</button>
            <button class="rename-btn" title="Rename chat" aria-label="Rename chat">✏️</button>
            <button class="delete-btn" title="Delete chat" aria-label="Delete chat">🗑️</button>
        </div>`;

    const pinBtn = item.querySelector('.chat-pin-btn');
    const archiveBtn = item.querySelector('.archive-btn');
    const renameBtn = item.querySelector('.rename-btn');
    const deleteBtn = item.querySelector('.delete-btn');

    pinBtn?.addEventListener('click', event => { event.stopPropagation(); togglePinConversation(conversation); });
    archiveBtn?.addEventListener('click', event => { event.stopPropagation(); toggleArchiveConversation(conversation); });
    
    renameBtn?.addEventListener("click", event => {
        event.stopPropagation();

        closeSidebarForModal();

        renameModal.classList.add("show");
        renameInput.value = conversation.title || "";
        renameIndex = conversations.indexOf(conversation);
    });

    deleteBtn?.addEventListener("click", event => {
        event.stopPropagation();

        closeSidebarForModal();

        deleteIndex = conversations.indexOf(conversation);
        deleteModal.classList.add("show");
    });

    const open = () => openConversation(conversations.indexOf(conversation));
    item.addEventListener('click', open);
    item.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); open(); }
    });
    return item;
}

function renderHistory() {
    const currentId = currentConversation !== null && conversations[currentConversation] ? conversations[currentConversation].id : null;
    const pinnedIds = getPinnedChatIds();
    const query = chatSearchQuery.trim().toLowerCase();
    const includeArchived = window.__oddiShowArchived === true;
    const archivedIds = getArchivedChatIds();

    const orderedConversations = [...conversations].sort((a, b) => {
        const ap = pinnedIds.includes(getConversationKey(a)) ? 1 : 0;
        const bp = pinnedIds.includes(getConversationKey(b)) ? 1 : 0;
        if (ap !== bp) return bp - ap;
        const activityDifference = getConversationDate(b) - getConversationDate(a);
        if (activityDifference !== 0) return activityDifference;
        return conversations.indexOf(a) - conversations.indexOf(b);
    });

    historyContainer.innerHTML = '';
    const pinnedSection = document.createElement('div');
    pinnedSection.className = 'pinned-history-section';
    const normalSection = document.createElement('div');
    normalSection.className = 'normal-history-section';
    const archivedSection = document.createElement('div');
    archivedSection.className = 'archived-history-section';
    archivedSection.hidden = !includeArchived && !query;

    const pinnedMatches = orderedConversations.filter(c => isConversationPinned(c) && !isConversationArchived(c) && conversationMatchesQuery(c, query));
    const normalMatches = orderedConversations.filter(c => !isConversationPinned(c) && !isConversationArchived(c) && conversationMatchesQuery(c, query));
    const archivedMatches = orderedConversations.filter(c => isConversationArchived(c) && conversationMatchesQuery(c, query));

    if (pinnedMatches.length) {
        pinnedMatches.forEach(c => pinnedSection.appendChild(createHistoryItem(c, { searchQuery: query })));
    } else if (!query) {
        const empty = document.createElement('div');
        empty.className = 'pinned-empty-state';
        empty.innerHTML = '<span class="empty-pin-icon">📌</span>No pinned chats yet';
        pinnedSection.appendChild(empty);
    }

    const groups = { Today: [], Yesterday: [], Earlier: [] };
    normalMatches.forEach(c => groups[getDateGroup(getConversationDate(c))].push(c));
    Object.entries(groups).forEach(([label, list]) => {
        if (!list.length) return;
        const group = document.createElement('div');
        group.className = 'history-date-group';
        group.innerHTML = `<div class="history-date-group-label">${label}</div>`;
        const items = document.createElement('div');
        items.className = 'history-date-group-items';
        list.forEach(c => items.appendChild(createHistoryItem(c, { searchQuery: query })));
        group.appendChild(items);
        normalSection.appendChild(group);
    });

    if (archivedMatches.length) {
        archivedMatches.forEach(c => archivedSection.appendChild(createHistoryItem(c, { archived: true, searchQuery: query })));
    }

    if (pinnedMatches.length || !query) historyContainer.appendChild(pinnedSection);
    historyContainer.appendChild(normalSection);

    const archiveToggle = document.createElement('button');
    archiveToggle.className = 'archived-toggle';
    archiveToggle.type = 'button';
    archiveToggle.textContent = `${includeArchived ? '▴ Hide' : '▾ Show'} archived${archivedMatches.length ? ` (${archivedMatches.length})` : ''}`;
    archiveToggle.onclick = () => { window.__oddiShowArchived = !window.__oddiShowArchived; renderHistory(); };
    historyContainer.appendChild(archiveToggle);
    historyContainer.appendChild(archivedSection);

    const visibleCount = pinnedMatches.length + normalMatches.length + archivedMatches.length;
    if (query && !visibleCount) {
        const empty = document.createElement('div');
        empty.className = 'chat-search-empty';
        empty.textContent = 'No chats or messages found.';
        historyContainer.innerHTML = '';
        historyContainer.appendChild(empty);
    }
}


function togglePinConversation(conversation) {
    const key = getConversationKey(conversation);
    if (!key) return;

    const ids = getPinnedChatIds();
    const index = ids.indexOf(key);

    if (index === -1) {
        ids.push(key);
    } else {
        ids.splice(index, 1);
    }

    savePinnedChatIds(ids);
    renderHistory();
}

function removePinnedConversation(conversation) {
    const key = getConversationKey(conversation);
    if (!key) return;
    savePinnedChatIds(getPinnedChatIds().filter(id => id !== key));
}

async function openConversation(
    index
) {

    if (generationActive) {
        return;
    }

    currentConversation = index;

    const conversation =
        conversations[index];

    touchConversation(conversation);
    renderHistory();

    chat.innerHTML = "";

    conversation.messages.forEach(
        (msg, messageIndex) => {

            if (msg.role === "user") {

                let fileHTML = "";

                if (Array.isArray(msg.fileRefs) && msg.fileRefs.length) {
                    msg.fileRefs.forEach(file => {
                        fileHTML += buildFileHTML(file.name, file.id);
                    });
                } else if (msg.files) {
                    msg.files.forEach(file => {
                        fileHTML += buildFileHTML(file);
                    });
                }

                chat.innerHTML += `
                    <div class="user-message ${msg.pinned ? "pinned-message" : ""}"
                         data-message-index="${messageIndex}">

                        ${fileHTML}

                        <div class="user-message-header">
                            <b>You:</b>
                            <button
                                class="message-action-btn user-pin-btn ${msg.pinned ? "active" : ""}"
                                onclick="togglePinMessage(this)"
                                title="${msg.pinned ? "Unpin message" : "Pin important message"}">
                                ${msg.pinned ? "📌 Pinned" : "📌 Pin"}
                            </button>
                        </div>

                        <div class="user-text">${escapeUserText(msg.text)}</div>

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

            } else {

                const feedback = msg.feedback || "";

                chat.innerHTML += `
                    <div class="bot-message ${msg.pinned ? "pinned-message" : ""} ${msg.stopped ? "stopped-message" : ""}"
                         data-message-index="${messageIndex}">

                        <div class="bot-header">

                            <button
                                class="message-sound-btn"
                                onclick="speakAIMessage(this)"
                                title="Read this AI message aloud">
                                🔊
                            </button>

                            <b>Oddi AI:</b>

                        </div>

                        <div class="ai-content">
                            ${renderRichContentToHtml(msg.text)}
                        </div>

                        <div class="bot-actions">
                            <button
                                class="message-action-btn bot-pin-btn ${msg.pinned ? "active" : ""}"
                                onclick="togglePinMessage(this)"
                                title="${msg.pinned ? "Unpin message" : "Pin important message"}">
                                ${msg.pinned ? "📌 Pinned" : "📌 Pin"}
                            </button>
                            <button
                                class="message-action-btn feedback-btn ${feedback === "like" ? "active" : ""}"
                                data-feedback="like"
                                onclick="setMessageFeedback(this, 'like')"
                                title="Like response">
                                👍
                            </button>
                            <button
                                class="message-action-btn feedback-btn ${feedback === "dislike" ? "active" : ""}"
                                data-feedback="dislike"
                                onclick="setMessageFeedback(this, 'dislike')"
                                title="Dislike response">
                                👎
                            </button>
                            <button
                                class="message-action-btn regenerate-btn"
                                onclick="regenerateResponse(this)"
                                title="Regenerate response">
                                ↻ Regenerate
                            </button>
                            <button
                                class="message-action-btn copy-btn"
                                onclick="copyAIResponse(this)"
                                title="Copy AI response">
                                📋 Copy
                            </button>
                        </div>

                    </div>
                `;
            }
        }
    );

    chat.querySelectorAll(".ai-content").forEach(content => {
        enhanceRichContent(content);
    });

    chat.scrollTop =
        chat.scrollHeight;

    sidebar.classList.remove("open");
    overlay.classList.remove("show");
}
