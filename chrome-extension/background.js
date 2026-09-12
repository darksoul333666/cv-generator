/* global chrome */

const API_BASE = "http://127.0.0.1:8000";
const APP_BASE = "http://localhost:3000";
const GOAL_TARGET = 40;
const GOAL_SLOTS = [
  { name: "cvgen-goal-08", hour: 8, minute: 0 },
  { name: "cvgen-goal-09", hour: 9, minute: 0 },
  { name: "cvgen-goal-12", hour: 12, minute: 0 },
  { name: "cvgen-goal-16", hour: 16, minute: 0 },
];

chrome.runtime.onInstalled.addListener(() => {
  scheduleGoalAlarms();
});
chrome.runtime.onStartup.addListener(() => {
  scheduleGoalAlarms();
});
scheduleGoalAlarms();

chrome.action.onClicked.addListener(async (tab) => {
  if (!tab?.id || !tab.url || !/^https?:/i.test(tab.url)) return;

  const ping = async () => {
    try {
      return await chrome.tabs.sendMessage(tab.id, { type: "CVGEN_COPY" });
    } catch {
      return null;
    }
  };

  let result = await ping();
  if (!result) {
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ["extract.js", "content.js"],
      });
      result = await ping();
    } catch (e) {
      console.error("cv-generator: no se pudo inyectar el extractor", e);
    }
  }

  showBadge(tab.id, Boolean(result?.ok));
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (!msg) return;
  if (msg.type === "CVGEN_OPEN_HISTORIAL") {
    openHistorial(msg.savedId || "")
      .then(() => sendResponse({ ok: true }))
      .catch(() => sendResponse({ ok: false }));
    return true;
  }
  if (msg.type === "CVGEN_GOAL_STATUS") {
    getGoalState()
      .then(sendResponse)
      .catch(() => sendResponse(defaultGoalState()));
    return true;
  }
  if (msg.type === "CVGEN_GOAL_TOGGLE") {
    toggleDailyGoal()
      .then(sendResponse)
      .catch(() => sendResponse(defaultGoalState()));
    return true;
  }
  if (msg.type === "CVGEN_FLUSH") {
    flushBatch()
      .then(sendResponse)
      .catch((err) => {
        sendResponse({
          ok: false,
          message: err instanceof Error ? err.message : "No se pudo generar el lote",
        });
      });
    return true;
  }
  if (msg.type === "CVGEN_QUEUE_STATUS") {
    getQueueStatus()
      .then(sendResponse)
      .catch(() => sendResponse({ ok: false, queued: 0, generating: 0, can_flush: false }));
    return true;
  }
  if (msg.type !== "CVGEN_OPTIMIZE") return;
  enqueueVacancy(msg.vacancyText || "")
    .then(sendResponse)
    .catch((err) => {
      sendResponse({
        ok: false,
        message: err instanceof Error ? err.message : "No se pudo generar el CV",
      });
    });
  return true;
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (!alarm?.name || !alarm.name.startsWith("cvgen-goal-")) return;
  await notifyGoalProgress();
  await scheduleGoalAlarms();
});

chrome.notifications.onClicked.addListener((id) => {
  if (id !== "cvgen-goal") return;
  openHistorial("");
});

function showBadge(tabId, ok) {
  chrome.action.setBadgeText({ tabId, text: ok ? "OK" : "!" });
  chrome.action.setBadgeBackgroundColor({
    tabId,
    color: ok ? "#14532d" : "#7f1d1d",
  });
  setTimeout(() => {
    chrome.action.setBadgeText({ tabId, text: "" });
  }, 2000);
}

function apiErrorDetail(payload, fallback) {
  if (!payload || typeof payload !== "object") return fallback;
  const d = payload.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => JSON.stringify(x)).join("; ");
  if (d != null) return String(d);
  return fallback;
}

function localDayKey(date = new Date()) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function startOfLocalDay() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

function defaultGoalState() {
  return {
    enabled: true,
    target: GOAL_TARGET,
    done: 0,
    remaining: GOAL_TARGET,
  };
}

async function readStore() {
  return chrome.storage.local.get({
    dailyGoalEnabled: true,
    localDay: "",
    localCount: 0,
  });
}

async function localCountToday() {
  const store = await readStore();
  const today = localDayKey();
  if (store.localDay !== today) return 0;
  return Number(store.localCount) || 0;
}

async function bumpLocalCount() {
  const today = localDayKey();
  const store = await readStore();
  const prev = store.localDay === today ? Number(store.localCount) || 0 : 0;
  await chrome.storage.local.set({ localDay: today, localCount: prev + 1 });
}

async function countHistoryToday() {
  try {
    const res = await fetch(`${API_BASE}/v1/history`, {
      method: "GET",
      credentials: "omit",
    });
    if (!res.ok) return null;
    const payload = await res.json().catch(() => ({}));
    const items = Array.isArray(payload.items) ? payload.items : [];
    const start = startOfLocalDay().getTime();
    return items.filter((item) => {
      const t = Date.parse(item && item.created_at);
      const ready = !item.status || item.status === "ready";
      return Number.isFinite(t) && t >= start && ready;
    }).length;
  } catch {
    return null;
  }
}

async function getGoalState() {
  const store = await readStore();
  const historyCount = await countHistoryToday();
  const local = await localCountToday();
  const done =
    historyCount == null ? local : Math.max(historyCount, local);
  const target = GOAL_TARGET;
  const remaining = Math.max(0, target - done);
  return {
    enabled: store.dailyGoalEnabled !== false,
    target,
    done,
    remaining,
  };
}

async function toggleDailyGoal() {
  const store = await readStore();
  const enabled = store.dailyGoalEnabled === false;
  await chrome.storage.local.set({ dailyGoalEnabled: enabled });
  if (enabled) await scheduleGoalAlarms();
  return getGoalState();
}

function nextOccurrence(hour, minute) {
  const when = new Date();
  when.setHours(hour, minute, 0, 0);
  if (when.getTime() <= Date.now() + 15_000) {
    when.setDate(when.getDate() + 1);
  }
  return when.getTime();
}

async function scheduleGoalAlarms() {
  for (const slot of GOAL_SLOTS) {
    await chrome.alarms.create(slot.name, {
      when: nextOccurrence(slot.hour, slot.minute),
    });
  }
}

function goalMessage(state) {
  if (state.remaining <= 0) {
    return `Objetivo cumplido: ${state.done}/${state.target} CVs generados y postulados hoy.`;
  }
  return `Van ${state.done} de ${state.target}. Te quedan ${state.remaining} CVs por generar y postular.`;
}

async function notifyGoalProgress() {
  const state = await getGoalState();
  if (!state.enabled) return;
  await chrome.notifications.create("cvgen-goal", {
    type: "basic",
    iconUrl: "icon48.png",
    title: "Objetivo diario: 40 CVs",
    message: goalMessage(state),
    priority: 2,
  });
}

async function enqueueVacancy(vacancyText) {
  const text = String(vacancyText || "").trim();
  if (text.length < 60) {
    return { ok: false, message: "No se encontró la vacante" };
  }

  let res;
  try {
    res = await fetch(`${API_BASE}/v1/queue`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "omit",
      body: JSON.stringify({ vacancy_text: text }),
    });
  } catch {
    return {
      ok: false,
      message: "No hay conexión con el backend (:8000)",
    };
  }

  const payload = await res.json().catch(() => ({}));
  if (!res.ok) {
    return {
      ok: false,
      message: apiErrorDetail(payload, `Error ${res.status}`),
    };
  }

  const goal = await getGoalState();
  const jobId = payload && payload.id ? String(payload.id) : "";
  const queued = Number(payload && payload.queued);
  const generating = Number(payload && payload.generating);
  return {
    ok: true,
    queued: true,
    message: (payload && payload.message) || "En lote",
    savedId: jobId,
    pending: Number(payload && payload.pending) || 0,
    position: Number(payload && payload.position) || 0,
    batchQueued: Number.isFinite(queued) ? queued : Number(payload && payload.pending) || 0,
    batchGenerating: Number.isFinite(generating) ? generating : 0,
    batchSize: Number(payload && payload.batch_size) || 5,
    goal,
  };
}

async function getQueueStatus() {
  try {
    const res = await fetch(`${API_BASE}/v1/queue/status`, {
      method: "GET",
      credentials: "omit",
    });
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) {
      return { ok: false, queued: 0, generating: 0, can_flush: false, message: "" };
    }
    return {
      ok: true,
      queued: Number(payload.queued) || 0,
      generating: Number(payload.generating) || 0,
      can_flush: Boolean(payload.can_flush),
      batchSize: Number(payload.batch_size) || 5,
      message: payload.message || "",
    };
  } catch {
    return { ok: false, queued: 0, generating: 0, can_flush: false, message: "" };
  }
}

async function flushBatch() {
  let res;
  try {
    res = await fetch(`${API_BASE}/v1/queue/flush`, {
      method: "POST",
      credentials: "omit",
    });
  } catch {
    return { ok: false, message: "No hay conexión con el backend (:8000)" };
  }
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) {
    return { ok: false, message: apiErrorDetail(payload, `Error ${res.status}`) };
  }
  return {
    ok: true,
    message: payload.message || "Generando lote…",
    started: Number(payload.started) || 0,
    queued: Number(payload.queued) || 0,
    generating: Number(payload.generating) || 0,
  };
}

async function openHistorial(savedId) {
  const url = savedId
    ? `${APP_BASE}/historial?id=${encodeURIComponent(savedId)}`
    : `${APP_BASE}/historial`;
  try {
    const existing = await chrome.tabs.query({ url: `${APP_BASE}/*` });
    if (existing[0]?.id) {
      await chrome.tabs.update(existing[0].id, { url, active: true });
      return;
    }
  } catch {
    /* crear pestaña nueva */
  }
  await chrome.tabs.create({ url });
}
