import { existsSync } from "node:fs";

const MAC_CHROME = [
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
  "/Applications/Chromium.app/Contents/MacOS/Chromium",
];

const LINUX_CHROME = [
  "/usr/bin/google-chrome-stable",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium-browser",
  "/usr/bin/chromium",
];

const WIN_CHROME = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
];

export function resolveChromeExecutable(): string | undefined {
  const fromEnv = process.env.CHROME_PATH?.trim();
  if (fromEnv && existsSync(fromEnv)) return fromEnv;

  const candidates =
    process.platform === "darwin"
      ? MAC_CHROME
      : process.platform === "win32"
        ? WIN_CHROME
        : LINUX_CHROME;

  return candidates.find((p) => existsSync(p));
}

/** Cursor inyecta un cache sandbox vacío; Puppeteer no debe buscar Chrome ahí. */
export function clearSandboxPuppeteerCache(): void {
  const dir = process.env.PUPPETEER_CACHE_DIR || "";
  if (dir.includes("cursor-sandbox-cache")) {
    delete process.env.PUPPETEER_CACHE_DIR;
  }
}
