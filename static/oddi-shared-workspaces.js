(() => {
  'use strict';

  if (window.__oddiSharedWorkspacesReady) return;
  window.__oddiSharedWorkspacesReady = true;

  const MAX_NAME_LENGTH = 80;
  const MAX_MESSAGE_LENGTH = 8000;
  const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
  const MAX_TOTAL_IMAGE_BYTES = 10 * 1024 * 1024;
  const MAX_MESSAGE_ATTACHMENTS = 5;
  const MESSAGE_REACTIONS = ['👍', '❤️', '😂', '😮', '😢', '🙏', '🎉', '🔥', '👏', '✅'];
  const MAX_TASK_TITLE_LENGTH = 180;
  const MAX_PROJECT_GOAL_LENGTH = 4000;
  const PROJECT_TEAM_SIZE_LABELS = Object.freeze({
    individual: 'Individual',
    '2-15': '2–15 members',
    '16+': '16+ members',
  });
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
    projectId: null,
    details: null,
    messages: new Map(),
    messageCursor: 0,
    messageSyncCursor: '',
    lastInviteCount: null,
    infoOpen: false,
    sending: false,
    listTimer: null,
    messageTimer: null,
    detailsTimer: null,
    toastTimer: null,
    refreshingMessages: false,
    expandedProjectIds: new Set(),
    replyTargetSeq: null,
    pendingAttachments: [],
    selectedMessageSeqs: new Set(),
    openMessageMenuSeq: null,
    reactionPickerSeq: null,
    forwardSeqs: [],
    messageHoldTimer: null,
    messageHoldSeq: null,
    messageHoldPoint: null,
    messageHoldTriggered: false,
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

  function resetMessageDraft() {
    window.clearTimeout(state.messageHoldTimer);
    state.messageHoldTimer = null;
    state.messageHoldSeq = null;
    state.messageHoldPoint = null;
    state.messageHoldTriggered = false;
    state.replyTargetSeq = null;
    state.pendingAttachments = [];
    state.selectedMessageSeqs.clear();
    state.openMessageMenuSeq = null;
    state.reactionPickerSeq = null;
    state.forwardSeqs = [];
  }

  function closeWorkspaceView() {
    stopPolling();
    root.hidden = true;
    document.body.classList.remove('oddi-shared-workspace-open');
    state.workspaceId = null;
    state.projectId = null;
    state.details = null;
    state.messages.clear();
    state.messageCursor = 0;
    state.messageSyncCursor = '';
    resetMessageDraft();
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

  function workspaceCard(workspace, activeId = '', extraClass = '') {
    return `<button type="button" class="oddi-sw-workspace-card${extraClass ? ` ${extraClass}` : ''}${workspace.id === activeId ? ' active' : ''}" data-action="open-workspace" data-workspace-id="${escapeHtml(workspace.id)}">
      <span class="oddi-sw-card-title">${avatar(workspace.name, true)}<span>${escapeHtml(workspace.name)}</span><span class="oddi-sw-card-stats"><span class="oddi-sw-muted">${Number(workspace.member_count || 0)} ${Number(workspace.member_count || 0) === 1 ? 'member' : 'members'}</span>${unreadBadge(workspace.unread_count)}</span></span>
      <span class="oddi-sw-card-preview">${escapeHtml(workspace.last_message || 'Shared group')}</span>
    </button>`;
  }

  function projectCard(project, workspace, activeProjectId = '') {
    const taskCount = Number(project.task_count || 0);
    const completed = Number(project.completed_count || 0);
    const progress = taskCount ? `${completed}/${taskCount} tasks` : 'Workflow not created';
    const expanded = state.expandedProjectIds.has(project.id);
    const panelId = `oddi-sw-project-contents-${String(project.id).replace(/[^a-zA-Z0-9_-]/g, '-')}`;
    return `<section class="oddi-sw-project-tree${expanded ? ' is-expanded' : ''}">
      <button type="button" class="oddi-sw-project-card${project.id === activeProjectId ? ' active' : ''}" data-action="toggle-project" data-project-id="${escapeHtml(project.id)}" data-project-name="${escapeHtml(project.name)}" aria-expanded="${expanded}" aria-controls="${escapeHtml(panelId)}">
        <span class="oddi-sw-project-mark" aria-hidden="true">P</span><span class="oddi-sw-project-copy"><strong>${escapeHtml(project.name)}</strong><small>${escapeHtml(progress)}</small></span>
        <span class="oddi-sw-project-indicators">${unreadBadge(workspace.unread_count)}<svg class="oddi-sw-project-chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></span>
      </button>
      <div class="oddi-sw-project-children" id="${escapeHtml(panelId)}"${expanded ? '' : ' hidden'}>
        ${workspaceCard(workspace, state.workspaceId === workspace.id ? workspace.id : '', 'oddi-sw-project-group-card')}
        <button type="button" class="oddi-sw-project-plan-link${project.id === activeProjectId ? ' active' : ''}" data-action="open-project" data-workspace-id="${escapeHtml(workspace.id)}" data-project-id="${escapeHtml(project.id)}">
          <span><strong>Project plan &amp; checklist</strong><small>Goal, deadline, and task progress</small></span><span aria-hidden="true">↗</span>
        </button>
      </div>
    </section>`;
  }

  function renderList() {
    const invitations = state.invitations;
    const workspaces = state.workspaces;
    const standaloneWorkspaces = workspaces.filter(workspace => !(workspace.projects || []).length);
    const workspaceCards = standaloneWorkspaces.length
      ? standaloneWorkspaces.map(workspace => workspaceCard(workspace)).join('')
      : `<div class="oddi-sw-empty-inline">${workspaces.length ? 'Groups linked to projects appear beneath each project.' : 'Your groups will show up here.'}</div>`;
    const projectCards = workspaces.flatMap(workspace => (workspace.projects || []).map(project => projectCard(project, workspace))).join('') || '<div class="oddi-sw-empty-inline">Projects you create in a group will show up here.</div>';
    const inviteCards = invitations.length ? invitations.map(inviteCard).join('') : '<div class="oddi-sw-empty-inline">No pending invitations.</div>';

    root.innerHTML = `<section class="oddi-sw-shell is-list">
      <header class="oddi-sw-top"><button type="button" class="oddi-sw-back-home" data-action="close" aria-label="Back to home"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H5m7 7-7-7 7-7"/></svg><span>Back to home</span></button></header>
      <div class="oddi-sw-body">
        <aside class="oddi-sw-list" aria-label="Shared workspaces and invitations">
          <div class="oddi-sw-list-head"><h2>Shared workspace</h2><button class="oddi-sw-primary" type="button" data-action="create-project">Create Project</button></div>
          <section class="oddi-sw-section"><div class="oddi-sw-section-label">Invitations <span class="oddi-sw-count">${invitations.length}</span></div>${inviteCards}</section>
          <section class="oddi-sw-section"><div class="oddi-sw-section-label">Groups</div>${workspaceCards}</section>
          <section class="oddi-sw-section"><div class="oddi-sw-section-label">Projects</div>${projectCards}</section>
        </aside>
        <main class="oddi-sw-empty"><span class="oddi-sw-empty-icon">&#10003;</span><h2>Plan it together</h2><p>Create a project with a clear goal and deadline, invite your group, and keep its checklist and shared ODDI conversation together.</p><button class="oddi-sw-primary" type="button" data-action="create-project">Create Project</button></main>
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
      if (!root.querySelector('.oddi-sw-modal-backdrop')) {
        if (state.page === 'project' && state.details) renderProject();
        else if (state.page === 'chat' && state.details) renderChat();
        else renderList();
      }
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
    const selectedCount = state.selectedMessageSeqs.size;
    const selectedToolbar = selectedCount ? `<div class="oddi-sw-selection-toolbar" role="toolbar" aria-label="Selected message actions"><strong>${selectedCount} selected</strong><button type="button" data-action="forward-selected">Forward</button><button type="button" class="is-danger" data-action="delete-selected">Delete</button><button type="button" data-action="clear-selection" aria-label="Clear selection">Cancel</button></div>` : '';
    const pinned = messages.filter(message => !message.deleted && message.pinned_until && Date.parse(message.pinned_until) > Date.now());
    const pinnedBanner = pinned.length ? `<button type="button" class="oddi-sw-pinned-banner${selectedCount ? ' has-selection' : ''}" data-action="jump-message" data-seq="${Number(pinned[0].seq)}"><span aria-hidden="true">📌</span><span><strong>${pinned.length > 1 ? `${pinned.length} pinned messages` : 'Pinned message'}</strong><small>${escapeHtml(String(pinned[0].text || 'Image').slice(0, 120))}</small></span></button>` : '';
    target.innerHTML = `${selectedToolbar}${pinnedBanner}<div class="oddi-sw-date-divider"><span>Messages in this shared group</span></div>${messages.length ? messages.map(message => {
      const isAssistant = message.kind === 'assistant';
      const mine = !!message.sender?.is_me;
      const isForwarded = message.kind === 'forwarded';
      const meta = isAssistant ? 'ODDI' : `${message.sender?.name || 'Member'}${mine ? ' · You' : ''}`;
      const time = message.created_at ? new Date(message.created_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : '';
      const forwardedAssistant = isForwarded && message.forwarded_from_sender === 'ODDI';
      const content = isAssistant || forwardedAssistant ? safeMarkdown(message.text) : escapeHtml(message.text).replace(/\n/g, '<br>');
      const reply = message.reply_to ? `<button type="button" class="oddi-sw-reply-quote" data-action="jump-message" data-seq="${Number(message.reply_to.seq)}"><strong>${escapeHtml(message.reply_to.sender_name || 'Member')}</strong><span>${escapeHtml(message.reply_to.text || (message.reply_to.has_attachments ? 'Image' : 'Message'))}</span></button>` : '';
      const attachments = (message.attachments || []).map(attachment => `<a class="oddi-sw-image-attachment" href="${escapeHtml(attachment.data)}" target="_blank" rel="noopener noreferrer" download="${escapeHtml(attachment.name || 'image')}"><img src="${escapeHtml(attachment.data)}" alt="${escapeHtml(attachment.name || 'Shared image')}" loading="lazy"></a>`).join('');
      const forwardedLabel = isForwarded ? `<div class="oddi-sw-forwarded-label">Forwarded from ${escapeHtml(message.forwarded_from_sender || 'a member')} · ${escapeHtml(message.forwarded_from_workspace || 'another group')}</div>` : '';
      const reactions = (message.reactions || []).map(reaction => `<button type="button" class="oddi-sw-reaction-chip${reaction.me ? ' mine' : ''}" data-action="react-message" data-seq="${Number(message.seq)}" data-emoji="${escapeHtml(reaction.emoji)}" aria-label="${escapeHtml(reaction.emoji)} ${Number(reaction.count)} reactions">${escapeHtml(reaction.emoji)} <span>${Number(reaction.count)}</span></button>`).join('');
      const isSelected = state.selectedMessageSeqs.has(Number(message.seq));
      const showSelectors = selectedCount > 0;
      const isAdmin = ['admin', 'owner'].includes(state.details?.workspace?.my_role);
      const canEdit = mine && !isAssistant && !message.deleted;
      const canDelete = (mine || isAdmin) && !message.deleted;
      const isPinned = !!message.pinned_until && Date.parse(message.pinned_until) > Date.now();
      const menuOpen = Number(state.openMessageMenuSeq) === Number(message.seq);
      const pickerOpen = Number(state.reactionPickerSeq) === Number(message.seq);
      const menu = menuOpen ? `<div class="oddi-sw-message-menu" role="menu"><button type="button" data-action="reply-message" data-seq="${Number(message.seq)}">↩ <span>Reply</span></button><button type="button" data-action="copy-message" data-seq="${Number(message.seq)}">▢ <span>Copy</span></button><button type="button" data-action="forward-message" data-seq="${Number(message.seq)}">➦ <span>Forward</span></button><button type="button" data-action="${isPinned ? 'unpin-message' : 'pin-message'}" data-seq="${Number(message.seq)}">♧ <span>${isPinned ? 'Unpin' : 'Pin'}</span></button>${canEdit ? `<button type="button" data-action="edit-message" data-seq="${Number(message.seq)}">✎ <span>Edit</span></button>` : ''}${canDelete ? `<button type="button" class="is-danger" data-action="delete-message" data-seq="${Number(message.seq)}">⌫ <span>Delete</span></button>` : ''}</div>` : '';
      const picker = pickerOpen ? `<div class="oddi-sw-reaction-picker" role="group" aria-label="Choose a reaction">${MESSAGE_REACTIONS.map(emoji => `<button type="button" data-action="react-message" data-seq="${Number(message.seq)}" data-emoji="${escapeHtml(emoji)}" aria-label="React ${escapeHtml(emoji)}">${escapeHtml(emoji)}</button>`).join('')}</div>` : '';
      const canReact = !message.deleted;
      const reactionTrigger = canReact ? `<button type="button" class="oddi-sw-message-tools-button oddi-sw-message-reaction-trigger" data-action="toggle-reaction-picker" data-seq="${Number(message.seq)}" aria-label="React to message" aria-expanded="${pickerOpen}"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><circle cx="9" cy="10" r=".7"/><circle cx="15" cy="10" r=".7"/><path d="M8.5 14.2c.8 1.4 2 2.1 3.5 2.1s2.7-.7 3.5-2.1"/></svg></button>` : '';
      const moreButton = canReact ? `<button type="button" class="oddi-sw-message-tools-button oddi-sw-message-more" data-action="toggle-message-menu" data-seq="${Number(message.seq)}" aria-label="Message options" aria-expanded="${menuOpen}">⋯</button>` : '';
      const messageBody = `<div class="oddi-sw-message-bubble">${reply}${forwardedLabel}${message.deleted ? '<span class="oddi-sw-deleted">This message was deleted.</span>' : `${attachments}${content}`}${moreButton}</div>`;
      let status = '';
      if (message.ai_status === 'queued') status = '<div class="oddi-sw-message-state">Waiting for ODDI<span class="oddi-sw-typing"><i></i><i></i><i></i></span></div>';
      if (message.ai_status === 'processing') status = '<div class="oddi-sw-message-state">ODDI is preparing a reply<span class="oddi-sw-typing"><i></i><i></i><i></i></span></div>';
      if (message.ai_status === 'failed') status = `<div class="oddi-sw-message-state error">${escapeHtml(message.ai_error || 'ODDI could not complete this reply.')}</div>`;
      const actionOpenClass = `${menuOpen ? ' has-menu-open' : ''}${pickerOpen ? ' has-picker-open' : ''}`;
      return `<article class="oddi-sw-message${mine ? ' mine' : ''}${isAssistant ? ' assistant' : ''}${isForwarded ? ' forwarded' : ''}${isSelected ? ' is-selected' : ''}${actionOpenClass}" data-seq="${Number(message.seq)}">${showSelectors ? `<button type="button" class="oddi-sw-message-select${isSelected ? ' selected' : ''}" data-action="toggle-select-message" data-seq="${Number(message.seq)}" aria-label="${isSelected ? 'Deselect' : 'Select'} message">${isSelected ? '✓' : ''}</button>` : ''}<div class="oddi-sw-message-main"><div class="oddi-sw-message-meta"><strong>${escapeHtml(meta)}</strong>${message.edited_at ? '<span>edited</span>' : ''}<time>${escapeHtml(time)}</time></div><div class="oddi-sw-message-content-row"><div class="oddi-sw-message-stack">${messageBody}${reactions ? `<div class="oddi-sw-message-reactions">${reactions}</div>` : ''}<div class="oddi-sw-message-reaction-row">${reactionTrigger}${picker}</div></div>${menu}</div>${status}</div></article>`;
    }).join('') : '<div class="oddi-sw-empty-inline" style="padding-top:45px">Start with a message. Use <strong>@ODDI</strong> when you want an AI reply.</div>'}`;
    if (scrollToBottom || wasNearBottom) target.scrollTop = target.scrollHeight;
  }

  function renderComposerState() {
    const replySlot = root.querySelector('.oddi-sw-reply-preview');
    const attachmentSlot = root.querySelector('.oddi-sw-attachment-preview');
    const reply = state.replyTargetSeq ? state.messages.get(Number(state.replyTargetSeq)) : null;
    if (replySlot) {
      replySlot.hidden = !reply;
      if (reply) replySlot.innerHTML = `<button type="button" data-action="jump-message" data-seq="${Number(reply.seq)}"><strong>Replying to ${escapeHtml(reply.sender?.name || 'Member')}</strong><span>${escapeHtml(reply.text || ((reply.attachments || []).length ? 'Image' : 'Message'))}</span></button><button type="button" data-action="clear-reply" aria-label="Cancel reply">×</button>`;
    }
    if (attachmentSlot) {
      attachmentSlot.innerHTML = state.pendingAttachments.map((item, index) => `<div class="oddi-sw-attachment-preview-item"><img src="${escapeHtml(item.data)}" alt=""><span>${escapeHtml(item.name)}</span><button type="button" data-action="remove-attachment" data-index="${index}" aria-label="Remove ${escapeHtml(item.name)}">×</button></div>`).join('');
      attachmentSlot.hidden = !state.pendingAttachments.length;
    }
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
          <div class="oddi-sw-composer-wrap"><div class="oddi-sw-ai-hint"><strong>To talk with ODDI, start your message with @ODDI.</strong> Otherwise, chat freely with your group.<span class="oddi-sw-ai-hint-sub">ODDI replies use the sender's remaining daily limit.</span><button class="oddi-sw-prefix" type="button" data-action="add-prefix">Add @ODDI</button></div><div class="oddi-sw-reply-preview" hidden></div><div class="oddi-sw-attachment-preview" hidden></div><form class="oddi-sw-compose" data-form="message"><input type="file" accept="image/png,image/jpeg,image/webp,image/gif" multiple hidden data-image-input><button type="button" class="oddi-sw-attach-button" data-action="attach-image" aria-label="Attach images" title="Attach images">＋</button><textarea name="text" rows="1" maxlength="${MAX_MESSAGE_LENGTH}" placeholder="Message your group…" aria-label="Message your group"></textarea><button type="submit" aria-label="Send message">↑</button></form></div>
        </main>
      </div>
    </section>`;
    renderMessages(true);
    renderComposerState();
    if (state.infoOpen) renderInfoPanel();
  }


  function renderChatSidebar(activeWorkspaceId) {
    const invitations = state.invitations.length
      ? `<div class="oddi-sw-section"><div class="oddi-sw-section-label">Invitations <span class="oddi-sw-count">${state.invitations.length}</span></div>${state.invitations.map(inviteCard).join('')}</div>`
      : '';
    const standaloneWorkspaces = state.workspaces.filter(item => !(item.projects || []).length);
    const workspaces = standaloneWorkspaces.map(item => workspaceCard(item, activeWorkspaceId)).join('');
    const projects = state.workspaces.flatMap(item => (item.projects || []).map(project => projectCard(project, item, state.projectId || ''))).join('');
    const groupEmptyMessage = state.workspaces.length ? 'Groups linked to projects appear beneath each project.' : 'Your groups will show up here.';
    return `<aside class="oddi-sw-list" aria-label="Groups, projects and invitations"><div class="oddi-sw-list-head"><h2>Shared workspace</h2><button class="oddi-sw-icon-btn" type="button" data-action="back-to-list" aria-label="All groups">Back</button></div>${invitations}<div class="oddi-sw-section"><div class="oddi-sw-section-label">Groups</div>${workspaces || `<div class="oddi-sw-empty-inline">${groupEmptyMessage}</div>`}</div><div class="oddi-sw-section"><div class="oddi-sw-section-label">Projects</div>${projects || '<div class="oddi-sw-empty-inline">Projects appear here.</div>'}</div><div class="oddi-sw-section"><button type="button" class="oddi-sw-secondary" data-action="create-project" style="width:100%">Create Project</button></div></aside>`;
  }

  function renderProjectView() {
    const target = root.querySelector('.oddi-sw-project-view');
    const project = (state.details?.projects || []).find(item => item.id === state.projectId);
    if (!target || !project || !state.details) return;
    const { workspace, members } = state.details;
    const isAdmin = workspace.my_role === 'admin' || workspace.my_role === 'owner';
    const teamSize = PROJECT_TEAM_SIZE_LABELS[project.team_size] || PROJECT_TEAM_SIZE_LABELS.individual;
    const tasks = Array.isArray(project.tasks) ? project.tasks : [];
    const done = Number(project.completed_count || 0);
    const progress = tasks.length ? Math.round(done * 100 / tasks.length) : 0;
    const deadline = project.deadline ? new Date(`${project.deadline}T00:00:00`).toLocaleDateString() : 'No deadline';
    const taskRows = tasks.length ? tasks.map(task => {
      const assignedName = task.assigned_user_name || (Number(task.assigned_user_id) === Number(pageAccountId) ? 'You' : 'Unassigned');
      const assignment = isAdmin
        ? `<select class="oddi-sw-task-assignee" data-task-assignee data-task-id="${escapeHtml(task.id)}" aria-label="Assign ${escapeHtml(task.title)}"><option value="">Unassigned</option>${members.filter(member => member.id != null).map(member => `<option value="${escapeHtml(member.id)}" ${Number(member.id) === Number(task.assigned_user_id) ? 'selected' : ''}>${escapeHtml(member.name)}${member.is_me ? ' (you)' : ''}</option>`).join('')}</select>`
        : `<span class="oddi-sw-task-assignee-label">${escapeHtml(assignedName)}</span>`;
      return `<article class="oddi-sw-task-row${task.status === 'done' ? ' is-done' : ''}">
        <label class="oddi-sw-task-check"><input type="checkbox" data-task-status data-task-id="${escapeHtml(task.id)}" ${task.status === 'done' ? 'checked' : ''}><span class="oddi-sw-task-checkmark" aria-hidden="true"></span><span class="oddi-sw-task-copy"><strong>${escapeHtml(task.title)}</strong>${task.details ? `<small>${escapeHtml(task.details)}</small>` : ''}</span></label>
        <div class="oddi-sw-task-tools">${assignment}${isAdmin ? `<button type="button" class="oddi-sw-task-delete" data-action="delete-project-task" data-task-id="${escapeHtml(task.id)}" aria-label="Delete ${escapeHtml(task.title)}" title="Delete task">&times;</button>` : ''}</div>
      </article>`;
    }).join('') : '<div class="oddi-sw-empty-inline">Your checklist will appear here after it is created.</div>';
    let workflow = '';
    if (project.workflow_status === 'offered' || project.workflow_status === 'failed') {
      workflow = `<section class="oddi-sw-workflow-offer"><div><span class="oddi-sw-project-eyebrow">OPTIONAL ODDI WORKFLOW</span><h3>Would you like ODDI to create a suggested workflow for this project?</h3><p>ODDI will turn your goal${project.deadline ? ' and deadline' : ''} into a practical checklist. Choosing Yes uses your daily ODDI allowance; tasks stay unassigned until an admin assigns them.</p></div><button class="oddi-sw-primary" type="button" data-action="generate-workflow">Yes, create workflow</button></section>`;
    } else if (project.workflow_status === 'generating') {
      workflow = '<section class="oddi-sw-workflow-offer is-generating"><strong>ODDI is creating your workflow...</strong><p>Your project checklist will appear here when it is ready.</p><span class="oddi-sw-typing"><i></i><i></i><i></i></span></section>';
    }
    target.innerHTML = `<div class="oddi-sw-project-content"><button type="button" class="oddi-sw-project-back" data-action="back-to-list">&larr; All projects</button>
      <header class="oddi-sw-project-heading"><div><span class="oddi-sw-project-eyebrow">PROJECT IN ${escapeHtml(workspace.name)}</span><h1>${escapeHtml(project.name)}</h1><div class="oddi-sw-project-meta"><span>Team size: <strong>${escapeHtml(teamSize)}</strong></span><span>Deadline: <strong>${escapeHtml(deadline)}</strong></span><span>${done} of ${tasks.length} tasks complete</span></div></div><div class="oddi-sw-project-actions">${isAdmin ? '<button type="button" class="oddi-sw-secondary" data-action="manage-group">Invite members</button>' : ''}<button type="button" class="oddi-sw-primary" data-action="open-workspace" data-workspace-id="${escapeHtml(workspace.id)}">Open group chat</button></div></header>
      <section class="oddi-sw-goal-card"><span class="oddi-sw-project-eyebrow">PROJECT GOAL</span><p>${escapeHtml(project.goal)}</p>${tasks.length ? `<div class="oddi-sw-progress-track" role="progressbar" aria-valuenow="${progress}" aria-valuemin="0" aria-valuemax="100"><span style="width:${progress}%"></span></div>` : ''}</section>
      ${workflow}
      <section class="oddi-sw-task-section"><div class="oddi-sw-project-section-head"><div><span class="oddi-sw-project-eyebrow">SHARED CHECKLIST</span><h2>Tasks &amp; milestones</h2><p>Admins assign tasks. Group members can mark the work complete.</p></div><span class="oddi-sw-task-count">${done}/${tasks.length}</span></div>
      ${taskRows}${isAdmin ? `<form class="oddi-sw-add-task" data-form="add-task"><input name="title" maxlength="${MAX_TASK_TITLE_LENGTH}" placeholder="Add a task or milestone" required><button type="submit" class="oddi-sw-secondary">Add task</button></form>` : ''}</section>
    </div>`;
  }

  function renderProject() {
    if (!state.details) return;
    const workspace = state.details.workspace;
    root.innerHTML = `<section class="oddi-sw-shell is-project"><header class="oddi-sw-top"><button type="button" class="oddi-sw-back-home" data-action="close" aria-label="Back to home"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H5m7 7-7-7 7-7"/></svg><span>Back to home</span></button><span class="oddi-sw-brand">ODDI</span><span class="oddi-sw-kicker">Project workspace</span></header><div class="oddi-sw-body">${renderChatSidebar(workspace.id)}<main class="oddi-sw-project-view" aria-label="Project details"></main></div></section>`;
    renderProjectView();
  }

  async function selectWorkspace(workspaceId) {
    stopPolling();
    resetMessageDraft();
    state.page = 'chat';
    state.workspaceId = workspaceId;
    state.projectId = null;
    state.messages.clear();
    state.messageCursor = 0;
    state.messageSyncCursor = '';
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

  async function openProject(workspaceId, projectId) {
    stopPolling();
    resetMessageDraft();
    state.page = 'project';
    state.workspaceId = workspaceId;
    state.projectId = projectId;
    state.expandedProjectIds.add(projectId);
    state.details = null;
    state.infoOpen = false;
    root.innerHTML = '<section class="oddi-sw-shell"><header class="oddi-sw-top"><button type="button" data-action="back-to-list" aria-label="Back to projects">Back</button><span class="oddi-sw-brand">ODDI</span><span class="oddi-sw-kicker">Loading project...</span></header><main class="oddi-sw-empty"><p>Opening your project...</p></main></section>';
    try {
      const details = await api(`/api/shared-workspaces/${encodeURIComponent(workspaceId)}`);
      if (state.workspaceId !== workspaceId || state.projectId !== projectId) return;
      if (!(details.projects || []).some(project => project.id === projectId)) throw new Error('This project is no longer available in the group.');
      state.details = details;
      renderProject();
      state.detailsTimer = window.setInterval(() => { void refreshDetails(); }, 5000);
      void refreshListQuietly();
    } catch (error) {
      state.page = 'list';
      state.projectId = null;
      showError(error.message, error.status === 401 || error.status === 403);
    }
  }

  function mergeMessages(messages) {
    let changed = false;
    (Array.isArray(messages) ? messages : []).forEach(message => {
      const seq = Number(message?.seq || 0);
      if (!seq) return;
      const previous = state.messages.get(seq);
      if (!previous || JSON.stringify(previous) !== JSON.stringify(message)) changed = true;
      state.messages.set(seq, message);
      state.messageCursor = Math.max(state.messageCursor, seq);
      const changedAt = String(message.updated_at || message.created_at || '');
      if (changedAt > state.messageSyncCursor) state.messageSyncCursor = changedAt;
    });
    return changed;
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
      const params = new URLSearchParams({ after_seq: String(state.messageCursor), limit: '200' });
      if (state.messageSyncCursor) params.set('updated_after', state.messageSyncCursor);
      const payload = await api(`/api/shared-workspaces/${encodeURIComponent(state.workspaceId)}/messages?${params.toString()}`);
      const changed = mergeMessages(payload.messages || []);
      if (changed) { renderMessages(false); renderComposerState(); }
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
      if (state.page === 'project') {
        const projectView = root.querySelector('.oddi-sw-project-view');
        const scrollTop = projectView?.scrollTop || 0;
        renderProjectView();
        if (projectView) root.querySelector('.oddi-sw-project-view').scrollTop = scrollTop;
      } else {
        renderHeader();
        renderInfoPanel();
      }
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
      if ((state.page === 'chat' || state.page === 'project') && !root.hidden) {
        const currentWorkspaceId = state.details?.workspace?.id || state.workspaceId;
        const aside = root.querySelector('.oddi-sw-list');
        if (aside) {
          const scrollTop = aside.scrollTop;
          const replacement = document.createElement('div');
          replacement.innerHTML = renderChatSidebar(currentWorkspaceId);
          aside.replaceWith(replacement.firstElementChild);
          root.querySelector('.oddi-sw-list').scrollTop = scrollTop;
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
    window.setTimeout(() => backdrop.querySelector('input:not([type="hidden"]),textarea,select,button')?.focus(), 40);
  }

  function openCreateProjectModal() {
    const groups = state.workspaces.filter(group => group.my_role === 'admin' || group.my_role === 'owner');
    const groupChoices = groups.length
      ? `<label><span>Group</span><select name="workspace_id" data-project-group>${groups.map(group => `<option value="${escapeHtml(group.id)}">${escapeHtml(group.name)}</option>`).join('')}<option value="">Create a new group</option></select></label><label class="oddi-sw-new-group-field" hidden><span>New group name</span><input name="group_name" maxlength="${MAX_NAME_LENGTH}" placeholder="e.g. Product team"></label>`
      : `<input type="hidden" name="workspace_id" value=""><label><span>Group name</span><input name="group_name" maxlength="${MAX_NAME_LENGTH}" placeholder="e.g. Product team" required></label>`;
    renderModal('Create a project', 'Set a clear goal and optional deadline. You can invite group members after creating it.', `<form class="oddi-sw-project-form" data-form="create-project">
      <label><span>Project name</span><input name="name" maxlength="${MAX_NAME_LENGTH}" placeholder="e.g. Prepare the product launch" required></label>
      ${groupChoices}
      <label><span>How many people will work on this project?</span><select name="team_size" required><option value="" selected disabled>Choose a team size</option><option value="individual">Individual</option><option value="2-15">2–15 members</option><option value="16+">16+ members</option></select></label>
      <label><span>Project goal</span><textarea name="goal" maxlength="${MAX_PROJECT_GOAL_LENGTH}" rows="3" placeholder="What should this project accomplish?" required></textarea></label>
      <label><span>Deadline <small>(optional)</small></span><input name="deadline" type="date"></label>
      <button class="oddi-sw-primary" type="submit">Create Project</button>
    </form>`);
    const form = root.querySelector('.oddi-sw-project-form');
    if (groups.length) {
      const selector = form?.querySelector('[data-project-group]');
      const newGroup = form?.querySelector('.oddi-sw-new-group-field');
      if (selector && newGroup) {
        newGroup.hidden = !!selector.value;
        newGroup.querySelector('input').required = !selector.value;
      }
    }
  }

  async function sendMessage(form) {
    if (state.sending || !state.workspaceId) return;
    const input = form.elements.namedItem('text');
    const text = String(input?.value || '').trim();
    if (!text && !state.pendingAttachments.length) return;
    state.sending = true;
    const submit = form.querySelector('button[type="submit"]');
    if (submit) submit.disabled = true;
    try {
      const clientId = window.crypto?.randomUUID ? window.crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      const payload = await api(`/api/shared-workspaces/${encodeURIComponent(state.workspaceId)}/messages`, {
        method: 'POST', body: JSON.stringify({
          text,
          client_message_id: clientId,
          reply_to_seq: state.replyTargetSeq,
          attachments: state.pendingAttachments.map(({ name, type, data }) => ({ name, type, data })),
        }),
      });
      if (input && input.value.trim() === text) input.value = '';
      state.pendingAttachments = [];
      state.replyTargetSeq = null;
      mergeMessages([payload.message]);
      renderMessages(true);
      renderComposerState();
      if (input) input.style.height = '38px';
      void refreshListQuietly();
    } catch (error) { showToast(error.message); }
    finally {
      state.sending = false;
      if (submit) submit.disabled = false;
      input?.focus();
    }
  }

  function readImageFile(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ''));
      reader.onerror = () => reject(new Error(`Could not read ${file.name || 'that image'}.`));
      reader.readAsDataURL(file);
    });
  }

  async function addImageFiles(fileList) {
    const files = [...(fileList || [])];
    if (!files.length) return;
    for (const file of files) {
      if (!['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(file.type)) {
        showToast('Attach a PNG, JPEG, WebP, or GIF image.');
        continue;
      }
      if (file.size > MAX_IMAGE_BYTES) { showToast('Each image must be smaller than 5 MB.'); continue; }
      if (state.pendingAttachments.length >= MAX_MESSAGE_ATTACHMENTS) { showToast(`Attach up to ${MAX_MESSAGE_ATTACHMENTS} images per message.`); break; }
      const total = state.pendingAttachments.reduce((sum, item) => sum + Number(item.size || 0), 0);
      if (total + file.size > MAX_TOTAL_IMAGE_BYTES) { showToast('Images in one message must total 10 MB or less.'); break; }
      try {
        const data = await readImageFile(file);
        state.pendingAttachments.push({ name: file.name || 'Image', type: file.type, data, size: file.size });
      } catch (error) { showToast(error.message); }
    }
    renderComposerState();
  }

  async function toggleMessageReaction(seq, emoji) {
    if (!state.workspaceId || !emoji) return;
    try {
      const payload = await api(`/api/shared-workspaces/${encodeURIComponent(state.workspaceId)}/messages/${encodeURIComponent(seq)}/reactions`, {
        method: 'POST', body: JSON.stringify({ emoji }),
      });
      mergeMessages([payload.message]);
      state.reactionPickerSeq = null;
      state.openMessageMenuSeq = null;
      renderMessages(false);
    } catch (error) { showToast(error.message); }
  }

  async function deleteMessages(seqs) {
    const requested = [...new Set((seqs || []).map(Number).filter(Number.isFinite))];
    const isAdmin = ['admin', 'owner'].includes(state.details?.workspace?.my_role);
    const selected = requested.filter(seq => {
      const message = state.messages.get(seq);
      return message && !message.deleted && (message.sender?.is_me || isAdmin);
    });
    if (requested.length > selected.length) showToast('Only your own messages can be deleted. Group admins can delete any message.');
    if (!selected.length || !state.workspaceId) return;
    if (selected.length > 100) { showToast('Delete up to 100 messages at a time.'); return; }
    const prompt = selected.length === 1
      ? 'Delete this message for everyone in the group?'
      : `Delete these ${selected.length} messages for everyone in the group?`;
    if (!window.confirm(prompt)) return;
    try {
      const payload = await api(`/api/shared-workspaces/${encodeURIComponent(state.workspaceId)}/messages/delete`, {
        method: 'POST', body: JSON.stringify({ seqs: selected }),
      });
      mergeMessages(payload.messages || []);
      state.selectedMessageSeqs.clear();
      state.openMessageMenuSeq = null;
      renderMessages(false);
      void refreshListQuietly();
      showToast(selected.length === 1 ? 'Message deleted.' : 'Messages deleted.');
    } catch (error) { showToast(error.message); }
  }

  function openForwardModal(seqs) {
    state.forwardSeqs = [...new Set((seqs || []).map(Number).filter(Number.isFinite))];
    if (state.forwardSeqs.length > 50) { state.forwardSeqs = []; showToast('Forward up to 50 messages at a time.'); return; }
    const groups = state.workspaces.filter(group => group.id !== state.workspaceId);
    if (!groups.length) { showToast('Join another group before forwarding messages.'); return; }
    const options = groups.map(group => `<option value="${escapeHtml(group.id)}">${escapeHtml(group.name)}</option>`).join('');
    renderModal('Forward message', 'Choose a group where you are a member.', `<form class="oddi-sw-forward-form" data-form="forward"><label><span>Forward to</span><select name="target_workspace_id" required>${options}</select></label><p>${state.forwardSeqs.length} ${state.forwardSeqs.length === 1 ? 'message' : 'messages'} selected</p><button class="oddi-sw-primary" type="submit">Forward</button></form>`);
  }

  function openPinModal(seq) {
    renderModal('Pin message', 'Choose how long this message should stay pinned. You can unpin it at any time.', `<form class="oddi-sw-pin-form" data-form="pin-message"><input type="hidden" name="seq" value="${Number(seq)}"><label><span><input type="radio" name="duration_hours" value="24" checked> 24 hours</span></label><label><span><input type="radio" name="duration_hours" value="168"> 7 days</span></label><label><span><input type="radio" name="duration_hours" value="720"> 30 days</span></label><button class="oddi-sw-primary" type="submit">Pin message</button></form>`);
  }

  function openEditModal(seq) {
    const message = state.messages.get(Number(seq));
    if (!message) return;
    renderModal('Edit message', 'Your change will be visible to everyone in this group.', `<form class="oddi-sw-edit-message-form" data-form="edit-message"><input type="hidden" name="seq" value="${Number(seq)}"><label><span>Message</span><textarea name="text" rows="4" maxlength="${MAX_MESSAGE_LENGTH}">${escapeHtml(message.text)}</textarea></label><button class="oddi-sw-primary" type="submit">Save changes</button></form>`);
  }

  async function jumpToMessage(seq) {
    const number = Number(seq);
    if (!Number.isFinite(number) || !number) return;
    let article = root.querySelector(`.oddi-sw-message[data-seq="${number}"]`);
    if (!article && state.workspaceId) {
      try {
        const payload = await api(`/api/shared-workspaces/${encodeURIComponent(state.workspaceId)}/messages?after_seq=${Math.max(0, number - 1)}&limit=1`);
        mergeMessages(payload.messages || []);
        renderMessages(false);
        article = root.querySelector(`.oddi-sw-message[data-seq="${number}"]`);
      } catch (error) { showToast(error.message); return; }
    }
    if (!article) { showToast('That message is no longer in this group.'); return; }
    article.scrollIntoView({ behavior: 'smooth', block: 'center' });
    article.classList.add('is-highlighted');
    window.setTimeout(() => article?.classList.remove('is-highlighted'), 1600);
  }

  function openReply(seq) {
    const message = state.messages.get(Number(seq));
    if (!message || message.deleted) return;
    state.replyTargetSeq = Number(seq);
    state.openMessageMenuSeq = null;
    state.reactionPickerSeq = null;
    renderMessages(false);
    renderComposerState();
    root.querySelector('.oddi-sw-compose textarea')?.focus();
  }

  function applyProjectSnapshot(snapshot) {
    if (!snapshot?.project || !state.details) return;
    state.details.workspace = snapshot.workspace || state.details.workspace;
    state.details.members = snapshot.members || state.details.members;
    const projects = state.details.projects || [];
    const index = projects.findIndex(item => item.id === snapshot.project.id);
    if (index >= 0) projects[index] = snapshot.project;
    else projects.unshift(snapshot.project);
    state.details.projects = projects;
  }

  function clearMessageHold() {
    window.clearTimeout(state.messageHoldTimer);
    state.messageHoldTimer = null;
    state.messageHoldSeq = null;
    state.messageHoldPoint = null;
  }

  function onMessagePointerDown(event) {
    if (event.pointerType !== 'touch' && event.pointerType !== 'pen') return;
    const article = event.target.closest('.oddi-sw-message');
    if (!article || event.target.closest('button,a,input,textarea,video,[data-action]')) return;
    clearMessageHold();
    state.messageHoldSeq = Number(article.dataset.seq);
    state.messageHoldPoint = { x: event.clientX, y: event.clientY };
    state.messageHoldTriggered = false;
    state.messageHoldTimer = window.setTimeout(() => {
      const seq = Number(state.messageHoldSeq);
      state.messageHoldTimer = null;
      if (!seq) return;
      state.messageHoldTriggered = true;
      state.selectedMessageSeqs.add(seq);
      state.openMessageMenuSeq = seq;
      state.reactionPickerSeq = null;
      renderMessages(false);
      window.setTimeout(() => { state.messageHoldTriggered = false; }, 800);
    }, 550);
  }

  function onMessagePointerMove(event) {
    if (!state.messageHoldTimer || !state.messageHoldPoint) return;
    if (Math.hypot(event.clientX - state.messageHoldPoint.x, event.clientY - state.messageHoldPoint.y) > 12) clearMessageHold();
  }

  function onMessagePointerEnd() {
    clearMessageHold();
  }

  function toggleSelectedMessage(seq) {
    const messageSeq = Number(seq);
    if (!messageSeq) return;
    if (state.selectedMessageSeqs.has(messageSeq)) state.selectedMessageSeqs.delete(messageSeq);
    else state.selectedMessageSeqs.add(messageSeq);
    state.openMessageMenuSeq = null;
    state.reactionPickerSeq = null;
    renderMessages(false);
  }

  async function handleClick(event) {
    if (state.messageHoldTriggered) {
      state.messageHoldTriggered = false;
      if (event.target.closest('.oddi-sw-message')) { event.preventDefault(); return; }
    }
    const isMessageActionClick = event.target.closest('.oddi-sw-message-tools-button,.oddi-sw-message-menu,.oddi-sw-reaction-picker');
    if ((state.openMessageMenuSeq || state.reactionPickerSeq) && !isMessageActionClick) {
      state.openMessageMenuSeq = null;
      state.reactionPickerSeq = null;
      renderMessages(false);
    }
    const messageArticle = event.target.closest('.oddi-sw-message');
    if (event.shiftKey && messageArticle && !event.target.closest('button,a,input,textarea,[data-action]')) {
      toggleSelectedMessage(messageArticle.dataset.seq);
      return;
    }
    const button = event.target.closest('[data-action]');
    if (!button) {
      const workspaceCard = event.target.closest('[data-workspace-id]');
      if (workspaceCard) void selectWorkspace(workspaceCard.dataset.workspaceId);
      return;
    }
    const action = button.dataset.action;
    const messageSeq = Number(button.dataset.seq || 0);
    if (action === 'toggle-message-menu') {
      state.openMessageMenuSeq = Number(state.openMessageMenuSeq) === messageSeq ? null : messageSeq;
      state.reactionPickerSeq = null;
      renderMessages(false);
      return;
    }
    if (action === 'reply-message') { openReply(messageSeq); return; }
    if (action === 'jump-message') { void jumpToMessage(messageSeq); return; }
    if (action === 'clear-reply') { state.replyTargetSeq = null; renderComposerState(); return; }
    if (action === 'copy-message') {
      const message = state.messages.get(messageSeq);
      if (!message) return;
      try {
        if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(message.text || '');
        else {
          const copyField = document.createElement('textarea'); copyField.value = message.text || ''; document.body.appendChild(copyField); copyField.select(); document.execCommand('copy'); copyField.remove();
        }
        showToast('Message copied.');
      } catch { showToast('Could not copy that message.'); }
      state.openMessageMenuSeq = null; renderMessages(false); return;
    }
    if (action === 'toggle-reaction-picker') {
      state.openMessageMenuSeq = null;
      state.reactionPickerSeq = Number(state.reactionPickerSeq) === messageSeq ? null : messageSeq;
      renderMessages(false);
      return;
    }
    if (action === 'react-message') { void toggleMessageReaction(messageSeq, button.dataset.emoji); return; }
    if (action === 'forward-message') { state.openMessageMenuSeq = null; openForwardModal([messageSeq]); return; }
    if (action === 'forward-selected') { openForwardModal([...state.selectedMessageSeqs]); return; }
    if (action === 'pin-message') { state.openMessageMenuSeq = null; openPinModal(messageSeq); return; }
    if (action === 'unpin-message') {
      try {
        const payload = await api(`/api/shared-workspaces/${encodeURIComponent(state.workspaceId)}/messages/${messageSeq}/pin`, { method: 'POST', body: JSON.stringify({ duration_hours: null }) });
        mergeMessages([payload.message]); renderMessages(false); showToast('Message unpinned.');
      } catch (error) { showToast(error.message); }
      return;
    }
    if (action === 'edit-message') { state.openMessageMenuSeq = null; openEditModal(messageSeq); return; }
    if (action === 'delete-message') { state.openMessageMenuSeq = null; void deleteMessages([messageSeq]); return; }
    if (action === 'toggle-select-message') { toggleSelectedMessage(messageSeq); return; }
    if (action === 'clear-selection') { state.selectedMessageSeqs.clear(); renderMessages(false); return; }
    if (action === 'delete-selected') { void deleteMessages([...state.selectedMessageSeqs]); return; }
    if (action === 'attach-image') { root.querySelector('[data-image-input]')?.click(); return; }
    if (action === 'remove-attachment') {
      state.pendingAttachments.splice(Number(button.dataset.index), 1); renderComposerState(); return;
    }
    if (action === 'close') {
      closeWorkspaceView();
      if (typeof window.__oddiOpenSidebar === 'function') window.__oddiOpenSidebar();
      else window.dispatchEvent(new CustomEvent('oddi:sidebar-open'));
      return;
    }
    if (action === 'reload') { stopPolling(); await refreshList(); state.page = 'list'; if (!root.querySelector('.oddi-sw-shell.is-error')) state.listTimer = window.setInterval(() => { if (!root.hidden && state.page === 'list') void refreshList(); }, 10000); return; }
    if (action === 'reload-page') { window.location.reload(); return; }
    if (action === 'signin') { window.location.assign('/login'); return; }
    if (action === 'back-to-list') { resetMessageDraft(); state.page = 'list'; state.workspaceId = null; state.projectId = null; state.details = null; stopPolling(); await refreshList(); if (!root.querySelector('.oddi-sw-shell.is-error')) state.listTimer = window.setInterval(() => { if (!root.hidden && state.page === 'list') void refreshList(); }, 10000); return; }
    if (action === 'create-project' || action === 'new-workspace') { openCreateProjectModal(); return; }
    if (action === 'open-workspace') { void selectWorkspace(button.dataset.workspaceId); return; }
    if (action === 'toggle-project') {
      const projectId = button.dataset.projectId;
      const tree = button.closest('.oddi-sw-project-tree');
      const contents = tree?.querySelector('.oddi-sw-project-children');
      if (!projectId || !contents) return;
      const expanded = !state.expandedProjectIds.has(projectId);
      if (expanded) state.expandedProjectIds.add(projectId);
      else state.expandedProjectIds.delete(projectId);
      button.setAttribute('aria-expanded', String(expanded));
      button.setAttribute('aria-label', (expanded ? 'Collapse ' : 'Expand ') + (button.dataset.projectName || 'project'));
      tree.classList.toggle('is-expanded', expanded);
      contents.hidden = !expanded;
      return;
    }
    if (action === 'open-project') { void openProject(button.dataset.workspaceId, button.dataset.projectId); return; }
    if (action === 'manage-group') {
      const workspaceId = state.workspaceId;
      state.infoOpen = true;
      await selectWorkspace(workspaceId);
      state.infoOpen = true;
      renderInfoPanel();
      return;
    }
    if (action === 'generate-workflow') {
      if (button.disabled || !state.projectId) return;
      button.disabled = true;
      const projectId = state.projectId;
      const project = (state.details?.projects || []).find(item => item.id === projectId);
      if (project) project.workflow_status = 'generating';
      renderProjectView();
      try {
        const snapshot = await api(`/api/shared-workspaces/projects/${encodeURIComponent(projectId)}/workflow`, { method: 'POST' });
        applyProjectSnapshot(snapshot);
        renderProjectView();
        await refreshListQuietly();
      } catch (error) {
        await refreshDetails();
        showToast(error.message);
      }
      return;
    }
    if (action === 'delete-project-task') {
      if (!window.confirm('Remove this task from the project checklist?')) return;
      try {
        const snapshot = await api(`/api/shared-workspaces/projects/${encodeURIComponent(state.projectId)}/tasks/${encodeURIComponent(button.dataset.taskId)}`, { method: 'DELETE' });
        applyProjectSnapshot(snapshot);
        renderProjectView();
        await refreshListQuietly();
      } catch (error) { showToast(error.message); }
      return;
    }
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
        state.page = 'list'; state.workspaceId = null; state.projectId = null; state.details = null; stopPolling();
        await refreshList();
        showToast('You left the group.');
      } catch (error) { showToast(error.message); }
      return;
    }
    if (action === 'delete-workspace') {
      if (!window.confirm('Delete this group and all of its messages for every member? This cannot be undone.')) return;
      try {
        await api(`/api/shared-workspaces/${encodeURIComponent(state.workspaceId)}`, { method: 'DELETE' });
        state.page = 'list'; state.workspaceId = null; state.projectId = null; state.details = null; stopPolling();
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
      if (kind === 'create-project') {
        const payload = {
          name: values.get('name'),
          goal: values.get('goal'),
          team_size: values.get('team_size'),
          deadline: values.get('deadline'),
          workspace_id: values.get('workspace_id'),
          group_name: values.get('group_name'),
        };
        const created = await api('/api/shared-workspaces/projects', { method: 'POST', body: JSON.stringify(payload) });
        root.querySelector('.oddi-sw-modal-backdrop')?.remove();
        state.workspaceId = created.workspace.id;
        await refreshList();
        await openProject(created.workspace.id, created.project.id);
        showToast('Project created. Invite your group, then choose Yes if you want ODDI to build a checklist.');
      } else if (kind === 'add-task') {
        const snapshot = await api(`/api/shared-workspaces/projects/${encodeURIComponent(state.projectId)}/tasks`, {
          method: 'POST', body: JSON.stringify({ title: values.get('title'), details: values.get('details') }),
        });
        applyProjectSnapshot(snapshot);
        renderProjectView();
        await refreshListQuietly();
      } else if (kind === 'create') {
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
      } else if (kind === 'forward') {
        const response = await api(`/api/shared-workspaces/${encodeURIComponent(state.workspaceId)}/messages/forward`, {
          method: 'POST', body: JSON.stringify({ target_workspace_id: values.get('target_workspace_id'), seqs: state.forwardSeqs }),
        });
        root.querySelector('.oddi-sw-modal-backdrop')?.remove();
        state.selectedMessageSeqs.clear(); state.forwardSeqs = [];
        await refreshListQuietly();
        showToast(`Forwarded ${response.messages?.length || 0} ${response.messages?.length === 1 ? 'message' : 'messages'}.`);
      } else if (kind === 'pin-message') {
        const seq = Number(values.get('seq'));
        const duration = Number(values.get('duration_hours'));
        const response = await api(`/api/shared-workspaces/${encodeURIComponent(state.workspaceId)}/messages/${seq}/pin`, {
          method: 'POST', body: JSON.stringify({ duration_hours: duration }),
        });
        root.querySelector('.oddi-sw-modal-backdrop')?.remove();
        mergeMessages([response.message]); renderMessages(false); showToast('Message pinned.');
      } else if (kind === 'edit-message') {
        const seq = Number(values.get('seq'));
        const response = await api(`/api/shared-workspaces/${encodeURIComponent(state.workspaceId)}/messages/${seq}`, {
          method: 'PATCH', body: JSON.stringify({ text: values.get('text') }),
        });
        root.querySelector('.oddi-sw-modal-backdrop')?.remove();
        mergeMessages([response.message]); renderMessages(false); void refreshListQuietly(); showToast('Message updated.');
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

  async function onChange(event) {
    const imageInput = event.target.closest('[data-image-input]');
    if (imageInput) {
      await addImageFiles(imageInput.files);
      imageInput.value = '';
      return;
    }
    const groupSelect = event.target.closest('[data-project-group]');
    if (groupSelect) {
      const field = groupSelect.form?.querySelector('.oddi-sw-new-group-field');
      if (field) {
        field.hidden = !!groupSelect.value;
        field.querySelector('input').required = !groupSelect.value;
      }
      return;
    }
    const statusInput = event.target.closest('[data-task-status]');
    const assigneeInput = event.target.closest('[data-task-assignee]');
    const control = statusInput || assigneeInput;
    if (!control || control.disabled || !state.projectId) return;
    const taskId = control.dataset.taskId;
    const value = statusInput ? { status: control.checked ? 'done' : 'todo' } : { assigned_user_id: control.value || null };
    control.disabled = true;
    try {
      const snapshot = await api(`/api/shared-workspaces/projects/${encodeURIComponent(state.projectId)}/tasks/${encodeURIComponent(taskId)}`, {
        method: 'PATCH', body: JSON.stringify(value),
      });
      applyProjectSnapshot(snapshot);
      renderProjectView();
      await refreshListQuietly();
    } catch (error) {
      await refreshDetails();
      showToast(error.message);
    }
  }

  async function openWorkspaceList() {
    stopPolling();
    resetMessageDraft();
    state.page = 'list';
    state.workspaceId = null;
    state.projectId = null;
    state.details = null;
    state.messages.clear();
    state.messageCursor = 0;
    state.messageSyncCursor = '';
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
  root.addEventListener('pointerdown', onMessagePointerDown, { passive: true });
  root.addEventListener('pointermove', onMessagePointerMove, { passive: true });
  root.addEventListener('pointerup', onMessagePointerEnd, { passive: true });
  root.addEventListener('pointercancel', onMessagePointerEnd, { passive: true });
  root.addEventListener('submit', event => { void handleSubmit(event); });
  root.addEventListener('keydown', onKeyDown);
  root.addEventListener('input', onInput);
  root.addEventListener('change', event => { void onChange(event); });
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
