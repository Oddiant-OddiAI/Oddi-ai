(function () {
  "use strict";

  const body = document.body;
  const userId = String(body?.dataset?.userId || "").trim();
  const profileScreen = document.getElementById("oddi-profile-screen");
  const profileModal = document.getElementById("oddiProfileModal");
  const activityKey = userId ? `oddi_active_minutes_v1:${userId}` : "";

  function localDateKey(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  }

  function readActivity() {
    if (!activityKey) return {};
    try {
      const parsed = JSON.parse(localStorage.getItem(activityKey) || "{}");
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
      return Object.fromEntries(Object.entries(parsed).filter(([key, value]) => /^\d{4}-\d{2}-\d{2}$/.test(key) && Number.isFinite(Number(value))));
    } catch (_) { return {}; }
  }

  if (body?.dataset?.loggedIn === "true" && activityKey) {
    let lastInteractionAt = Date.now();
    const markActive = () => { lastInteractionAt = Date.now(); };
    ["pointerdown", "keydown", "touchstart", "wheel", "scroll"].forEach(name =>
      window.addEventListener(name, markActive, { passive: true })
    );
    window.setInterval(() => {
      const now = Date.now();
      if (document.visibilityState !== "visible" || now - lastInteractionAt > 5 * 60 * 1000) return;
      const activity = readActivity();
      const today = localDateKey(new Date(now));
      activity[today] = Math.max(0, Number(activity[today] || 0)) + 1;
      const cutoff = new Date(now);
      cutoff.setFullYear(cutoff.getFullYear() - 5);
      const cutoffKey = localDateKey(cutoff);
      Object.keys(activity).forEach(key => { if (key < cutoffKey) delete activity[key]; });
      try { localStorage.setItem(activityKey, JSON.stringify(activity)); } catch (_) {}
      window.dispatchEvent(new CustomEvent("oddi:working-hours-updated"));
    }, 60 * 1000);
  }

  if (!profileScreen) {
    const params = new URLSearchParams(window.location.search);
    if (params.get("openSettings") === "1") {
      params.delete("openSettings");
      const query = params.toString();
      history.replaceState(null, "", `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`);
      window.setTimeout(() => document.getElementById("settingsBtn")?.click(), 120);
    }
    if (params.get("openProfile") === "1") {
      params.delete("openProfile");
      const query = params.toString();
      history.replaceState(null, "", `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`);
      window.setTimeout(() => document.dispatchEvent(new CustomEvent("oddi:profile-open")), 180);
    }
    return;
  }

  const statNodes = {
    lifetime: document.getElementById("oddi-stat-lifetime"),
    peak: document.getElementById("oddi-stat-peak"),
    task: document.getElementById("oddi-stat-task"),
    bestStreak: document.getElementById("oddi-stat-best-streak"),
    currentStreak: document.getElementById("oddi-stat-current-streak"),
  };
  const chart = document.getElementById("oddi-working-chart");
  const total = document.getElementById("oddi-working-hours-total");
  const caption = document.getElementById("oddi-working-hours-caption");
  const tabs = Array.from(document.querySelectorAll(".oddi-working-tabs [data-range]"));
  let range = "daily";
  let statsLoaded = false;
  let statsLoading = false;

  function formatCount(value) {
    return Math.max(0, Number(value) || 0).toLocaleString();
  }

  function formatDuration(seconds) {
    const minutes = Math.floor(Math.max(0, Number(seconds) || 0) / 60);
    if (!minutes) return "—";
    const hours = Math.floor(minutes / 60);
    const remaining = minutes % 60;
    if (hours >= 24) {
      const days = Math.floor(hours / 24);
      const restHours = hours % 24;
      return restHours ? `${days}d ${restHours}h` : `${days}d`;
    }
    return hours ? `${hours}h ${remaining}m` : `${minutes}m`;
  }

  function dateKeyFromTimestamp(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "" : localDateKey(date);
  }

  function streaks(timestamps) {
    const dates = [...new Set((Array.isArray(timestamps) ? timestamps : []).map(dateKeyFromTimestamp).filter(Boolean))].sort();
    if (!dates.length) return { best: 0, current: 0 };
    const toDay = key => {
      const [year, month, day] = key.split("-").map(Number);
      return Math.floor(Date.UTC(year, month - 1, day) / 86400000);
    };
    let best = 1;
    let chain = 1;
    for (let index = 1; index < dates.length; index += 1) {
      chain = toDay(dates[index]) - toDay(dates[index - 1]) === 1 ? chain + 1 : 1;
      best = Math.max(best, chain);
    }
    const today = localDateKey(new Date());
    let current = 0;
    let cursor = dates[dates.length - 1];
    const currentAge = toDay(today) - toDay(cursor);
    if (currentAge >= 0 && currentAge <= 1) {
      current = 1;
      while (true) {
        const [year, month, day] = cursor.split("-").map(Number);
        const previous = new Date(year, month - 1, day - 1);
        const previousKey = localDateKey(previous);
        if (!dates.includes(previousKey)) break;
        cursor = previousKey;
        current += 1;
      }
    }
    return { best, current };
  }

  function durationMap() {
    const source = readActivity();
    return Object.fromEntries(Object.entries(source).map(([key, value]) => [key, Math.max(0, Number(value) || 0)]));
  }

  function periods(activity, selectedRange) {
    const now = new Date();
    if (selectedRange === "monthly") {
      return Array.from({ length: 12 }, (_, offset) => {
        const date = new Date(now.getFullYear(), now.getMonth() - (11 - offset), 1);
        const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
        const minutes = Object.entries(activity).reduce((sum, [day, value]) => sum + (day.startsWith(`${key}-`) ? value : 0), 0);
        return { key, label: date.toLocaleDateString(undefined, { month: "short" }), minutes };
      });
    }
    if (selectedRange === "yearly") {
      return Array.from({ length: 5 }, (_, offset) => {
        const year = now.getFullYear() - (4 - offset);
        const minutes = Object.entries(activity).reduce((sum, [day, value]) => sum + (day.startsWith(`${year}-`) ? value : 0), 0);
        return { key: String(year), label: String(year), minutes };
      });
    }
    return Array.from({ length: 14 }, (_, offset) => {
      const date = new Date(now.getFullYear(), now.getMonth(), now.getDate() - (13 - offset));
      const key = localDateKey(date);
      return { key, label: date.toLocaleDateString(undefined, { month: "short", day: "numeric" }), minutes: Number(activity[key] || 0) };
    });
  }

  function renderChart() {
    if (!chart) return;
    const activity = durationMap();
    const data = periods(activity, range);
    const max = Math.max(1, ...data.map(item => item.minutes));
    const sum = data.reduce((value, item) => value + item.minutes, 0);
    const fragment = document.createDocumentFragment();
    const grid = document.createElement("div");
    grid.className = "oddi-chart-grid";
    fragment.appendChild(grid);
    data.forEach(item => {
      const column = document.createElement("div");
      column.className = "oddi-chart-column";
      const track = document.createElement("div");
      track.className = "oddi-chart-bar-track";
      const bar = document.createElement("span");
      bar.className = "oddi-chart-bar";
      const height = item.minutes ? Math.max(5, Math.round((item.minutes / max) * 140)) : 2;
      bar.style.height = `${height}px`;
      bar.title = `${item.label}: ${formatDuration(item.minutes * 60)}`;
      track.appendChild(bar);
      const label = document.createElement("span");
      label.className = "oddi-chart-label";
      label.textContent = item.label;
      column.append(track, label);
      fragment.appendChild(column);
    });
    if (!sum) {
      const empty = document.createElement("span");
      empty.className = "oddi-working-empty";
      empty.textContent = "No activity recorded yet";
      fragment.appendChild(empty);
    }
    chart.replaceChildren(fragment);
    if (total) total.textContent = formatDuration(sum * 60);
    if (caption) caption.textContent = range === "daily" ? "in the last 14 days" : range === "monthly" ? "in the last 12 months" : "in the last 5 years";
    chart.setAttribute("aria-label", `Working hours, ${range}: ${formatDuration(sum * 60)}`);
  }

  tabs.forEach(tab => tab.addEventListener("click", () => {
    range = String(tab.dataset.range || "daily");
    tabs.forEach(item => item.setAttribute("aria-selected", item === tab ? "true" : "false"));
    renderChart();
  }));
  window.addEventListener("oddi:working-hours-updated", renderChart);
  renderChart();

  const avatar = document.getElementById("oddi-profile-avatar");
  const nameNode = document.getElementById("oddi-profile-name");
  const handleNode = document.getElementById("oddi-profile-handle");
  const accountName = String(body?.dataset?.username || "ODDI user").trim();
  const accountEmail = String(body?.dataset?.email || "").trim();
  if (avatar) avatar.textContent = accountName.charAt(0).toUpperCase() || "U";
  if (nameNode) nameNode.textContent = accountName;
  if (handleNode) handleNode.textContent = `@${accountEmail.split("@")[0] || accountName.toLowerCase().replace(/\s+/g, "")}`;

  async function loadStats() {
    if (statsLoaded || statsLoading) return;
    statsLoading = true;
    try {
      const response = await fetch("/api/account/stats", { credentials: "same-origin", cache: "no-store", headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`Profile stats failed (${response.status})`);
      const data = await response.json();
      if (statNodes.lifetime) statNodes.lifetime.textContent = formatCount(data.lifetime_tokens);
      if (statNodes.peak) statNodes.peak.textContent = formatCount(data.peak_tokens);
      if (statNodes.task) statNodes.task.textContent = formatDuration(data.longest_task_seconds);
      const current = streaks(data.activity_timestamps);
      if (statNodes.bestStreak) statNodes.bestStreak.textContent = `${current.best} ${current.best === 1 ? "day" : "days"}`;
      if (statNodes.currentStreak) statNodes.currentStreak.textContent = `${current.current} ${current.current === 1 ? "day" : "days"}`;
      statsLoaded = true;
    } catch (_) {
      Object.values(statNodes).forEach(node => { if (node) node.textContent = "—"; });
    } finally {
      statsLoading = false;
    }
  }

  function openProfile() {
    if (!profileModal) return;
    profileModal.classList.add("show");
    profileModal.setAttribute("aria-hidden", "false");
    body.classList.add("oddi-profile-open");
    renderChart();
    loadStats();
    window.setTimeout(() => profileModal.querySelector("[data-profile-close]")?.focus(), 0);
  }

  function closeProfile() {
    if (!profileModal) return;
    profileModal.classList.remove("show");
    profileModal.setAttribute("aria-hidden", "true");
    body.classList.remove("oddi-profile-open");
    document.querySelector(".oddi-rs-profile-main")?.focus();
  }

  document.addEventListener("oddi:profile-open", openProfile);
  document.addEventListener("oddi:profile-close", closeProfile);
  profileModal?.addEventListener("click", event => {
    const target = event.target;
    if (target instanceof Element && target.closest("[data-profile-close], [data-profile-dismiss]")) closeProfile();
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && profileModal?.classList.contains("show")) closeProfile();
  });

  const params = new URLSearchParams(window.location.search);
  const openProfileFromUrl = params.get("openProfile") === "1";
  const openSettingsFromUrl = params.get("openSettings") === "1";
  if (openProfileFromUrl) params.delete("openProfile");
  if (openSettingsFromUrl) params.delete("openSettings");
  if (openProfileFromUrl || openSettingsFromUrl) {
    const query = params.toString();
    history.replaceState(null, "", `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`);
  }
  if (openProfileFromUrl) window.setTimeout(openProfile, 180);
  if (openSettingsFromUrl) window.setTimeout(() => document.getElementById("settingsBtn")?.click(), 180);
})();
