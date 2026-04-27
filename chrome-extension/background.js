/* global chrome */
const API = "http://127.0.0.1:8000/v1/extension/optimize";

chrome.action.onClicked.addListener(async (tab) => {
  if (!tab?.id || !tab.url?.startsWith("http")) {
    return;
  }
  let vacancyText = "";
  try {
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => document.body?.innerText?.slice(0, 120_000) || "",
    });
    vacancyText = result || "";
  } catch (e) {
    console.error("cv-generator extension: no se pudo leer la página", e);
    return;
  }

  let sourceSite = "web";
  try {
    const host = new URL(tab.url).hostname.replace(/^www\./, "");
    sourceSite = host.split(".")[0] || "web";
  } catch {
    /* ignore */
  }

  const payload = {
    vacancy_text: vacancyText,
    vacancy_title: tab.title || null,
    source_site: sourceSite,
  };

  try {
    const res = await fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await res.text();
    if (!res.ok) {
      console.error("cv-generator extension:", res.status, body);
      return;
    }
    console.info("cv-generator extension: CV guardado en caché", body.slice(0, 200));
  } catch (e) {
    console.error("cv-generator extension: ¿está el backend en :8000?", e);
  }
});
