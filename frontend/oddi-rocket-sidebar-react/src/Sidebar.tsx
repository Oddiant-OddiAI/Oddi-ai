import { useEffect, useMemo, useState } from 'react';
import {
  Archive, Brain, ChevronLeft, ChevronRight, Download, FolderOpen,
  LogOut, MessageSquare, Moon, MoreHorizontal, Pin, Plus, Search,
  Settings, Sun, X, Pencil, Trash2, Menu
} from 'lucide-react';

type Conversation = {
  id: string | number;
  title?: string;
  pinned?: boolean;
  archived?: boolean;
  deleted?: boolean;
  updated_at?: string;
  created_at?: string;
  messages?: unknown[];
  revision?: number;
};

type OddiWindow = Window & {
  oddiConversations?: Conversation[];
  __oddiOpenConversation?: (index: number) => void;
  togglePinConversation?: (conversation: Conversation) => Promise<unknown>;
  toggleArchiveConversation?: (conversation: Conversation) => Promise<unknown>;
  updateConversationMetadata?: (conversation: Conversation, patch: Record<string, unknown>) => Promise<boolean>;
  saveConversation?: (conversation: Conversation) => Promise<boolean>;
};

const WIN = () => window as OddiWindow;

function groupFor(value?: string) {
  if (!value) return 'Earlier';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return 'Earlier';
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  const week = new Date(today);
  week.setDate(week.getDate() - 7);
  if (d >= today) return 'Today';
  if (d >= yesterday) return 'Yesterday';
  if (d >= week) return 'Last 7 Days';
  return 'Earlier';
}

function grouped(items: Conversation[]) {
  const order = ['Today', 'Yesterday', 'Last 7 Days', 'Earlier'];
  const map = new Map<string, Conversation[]>();
  items.filter(c => !c.archived && !c.deleted).forEach(c => {
    const key = groupFor(c.updated_at || c.created_at);
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(c);
  });
  return order.filter(k => map.has(k)).map(label => ({ label, items: map.get(label)! }));
}

function refreshLegacySidebar() {
  window.dispatchEvent(new CustomEvent('oddi:conversations-changed'));
}

async function updateMetadata(c: Conversation, patch: Record<string, unknown>) {
  const legacy = WIN().updateConversationMetadata;
  if (legacy) return legacy(c, patch);
  const r = await fetch(`/api/conversations/${encodeURIComponent(String(c.id))}/metadata`, {
    method: 'PUT', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw new Error(`Metadata update failed (${r.status})`);
  const data = await r.json();
  Object.assign(c, data?.conversation || {});
  return true;
}

async function saveRenamedConversation(c: Conversation, title: string) {
  const legacy = WIN().saveConversation;
  if (legacy) {
    c.title = title;
    return legacy(c);
  }
  const r = await fetch(`/api/conversations/${encodeURIComponent(String(c.id))}`, {
    method: 'PUT', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ title, messages: Array.isArray(c.messages) ? c.messages : [], expected_revision: Number(c.revision || 0) }),
  });
  if (!r.ok) throw new Error(`Rename failed (${r.status})`);
  const data = await r.json();
  Object.assign(c, data?.conversation || {}, { title });
  return true;
}

function openConversationInLegacyApp(c: Conversation, fallbackIndex: number) {
  const key = String(c.id);
  const row = document.querySelector<HTMLElement>(`.history-item[data-conversation-id="${CSS.escape(key)}"]`);
  if (row) { row.click(); return; }

  const list = Array.isArray(WIN().oddiConversations) ? WIN().oddiConversations! : [];
  const index = list.findIndex(item => String(item?.id) === key);
  const opener = WIN().__oddiOpenConversation;
  if (opener && index >= 0) { opener(index); return; }
  if (opener && fallbackIndex >= 0) opener(fallbackIndex);
}

function openExistingModal(id: string) {
  const modal = document.getElementById(id);
  if (!modal) return false;
  modal.classList.add('show');
  modal.setAttribute('aria-hidden', 'false');
  return true;
}

export default function Sidebar() {
  const [open, setOpen] = useState(true);
  const [collapsed, setCollapsed] = useState(false);
  const [query, setQuery] = useState('');
  const [items, setItems] = useState<Conversation[]>([]);
  const [active, setActive] = useState<string | number | null>(null);
  const [menuId, setMenuId] = useState<string | number | null>(null);
  const [archiveModalOpen, setArchiveModalOpen] = useState(false);
  const [theme, setTheme] = useState<'light' | 'dark'>(document.body.classList.contains('dark-mode') ? 'dark' : 'light');
  const loggedIn = document.body.dataset.loggedIn === 'true';
  const username = document.body.dataset.username?.trim() || '';
  const email = document.body.dataset.email?.trim() || '';
  const [installReady, setInstallReady] = useState(false);

  useEffect(() => {
    const root = document.getElementById('oddi-react-sidebar-root');
    const sync = () => {
      document.body.classList.toggle('oddi-react-sidebar-open', open);
      document.body.classList.toggle('oddi-react-sidebar-collapsed', open && collapsed);
      root?.classList.toggle('is-open', open);
      root?.classList.toggle('is-collapsed', open && collapsed);
      root?.classList.toggle('is-closed', !open);
    };
    sync();
    return () => document.body.classList.remove('oddi-react-sidebar-open', 'oddi-react-sidebar-collapsed');
  }, [open, collapsed]);

  useEffect(() => {
    const observer = new MutationObserver(() => setTheme(document.body.classList.contains('dark-mode') ? 'dark' : 'light'));
    observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (!(event.target as HTMLElement)?.closest('.oddi-rs-chat-menu')) setMenuId(null);
    };
    const key = (event: KeyboardEvent) => { if (event.key === 'Escape') setMenuId(null); };
    document.addEventListener('click', close);
    document.addEventListener('keydown', key);
    return () => { document.removeEventListener('click', close); document.removeEventListener('keydown', key); };
  }, []);

  async function load() {
    try {
      const r = await fetch('/api/conversations', { credentials: 'same-origin', headers: { Accept: 'application/json' }, cache: 'no-store' });
      if (!r.ok) return;
      const data = await r.json();
      const list = Array.isArray(data) ? data : (Array.isArray(data?.conversations) ? data.conversations : []);
      setItems(list);
      if (active === null && list[0]) setActive(list[0].id);
    } catch (error) { console.error('ODDI sidebar conversation load failed:', error); }
  }

  useEffect(() => {
    load();
    const refresh = () => load();
    window.addEventListener('oddi:conversations-changed', refresh);
    return () => window.removeEventListener('oddi:conversations-changed', refresh);
  }, []);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return grouped(q ? items.filter(c => (c.title || '').toLowerCase().includes(q)) : items);
  }, [items, query]);

  function newChat() {
    const button = document.getElementById('newChatBtn');
    if (button) button.click();
    else WIN().__oddiOpenConversation?.(-1);
  }

  function select(c: Conversation) {
    const fallbackIndex = items.findIndex(item => String(item.id) === String(c.id));
    setActive(c.id);
    setMenuId(null);
    openConversationInLegacyApp(c, fallbackIndex);
  }

  async function pin(c: Conversation) {
    setMenuId(null);
    try {
      if (WIN().togglePinConversation) await WIN().togglePinConversation!(c);
      else await updateMetadata(c, { pinned: !c.pinned });
      setItems(prev => prev.map(x => String(x.id) === String(c.id) ? { ...x, pinned: !c.pinned } : x));
      refreshLegacySidebar();
    } catch (error) { console.error('Pin failed:', error); }
  }

  async function archive(c: Conversation) {
    setMenuId(null);
    try {
      if (WIN().toggleArchiveConversation) {
        await WIN().toggleArchiveConversation!(c);
      } else {
        await updateMetadata(c, { archived: !c.archived, deleted: false });
      }
      if (String(active) === String(c.id) && !c.archived) setActive(null);
      await load();
      refreshLegacySidebar();
    } catch (error) {
      console.error('Archive failed:', error);
    }
  }

  function rename(c: Conversation) {
    setMenuId(null);
    const modal = document.getElementById('renameModal');
    const input = document.getElementById('renameInput') as HTMLInputElement | null;
    const save = document.getElementById('saveRename');
    const cancel = document.getElementById('cancelRename');
    if (!modal || !input || !save || !cancel) return;

    input.value = c.title || 'New Chat';
    modal.classList.add('show');
    modal.setAttribute('aria-hidden', 'false');
    setTimeout(() => { input.focus(); input.select(); }, 0);

    save.onclick = async () => {
      const next = input.value.trim();
      if (!next || next === c.title) {
        modal.classList.remove('show');
        modal.setAttribute('aria-hidden', 'true');
        return;
      }
      save.setAttribute('disabled', 'true');
      try {
        await saveRenamedConversation(c, next);
        c.title = next;
        await load();
        refreshLegacySidebar();
        modal.classList.remove('show');
        modal.setAttribute('aria-hidden', 'true');
      } catch (error) {
        console.error('Rename failed:', error);
        alert('Could not rename this chat. Please try again.');
      } finally {
        save.removeAttribute('disabled');
      }
    };

    cancel.onclick = () => {
      modal.classList.remove('show');
      modal.setAttribute('aria-hidden', 'true');
    };
  }

  function moveToBin(c: Conversation) {
    setMenuId(null);
    const modal = document.getElementById('deleteModal');
    const cancel = document.getElementById('cancelDelete');
    const confirm = document.getElementById('confirmDelete');
    if (!modal || !cancel || !confirm) return;

    modal.classList.add('show');
    modal.setAttribute('aria-hidden', 'false');

    confirm.onclick = async () => {
      confirm.setAttribute('disabled', 'true');
      try {
        await updateMetadata(c, { deleted: true, pinned: false, archived: false });
        if (String(active) === String(c.id)) setActive(null);
        modal.classList.remove('show');
        modal.setAttribute('aria-hidden', 'true');
        await load();
        refreshLegacySidebar();
      } catch (error) {
        console.error('Move to Bin failed:', error);
        alert('Could not move this chat to the Bin. Please try again.');
      } finally {
        confirm.removeAttribute('disabled');
      }
    };

    cancel.onclick = () => {
      modal.classList.remove('show');
      modal.setAttribute('aria-hidden', 'true');
    };
  }

  function openMemory() {
    if (document.getElementById('memoryBtn')) { document.getElementById('memoryBtn')!.click(); return; }
    openExistingModal('memoryModal');
    window.dispatchEvent(new CustomEvent('oddi:open-memory'));
  }

  function openArchive() {
    const legacyButton = document.getElementById('archivedBtn');
    if (legacyButton) {
      legacyButton.click();
      return;
    }
    setMenuId(null);
    setArchiveModalOpen(true);
    load();
    window.dispatchEvent(new CustomEvent('oddi:open-archive'));
  }

  function openSettings() {
    if (document.getElementById('settingsBtn')) { document.getElementById('settingsBtn')!.click(); return; }
    openExistingModal('settingsModal');
  }

  function syncThemeViaLegacyApp() {
    const button = document.getElementById('themeBtn');
    if (button) button.click();
    else document.body.classList.toggle('dark-mode');
  }

  async function installOddi() {
    const button = document.getElementById('installBtn');
    if (button) { button.click(); return; }
    const promptEvent = (window as Window & { __oddiInstallPrompt?: { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> } }).__oddiInstallPrompt;
    if (promptEvent) {
      await promptEvent.prompt();
      setInstallReady(false);
      return;
    }
    if (window.matchMedia('(display-mode: standalone)').matches) return;
    alert('ODDI is ready to install. Use your browser menu → Install ODDI AI.');
  }

  useEffect(() => {
    const handler = (event: Event) => {
      const prompt = event as Event & { prompt?: () => Promise<void>; userChoice?: Promise<{ outcome: string }> };
      if (!prompt.prompt || !prompt.userChoice) return;
      event.preventDefault();
      (window as Window & { __oddiInstallPrompt?: typeof prompt }).__oddiInstallPrompt = prompt;
      setInstallReady(true);
    };
    window.addEventListener('beforeinstallprompt', handler);
    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  return <>
    {open && <button className="oddi-rs-backdrop" aria-label="Close sidebar" onClick={() => setOpen(false)} />}

    <aside className={`oddi-rs-sidebar ${open ? 'open' : 'closed'} ${collapsed ? 'collapsed' : ''}`} aria-label="ODDI AI sidebar">
      <header className="oddi-rs-header">
        <button className="oddi-rs-brand" onClick={() => collapsed && setCollapsed(false)} aria-label="ODDI AI">
          <img
            src={theme === 'dark' ? '/static/symbol-dark.png' : '/static/symbol.png'}
            alt="ODDI"
            style={{
              background: theme === 'dark' ? '#fff' : 'transparent',
              borderRadius: 5,
              padding: theme === 'dark' ? 2 : 0,
              display: 'block',
            }}
          />
          {!collapsed && <span>ODDI AI</span>}
        </button>
        <button className="oddi-rs-collapse" onClick={() => setCollapsed(v => !v)} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
          {collapsed ? <ChevronRight size={15} /> : <ChevronLeft size={15} />}
        </button>
        <button className="oddi-rs-mobile-close" onClick={() => setOpen(false)} aria-label="Close sidebar"><X size={15} /></button>
      </header>

      <main className="oddi-rs-main">
        <button className="oddi-rs-new" onClick={newChat}><Plus size={15} />{!collapsed && <span>New Chat</span>}</button>

        {!collapsed && <div className="oddi-rs-search">
          <Search size={13} />
          <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search conversations..." aria-label="Search conversations" />
          {query && <button className="oddi-rs-search-clear" onClick={() => setQuery('')} aria-label="Clear search">×</button>}
        </div>}

        <div className="oddi-rs-history">
          {collapsed
            ? visible.flatMap(g => g.items).slice(0, 8).map(c =>
              <button key={c.id} className={`oddi-rs-mini-chat ${active === c.id ? 'active' : ''}`} onClick={() => { setCollapsed(false); select(c); }} title={c.title || 'New Chat'}>
                {c.pinned ? <Pin size={13} /> : <MessageSquare size={13} />}
              </button>
            )
            : visible.map(g =>
              <section className="oddi-rs-group" key={g.label}>
                <div className="oddi-rs-label">{g.label}</div>
                {g.items.map(c => <div key={c.id} className={`oddi-rs-chat ${active === c.id ? 'active' : ''}`} onClick={() => select(c)} role="button" tabIndex={0} onKeyDown={e => e.key === 'Enter' && select(c)}>
                  {c.pinned ? <Pin size={11} /> : <MessageSquare size={11} />}
                  <span>{c.title || 'New Chat'}</span>
                  <div className="oddi-rs-actions">
                    <button onClick={e => { e.stopPropagation(); pin(c); }} title={c.pinned ? 'Unpin chat' : 'Pin chat'} aria-label={c.pinned ? 'Unpin chat' : 'Pin chat'}><Pin size={11} /></button>
                    <div className="oddi-rs-chat-menu">
                      <button onClick={e => { e.stopPropagation(); setMenuId(menuId === c.id ? null : c.id); }} title="More" aria-label="More"><MoreHorizontal size={13} /></button>
                      {menuId === c.id && <div className="oddi-rs-menu" onClick={e => e.stopPropagation()}>
                        <button onClick={() => rename(c)}><Pencil size={13} /><span>Rename</span></button>
                        <button onClick={() => archive(c)}><Archive size={13} /><span>{c.archived ? 'Unarchive' : 'Archive'}</span></button>
                        <button className="danger" onClick={() => moveToBin(c)}><Trash2 size={13} /><span>Delete</span></button>
                      </div>}
                    </div>
                  </div>
                </div>)}
              </section>
            )}
        </div>

        <nav
          className="oddi-rs-nav"
          aria-label="Sidebar utilities"
          style={{
            display: collapsed ? 'flex' : 'grid',
            gridTemplateColumns: '1fr',
            gap: collapsed ? 4 : 2,
            padding: collapsed ? '8px 6px' : '8px 10px',
            borderTop: collapsed ? '0' : '1px solid rgba(255,255,255,.10)',
            marginTop: collapsed ? 4 : 8,
          }}
        >
          {[
            { label: 'Memory', icon: <Brain size={14} />, action: openMemory, badge: '24' },
            { label: 'Files', icon: <FolderOpen size={14} />, action: openFilePicker, badge: '8' },
            { label: 'Archive', icon: <Archive size={14} />, action: openArchive },
            { label: 'Settings', icon: <Settings size={14} />, action: openSettings },
          ].map(item => (
            <button
              key={item.label}
              type="button"
              onClick={item.action}
              title={item.label}
              style={{
                width: '100%', minHeight: 32, display: 'flex', alignItems: 'center', gap: 10,
                padding: '7px 8px', border: 0, borderRadius: 7, background: 'transparent',
                color: 'var(--oddi-sidebar-muted, #a5a5a5)', font: 'inherit', fontSize: 13,
                textAlign: 'left', cursor: 'pointer', boxSizing: 'border-box',
              }}
              onMouseEnter={e => { e.currentTarget.style.background='rgba(255,255,255,.07)'; e.currentTarget.style.color='var(--oddi-sidebar-text, #f5f5f5)'; }}
              onMouseLeave={e => { e.currentTarget.style.background='transparent'; e.currentTarget.style.color='var(--oddi-sidebar-muted, #a5a5a5)'; }}
            >
              <span style={{ width: 18, display: 'inline-flex', justifyContent: 'center', flexShrink: 0 }}>{item.icon}</span>
              {!collapsed && <span style={{ flex: 1 }}>{item.label}</span>}
              {!collapsed && item.badge && <b style={{ minWidth: 19, height: 19, padding: '0 5px', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', borderRadius: 999, background: 'rgba(255,255,255,.08)', border: '1px solid rgba(255,255,255,.12)', color: '#9d9d9d', fontSize: 10, fontWeight: 600, boxSizing: 'border-box' }}>{item.badge}</b>}
            </button>
          ))}
        </nav>

        <button className="oddi-rs-theme" onClick={syncThemeViaLegacyApp}>
          {theme === 'dark' ? <Moon size={14} /> : <Sun size={14} />}
          {!collapsed && <span>{theme === 'dark' ? 'Dark Mode' : 'Bright Mode'}</span>}
        </button>

        {!collapsed && <button className="oddi-rs-install" onClick={installOddi}><Download size={13} /> {installReady ? 'Install ODDI AI' : 'Install ODDI AI'}</button>}
      </main>

      <footer className="oddi-rs-profile" style={{ display:'flex', alignItems:'center', gap:8, padding: collapsed ? '9px 7px' : '9px 10px', borderTop:'1px solid rgba(255,255,255,.10)', minHeight:54, boxSizing:'border-box' }}>
        <button
          className="oddi-rs-profile-main"
          type="button"
          onClick={() => document.getElementById('headerMoreBtn')?.click()}
          title={loggedIn ? 'Account settings' : 'Sign in'}
          style={{ flex:1, minWidth:0, display:'flex', alignItems:'center', gap:9, padding:0, border:0, background:'transparent', color:'#f5f5f5', font:'inherit', textAlign:'left', cursor:'pointer' }}
        >
          <div className="oddi-rs-avatar" style={{ width:30, height:30, minWidth:30, borderRadius:'50%', display:'flex', alignItems:'center', justifyContent:'center', background:'#f5f5f5', color:'#111', fontSize:12, fontWeight:700 }}>
            {loggedIn ? (username.charAt(0).toUpperCase() || 'U') : '?'}
          </div>
          {!collapsed && <div style={{ minWidth:0, display:'flex', flexDirection:'column', gap:2 }}>
            <strong style={{ fontSize:12, lineHeight:1.15, fontWeight:650, color:'#f5f5f5', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{loggedIn ? username : 'Sign in'}</strong>
            <small style={{ fontSize:9, lineHeight:1.15, color:'#777', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{loggedIn ? (email || 'Your profile') : 'Sign in to ODDI AI'}</small>
          </div>}
        </button>
        {loggedIn && <button className="oddi-rs-logout" type="button" onClick={() => document.getElementById('logoutBtn')?.click()} title="Sign out" style={{ width:26, height:26, display:'inline-flex', alignItems:'center', justifyContent:'center', flexShrink:0, border:0, borderRadius:6, background:'transparent', color:'#777', cursor:'pointer' }}><LogOut size={13} /></button>}
      </footer>
    </aside>

    {archiveModalOpen && (
      <div
        role="presentation"
        onMouseDown={e => { if (e.target === e.currentTarget) setArchiveModalOpen(false); }}
        style={{ position: 'fixed', inset: 0, zIndex: 2147483000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, background: 'rgba(0,0,0,.58)', backdropFilter: 'blur(4px)' }}
      >
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="oddi-react-archive-title"
          style={{ width: 'min(620px, calc(100vw - 40px))', maxHeight: 'min(620px, calc(100vh - 80px))', overflow: 'hidden', display: 'flex', flexDirection: 'column', borderRadius: 16, border: '1px solid rgba(255,255,255,.14)', background: theme === 'dark' ? '#111' : '#fff', color: theme === 'dark' ? '#f5f5f5' : '#171717', boxShadow: '0 24px 80px rgba(0,0,0,.35)' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 20px', borderBottom: theme === 'dark' ? '1px solid rgba(255,255,255,.10)' : '1px solid rgba(0,0,0,.10)' }}>
            <div>
              <h3 id="oddi-react-archive-title" style={{ margin: 0, fontSize: 17, fontWeight: 700 }}>Archived Chats</h3>
              <p style={{ margin: '5px 0 0', fontSize: 12, opacity: .62 }}>Archived chats are kept here and do not appear in normal history.</p>
            </div>
            <button type="button" onClick={() => setArchiveModalOpen(false)} aria-label="Close archived chats" style={{ width: 32, height: 32, border: 0, borderRadius: 8, background: theme === 'dark' ? '#1d1d1d' : '#f2f2f2', color: 'inherit', cursor: 'pointer', fontSize: 17 }}>×</button>
          </div>
          <div style={{ overflowY: 'auto', padding: 12 }}>
            {items.filter(c => c.archived && !c.deleted).length === 0 ? (
              <div style={{ padding: '38px 18px', textAlign: 'center', fontSize: 13, opacity: .58 }}>📦 No archived chats</div>
            ) : items.filter(c => c.archived && !c.deleted).map(c => (
              <div key={c.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '11px 10px', borderRadius: 9, marginBottom: 4 }}>
                <Archive size={14} style={{ flexShrink: 0, opacity: .65 }} />
                <button type="button" onClick={() => { setArchiveModalOpen(false); select(c); }} title={c.title || 'New Chat'} style={{ flex: 1, minWidth: 0, border: 0, background: 'transparent', color: 'inherit', textAlign: 'left', cursor: 'pointer', font: 'inherit', fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.title || 'New Chat'}</button>
                <button type="button" onClick={async () => { try { await updateMetadata(c, { archived: false }); await load(); refreshLegacySidebar(); } catch (error) { console.error('Restore archive failed:', error); } }} style={{ border: theme === 'dark' ? '1px solid #333' : '1px solid #ddd', borderRadius: 7, padding: '6px 9px', background: theme === 'dark' ? '#191919' : '#f7f7f7', color: 'inherit', cursor: 'pointer', font: 'inherit', fontSize: 11, whiteSpace: 'nowrap' }}>Restore</button>
              </div>
            ))}
          </div>
        </div>
      </div>
    )}

    {!open && (
      <div className="oddi-rs-rail" aria-label="Open ODDI sidebar">
        <button
          className="oddi-rs-launcher"
          onClick={() => setOpen(true)}
          title="Open sidebar"
          aria-label="Open sidebar"
        >
          <Menu size={21} />
        </button>
      </div>
    )}

  </>;
}

function openFilePicker() {
  (document.getElementById('fileInput') as HTMLInputElement | null)?.click();
}
