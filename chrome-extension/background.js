/* global chrome */

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

  if (result?.ok) {
    chrome.action.setBadgeText({ tabId: tab.id, text: "OK" });
    chrome.action.setBadgeBackgroundColor({ tabId: tab.id, color: "#14532d" });
  } else {
    chrome.action.setBadgeText({ tabId: tab.id, text: "!" });
    chrome.action.setBadgeBackgroundColor({ tabId: tab.id, color: "#7f1d1d" });
  }
  setTimeout(() => {
    chrome.action.setBadgeText({ tabId: tab.id, text: "" });
  }, 2000);
});
