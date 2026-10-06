import { useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent, type PointerEvent as ReactPointerEvent } from 'react';
import {
  Archive, Brain, ChevronLeft, ChevronRight, Download, FolderOpen,
  Home, LogOut, MessageSquare, Moon, MoreHorizontal, Pin, Plus, Search,
  Settings, Sun, X, Pencil, Trash2, Menu, Monitor, Share2
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
  __oddiOpenSidebar?: () => void;
  newChat?: () => Promise<unknown>;
  __oddiWelcomeTemplate?: HTMLElement | null;
  __oddiReturnToHome?: boolean;
  __oddiApplyTheme?: (theme: string) => void;
  __oddiShowToast?: (message: string) => void;
  showOddiToast?: (message: string, type?: string) => void;
  __oddiOpenExportShare?: (ids: Array<string | number>, intent?: 'share' | 'download') => boolean;
  __oddiFreshChatActive?: boolean;
  __oddiFreshChatLockUntil?: number;
  __oddiKeepSidebarOnFreshHome?: boolean;
  __oddiConversationDataReady?: boolean;
  __oddiConversationLoadStarted?: boolean;
  setArchivedPreviewState?: (value: boolean) => void;
  togglePinConversation?: (conversation: Conversation, options?: { deferRender?: boolean }) => Promise<unknown>;
  toggleArchiveConversation?: (conversation: Conversation, options?: { deferRender?: boolean }) => Promise<unknown>;
  updateConversationMetadata?: (conversation: Conversation, patch: Record<string, unknown>, options?: { deferRender?: boolean }) => Promise<boolean>;
  saveConversation?: (conversation: Conversation) => Promise<boolean>;
  __oddiInstallPrompt?: { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };
  showActionConfirmation?: (title: string, message: string, confirmLabel: string, danger?: boolean) => Promise<boolean>;
  renderBin?: () => Promise<void>;
};

const WIN = () => window as OddiWindow;
const PENDING_GENERATION_KEY = 'oddi_pending_chat_generation_v1';
const LAST_OPEN_CONVERSATION_KEY = 'oddi_last_open_conversation_v1';
const FRESH_CHAT_MARKER = '__oddi_fresh_chat__';

function getPendingConversationId() {
  try {
    const pending = JSON.parse(localStorage.getItem(PENDING_GENERATION_KEY) || 'null');
    return pending?.conversationId ? String(pending.conversationId) : null;
  } catch { return null; }
}

function getLastOpenConversationId() {
  // sessionStorage preserves the selected chat on reload in this tab without
  // making a separately opened tab inherit the same conversation.
  try { return sessionStorage.getItem(LAST_OPEN_CONVERSATION_KEY); }
  catch { return null; }
}

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

  async function updateMetadata(c: Conversation, patch: Record<string, unknown>, options = { deferRender: true }) {
  const legacy = WIN().updateConversationMetadata;
  if (legacy) return legacy(c, patch, options);
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

function openConversationInLegacyApp(c: Conversation) {
  const key = String(c.id);
  const row = document.querySelector<HTMLElement>(`.history-item[data-conversation-id="${CSS.escape(key)}"]`);
  if (row) { row.click(); return; }

  const openById = () => {
    const list = Array.isArray(WIN().oddiConversations) ? WIN().oddiConversations! : [];
    const index = list.findIndex(item => String(item?.id) === key);
    const opener = WIN().__oddiOpenConversation;
    if (!opener || index < 0) return false;
    void opener(index);
    return true;
  };

  if (openById()) return;

  // The React list can arrive before the legacy viewer finishes hydrating.
  // Keep this selection by ID and resolve its real index when data is ready.
  const onReady = () => {
    if (!openById()) return;
    window.removeEventListener('oddi:conversations-loaded', onReady);
    window.removeEventListener('oddi:conversations-changed', onReady);
    window.clearTimeout(timeout);
  };
  window.addEventListener('oddi:conversations-loaded', onReady);
  window.addEventListener('oddi:conversations-changed', onReady);
  const timeout = window.setTimeout(() => {
    window.removeEventListener('oddi:conversations-loaded', onReady);
    window.removeEventListener('oddi:conversations-changed', onReady);
  }, 20000);
}

function openExistingModal(id: string) {
  const modal = document.getElementById(id);
  if (!modal) return false;
  modal.classList.add('show');
  modal.setAttribute('aria-hidden', 'false');
  return true;
}

export default function Sidebar() {
  const [open, setOpen] = useState(() => typeof window === 'undefined' || !window.matchMedia('(max-width: 768px)').matches);
  // Remember the sidebar state before entering the legacy Memory view. Desktop
  // normally starts open; phone normally starts closed so its hamburger rail
  // must remain available after Memory is closed.
  const openBeforeMemoryRef = useRef<boolean | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [query, setQuery] = useState('');
  const [items, setItems] = useState<Conversation[]>([]);
  const [active, setActive] = useState<string | number | null>(null);
  const [chatStarted, setChatStarted] = useState(() => !document.getElementById('welcomeContainer'));
  const [generatingConversationId, setGeneratingConversationId] = useState<string | null>(getPendingConversationId);
  const [menuId, setMenuId] = useState<string | number | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [bulkBusy, setBulkBusy] = useState(false);
  const [busyConversationIds, setBusyConversationIds] = useState<Set<string>>(() => new Set());
  const pendingActionsRef = useRef<Set<string>>(new Set());
  const bulkBusyRef = useRef(false);
  const pressTimerRef = useRef<number | null>(null);
  const pressOriginRef = useRef<{ x: number; y: number } | null>(null);
  const longPressHandledRef = useRef(false);
  const [archiveModalOpen, setArchiveModalOpen] = useState(false);
  const [theme, setTheme] = useState<'light' | 'dark' | 'system'>(() => {
    try {
      const saved = localStorage.getItem('oddi_theme_v1');
      if (saved === 'system' || saved === 'light' || saved === 'dark') return saved;
    } catch {}
    return document.body.classList.contains('dark-mode') ? 'dark' : 'light';
  });
  const [isDarkAppearance, setIsDarkAppearance] = useState(() => document.body.classList.contains('dark-mode'));
  const loggedIn = document.body.dataset.loggedIn === 'true';
  const username = document.body.dataset.username?.trim() || '';
  const email = document.body.dataset.email?.trim() || '';
  const [installReady, setInstallReady] = useState(false);
  const [isPhone, setIsPhone] = useState(() =>
    typeof window !== 'undefined' && window.matchMedia('(max-width: 768px)').matches
  );
  // Do not render the phone hamburger until the splash screen has finished.
  // This prevents the opener from flashing above the splash during a reload.
  const [splashReady, setSplashReady] = useState(() =>
    typeof document === 'undefined' || !document.getElementById('oddi-video-splash')
  );
  const [uploadedFiles, setUploadedFiles] = useState<Array<{name: string; type?: string; size?: number}>>([]);

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
    const app = document.querySelector('.app');
    if (!app) return;
    const syncChatView = () => setChatStarted(
      app.classList.contains('chat-started') || !document.getElementById('welcomeContainer')
    );
    const observer = new MutationObserver(syncChatView);
    observer.observe(app, { attributes: true, attributeFilter: ['class'], childList: true, subtree: true });
    syncChatView();
    return () => observer.disconnect();
  }, []);

  // Expose the React-owned open action to the legacy template hamburger and
  // gesture handler. They must never mutate sidebar DOM classes directly.
  useEffect(() => {
    const openSidebar = () => {
      setCollapsed(false);
      setOpen(true);
    };
    WIN().__oddiOpenSidebar = openSidebar;
    return () => {
      if (WIN().__oddiOpenSidebar === openSidebar) delete WIN().__oddiOpenSidebar;
    };
  }, []);

  useEffect(() => {
    const sync = () => setIsDarkAppearance(document.body.classList.contains('dark-mode'));
    const observer = new MutationObserver(sync);
    observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
    const onSystemTheme = () => {
      if (localStorage.getItem('oddi_theme_v1') === 'system') WIN().__oddiApplyTheme?.('system');
      sync();
    };
    const onThemeChanged = (event: Event) => {
      const next = (event as CustomEvent<{theme?: string}>).detail?.theme;
      if (next === 'light' || next === 'dark' || next === 'system') setTheme(next);
      sync();
    };
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    media.addEventListener?.('change', onSystemTheme);
    window.addEventListener('oddi:theme-changed', onThemeChanged);
    return () => { observer.disconnect(); media.removeEventListener?.('change', onSystemTheme); window.removeEventListener('oddi:theme-changed', onThemeChanged); };
  }, []);

  useEffect(() => {
    const syncGeneration = () => setGeneratingConversationId(getPendingConversationId());
    const onConversationOpened = (event: Event) => {
      const id = (event as CustomEvent<{ id?: string | number | null }>).detail?.id;
      setActive(id ?? null);
    };
    syncGeneration();
    window.addEventListener('oddi:generation-state-changed', syncGeneration);
    window.addEventListener('storage', syncGeneration);
    window.addEventListener('oddi:conversation-opened', onConversationOpened);
    return () => {
      window.removeEventListener('oddi:generation-state-changed', syncGeneration);
      window.removeEventListener('storage', syncGeneration);
      window.removeEventListener('oddi:conversation-opened', onConversationOpened);
    };
  }, []);

  // Phone-only behavior: keep the desktop/sidebar rail exactly as it is.
  useEffect(() => {
    const media = window.matchMedia('(max-width: 768px)');
    const syncPhone = () => setIsPhone(media.matches);
    syncPhone();
    media.addEventListener?.('change', syncPhone);
    return () => media.removeEventListener?.('change', syncPhone);
  }, []);

  // Splash-screen gate for the phone opener. The splash is controlled by
  // index.html and is removed after it receives the `oddi-splash-hidden` class.
  // Keep observing both its class and its removal so the hamburger appears only
  // after the splash is actually gone.
  useEffect(() => {
    const splash = document.getElementById('oddi-video-splash');
    if (!splash) {
      setSplashReady(true);
      return;
    }

    const syncSplash = () => {
      setSplashReady(splash.classList.contains('oddi-splash-hidden'));
    };

    syncSplash();
    const splashObserver = new MutationObserver(syncSplash);
    splashObserver.observe(splash, { attributes: true, attributeFilter: ['class'] });

    const bodyObserver = new MutationObserver(() => {
      if (!document.getElementById('oddi-video-splash')) {
        setSplashReady(true);
        bodyObserver.disconnect();
      }
    });
    bodyObserver.observe(document.body, { childList: true, subtree: true });

    return () => {
      splashObserver.disconnect();
      bodyObserver.disconnect();
    };
  }, []);

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (!(event.target as HTMLElement)?.closest('.oddi-rs-chat-menu')) setMenuId(null);
    };
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuId(null);

      // ODDI sidebar shortcut: Ctrl + Shift + B
      // Keep it global so it works even when the sidebar is closed.
      if (
        event.ctrlKey &&
        event.shiftKey &&
        !event.altKey &&
        !event.metaKey &&
        event.key.toLowerCase() === 'b'
      ) {
        event.preventDefault();
        event.stopPropagation();
        setCollapsed(false);
        setOpen(value => !value);
      }
    };
    document.addEventListener('click', close);
    document.addEventListener('keydown', key);
    return () => { document.removeEventListener('click', close); document.removeEventListener('keydown', key); };
  }, []);

  // Memory is a main-window view. The sidebar closes while Memory is open.
  // The closed rail itself stays mounted; CSS hides it only while the Memory
  // surface is visible. This keeps the phone opener reliable and avoids
  // React mounting/unmounting the rail in response to legacy DOM mutations.

  // Memory is a legacy main-window view. When its close button removes
  // the .show class, restore the React sidebar state that openMemory()
  // intentionally closed. This keeps the sidebar state in React instead of
  // relying on a page reload or DOM-only workaround.
  useEffect(() => {
    const memoryModal = document.getElementById('memoryModal');
    if (!memoryModal) return;

    const observer = new MutationObserver(() => {
      const memoryOpen = memoryModal.classList.contains('show');
      if (!memoryOpen && openBeforeMemoryRef.current !== null) {
        const previousOpen = openBeforeMemoryRef.current;
        openBeforeMemoryRef.current = null;
        setOpen(previousOpen);
      }
    });

    observer.observe(memoryModal, {
      attributes: true,
      attributeFilter: ['class'],
    });

    return () => observer.disconnect();
  }, []);

  // Library is a legacy modal created by index.html. Opening Library closes
  // the React sidebar, but closing Library must restore the desktop sidebar.
  // Phone intentionally keeps its hamburger-only closed state.
  useEffect(() => {
    let modalObserver: MutationObserver | null = null;
    let bodyObserver: MutationObserver | null = null;

    const attachLibraryObserver = (modal: HTMLElement | null) => {
      if (!modal || modalObserver) return;
      let wasOpen = modal.classList.contains('show');

      const onLibraryClassChange = () => {
        const isOpenNow = modal.classList.contains('show');
        if (wasOpen && !isOpenNow && !window.matchMedia('(max-width: 768px)').matches) {
          setCollapsed(false);
          setOpen(true);
        }
        wasOpen = isOpenNow;
      };

      modalObserver = new MutationObserver(onLibraryClassChange);
      modalObserver.observe(modal, {
        attributes: true,
        attributeFilter: ['class'],
      });
    };

    attachLibraryObserver(document.getElementById('oddiLibraryModal'));

    if (!modalObserver) {
      bodyObserver = new MutationObserver(() => {
        const modal = document.getElementById('oddiLibraryModal');
        if (modal) {
          attachLibraryObserver(modal);
          bodyObserver?.disconnect();
          bodyObserver = null;
        }
      });
      bodyObserver.observe(document.body, { childList: true, subtree: true });
    }

    return () => {
      modalObserver?.disconnect();
      bodyObserver?.disconnect();
      modalObserver = null;
      bodyObserver = null;
    };
  }, []);

  // File/gesture bridge from the legacy index.html. A selected upload expands
  // the React sidebar and shows the attachment directly inside it on desktop
  // and phone. This is presentation-only; the actual upload pipeline remains
  // owned by the main app.
  useEffect(() => {
    const onAttachments = (event: Event) => {
      const detail = (event as CustomEvent).detail || {};
      const files = Array.isArray(detail.files) ? detail.files : [];
      setUploadedFiles(files.slice(0, 12));
      if (files.length) {
        setCollapsed(false);
        setOpen(true);
      }
    };
    const onClearAttachments = () => setUploadedFiles([]);
    const onOpenSidebarShortcut = () => WIN().__oddiOpenSidebar?.();
    const onCloseSidebarShortcut = () => { setCollapsed(false); setOpen(false); };
    const onToggleSidebarShortcut = () => setOpen(v => !v);
    window.addEventListener('oddi:attachments-changed', onAttachments as EventListener);
    window.addEventListener('oddi:attachments-cleared', onClearAttachments);
    window.addEventListener('oddi:sidebar-open', onOpenSidebarShortcut);
    window.addEventListener('oddi:sidebar-close', onCloseSidebarShortcut);
    window.addEventListener('oddi:sidebar-toggle', onToggleSidebarShortcut);
    return () => {
      window.removeEventListener('oddi:attachments-changed', onAttachments as EventListener);
      window.removeEventListener('oddi:attachments-cleared', onClearAttachments);
      window.removeEventListener('oddi:sidebar-open', onOpenSidebarShortcut);
      window.removeEventListener('oddi:sidebar-close', onCloseSidebarShortcut);
      window.removeEventListener('oddi:sidebar-toggle', onToggleSidebarShortcut);
    };
  }, []);

  // Installed PWA/app state: the install control is meaningful only while an
  // installation is available. It disappears after installation.
  useEffect(() => {
    const isInstalled = () =>
      window.matchMedia('(display-mode: standalone)').matches ||
      (window.navigator as Navigator & { standalone?: boolean }).standalone === true;
    const syncInstall = () => setInstallReady(!isInstalled() && !!(WIN().__oddiInstallPrompt));
    const onPrompt = () => setInstallReady(!isInstalled());
    const onInstalled = () => setInstallReady(false);
    syncInstall();
    window.addEventListener('beforeinstallprompt', onPrompt as EventListener);
    window.addEventListener('appinstalled', onInstalled);
    return () => {
      window.removeEventListener('beforeinstallprompt', onPrompt as EventListener);
      window.removeEventListener('appinstalled', onInstalled);
    };
  }, []);

  async function load() {
    try {
      const r = await fetch('/api/conversations', { credentials: 'same-origin', headers: { Accept: 'application/json' }, cache: 'no-store' });
      if (!r.ok) return;
      const data = await r.json();
      const list = Array.isArray(data) ? data : (Array.isArray(data?.conversations) ? data.conversations : []);
      setItems(list);
      const preferredId = getLastOpenConversationId();
      const preferred = preferredId && list.find((c: Conversation) => String(c.id) === String(preferredId));
      if (preferredId === FRESH_CHAT_MARKER) setActive(null);
      else if (preferred) setActive(preferred.id);
      else if (active === null && list[0]) setActive(list[0].id);
    } catch (error) { console.error('ODDI sidebar conversation load failed:', error); }
  }

  useEffect(() => {
    const syncFromLegacy = (event?: Event) => {
      const detail = (event as CustomEvent<{ conversations?: Conversation[] }> | undefined)?.detail;
      const list = Array.isArray(detail?.conversations)
        ? detail!.conversations!
        : Array.isArray(WIN().oddiConversations) ? WIN().oddiConversations! : [];
      setItems(list.slice());
      const preferredId = getLastOpenConversationId();
      const preferred = preferredId && list.find(c => String(c.id) === String(preferredId));
      if (preferredId === FRESH_CHAT_MARKER) setActive(null);
      else if (preferred) setActive(preferred.id);
      else if (list[0]) setActive(current => current ?? list[0].id);
    };
    const onLoaded = (event: Event) => syncFromLegacy(event);
    window.addEventListener('oddi:conversations-loaded', onLoaded);
    if (WIN().__oddiConversationDataReady) syncFromLegacy();
    else if (!WIN().__oddiConversationLoadStarted) load();
    const refresh = () => load();
    window.addEventListener('oddi:conversations-changed', refresh);
    return () => {
      window.removeEventListener('oddi:conversations-loaded', onLoaded);
      window.removeEventListener('oddi:conversations-changed', refresh);
    };
  }, []);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const source = q ? items.filter(c => (c.title || '').toLowerCase().includes(q)) : items;
    return grouped(source);
  }, [items, query]);

  const pinnedItems = useMemo(() => {
    const q = query.trim().toLowerCase();
    return items
      .filter(c => !c.archived && !c.deleted && !!c.pinned && (!q || (c.title || '').toLowerCase().includes(q)))
      .sort((a,b) => new Date(b.updated_at || b.created_at || 0).getTime() - new Date(a.updated_at || a.created_at || 0).getTime());
  }, [items, query]);

  function newChat() {
    const startNewChat = WIN().newChat;
    if (startNewChat) {
      void startNewChat().catch(error => console.error('ODDI New Chat failed:', error));
      return;
    }
    document.querySelector<HTMLButtonElement>('.new-chat-btn, .sidebar-new-chat-utility-btn')?.click();
  }

  function goHome() {
    WIN().__oddiReturnToHome = true;
    // On desktop, return to Home inside the collapsed sidebar. Closing it
    // makes the legacy fallback hamburger appear over the welcome screen.
    WIN().__oddiKeepSidebarOnFreshHome = !isPhone;
    newChat();
  }

  function select(c: Conversation) {
    WIN().__oddiKeepSidebarOnFreshHome = false;
    WIN().__oddiFreshChatActive = false;
    WIN().__oddiFreshChatLockUntil = 0;
    setActive(c.id);
    setMenuId(null);
    openConversationInLegacyApp(c);
  }

  function toggleSelected(c: Conversation) {
    const id = String(c.id);
    setSelectedIds(previous => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function onChatPointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    if ((event.pointerType === 'mouse' && event.button !== 0) || (event.target as HTMLElement).closest('button, a, input')) return;
    if (pressTimerRef.current !== null) window.clearTimeout(pressTimerRef.current);
    longPressHandledRef.current = false;
    pressOriginRef.current = { x: event.clientX, y: event.clientY };
    const row = event.currentTarget;
    pressTimerRef.current = window.setTimeout(() => {
      pressTimerRef.current = null;
      longPressHandledRef.current = true;
      const id = String(row.dataset.conversationId || '');
      const conversation = items.find(item => String(item.id) === id);
      if (conversation) toggleSelected(conversation);
    }, 480);
  }

  function onChatPointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    const origin = pressOriginRef.current;
    if (origin && (Math.abs(event.clientX - origin.x) > 12 || Math.abs(event.clientY - origin.y) > 12) && pressTimerRef.current !== null) {
      window.clearTimeout(pressTimerRef.current);
      pressTimerRef.current = null;
    }
  }

  function onChatPointerEnd() {
    if (pressTimerRef.current !== null) window.clearTimeout(pressTimerRef.current);
    pressTimerRef.current = null;
    pressOriginRef.current = null;
    // Pointer-up is followed by click. Keep the long-press marker until that
    // click is consumed, then clear it in case the browser suppresses click.
    window.setTimeout(() => { longPressHandledRef.current = false; }, 700);
  }

  function onChatClick(c: Conversation, event: ReactMouseEvent<HTMLDivElement>) {
    if (longPressHandledRef.current) {
      longPressHandledRef.current = false;
      event.preventDefault();
      event.stopPropagation();
      return;
    }
    if (selectedIds.size) {
      event.preventDefault();
      toggleSelected(c);
      return;
    }
    select(c);
  }

  function setConversationBusy(id: string, busy: boolean) {
    setBusyConversationIds(previous => {
      const next = new Set(previous);
      if (busy) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  async function shareSelectedChats() {
    if (!selectedIds.size) return;
    const ids = [...selectedIds];
    const openExport = WIN().__oddiOpenExportShare;
    if (openExport) openExport(ids, 'share');
    else window.dispatchEvent(new CustomEvent('oddi:open-export-share', { detail: { ids, intent: 'share' } }));
  }

  async function downloadSelectedChats() {
    if (!selectedIds.size) return;
    const ids = [...selectedIds];
    const openExport = WIN().__oddiOpenExportShare;
    if (openExport) openExport(ids, 'download');
    else window.dispatchEvent(new CustomEvent('oddi:open-export-share', { detail: { ids, intent: 'download' } }));
  }

  function notifyBulkBinResult(message: string, type: 'success' | 'error' = 'success') {
    WIN().showOddiToast?.(message, type);
    if (type === 'success' && document.hidden && 'Notification' in window && Notification.permission === 'granted') {
      try { new Notification('ODDI-AI', { body: message }); }
      catch (error) { console.debug('Background Bin notification was unavailable:', error); }
    }
  }

  async function moveSelectedChatsToBin() {
    if (!selectedIds.size || bulkBusyRef.current) return;
    bulkBusyRef.current = true;
    setBulkBusy(true);
    const selected = items.filter(item => selectedIds.has(String(item.id)));
    const confirmAction = WIN().showActionConfirmation;
    try {
      const confirmed = confirmAction
        ? await confirmAction('Move Selected Chats to Bin?', `${selected.length} ${selected.length === 1 ? 'chat' : 'chats'} will be moved to the Bin.`, 'Move to Bin', true)
        : window.confirm(`Move ${selected.length} chats to the Bin?`);
      if (!confirmed) return;
      const movedIds = new Set(selected.map(item => String(item.id)));
      setItems(previous => previous.filter(item => !movedIds.has(String(item.id))));
      setSelectedIds(new Set());
      const selectedActive = active !== null && movedIds.has(String(active));
      if (selectedActive) {
        setActive(null);
        const startFresh = WIN().newChat;
        if (startFresh) void startFresh().catch(error => console.error('Could not start a new chat:', error));
      }
      WIN().showOddiToast?.(`Moving ${selected.length} ${selected.length === 1 ? 'chat' : 'chats'} to Bin…`);
      const results = await Promise.allSettled(selected.map(item => updateMetadata(item, { deleted: true, pinned: false, archived: false })));
      const failed = results.flatMap((result, index) => result.status === 'fulfilled' && result.value !== false ? [] : [selected[index]]);
      if (failed.length) {
        const failedIds = new Set(failed.map(item => String(item.id)));
        setItems(previous => [...failed.filter(item => !previous.some(existing => String(existing.id) === String(item.id))), ...previous]);
        setSelectedIds(failedIds);
        throw new Error(`${failed.length} ${failed.length === 1 ? 'chat could' : 'chats could'} not be moved and ${failed.length === 1 ? 'was' : 'were'} restored.`);
      }
      if (document.getElementById('binModal')?.classList.contains('show')) void WIN().renderBin?.();
      notifyBulkBinResult(`${selected.length} ${selected.length === 1 ? 'chat' : 'chats'} moved to Bin`);
    } catch (error) {
      console.error('Bulk move to Bin failed:', error);
      notifyBulkBinResult(error instanceof Error ? error.message : 'Could not move the selected chats to the Bin.', 'error');
    } finally {
      bulkBusyRef.current = false;
      setBulkBusy(false);
    }
  }

  async function pin(c: Conversation) {
    setMenuId(null);
    const id = String(c.id);
    if (pendingActionsRef.current.has(id)) return;
    pendingActionsRef.current.add(id);
    setConversationBusy(id, true);
    const previous = !!c.pinned;
    setItems(items => items.map(item => String(item.id) === id ? { ...item, pinned: !previous } : item));
    try {
      const saved = await updateMetadata(c, { pinned: !previous }, { deferRender: true });
      if (saved === false) throw new Error('Pin state was not saved.');
      c.pinned = !previous;
    } catch (error) {
      setItems(items => items.map(item => String(item.id) === id ? { ...item, pinned: previous } : item));
      console.error('Pin failed:', error);
      WIN().showOddiToast?.('Could not save the pin. Please try again.');
    }
    finally { pendingActionsRef.current.delete(id); setConversationBusy(id, false); }
  }

  async function archive(c: Conversation) {
    setMenuId(null);
    const id = String(c.id);
    if (pendingActionsRef.current.has(id)) return;
    pendingActionsRef.current.add(id);
    setConversationBusy(id, true);
    const previous = !!c.archived;
    const next = !previous;
    const wasActive = String(active) === id;
    setItems(items => items.map(item => String(item.id) === id ? { ...item, archived: next, deleted: false } : item));
    if (wasActive && next) {
      setActive(null);
      WIN().setArchivedPreviewState?.(true);
    }
    try {
      const saved = await updateMetadata(c, { archived: next, deleted: false }, { deferRender: true });
      if (saved === false) throw new Error('Archive state was not saved.');
      c.archived = next;
      c.deleted = false;
    } catch (error) {
      setItems(items => items.map(item => String(item.id) === id ? { ...item, archived: previous } : item));
      if (wasActive && next) {
        setActive(c.id);
        WIN().setArchivedPreviewState?.(false);
      }
      console.error('Archive failed:', error);
      WIN().showOddiToast?.('Could not archive this chat. Please try again.');
    } finally { pendingActionsRef.current.delete(id); setConversationBusy(id, false); }
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
      const id = String(c.id);
      if (pendingActionsRef.current.has(id)) return;
      pendingActionsRef.current.add(id);
      save.setAttribute('disabled', 'true');
      const previousTitle = c.title;
      setConversationBusy(id, true);
      c.title = next;
      setItems(previous => previous.map(item => String(item.id) === id ? { ...item, title: next } : item));
      modal.classList.remove('show');
      modal.setAttribute('aria-hidden', 'true');
      WIN().showOddiToast?.('Saving chat name…');
      try {
        const saved = await updateMetadata(c, { title: next }, { deferRender: true });
        if (saved === false) throw new Error('Rename was not saved.');
        WIN().showOddiToast?.('Chat renamed');
      } catch (error) {
        c.title = previousTitle;
        setItems(previous => previous.map(item => String(item.id) === id ? { ...item, title: previousTitle } : item));
        console.error('Rename failed:', error);
        WIN().showOddiToast?.('Could not rename this chat. Please try again.');
      } finally {
        save.removeAttribute('disabled');
        pendingActionsRef.current.delete(id);
        setConversationBusy(id, false);
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
      const id = String(c.id);
      if (pendingActionsRef.current.has(id)) return;
      pendingActionsRef.current.add(id);
      confirm.setAttribute('disabled', 'true');
      setConversationBusy(id, true);
      const wasActive = String(active) === id;
      setItems(previous => previous.filter(item => String(item.id) !== id));
      if (wasActive) setActive(null);
      modal.classList.remove('show');
      modal.setAttribute('aria-hidden', 'true');
      WIN().showOddiToast?.('Moving chat to Bin…');
      if (wasActive && WIN().newChat) void WIN().newChat!().catch(error => console.error('Could not open a new chat:', error));
      try {
        const saved = await updateMetadata(c, { deleted: true, pinned: false, archived: false }, { deferRender: true });
        if (saved === false) throw new Error('Move to Bin was not saved.');
        if (document.getElementById('binModal')?.classList.contains('show')) void WIN().renderBin?.();
        WIN().showOddiToast?.('Chat moved to Bin');
      } catch (error) {
        setItems(previous => previous.some(item => String(item.id) === id) ? previous : [c, ...previous]);
        console.error('Move to Bin failed:', error);
        WIN().showOddiToast?.('Could not move this chat to the Bin. The chat was restored.');
      } finally {
        confirm.removeAttribute('disabled');
        pendingActionsRef.current.delete(id);
        setConversationBusy(id, false);
      }
    };

    cancel.onclick = () => {
      modal.classList.remove('show');
      modal.setAttribute('aria-hidden', 'true');
    };
  }

  function openMemory() {
    // Memory is a main-window view. Preserve the state that existed immediately
    // before opening it so closing Memory restores desktop or phone behavior
    // instead of always forcing the sidebar open.
    openBeforeMemoryRef.current = open;
    setOpen(false);

    if (document.getElementById('memoryBtn')) {
      document.getElementById('memoryBtn')!.click();
      return;
    }

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

  function openLibrary() {
    setMenuId(null);
    setCollapsed(false);
    setOpen(false);
    window.dispatchEvent(new CustomEvent('oddi:open-library'));
  }

  function openSettings() {
    if (document.getElementById('settingsBtn')) { document.getElementById('settingsBtn')!.click(); return; }
    openExistingModal('settingsModal');
  }

  function syncThemeViaLegacyApp() {
    const next = theme === 'light' ? 'dark' : theme === 'dark' ? 'system' : 'light';
    setTheme(next);
    WIN().__oddiApplyTheme?.(next);
    window.dispatchEvent(new CustomEvent('oddi:theme-changed', { detail: { theme: next } }));
    const label = `${next === 'system' ? 'System' : next === 'dark' ? 'Dark' : 'Light'} mode`;
    if (WIN().showOddiToast) WIN().showOddiToast!(`Appearance: ${label}`);
    else if (WIN().__oddiShowToast) WIN().__oddiShowToast!(`Appearance: ${label}`);
    else window.dispatchEvent(new CustomEvent('oddi:toast', { detail: { message: `Appearance: ${label}` } }));
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
    <button className={`oddi-rs-backdrop ${open ? 'is-open' : 'is-closed'}`} aria-label="Close sidebar" onClick={() => setOpen(false)} />

    <aside className={`oddi-rs-sidebar ${open ? 'open' : 'closed'} ${collapsed ? 'collapsed' : ''}`} aria-label="ODDI AI sidebar">
      <header className="oddi-rs-header">
        <button className="oddi-rs-brand" onClick={() => collapsed && setCollapsed(false)} aria-label="ODDI AI">
          <img
            src={isDarkAppearance ? '/static/symbol-dark.png' : '/static/symbol.png'}
            alt="ODDI"
            style={{
              background: isDarkAppearance ? '#fff' : 'transparent',
              borderRadius: 5,
              padding: isDarkAppearance ? 2 : 0,
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
        {chatStarted && collapsed && <button className="oddi-rs-home" onClick={goHome} aria-label="Go to home" title="Home"><Home size={19} strokeWidth={3} /></button>}
        <button className="oddi-rs-new" onClick={newChat}><Plus size={19} strokeWidth={3} />{!collapsed && <span>New Chat</span>}</button>

        {!collapsed && <div className="oddi-rs-search">
          <Search size={13} />
          <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search conversations..." aria-label="Search conversations" />
          {query && <button className="oddi-rs-search-clear" onClick={() => setQuery('')} aria-label="Clear search">×</button>}
        </div>}

        {uploadedFiles.length > 0 && !collapsed && (
          <div className="oddi-rs-upload-strip" aria-label="Uploaded files">
            <div className="oddi-rs-upload-title"><FolderOpen size={12} /><span>Attachments</span><b>{uploadedFiles.length}</b></div>
            <div className="oddi-rs-upload-list">
              {uploadedFiles.map((file, index) => (
                <div className="oddi-rs-upload-item" key={`${file.name}-${index}`}>
                  <span className="oddi-rs-upload-icon">{file.type?.startsWith('image/') ? '🖼️' : '📎'}</span>
                  <span className="oddi-rs-upload-name" title={file.name}>{file.name}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="oddi-rs-history">
          {selectedIds.size > 0 && !collapsed && <div className="oddi-rs-selection-toolbar" role="toolbar" aria-label="Selected chat actions">
            <div className="oddi-rs-selection-count">{bulkBusy ? 'Preparing selected chats…' : `${selectedIds.size} selected`}</div>
            <div className="oddi-rs-selection-actions">
              <button type="button" onClick={() => void shareSelectedChats()} disabled={bulkBusy} title="Share selected chats" aria-label="Share selected chats"><Share2 size={14} /></button>
              <button type="button" onClick={() => void downloadSelectedChats()} disabled={bulkBusy} title="Download selected chats" aria-label="Download selected chats"><Download size={14} /></button>
              <button type="button" className="danger" onClick={() => void moveSelectedChatsToBin()} disabled={bulkBusy} title="Move selected chats to Bin" aria-label="Move selected chats to Bin"><Trash2 size={14} /></button>
              <button type="button" className="clear" onClick={() => setSelectedIds(new Set())} disabled={bulkBusy} title="Clear selection" aria-label="Clear selection"><X size={13} /></button>
            </div>
          </div>}
          {collapsed
              ? [...pinnedItems, ...visible.flatMap(g => g.items).filter(c => !c.pinned)].slice(0, 8).map(c =>
              <button key={c.id} className={`oddi-rs-mini-chat ${active === c.id ? 'active' : ''}`} onClick={() => { setCollapsed(false); select(c); }} title={`${generatingConversationId === String(c.id) ? 'Generating response · ' : ''}${c.title || 'New Chat'}`}>
                {generatingConversationId === String(c.id) ? <span className="oddi-rs-chat-spinner" role="status" aria-label="Generating response" /> : c.pinned ? <Pin size={13} /> : <MessageSquare size={13} />}
              </button>
            )
            : <>
                {pinnedItems.length > 0 && <section className="oddi-rs-pinned-group" aria-label="Pinned chats">
                  <div className="oddi-rs-label"><Pin size={11} /> <span>Pinned</span></div>
                  {pinnedItems.map(c => <div key={`pinned-${c.id}`} data-conversation-id={String(c.id)} className={`oddi-rs-chat pinned ${active === c.id ? 'active' : ''} ${selectedIds.has(String(c.id)) ? 'selected' : ''} ${selectedIds.size ? 'selecting' : ''} ${busyConversationIds.has(String(c.id)) ? 'busy' : ''}`} onPointerDown={onChatPointerDown} onPointerMove={onChatPointerMove} onPointerUp={onChatPointerEnd} onPointerCancel={onChatPointerEnd} onContextMenu={e => e.preventDefault()} onClick={e => onChatClick(c, e)} role="button" aria-pressed={selectedIds.has(String(c.id))} tabIndex={0} onKeyDown={e => e.key === 'Enter' && (selectedIds.size ? toggleSelected(c) : select(c))}>
                    <span className="oddi-rs-select-check" aria-hidden="true">{selectedIds.has(String(c.id)) ? '✓' : ''}</span>
                    <Pin size={11} />
                    <span className="oddi-rs-title-glass"><span>{c.title || 'New Chat'}</span></span>
                    {generatingConversationId === String(c.id) && <span className="oddi-rs-chat-spinner" role="status" aria-label="Generating response" title="Generating response" />}
                    <div className="oddi-rs-actions">
                      <button onClick={e => { e.stopPropagation(); pin(c); }} title="Unpin chat" aria-label="Unpin chat"><Pin size={11} /></button>
                      <div className="oddi-rs-chat-menu">
                        <button onClick={e => { e.stopPropagation(); setMenuId(menuId === c.id ? null : c.id); }} title="More" aria-label="More"><MoreHorizontal size={13} /></button>
                        {menuId === c.id && <div className="oddi-rs-menu" onClick={e => e.stopPropagation()}>
                          <button onClick={() => rename(c)}><Pencil size={13} /><span>Rename</span></button>
                          <button onClick={() => archive(c)}><Archive size={13} /><span>Archive</span></button>
                          <button className="danger" onClick={() => moveToBin(c)}><Trash2 size={13} /><span>Delete</span></button>
                        </div>}
                      </div>
                    </div>
                  </div>)}
                </section>}
                {visible.filter(g => g.items.some(c => !c.pinned)).map(g =>
                  <section className="oddi-rs-group" key={g.label}>
                    <div className="oddi-rs-label">{g.label}</div>
                    {g.items.filter(c => !c.pinned).map(c => <div key={c.id} data-conversation-id={String(c.id)} className={`oddi-rs-chat ${active === c.id ? 'active' : ''} ${selectedIds.has(String(c.id)) ? 'selected' : ''} ${selectedIds.size ? 'selecting' : ''} ${busyConversationIds.has(String(c.id)) ? 'busy' : ''}`} onPointerDown={onChatPointerDown} onPointerMove={onChatPointerMove} onPointerUp={onChatPointerEnd} onPointerCancel={onChatPointerEnd} onContextMenu={e => e.preventDefault()} onClick={e => onChatClick(c, e)} role="button" aria-pressed={selectedIds.has(String(c.id))} tabIndex={0} onKeyDown={e => e.key === 'Enter' && (selectedIds.size ? toggleSelected(c) : select(c))}>
                      {generatingConversationId === String(c.id) ? <span className="oddi-rs-chat-spinner" role="status" aria-label="Generating response" title="Generating response" /> : <MessageSquare size={11} />}
                      <span className="oddi-rs-title-glass"><span>{c.title || 'New Chat'}</span></span>
                      <div className="oddi-rs-actions">
                        <button onClick={e => { e.stopPropagation(); pin(c); }} title="Pin chat" aria-label="Pin chat"><Pin size={11} /></button>
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
              </>
          }
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
            { label: 'Library', icon: <FolderOpen size={14} />, action: openLibrary },
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

        <button className="oddi-rs-theme" onClick={syncThemeViaLegacyApp} title={`Switch appearance (current: ${theme})`}>
          {theme === 'dark' ? <Moon size={14} /> : theme === 'system' ? <Monitor size={14} /> : <Sun size={14} />}
          {!collapsed && <span>{theme === 'dark' ? 'Dark Mode' : theme === 'system' ? 'System Mode' : 'Bright Mode'}</span>}
        </button>

        {!collapsed && installReady && <button className="oddi-rs-install" onClick={installOddi}><Download size={13} />Install ODDI AI</button>}
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
            <strong style={{ fontSize:12, lineHeight:1.15, fontWeight:650, color:theme === 'dark' ? '#f5f5f5' : '#111', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{loggedIn ? username : 'Sign in'}</strong>
            <small style={{ fontSize:9, lineHeight:1.15, color:theme === 'dark' ? '#777' : '#777', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{loggedIn ? (email || 'Your profile') : 'Sign in to ODDI AI'}</small>
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

    {isPhone && splashReady && (
      <div className={`oddi-rs-rail ${open ? 'is-sidebar-open' : 'is-sidebar-closed'}`} aria-label="Mobile sidebar opener">
        <button className="oddi-rs-launcher oddi-rs-phone-launcher" onClick={() => {
          WIN().__oddiOpenSidebar?.();
        }} title="Open sidebar" aria-label="Open sidebar">
          <Menu size={21} aria-hidden="true" />
        </button>
      </div>
    )}

  </>;
}

function openFilePicker() {
  (document.getElementById('fileInput') as HTMLInputElement | null)?.click();
}

