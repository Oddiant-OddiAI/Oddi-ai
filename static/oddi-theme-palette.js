(() => {
  const PALETTE_KEY = 'oddi_palette_v1';
  const THEME_KEY = 'oddi_theme_v1';
  const root = document.documentElement;
  const body = document.body;
  const paletteValue = value => value === 'cyber-green' || value === 'cyber-blue' ? value : 'mono';
  const themeValue = value => value === 'dark' || value === 'system' ? value : 'light';
  const readStorage = key => {
    try { return localStorage.getItem(key); } catch { return null; }
  };

  function syncPalette(value) {
    const palette = paletteValue(value ?? readStorage(PALETTE_KEY));
    root.dataset.oddiPalette = palette;
    if (body) body.dataset.oddiPalette = palette;
  }

  function syncAppearance(value) {
    const theme = themeValue(value ?? readStorage(THEME_KEY));
    const systemDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
    const isDark = theme === 'dark' || (theme === 'system' && systemDark);
    const appearance = theme === 'system' ? (isDark ? 'system-dark' : 'system-light') : theme;
    root.dataset.oddiAppearance = appearance;
    if (!body) return;
    body.dataset.oddiAppearance = appearance;
    if (typeof window.__oddiApplyTheme !== 'function') {
      body.classList.toggle('dark-mode', isDark);
      body.classList.toggle('oddi-system-theme', theme === 'system');
    }
  }

  function syncAll() {
    syncPalette();
    syncAppearance();
  }

  syncAll();
  document.addEventListener('oddi:palette-changed', event => syncPalette(event.detail?.palette));
  document.addEventListener('oddi:theme-changed', event => syncAppearance(event.detail?.theme));
  window.addEventListener('oddi:theme-changed', event => syncAppearance(event.detail?.theme));
  window.addEventListener('storage', event => {
    if (!event.key || event.key === PALETTE_KEY || event.key === THEME_KEY) syncAll();
  });
  window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener?.('change', () => {
    if (readStorage(THEME_KEY) === 'system') syncAppearance('system');
  });
})();
