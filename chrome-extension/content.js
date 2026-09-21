/* global chrome */
(function () {
  "use strict";

  if (window.__cvGenUi) return;
  window.__cvGenUi = true;

  const BTN_ID = "cvgen-copy-host";
  let generating = false;

  function toast(host, message, ok, ms, onClick) {
    const el = host.shadowRoot.getElementById("cvgen-toast");
    if (!el) return;
    el.textContent = message;
    el.dataset.ok = ok ? "1" : "0";
    el.dataset.click = onClick ? "1" : "0";
    el.hidden = false;
    el.onclick = null;
    el.tabIndex = onClick ? 0 : -1;
    if (onClick) {
      el.setAttribute("aria-label", `${message}. Enter abre el historial`);
      el.onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        onClick();
      };
      el.focus();
    } else {
      el.removeAttribute("aria-label");
    }
    clearTimeout(toast._t);
    if (ms === 0) return;
    toast._t = setTimeout(() => {
      el.hidden = true;
      el.onclick = null;
      el.dataset.click = "0";
      el.removeAttribute("aria-label");
    }, ms == null ? 2200 : ms);
  }

  function copyText(text) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.cssText = "position:fixed;left:-9999px;top:0;opacity:0";
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch {
      ok = false;
    }
    ta.remove();
    if (ok) return Promise.resolve();
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return Promise.reject(new Error("clipboard"));
  }

  async function readVacancy() {
    const api = window.__cvGen;
    if (!api) return { ok: false, message: "Extractor no cargado", text: "" };
    api.clickExpanders(api.descriptionRoot(document));
    await new Promise((r) => setTimeout(r, 180));
    let text = api.extractVacancy(document, location);
    const site = api.siteFromHost(location.hostname);
    if ((site === "linkedin" || site === "occ") && text.length < 400) {
      await new Promise((r) => setTimeout(r, 700));
      api.clickExpanders(api.descriptionRoot(document));
      await new Promise((r) => setTimeout(r, 200));
      text = api.extractVacancy(document, location);
    }
    if (!text || text.length < 60) {
      return { ok: false, message: "No se encontró la vacante", text: "" };
    }
    return { ok: true, message: "Vacante lista", text };
  }

  async function copyVacancy() {
    const extracted = await readVacancy();
    if (!extracted.ok) return extracted;
    try {
      await copyText(extracted.text);
      return { ok: true, message: "Vacante copiada", chars: extracted.text.length };
    } catch {
      return { ok: false, message: "No se pudo copiar" };
    }
  }

  function setGenerateBusy(host, busy) {
    generating = busy;
    const wrap = host.shadowRoot.getElementById("wrap");
    const btn = host.shadowRoot.getElementById("cvgen-gen");
    if (wrap) wrap.setAttribute("aria-busy", busy ? "true" : "false");
    if (!btn) return;
    btn.disabled = busy;
    btn.textContent = busy ? "Añadiendo…" : "Generar CV";
  }

  function renderQueue(host, state) {
    const flushBtn = host.shadowRoot.getElementById("cvgen-flush");
    const retryBtn = host.shadowRoot.getElementById("cvgen-retry");
    if (!state) return;
    const queued = Number(state.queued) || 0;
    const generatingCount = Number(state.generating) || 0;
    const failed = Number(state.failed) || 0;
    const canFlush = Boolean(state.can_flush) && queued > 0;
    const canRetry = Boolean(state.can_retry_failed) && failed > 0 && generatingCount < 1;
    if (flushBtn) {
      flushBtn.hidden = queued < 1 && generatingCount < 1;
      flushBtn.disabled = !canFlush;
      if (generatingCount > 0) {
        flushBtn.textContent = `Generando ${generatingCount}…`;
      } else {
        flushBtn.textContent = queued ? `Generar lote (${queued})` : "Generar lote";
      }
    }
    if (retryBtn) {
      retryBtn.hidden = failed < 1;
      retryBtn.disabled = !canRetry;
      const take = Math.min(failed, Number(state.batchSize) || 5);
      retryBtn.textContent =
        failed > take
          ? `Reenviar lote (${take} de ${failed})`
          : failed > 0
            ? `Reenviar lote (${failed})`
            : "Reenviar lote";
    }
  }

  async function refreshQueue(host) {
    try {
      const state = await chrome.runtime.sendMessage({ type: "CVGEN_QUEUE_STATUS" });
      renderQueue(host, state);
    } catch {
      /* sin backend */
    }
  }

  function renderGoal(host, state) {
    const el = host.shadowRoot.getElementById("cvgen-goal");
    if (!el || !state) return;
    el.hidden = false;
    el.setAttribute("aria-pressed", state.enabled ? "true" : "false");
    if (!state.enabled) {
      el.dataset.on = "0";
      el.textContent = "Activar objetivo 40/día";
      return;
    }
    el.dataset.on = "1";
    el.textContent = `Hoy ${state.done}/${state.target} · quedan ${state.remaining}`;
  }

  async function refreshGoal(host) {
    try {
      const state = await chrome.runtime.sendMessage({ type: "CVGEN_GOAL_STATUS" });
      renderGoal(host, state);
    } catch {
      /* sin service worker aún */
    }
  }

  async function toggleGoal(host) {
    try {
      const state = await chrome.runtime.sendMessage({ type: "CVGEN_GOAL_TOGGLE" });
      renderGoal(host, state);
      toast(
        host,
        state.enabled
          ? `Objetivo diario activo: ${state.done}/${state.target}`
          : "Objetivo diario desactivado",
        true,
        2200,
      );
    } catch {
      toast(host, "No se pudo cambiar el objetivo", false);
    }
  }

  async function generateVacancy(host) {
    if (generating) return;
    const extracted = await readVacancy();
    if (!extracted.ok) {
      toast(host, extracted.message, false);
      return;
    }
    try {
      await copyText(extracted.text);
    } catch {
      /* el envío al API no depende del portapapeles */
    }
    setGenerateBusy(host, true);
    toast(host, "Encolando…", true, 0);
    try {
      const result = await chrome.runtime.sendMessage({
        type: "CVGEN_OPTIMIZE",
        vacancyText: extracted.text,
      });
      const ok = Boolean(result && result.ok);
      const savedId = result && result.savedId ? String(result.savedId) : "";
      if (result && result.goal) renderGoal(host, result.goal);
      else await refreshGoal(host);
      renderQueue(host, {
        queued: result && result.batchQueued,
        generating: result && result.batchGenerating,
        failed: result && result.failed,
        can_flush: Boolean(result && result.batchQueued > 0 && !result.batchGenerating),
        can_retry_failed: Boolean(result && result.failed > 0 && !result.batchGenerating),
      });
      await refreshQueue(host);
      toast(
        host,
        (result && result.message) || "Sin respuesta del backend",
        ok,
        ok ? 8000 : 4000,
        ok
          ? () => {
              chrome.runtime.sendMessage({
                type: "CVGEN_OPEN_HISTORIAL",
                savedId,
              });
            }
          : null,
      );
    } catch {
      toast(host, "Recarga la extensión e inténtalo de nuevo", false, 4000);
    } finally {
      setGenerateBusy(host, false);
    }
  }

  async function flushVacancyBatch(host) {
    const btn = host.shadowRoot.getElementById("cvgen-flush");
    if (btn) btn.disabled = true;
    toast(host, "Generando lote…", true, 0);
    try {
      const result = await chrome.runtime.sendMessage({ type: "CVGEN_FLUSH" });
      const ok = Boolean(result && result.ok);
      toast(
        host,
        (result && result.message) || "Sin respuesta del backend",
        ok,
        ok ? 8000 : 4000,
        ok
          ? () => {
              chrome.runtime.sendMessage({ type: "CVGEN_OPEN_HISTORIAL", savedId: "" });
            }
          : null,
      );
      await refreshQueue(host);
      await refreshGoal(host);
    } catch {
      toast(host, "Recarga la extensión e inténtalo de nuevo", false, 4000);
    }
  }

  async function retryFailedVacancyBatch(host) {
    const btn = host.shadowRoot.getElementById("cvgen-retry");
    if (btn) btn.disabled = true;
    toast(host, "Reenviando lote fallido…", true, 0);
    try {
      const result = await chrome.runtime.sendMessage({ type: "CVGEN_RETRY_FAILED" });
      const ok = Boolean(result && result.ok);
      toast(
        host,
        (result && result.message) || "Sin respuesta del backend",
        ok,
        ok ? 8000 : 4000,
        ok
          ? () => {
              chrome.runtime.sendMessage({ type: "CVGEN_OPEN_HISTORIAL", savedId: "" });
            }
          : null,
      );
      await refreshQueue(host);
      await refreshGoal(host);
    } catch {
      toast(host, "Recarga la extensión e inténtalo de nuevo", false, 4000);
    }
  }

  function mountButton() {
    if (document.getElementById(BTN_ID)) return;
    if (!document.body) return;

    const host = document.createElement("div");
    host.id = BTN_ID;
    host.style.cssText =
      "all:unset;position:fixed;z-index:2147483647;right:16px;top:72px;display:block;pointer-events:none;";
    const shadow = host.attachShadow({ mode: "open" });
    shadow.innerHTML = `
      <style>
        :host { all: initial; display: block; pointer-events: none; }
        #wrap {
          font-family: ui-sans-serif, system-ui, sans-serif;
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          gap: 8px;
          pointer-events: auto;
        }
        button {
          appearance: none;
          border: 0;
          cursor: pointer;
          color: #fafafa;
          font-size: 13px;
          font-weight: 600;
          letter-spacing: 0.01em;
          padding: 10px 14px;
          border-radius: 999px;
          box-shadow: 0 8px 24px rgba(0,0,0,.28);
        }
        #cvgen-btn { background: #18181b; }
        #cvgen-btn:hover { background: #27272a; }
        #cvgen-gen { background: #0f766e; }
        #cvgen-gen:hover { background: #0d9488; }
        #cvgen-flush { background: #b45309; }
        #cvgen-flush:hover { background: #d97706; }
        #cvgen-flush[hidden] { display: none; }
        #cvgen-retry { background: #9f1239; }
        #cvgen-retry:hover { background: #be123c; }
        #cvgen-retry[hidden] { display: none; }
        button:focus-visible {
          outline: 2px solid #5eead4;
          outline-offset: 2px;
        }
        button:active { transform: translateY(1px); }
        button:disabled {
          cursor: wait;
          opacity: 0.72;
          transform: none;
        }
        #cvgen-goal {
          background: #18181b;
          font-size: 12px;
          padding: 8px 12px;
        }
        #cvgen-goal[data-on="1"] { background: #134e4a; }
        #cvgen-goal[data-on="0"] { background: #3f3f46; }
        #cvgen-goal:hover { filter: brightness(1.08); }
        #cvgen-toast {
          text-align: right;
          font-size: 12px;
          font-weight: 600;
          padding: 6px 10px;
          border-radius: 8px;
          background: #18181b;
          color: #fafafa;
          max-width: 240px;
        }
        #cvgen-toast[data-ok="0"] { background: #7f1d1d; }
        #cvgen-toast[data-ok="1"] { background: #14532d; }
        #cvgen-toast[data-click="1"] {
          cursor: pointer;
          text-decoration: underline;
          text-underline-offset: 2px;
        }
        #cvgen-toast[data-click="1"]:hover { background: #166534; }
        #cvgen-toast:focus-visible {
          outline: 2px solid #5eead4;
          outline-offset: 2px;
        }
      </style>
      <div id="wrap" role="region" aria-label="CV Generator">
        <button type="button" id="cvgen-btn" aria-label="Copiar vacante">Copiar vacante</button>
        <button type="button" id="cvgen-gen" aria-label="Añadir vacante al lote">Generar CV</button>
        <button type="button" id="cvgen-flush" hidden disabled>Generar lote</button>
        <button type="button" id="cvgen-retry" hidden disabled>Reenviar lote</button>
        <button type="button" id="cvgen-goal" hidden aria-pressed="false">Hoy 0/40</button>
        <button type="button" id="cvgen-toast" hidden></button>
      </div>
    `;
    shadow.getElementById("cvgen-btn").addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      const result = await copyVacancy();
      toast(host, result.message, result.ok);
    });
    shadow.getElementById("cvgen-gen").addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      await generateVacancy(host);
    });
    shadow.getElementById("cvgen-flush").addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      await flushVacancyBatch(host);
    });
    shadow.getElementById("cvgen-retry").addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      await retryFailedVacancyBatch(host);
    });
    shadow.getElementById("cvgen-goal").addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      await toggleGoal(host);
    });
    (document.documentElement || document.body).appendChild(host);
    refreshGoal(host);
    refreshQueue(host);
    host._cvgenPoll = setInterval(() => {
      refreshQueue(host);
    }, 4000);
  }

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (!msg || msg.type !== "CVGEN_COPY") return;
    copyVacancy().then((result) => {
      const host = document.getElementById(BTN_ID);
      if (host && host.shadowRoot) toast(host, result.message, result.ok);
      sendResponse(result);
    });
    return true;
  });

  function jobPanePresent() {
    const host = (location.hostname || "").replace(/^www\./, "").toLowerCase();
    const path = location.pathname || "";
    const search = location.search || "";
    if (host === "occ.com.mx" || host.endsWith(".occ.com.mx")) {
      return (
        /\/empleo\/oferta\//.test(path) ||
        /\/empleos\//.test(path) ||
        /[?&]jobid=/.test(search) ||
        Boolean(
          document.querySelector("#job-detail-container") ||
            document.querySelector("[data-offers-grid-detail-container]") ||
            document.querySelector("[data-offers-grid-detail-title]") ||
            document.querySelector("[data-offers-grid-offer-item-container]"),
        )
      );
    }
    if (
      /\/jobs(\/|$)/.test(path) ||
      /\/empleos\/[^/]+\/[^/?#]+/.test(path) ||
      /[?&]currentJobId=/.test(search) ||
      /[?&]jobid=/.test(search) ||
      /\/empleo\/oferta\//.test(path) ||
      /\/viewjob/.test(path + search) ||
      /[?&](?:jk|vjk)=/.test(search)
    ) {
      return true;
    }
    return Boolean(
      document.querySelector("#jobDescriptionText") ||
        document.querySelector(".jobsearch-JobComponent") ||
        document.querySelector("#jobsearch-ViewjobPaneWrapper") ||
        document.querySelector("#job-details") ||
        document.querySelector("#job-body") ||
        document.querySelector("#job-detail-container") ||
        document.querySelector("[data-offers-grid-detail-container]") ||
        document.querySelector("h1.gb-landing-cover__title") ||
        document.querySelector(".jobs-description__content") ||
        document.querySelector(".jobs-description") ||
        document.querySelector(".jobs-details") ||
        document.querySelector(".jobs-search__job-details") ||
        document.querySelector(".job-view-layout") ||
        document.querySelector(".job-details-jobs-unified-top-card") ||
        document.querySelector('[id^="JobDetails_AboutTheJob_"]') ||
        document.querySelector('[data-test="jobDescriptionText"]') ||
        document.querySelector(".box_desc") ||
        document.body?.classList?.contains("jobs-show")
    );
  }

  function syncButton() {
    const exists = document.getElementById(BTN_ID);
    if (jobPanePresent()) {
      if (!exists || !exists.isConnected) {
        if (exists) exists.remove();
        mountButton();
      }
    } else if (exists) {
      if (exists._cvgenPoll) clearInterval(exists._cvgenPoll);
      exists.remove();
    }
  }

  let syncTimer = 0;
  const observer = new MutationObserver(() => {
    clearTimeout(syncTimer);
    syncTimer = setTimeout(syncButton, 250);
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });

  const wrapHistory = (fn) =>
    function historyHook() {
      const ret = fn.apply(this, arguments);
      setTimeout(syncButton, 50);
      return ret;
    };
  try {
    history.pushState = wrapHistory(history.pushState.bind(history));
    history.replaceState = wrapHistory(history.replaceState.bind(history));
  } catch {
    /* ignore */
  }
  window.addEventListener("popstate", () => setTimeout(syncButton, 50));

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", syncButton, { once: true });
  } else {
    syncButton();
  }
})();
