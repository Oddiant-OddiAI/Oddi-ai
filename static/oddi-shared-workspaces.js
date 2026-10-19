(() => {
  'use strict';

  if (window.__oddiSharedWorkspacesReady) return;
  window.__oddiSharedWorkspacesReady = true;

  const MAX_NAME_LENGTH = 80;
  const MAX_MESSAGE_LENGTH = 8000;
  const pageAccountId = document.body.dataset.userId?.trim() || '';

  const root = document.createElement('div');
  root.id = 'oddi-shared-root';
  root.hidden = true;
  root.setAttribute('aria-live', 'polite');
  document.body.appendChild(root);
  window.__oddiSharedWorkspaceNotify = message => {
    if (!root.hidden) showToast(message);
    else if (typeof window.showOddiToast === 'function') window.showOddiToast(message);
  };

  const state = {
    page: 'list',
    workspaces: [],
    invitations: [],
    workspaceId: null,
    details: null,
    messages: new Map(),
    messageCursor: 0,
    lastInviteCount: null,
    infoOpen: false,
    sending: false,
    listTimer: null,
    messageTimer: null,
    detailsTimer: null,
    toastTimer: null,
    refreshingMessages: false,
  };

  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);

  function safeMarkdown(value) {
    const raw = String(value ?? '');
    if (!window.marked?.parse) return escapeHtml(raw).replace(/\n/g, '<br>');
    try {
      const parsed = window.marked.parse(raw, { breaks: true });
      const documentNode = new DOMParser().parseFromString(parsed, 'text/html');
      const allowed = new Set(['P','BR','STRONG','B','EM','I','CODE','PRE','UL','OL','LI','BLOCKQUOTE','H1','H2','H3','H4','HR','A','TABLE','THEAD','TBODY','TR','TH','TD']);
      const visit = node => {
        [...node.childNodes].forEach(child => {
          if (child.nodeType !== Node.ELEMENT_NODE) return;
          if (!allowed.has(child.tagName)) {
            child.replaceWith(documentNode.createTextNode(child.textContent || ''));
            return;
          }
          [...child.attributes].forEach(attribute => {
            if (child.tagName !== 'A' || attribute.name.toLowerCase() !== 'href') child.removeAttribute(attribute.name);
          });
          if (child.tagName === 'A') {
            const href = child.getAttribute('href') || '';
            if (!/^(https?:|mailto:)/i.test(href)) child.removeAttribute('href');
            else {
              child.setAttribute('target', '_blank');
              child.setAttribute('rel', 'noopener noreferrer');
            }
          }
          visit(child);
        });
      };
      visit(documentNode.body);
      return documentNode.body.innerHTML;
    } catch { return escapeHtml(raw).replace(/\n/g, '<br>'); }
  }

  function initials(name) {
    const words = String(name || '?').trim().split(/\s+/).filter(Boolean);
    return ((words[0]?.[0] || '?') + (words.length > 1 ? words[words.length - 1][0] : '')).toUpperCase().slice(0, 2);
  }

  function avatar(name, small = false) {
    return `<span class="oddi-sw-avatar${small ? ' small' : ''}" aria-hidden="true">${escapeHtml(initials(name))}</span>`;
  }

  function unreadBadge(value) {
    const count = Math.max(0, Number(value || 0));
    return count ? `<span class="oddi-sw-unread-badge" aria-label="${count} unread messages">${count > 99 ? '99+' : count}</span>` : '';
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      credentials: 'same-origin',
      cache: 'no-store',
      headers: { Accept: 'application/json', ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(options.headers || {}) },
      ...options,
    });
    let payload = {};
    try { payload = await response.json(); } catch { payload = {}; }
    if (!response.ok) {
      const detail = payload?.detail || payload?.error || `ODDI couldn't complete that request (${response.status}).`;
      const error = new Error(String(detail));
      error.status = response.status;
      throw error;
    }
    return payload;
  }

  function showToast(message) {
    let toast = root.querySelector('.oddi-sw-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.className = 'oddi-sw-toast';
      root.appendChild(toast);
    }
    toast.textContent = String(message || '');
    toast.hidden = false;
    window.clearTimeout(state.toastTimer);
    state.toastTimer = window.setTimeout(() => { toast?.remove(); }, 3000);
  }

  function stopPolling() {
    for (const name of ['listTimer', 'messageTimer', 'detailsTimer']) {
      if (state[name]) window.clearInterval(state[name]);
      state[name] = null;
    }
  }

  function closeWorkspaceView() {
    stopPolling();
    root.hidden = true;
    document.body.classList.remove('oddi-shared-workspace-open');
    state.workspaceId = null;
    state.details = null;
    state.messages.clear();
    state.messageCursor = 0;
    state.infoOpen = false;
  }

  function showError(message, signedOut = false, refreshPage = false) {
    root.innerHTML = `<section class="oddi-sw-shell is-error">
      <header class="oddi-sw-top"><button type="button" class="oddi-sw-back-home" data-action="close" aria-label="Back to home"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H5m7 7-7-7 7-7"/></svg><span>Back to home</span></button></header>
      <main class="oddi-sw-empty"><span class="oddi-sw-empty-icon">⌁</span><h2>${signedOut ? 'Sign in to collaborate' : 'We could not load your workspace'}</h2><p>${escapeHtml(message)}</p>${signedOut ? '<button class="oddi-sw-primary" data-action="signin" type="button">Sign in</button>' : refreshPage ? '<button class="oddi-sw-secondary" data-action="reload-page" type="button">Refresh page</button>' : '<button class="oddi-sw-secondary" data-action="reload" type="button">Try again</button>'}</main>
    </section>`;
  }

  function inviteCard(invite) {
    return `<article class="oddi-sw-invite-card">
      <p class="oddi-sw-invite-copy"><strong>${escapeHtml(invite.inviter_name || invite.inviter_email || 'An ODDI user')}</strong> invited you to <strong>${escapeHtml(invite.workspace_name || 'a shared workspace')}</strong>.</p>
      <div class="oddi-sw-invite-actions"><button class="oddi-sw-primary" type="button" data-action="respond-invite" data-choice="accept" data-invitation-id="${escapeHtml(invite.id)}">Accept</button><button class="oddi-sw-secondary" type="button" data-action="respond-invite" data-choice="reject" data-invitation-id="${escapeHtml(invite.id)}">Decline</button></div>
    </article>`;
  }

  function renderList() {
    const invitations = state.invitations;
    const workspaces = state.workspaces;
    const workspaceCards = workspaces.length ? workspaces.map(workspace => `
      <button type="button" class="oddi-sw-workspace-card" data-action="open-workspace" data-workspace-id="${escapeHtml(workspace.id)}">
        <span class="oddi-sw-card-title">${avatar(workspace.name, true)}<span>${escapeHtml(workspace.name)}</span><span class="oddi-sw-card-stats"><span class="oddi-sw-muted">${Number(workspace.member_count || 0)} ${Number(workspace.member_count || 0) === 1 ? 'member' : 'members'}</span>${unreadBadge(workspace.unread_count)}</span></span>
        <span class="oddi-sw-card-preview">${escapeHtml(workspace.last_message || 'Start the group conversation')}</span>
      </button>`).join('') : '<div class="oddi-sw-empty-inline">Your shared groups will show up here.</div>';
    const inviteCards = invitations.length ? invitations.map(inviteCard).join('') : '<div class="oddi-sw-empty-inline">No pending invitations.</div>';

    root.innerHTML = `<section class="oddi-sw-shell is-list">
      <header class="oddi-sw-top"><button type="button" class="oddi-sw-back-home" data-action="close" aria-label="Back to home"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H5m7 7-7-7 7-7"/></svg><span>Back to home</span></button></header>
      <div class="oddi-sw-body">
        <aside class="oddi-sw-list" aria-label="Shared workspaces and invitations">
          <div class="oddi-sw-list-head"><h2>Your groups</h2><button class="oddi-sw-primary" type="button" data-action="new-workspace">＋ New</button></div>
          <section class="oddi-sw-section"><div class="oddi-sw-section-label">Invitations <span class="oddi-sw-count">${invitations.length}</span></div>${inviteCards}</section>
          <section class="oddi-sw-section"><div class="oddi-sw-section-label">Shared workspaces</div>${workspaceCards}</section>
        </aside>
        <main class="oddi-sw-empty"><span class="oddi-sw-empty-icon">⌁</span><h2>Work through it together</h2><p>Create a shared group, invite as many ODDI members as you need, and chat together. Messages stay in the group; ODDI replies only when someone starts with <strong>@ODDI</strong>.</p><button class="oddi-sw-primary" type="button" data-action="new-workspace">Create a workspace</button></main>
      </div>
    </section>`;
  }

  async function refreshList() {
    try {
      const payload = await api('/api/shared-workspaces');
      if (pageAccountId && payload.account_id != null && String(payload.account_id) !== pageAccountId) {
        stopPolling();
        showError('Your signed-in account changed. Refresh this page to continue.', false, true);
        return;
      }
      state.workspaces = Array.isArray(payload.workspaces) ? payload.workspaces : [];
      state.invitations = Array.isArray(payload.invitations) ? payload.invitations : [];
      const hasNewInvite = state.lastInviteCount !== null && state.invitations.length > state.lastInviteCount;
      state.lastInviteCount = state.invitations.length;
      if (!root.querySelector('.oddi-sw-modal-backdrop')) renderList();
      if (hasNewInvite) showToast('You have a new shared workspace invitation.');
      window.dispatchEvent(new Event('oddi:shared-invitations-changed'));
    } catch (error) {
      showError(error.message, error.status === 401 || error.status === 403);
    }
  }

  function quotaText(quota) {
    if (quota?.unlimited) return 'No daily cap';
    const pieces = [];
    if (quota?.requests_remaining !== null && quota?.requests_remaining !== undefined) {
      pieces.push(`${quota.requests_remaining} AI request${quota.requests_remaining === 1 ? '' : 's'} left today`);
    }
    if (quota?.tokens_remaining !== null && quota?.tokens_remaining !== undefined) {
      pieces.push(`${Number(quota.tokens_remaining).toLocaleString()} tokens left`);
    }
    return pieces.join(' · ') || (quota?.available ? 'Daily limit available' : 'Daily AI limit reached');
  }

  function renderHeader() {
    const target = root.querySelector('.oddi-sw-chat-header');
    if (!target || !state.details) return;
    const { workspace, members } = state.details;
    target.innerHTML = `<span class="oddi-sw-avatar-stack">${members.slice(0, 4).map(member => avatar(member.name, true)).join('')}</span>
      <span class="oddi-sw-chat-title"><strong>${escapeHtml(workspace.name)}</strong><small>${members.length} ${members.length === 1 ? 'member' : 'members'} · tap for group info</small></span>
      <span class="oddi-sw-icon-btn" aria-hidden="true">•••</span>`;
  }

  function renderInfoPanel() {
    root.querySelector('.oddi-sw-info-backdrop')?.remove();
    root.querySelector('.oddi-sw-info')?.remove();
    if (!state.infoOpen || !state.details) return;
    const { workspace, members, invitations } = state.details;
    const isAdmin = workspace.my_role === 'admin' || workspace.my_role === 'owner';
    const memberRows = members.map(member => `
      <div class="oddi-sw-member">${avatar(member.name)}<div class="oddi-sw-member-copy"><strong>${escapeHtml(member.name)}${member.is_me ? ' · You' : ''}</strong><small>${escapeHtml(member.email)}</small><div class="oddi-sw-quota">${escapeHtml(quotaText(member.quota))}</div></div><span class="oddi-sw-role">${member.role === 'admin' || member.role === 'owner' ? 'Admin' : 'Member'}</span>
      ${isAdmin && !member.is_me ? `<button class="oddi-sw-icon-btn" type="button" data-action="remove-member" data-member-id="${escapeHtml(member.id)}" aria-label="Remove ${escapeHtml(member.name)}" title="Remove member">×</button>` : ''}</div>`).join('');
    const invitationRows = invitations?.length ? invitations.map(invite => `
      <div class="oddi-sw-invite-status"><span>${escapeHtml(invite.invitee_email)}</span><span style="margin-left:auto">${escapeHtml(invite.status)}</span>${invite.status === 'pending' ? `<button class="oddi-sw-icon-btn" type="button" data-action="revoke-invite" data-invitation-id="${escapeHtml(invite.id)}" aria-label="Cancel invitation">×</button>` : ''}</div>`).join('') : '<div class="oddi-sw-empty-inline">No invitations yet.</div>';
    const backdrop = document.createElement('div');
    backdrop.className = 'oddi-sw-info-backdrop';
    backdrop.dataset.action = 'close-info';
    root.appendChild(backdrop);
    const panel = document.createElement('aside');
    panel.className = 'oddi-sw-info';
    panel.setAttribute('aria-label', 'Group info');
    panel.innerHTML = `<div class="oddi-sw-info-head"><button type="button" class="oddi-sw-icon-btn" data-action="close-info" aria-label="Close group info">×</button><strong>Group info</strong><span class="oddi-sw-muted" style="font-size:11px">${members.length} ${members.length === 1 ? 'member' : 'members'}</span></div>
      <div class="oddi-sw-kicker">Shared ODDI group</div>
      ${isAdmin ? `<form class="oddi-sw-info-title-form" data-form="rename"><input name="name" maxlength="${MAX_NAME_LENGTH}" value="${escapeHtml(workspace.name)}" aria-label="Group name"><button type="submit" title="Save group name">✓</button></form>` : `<h2 style="margin:5px 0 16px">${escapeHtml(workspace.name)}</h2>`}
      <div class="oddi-sw-info-subtitle">${members.length} ${members.length === 1 ? 'member' : 'members'}</div>${memberRows || '<div class="oddi-sw-empty-inline">No members found.</div>'}
      ${isAdmin ? `<div class="oddi-sw-info-subtitle">Invite someone</div><form class="oddi-sw-info-form" data-form="invite"><input name="email" type="email" maxlength="254" placeholder="name@example.com" required aria-label="Invite by email"><button class="oddi-sw-primary" type="submit">Invite</button></form><small class="oddi-sw-muted">They can accept in ODDI after signing in with this email. Invitations expire in 14 days.</small><div class="oddi-sw-info-subtitle">Invitation activity</div>${invitationRows}` : ''}
      <div class="oddi-sw-info-subtitle">Daily ODDI limit</div><p class="oddi-sw-muted" style="font-size:11px;line-height:1.6">Every member, including the admin, gets up to 10 ODDI requests and 20,000 tokens per day; whichever limit runs out first. Group replies count against the sender's account allowance.</p>
      <div class="oddi-sw-info-actions">${isAdmin ? '<button class="oddi-sw-danger" type="button" data-action="delete-workspace">Delete group</button>' : '<button class="oddi-sw-secondary" type="button" data-action="leave-workspace">Leave group</button>'}</div>`;
    root.appendChild(panel);
  }

  function renderMessages(scrollToBottom = false) {
    const target = root.querySelector('.oddi-sw-messages');
    if (!target) return;
    const wasNearBottom = target.scrollHeight - target.scrollTop - target.clientHeight < 100;
    const messages = [...state.messages.values()].sort((a, b) => a.seq - b.seq);
    if (!messages.length) {
      target.innerHTML = '<div class="oddi-sw-empty-inline" style="padding-top:45px">Start with a message. Use <strong>@ODDI</strong> when you want an AI reply.</div>';
      return;
    }
    target.innerHTML = `<div class="oddi-sw-date-divider"><span>Messages in this shared group</span></div>${messages.map(message => {
      const isAssistant = message.kind === 'assistant';
      const mine = !!message.sender?.is_me;
      const meta = isAssistant ? 'ODDI' : `${message.sender?.name || 'Member'}${mine ? ' · You' : ''}`;
      const time = message.created_at ? new Date(message.created_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : '';
      const content = isAssistant ? safeMarkdown(message.text) : escapeHtml(message.text).replace(/\n/g, '<br>');
      let status = '';
      if (message.ai_status === 'queued') status = '<div class="oddi-sw-message-state">Waiting for ODDI<span class="oddi-sw-typing"><i></i><i></i><i></i></span></div>';
      if (message.ai_status === 'processing') status = '<div class="oddi-sw-message-state">ODDI is preparing a reply<span class="oddi-sw-typing"><i></i><i></i><i></i></span></div>';
      if (message.ai_status === 'failed') status = `<div class="oddi-sw-message-state error">${escapeHtml(message.ai_error || 'ODDI could not complete this reply.')}</div>`;
      return `<article class="oddi-sw-message${mine ? ' mine' : ''}${isAssistant ? ' assistant' : ''}" data-seq="${Number(message.seq)}"><div class="oddi-sw-message-meta"><strong>${escapeHtml(meta)}</strong><time>${escapeHtml(time)}</time></div><div class="oddi-sw-message-bubble">${content}</div>${status}</article>`;
    }).join('')}`;
    if (scrollToBottom || wasNearBottom) target.scrollTop = target.scrollHeight;
  }

  function renderChat() {
    if (!state.details) return;
    const { workspace, members } = state.details;
    root.innerHTML = `<section class="oddi-sw-shell is-chat">
      <header class="oddi-sw-top"><button type="button" data-action="back-to-list" aria-label="Back to groups">‹</button><span class="oddi-sw-brand">ODDI</span><span class="oddi-sw-kicker">Shared workspace</span><span class="oddi-sw-top-spacer"></span></header>
      <div class="oddi-sw-body">
        ${renderChatSidebar(workspace.id)}
        <main class="oddi-sw-chat" aria-label="${escapeHtml(workspace.name)} group chat"><button type="button" class="oddi-sw-chat-header" data-action="group-info" aria-label="Open group info"><span class="oddi-sw-avatar-stack">${members.slice(0, 4).map(member => avatar(member.name, true)).join('')}</span><span class="oddi-sw-chat-title"><strong>${escapeHtml(workspace.name)}</strong><small>${members.length} ${members.length === 1 ? 'member' : 'members'} · tap for group info</small></span><span class="oddi-sw-icon-btn" aria-hidden="true">•••</span></button>
          <div class="oddi-sw-messages" role="log" aria-label="Group messages" aria-live="polite"></div>
          <div class="oddi-sw-composer-wrap"><div class="oddi-sw-ai-hint"><strong>To talk with ODDI, start your message with @ODDI.</strong> Otherwise, chat freely with your group.<span class="oddi-sw-ai-hint-sub">ODDI replies use the sender's remaining daily limit.</span><button class="oddi-sw-prefix" type="button" data-action="add-prefix">Add @ODDI</button></div><form class="oddi-sw-compose" data-form="message"><textarea name="text" rows="1" maxlength="${MAX_MESSAGE_LENGTH}" placeholder="Message your group…" aria-label="Message your group"></textarea><button type="submit" aria-label="Send message">↑</button></form></div>
        </main>
      </div>
    </section>`;
    renderMessages(true);
    if (state.infoOpen) renderInfoPanel();
  }


  function renderChatSidebar(activeWorkspaceId) {
    const invitations = state.invitations.length
      ? `<div class="oddi-sw-section"><div class="oddi-sw-section-label">Invitations <span class="oddi-sw-count">${state.invitations.length}</span></div>${state.invitations.map(inviteCard).join('')}</div>`
      : '';
    const workspaces = state.workspaces.map(item => `<button type="button" class="oddi-sw-workspace-card${item.id === activeWorkspaceId ? ' active' : ''}" data-action="open-workspace" data-workspace-id="${escapeHtml(item.id)}"><span class="oddi-sw-card-title">${avatar(item.name, true)}<span>${escapeHtml(item.name)}</span>${unreadBadge(item.unread_count)}</span><span class="oddi-sw-card-preview">${escapeHtml(item.last_message || 'Shared group')}</span></button>`).join('');
    return `<aside class="oddi-sw-list" aria-label="Groups and invitations"><div class="oddi-sw-list-head"><h2>Group chat</h2><button class="oddi-sw-icon-btn" type="button" data-action="back-to-list" aria-label="All groups">Back</button></div>${invitations}<div class="oddi-sw-section"><div class="oddi-sw-section-label">Your groups</div>${workspaces || '<div class="oddi-sw-empty-inline">Your shared groups will show up here.</div>'}</div><div class="oddi-sw-section"><button type="button" class="oddi-sw-secondary" data-action="new-workspace" style="width:100%">Create another group</button></div></aside>`;
  }

  async function selectWorkspace(workspaceId) {
    stopPolling();
    state.page = 'chat';
    state.workspaceId = workspaceId;
    state.messages.clear();
    state.messageCursor = 0;
    state.details = null;
    state.infoOpen = false;
    root.innerHTML = '<section class="oddi-sw-shell"><header class="oddi-sw-top"><button type="button" data-action="back-to-list" aria-label="Back to groups">‹</button><span class="oddi-sw-brand">ODDI</span><span class="oddi-sw-kicker">Loading group…</span></header><main class="oddi-sw-empty"><span class="oddi-sw-empty-icon">⌁</span><p>Opening your shared conversation…</p></main></section>';
    try {
      const [details, messages] = await Promise.all([
        api(`/api/shared-workspaces/${encodeURIComponent(workspaceId)}`),
        api(`/api/shared-workspaces/${encodeURIComponent(workspaceId)}/messages?limit=100`),
      ]);
      if (state.workspaceId !== workspaceId) return;
      state.details = details;
      mergeMessages(messages.messages || []);
      renderChat();
      void markCurrentWorkspaceRead();
      state.messageTimer = window.setInterval(() => { void refreshMessages(); }, 1200);
      state.detailsTimer = window.setInterval(() => { void refreshDetails(); }, 15000);
    } catch (error) {
      state.page = 'list';
      showError(error.message, error.status === 401 || error.status === 403);
    }
  }

  function mergeMessages(messages) {
    (Array.isArray(messages) ? messages : []).forEach(message => {
      const seq = Number(message?.seq || 0);
      if (!seq) return;
      state.messages.set(seq, message);
      state.messageCursor = Math.max(state.messageCursor, seq);
    });
  }

  async function markCurrentWorkspaceRead() {
    const workspaceId = state.workspaceId;
    if (!workspaceId || root.hidden || document.hidden) return;
    try {
      await api(`/api/shared-workspaces/${encodeURIComponent(workspaceId)}/read`, { method: 'POST' });
      if (state.workspaceId === workspaceId) await refreshListQuietly();
    } catch { /* Keep the conversation usable if read receipts are unavailable. */ }
  }

  async function refreshMessages() {
    if (!state.workspaceId || state.refreshingMessages) return;
    state.refreshingMessages = true;
    try {
      const previousCursor = state.messageCursor;
      const payload = await api(`/api/shared-workspaces/${encodeURIComponent(state.workspaceId)}/messages?after_seq=${Math.max(0, state.messageCursor - 20)}&limit=200`);
      const before = state.messages.size;
      mergeMessages(payload.messages || []);
      if (state.messages.size !== before || (payload.messages || []).some(item => item.ai_status === 'queued' || item.ai_status === 'processing')) renderMessages(false);
      const incoming = (payload.messages || []).some(item => Number(item.seq || 0) > previousCursor && !item.sender?.is_me);
      if (incoming && !document.hidden && !root.hidden) void markCurrentWorkspaceRead();
    } catch (error) {
      if (error.status === 401 || error.status === 403 || error.status === 404) {
        stopPolling();
        showError(error.message, error.status === 401 || error.status === 403);
      }
    } finally {
      state.refreshingMessages = false;
    }
  }

  async function refreshDetails() {
    if (!state.workspaceId) return;
    try {
      const details = await api(`/api/shared-workspaces/${encodeURIComponent(state.workspaceId)}`);
      if (state.workspaceId !== details.workspace.id) return;
      state.details = details;
      renderHeader();
      renderInfoPanel();
      void refreshListQuietly();
    } catch (error) {
      if (error.status === 401 || error.status === 403 || error.status === 404) {
        stopPolling();
        showError(error.message, error.status === 401 || error.status === 403);
      }
    }
  }

  async function refreshListQuietly() {
    try {
      const payload = await api('/api/shared-workspaces');
      if (pageAccountId && payload.account_id != null && String(payload.account_id) !== pageAccountId) {
        stopPolling();
        showError('Your signed-in account changed. Refresh this page to continue.', false, true);
        return;
      }
      state.workspaces = Array.isArray(payload.workspaces) ? payload.workspaces : [];
      state.invitations = Array.isArray(payload.invitations) ? payload.invitations : [];
      if (state.page === 'chat' && !root.hidden) {
        const currentWorkspaceId = state.details?.workspace?.id || state.workspaceId;
        const aside = root.querySelector('.oddi-sw-list');
        if (aside) {
          const replacement = document.createElement('div');
          replacement.innerHTML = renderChatSidebar(currentWorkspaceId);
          aside.replaceWith(replacement.firstElementChild);
        }
      }
      window.dispatchEvent(new Event('oddi:shared-invitations-changed'));
    } catch { /* The current chat remains usable if the list refresh fails. */ }
  }

  function renderModal(title, description, formMarkup) {
    root.querySelector('.oddi-sw-modal-backdrop')?.remove();
    const backdrop = document.createElement('div');
    backdrop.className = 'oddi-sw-modal-backdrop';
    backdrop.innerHTML = `<section class="oddi-sw-modal" role="dialog" aria-modal="true"><h2>${escapeHtml(title)}</h2><p>${escapeHtml(description)}</p>${formMarkup}</section>`;
    root.appendChild(backdrop);
    backdrop.addEventListener('click', event => { if (event.target === backdrop) backdrop.remove(); });
    window.setTimeout(() => backdrop.querySelector('input')?.focus(), 40);
  }

  function openCreateModal() {
    renderModal('Create a shared group', 'Choose a name now. You can invite as many ODDI members as you need after creating it.', `<form class="oddi-sw-create-form" data-form="create"><input name="name" maxlength="${MAX_NAME_LENGTH}" placeholder="e.g. Product launch" required aria-label="Group name"><button class="oddi-sw-primary" type="submit">Create</button></form>`);
  }

  async function sendMessage(form) {
    if (state.sending || !state.workspaceId) return;
    const input = form.elements.namedItem('text');
    const text = String(input?.value || '').trim();
    if (!text) return;
    state.sending = true;
    const submit = form.querySelector('button[type="submit"]');
    if (submit) submit.disabled = true;
    try {
      const clientId = window.crypto?.randomUUID ? window.crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      const payload = await api(`/api/shared-workspaces/${encodeURIComponent(state.workspaceId)}/messages`, {
        method: 'POST', body: JSON.stringify({ text, client_message_id: clientId }),
      });
      if (input && input.value.trim() === text) input.value = '';
      mergeMessages([payload.message]);
      renderMessages(true);
      if (input) input.style.height = '38px';
      void refreshListQuietly();
    } catch (error) { showToast(error.message); }
    finally {
      state.sending = false;
      if (submit) submit.disabled = false;
      input?.focus();
    }
  }

  async function handleClick(event) {
    const button = event.target.closest('[data-action]');
    if (!button) {
      const workspaceCard = event.target.closest('[data-workspace-id]');
      if (workspaceCard) void selectWorkspace(workspaceCard.dataset.workspaceId);
      return;
    }
    const action = button.dataset.action;
    if (action === 'close') {
      closeWorkspaceView();
      if (typeof window.__oddiOpenSidebar === 'function') window.__oddiOpenSidebar();
      else window.dispatchEvent(new CustomEvent('oddi:sidebar-open'));
      return;
    }
    if (action === 'reload') { stopPolling(); await refreshList(); state.page = 'list'; if (!root.querySelector('.oddi-sw-shell.is-error')) state.listTimer = window.setInterval(() => { if (!root.hidden && state.page === 'list') void refreshList(); }, 10000); return; }
    if (action === 'reload-page') { window.location.reload(); return; }
    if (action === 'signin') { window.location.assign('/login'); return; }
    if (action === 'back-to-list') { state.page = 'list'; state.workspaceId = null; state.details = null; stopPolling(); await refreshList(); if (!root.querySelector('.oddi-sw-shell.is-error')) state.listTimer = window.setInterval(() => { if (!root.hidden && state.page === 'list') void refreshList(); }, 10000); return; }
    if (action === 'new-workspace') { openCreateModal(); return; }
    if (action === 'open-workspace') { void selectWorkspace(button.dataset.workspaceId); return; }
    if (action === 'group-info') { state.infoOpen = !state.infoOpen; renderInfoPanel(); return; }
    if (action === 'close-info') { state.infoOpen = false; renderInfoPanel(); return; }
    if (action === 'add-prefix') {
      const input = root.querySelector('.oddi-sw-compose textarea');
      if (!input) return;
      const value = input.value;
      input.value = /^\s*@oddi\b/i.test(value) ? value : `@ODDI ${value}`;
      input.focus();
      input.setSelectionRange(input.value.length, input.value.length);
      input.dispatchEvent(new Event('input', { bubbles: true }));
      return;
    }
    if (action === 'respond-invite') {
      button.disabled = true;
      try {
        const result = await api(`/api/shared-workspaces/invitations/${encodeURIComponent(button.dataset.invitationId)}/respond`, { method: 'POST', body: JSON.stringify({ action: button.dataset.choice }) });
        await refreshList();
        window.dispatchEvent(new Event('oddi:shared-invitations-changed'));
        if (result.status === 'accepted') showToast('Invitation accepted. The group is ready.');
        else showToast('Invitation declined.');
      } catch (error) { button.disabled = false; showToast(error.message); }
      return;
    }
    if (action === 'remove-member') {
      if (!window.confirm('Remove this person from the group? They will no longer be able to read or send group messages.')) return;
      try {
        await api(`/api/shared-workspaces/${encodeURIComponent(state.workspaceId)}/members/${encodeURIComponent(button.dataset.memberId)}`, { method: 'DELETE' });
        await refreshDetails();
        await refreshListQuietly();
        showToast('Member removed from the group.');
      } catch (error) { showToast(error.message); }
      return;
    }
    if (action === 'revoke-invite') {
      try {
        await api(`/api/shared-workspaces/${encodeURIComponent(state.workspaceId)}/invitations/${encodeURIComponent(button.dataset.invitationId)}`, { method: 'DELETE' });
        await refreshDetails();
        showToast('Invitation cancelled.');
      } catch (error) { showToast(error.message); }
      return;
    }
    if (action === 'leave-workspace') {
      if (!window.confirm('Leave this group? You will lose access to its messages.')) return;
      try {
        await api(`/api/shared-workspaces/${encodeURIComponent(state.workspaceId)}/leave`, { method: 'POST' });
        state.workspaceId = null; state.details = null; stopPolling();
        await refreshList();
        showToast('You left the group.');
      } catch (error) { showToast(error.message); }
      return;
    }
    if (action === 'delete-workspace') {
      if (!window.confirm('Delete this group and all of its messages for every member? This cannot be undone.')) return;
      try {
        await api(`/api/shared-workspaces/${encodeURIComponent(state.workspaceId)}`, { method: 'DELETE' });
        state.workspaceId = null; state.details = null; stopPolling();
        await refreshList();
        showToast('Group deleted.');
      } catch (error) { showToast(error.message); }
    }
  }

  async function handleSubmit(event) {
    const form = event.target;
    if (!form.matches('form[data-form]')) return;
    event.preventDefault();
    const kind = form.dataset.form;
    const values = new FormData(form);
    try {
      if (kind === 'create') {
        const created = await api('/api/shared-workspaces', { method: 'POST', body: JSON.stringify({ name: values.get('name') }) });
        root.querySelector('.oddi-sw-modal-backdrop')?.remove();
        state.workspaces = [created.workspace, ...state.workspaces.filter(item => item.id !== created.workspace.id)];
        await selectWorkspace(created.workspace.id);
      } else if (kind === 'invite') {
        const response = await api(`/api/shared-workspaces/${encodeURIComponent(state.workspaceId)}/invitations`, { method: 'POST', body: JSON.stringify({ email: values.get('email') }) });
        form.reset();
        await refreshDetails();
        showToast(`Invitation sent to ${response.email}. They can accept it inside ODDI.`);
      } else if (kind === 'rename') {
        const details = await api(`/api/shared-workspaces/${encodeURIComponent(state.workspaceId)}`, { method: 'PATCH', body: JSON.stringify({ name: values.get('name') }) });
        state.details = details;
        renderChat();
        state.infoOpen = true;
        renderInfoPanel();
        showToast('Group name updated.');
      } else if (kind === 'message') {
        await sendMessage(form);
      }
    } catch (error) { showToast(error.message); }
  }

  function onKeyDown(event) {
    if (event.key === 'Escape') {
      if (root.querySelector('.oddi-sw-modal-backdrop')) root.querySelector('.oddi-sw-modal-backdrop').remove();
      else if (state.infoOpen) { state.infoOpen = false; renderInfoPanel(); }
      else closeWorkspaceView();
      return;
    }
    if (event.target.matches('.oddi-sw-compose textarea') && event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      event.target.closest('form')?.requestSubmit();
    }
  }

  function onInput(event) {
    if (!event.target.matches('.oddi-sw-compose textarea')) return;
    event.target.style.height = '38px';
    event.target.style.height = `${Math.min(140, event.target.scrollHeight)}px`;
  }

  async function openWorkspaceList() {
    stopPolling();
    state.page = 'list';
    state.workspaceId = null;
    state.details = null;
    state.messages.clear();
    state.messageCursor = 0;
    state.infoOpen = false;
    root.hidden = false;
    document.body.classList.add('oddi-shared-workspace-open');
    window.dispatchEvent(new CustomEvent('oddi:sidebar-close'));
    root.innerHTML = '<section class="oddi-sw-shell"><header class="oddi-sw-top"><button type="button" class="oddi-sw-back-home" data-action="close" aria-label="Back to home"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H5m7 7-7-7 7-7"/></svg><span>Back to home</span></button></header><main class="oddi-sw-empty"><span class="oddi-sw-empty-icon">⌁</span><p>Loading your shared groups…</p></main></section>';
    await refreshList();
    if (!root.querySelector('.oddi-sw-shell.is-error')) {
      state.listTimer = window.setInterval(() => { if (!root.hidden && state.page === 'list' && !root.querySelector('.oddi-sw-modal-backdrop')) void refreshList(); }, 10000);
    }
  }

  root.addEventListener('click', event => { void handleClick(event); });
  root.addEventListener('submit', event => { void handleSubmit(event); });
  root.addEventListener('keydown', onKeyDown);
  root.addEventListener('input', onInput);
  window.addEventListener('oddi:shared-workspaces-open', () => { void openWorkspaceList(); });
  window.addEventListener('oddi:shared-workspaces-notification', event => {
    const detail = event.detail || {};
    showToast(detail.message || 'You have a shared workspace update.');
  });
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && !root.hidden && state.page === 'chat') void refreshMessages();
  });
  window.addEventListener('focus', () => {
    if (!root.hidden && state.page === 'chat') void refreshMessages();
  });
})();
