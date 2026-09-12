"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { AppNav } from "./app-nav";
import {
  fetchTodayGoalState,
  goalAlertMessage,
  goalFromCount,
  currentSlotAlertKey,
  msUntilNextSlot,
  readGoalEnabled,
  readLastAlertKey,
  writeGoalEnabled,
  writeLastAlertKey,
  type DailyGoalState,
} from "@/lib/daily-goal";

type DailyGoalContextValue = {
  state: DailyGoalState;
  refresh: () => Promise<DailyGoalState>;
  toggle: () => Promise<void>;
  enableAlerts: () => Promise<void>;
  notifyPermission: NotificationPermission | "unsupported";
};

const DailyGoalContext = createContext<DailyGoalContextValue | null>(null);

export function useDailyGoal(): DailyGoalContextValue {
  const ctx = useContext(DailyGoalContext);
  if (!ctx) {
    throw new Error("useDailyGoal debe usarse dentro de DailyGoalRoot");
  }
  return ctx;
}

function notificationPermission(): NotificationPermission | "unsupported" {
  if (typeof window === "undefined" || typeof Notification === "undefined") {
    return "unsupported";
  }
  return Notification.permission;
}

function showDesktopAlert(body: string) {
  if (typeof Notification === "undefined") return;
  if (Notification.permission !== "granted") return;
  try {
    new Notification("Objetivo diario: 40 CVs", {
      body,
      tag: "cvgen-daily-goal",
    });
  } catch {
    /* Safari privado u origen no seguro */
  }
}

export function DailyGoalRoot({ children }: { children: ReactNode }) {
  const [state, setState] = useState<DailyGoalState>(() =>
    goalFromCount(0, true),
  );
  const [banner, setBanner] = useState<string | null>(null);
  const [notifyPermission, setNotifyPermission] = useState<
    NotificationPermission | "unsupported"
  >("default");

  const refresh = useCallback(async () => {
    const next = await fetchTodayGoalState(readGoalEnabled());
    setState(next);
    return next;
  }, []);

  const fireAlert = useCallback(async (forceKey?: string) => {
    if (!readGoalEnabled()) return;
    const key = forceKey ?? currentSlotAlertKey();
    if (!key || readLastAlertKey() === key) return;
    writeLastAlertKey(key);
    const next = await fetchTodayGoalState(true);
    setState(next);
    const message = goalAlertMessage(next);
    setBanner(message);
    showDesktopAlert(message);
  }, []);

  const toggle = useCallback(async () => {
    const enabled = !readGoalEnabled();
    writeGoalEnabled(enabled);
    if (enabled && typeof Notification !== "undefined" && Notification.permission === "default") {
      const perm = await Notification.requestPermission();
      setNotifyPermission(perm);
    }
    setState(await fetchTodayGoalState(enabled));
  }, []);

  const enableAlerts = useCallback(async () => {
    if (typeof Notification === "undefined") return;
    const perm = await Notification.requestPermission();
    setNotifyPermission(perm);
  }, []);

  useEffect(() => {
    setNotifyPermission(notificationPermission());
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const onFocus = () => {
      void refresh();
    };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onFocus);
    return () => {
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onFocus);
    };
  }, [refresh]);

  useEffect(() => {
    if (!state.enabled) return;
    let timeoutId = 0;
    const tick = () => {
      void fireAlert();
      timeoutId = window.setTimeout(tick, Math.min(msUntilNextSlot(), 30_000));
    };
    tick();
    return () => window.clearTimeout(timeoutId);
  }, [state.enabled, fireAlert]);

  useEffect(() => {
    if (!banner) return;
    const id = window.setTimeout(() => setBanner(null), 10_000);
    return () => window.clearTimeout(id);
  }, [banner]);

  const value = useMemo(
    () => ({ state, refresh, toggle, enableAlerts, notifyPermission }),
    [state, refresh, toggle, enableAlerts, notifyPermission],
  );

  return (
    <DailyGoalContext.Provider value={value}>
      <DailyGoalBar
        state={state}
        notifyPermission={notifyPermission}
        onToggle={() => void toggle()}
        onEnableAlerts={() => void enableAlerts()}
      />
      {banner ? (
        <div
          className="fixed right-4 top-16 z-50 max-w-sm rounded-xl border border-teal-800 bg-teal-900 px-4 py-3 text-sm font-medium text-white shadow-lg"
          role="status"
          aria-live="polite"
        >
          {banner}
        </div>
      ) : null}
      {children}
    </DailyGoalContext.Provider>
  );
}

function DailyGoalBar({
  state,
  notifyPermission,
  onToggle,
  onEnableAlerts,
}: {
  state: DailyGoalState;
  notifyPermission: NotificationPermission | "unsupported";
  onToggle: () => void;
  onEnableAlerts: () => void;
}) {
  const hoursLabel = "Avisos 8:00 a.m. · 9:00 a.m. · 12:00 p.m. · 4:00 p.m.";
  const pct = Math.min(100, Math.round((state.done / state.target) * 100));

  return (
    <div className="border-b border-zinc-200 bg-white">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-2">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-3">
          <AppNav />
          <button
            type="button"
            onClick={onToggle}
            aria-pressed={state.enabled}
            className={`rounded-full px-3 py-1.5 text-sm font-semibold ${
              state.enabled
                ? "bg-teal-800 text-white hover:bg-teal-700"
                : "bg-zinc-200 text-zinc-700 hover:bg-zinc-300"
            }`}
          >
            {state.enabled
              ? `Hoy ${state.done}/${state.target} · quedan ${state.remaining}`
              : "Activar objetivo 40/día"}
          </button>
          {state.enabled ? (
            <div
              className="h-1.5 w-36 overflow-hidden rounded-full bg-zinc-200"
              role="progressbar"
              aria-label={`Progreso del objetivo diario: ${state.done} de ${state.target}`}
              aria-valuemin={0}
              aria-valuemax={state.target}
              aria-valuenow={state.done}
            >
              <div
                className="h-full rounded-full bg-teal-700 transition-[width]"
                style={{ width: `${pct}%` }}
              />
            </div>
          ) : null}
          <p className="text-xs text-zinc-500">
            {state.enabled
              ? hoursLabel
              : "Pulsa para seguir 40 CVs al día"}
          </p>
        </div>
        {state.enabled && notifyPermission === "default" ? (
          <button
            type="button"
            onClick={onEnableAlerts}
            className="rounded-lg border border-zinc-300 bg-white px-3 py-1 text-xs font-medium text-zinc-800 hover:bg-zinc-100"
          >
            Permitir avisos del navegador
          </button>
        ) : null}
      </div>
    </div>
  );
}
