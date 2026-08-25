/* global chrome */
(function () {
  "use strict";

  if (window.__cvGenUi) return;
  window.__cvGenUi = true;

  const BTN_ID = "cvgen-copy-host";

  function toast(host, message, ok) {
    const el = host.shadowRoot.getElementById("cvgen-toast");
    if (!el) return;
    el.textContent = message;
    el.dataset.ok = ok ? "1" : "0";
    el.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => {
      el.hidden = true;
    }, 2200);
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

  async function copyVacancy() {
    const api = window.__cvGen;
    if (!api) return { ok: false, message: "Extractor no cargado" };
    api.clickExpanders(api.descriptionRoot(document));
    await new Promise((r) => setTimeout(r, 180));
    const text = api.extractVacancy(document, location);
    if (!text || text.length < 60) {
      return { ok: false, message: "No se encontró la vacante" };
    }
    try {
      await copyText(text);
      return { ok: true, message: "Vacante copiada", chars: text.length };
    } catch {
      return { ok: false, message: "No se pudo copiar" };
    }
  }

  function mountButton() {
    if (document.getElementById(BTN_ID)) return;
    if (!document.body) return;

    const host = document.createElement("div");
    host.id = BTN_ID;
    host.style.cssText =
      "all:initial;position:fixed;z-index:2147483646;right:16px;top:16px;";
    const shadow = host.attachShadow({ mode: "open" });
    shadow.innerHTML = `
      <style>
        :host { all: initial; }
        #wrap { font-family: ui-sans-serif, system-ui, sans-serif; }
        button {
          appearance: none;
          border: 0;
          cursor: pointer;
          background: #18181b;
          color: #fafafa;
          font-size: 13px;
          font-weight: 600;
          letter-spacing: 0.01em;
          padding: 10px 14px;
          border-radius: 999px;
          box-shadow: 0 8px 24px rgba(0,0,0,.28);
        }
        button:hover { background: #27272a; }
        button:active { transform: translateY(1px); }
        #cvgen-toast {
          margin-top: 8px;
          text-align: right;
          font-size: 12px;
          font-weight: 600;
          padding: 6px 10px;
          border-radius: 8px;
          background: #18181b;
          color: #fafafa;
        }
        #cvgen-toast[data-ok="0"] { background: #7f1d1d; }
        #cvgen-toast[data-ok="1"] { background: #14532d; }
      </style>
      <div id="wrap">
        <button type="button" id="cvgen-btn">Copiar vacante</button>
        <div id="cvgen-toast" hidden></div>
      </div>
    `;
    shadow.getElementById("cvgen-btn").addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      const result = await copyVacancy();
      toast(host, result.message, result.ok);
    });
    document.body.appendChild(host);
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
    return Boolean(
      document.querySelector("#jobDescriptionText") ||
        document.querySelector(".jobsearch-JobComponent") ||
        document.querySelector("#job-details") ||
        document.querySelector(".jobs-description__content") ||
        document.querySelector('[data-test="jobDescriptionText"]') ||
        document.querySelector(".box_desc") ||
        /\/jobs\/view\//.test(location.pathname) ||
        /\/viewjob/.test(location.pathname + location.search)
    );
  }

  function syncButton() {
    const exists = document.getElementById(BTN_ID);
    if (jobPanePresent()) {
      if (!exists) mountButton();
    } else if (exists) {
      exists.remove();
    }
  }

  let syncTimer = 0;
  const observer = new MutationObserver(() => {
    clearTimeout(syncTimer);
    syncTimer = setTimeout(syncButton, 250);
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", syncButton, { once: true });
  } else {
    syncButton();
  }
})();
