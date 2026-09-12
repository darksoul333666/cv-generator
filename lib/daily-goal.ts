import { listCvHistory } from "./api";

export const DAILY_GOAL_TARGET = 40;
export const DAILY_GOAL_HOURS = [8, 9, 12, 16] as const;

const ENABLED_KEY = "cvgen-daily-goal-enabled";
const LAST_ALERT_KEY = "cvgen-daily-goal-last-alert";

export type DailyGoalState = {
  enabled: boolean;
  target: number;
  done: number;
  remaining: number;
};

export function localDayKey(date = new Date()): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function isCreatedToday(iso: string, now = new Date()): boolean {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return false;
  return localDayKey(new Date(t)) === localDayKey(now);
}

export function goalFromCount(done: number, enabled: boolean): DailyGoalState {
  const target = DAILY_GOAL_TARGET;
  return {
    enabled,
    target,
    done,
    remaining: Math.max(0, target - done),
  };
}

export function goalAlertMessage(state: DailyGoalState): string {
  if (state.remaining <= 0) {
    return `Objetivo cumplido: ${state.done}/${state.target} CVs generados y postulados hoy.`;
  }
  return `Van ${state.done} de ${state.target}. Te quedan ${state.remaining} CVs por generar y postular.`;
}

export function readGoalEnabled(): boolean {
  if (typeof window === "undefined") return true;
  return window.localStorage.getItem(ENABLED_KEY) !== "0";
}

export function writeGoalEnabled(enabled: boolean): void {
  window.localStorage.setItem(ENABLED_KEY, enabled ? "1" : "0");
}

export function currentSlotAlertKey(now = new Date()): string | null {
  const hour = now.getHours() as (typeof DAILY_GOAL_HOURS)[number];
  if (!(DAILY_GOAL_HOURS as readonly number[]).includes(hour)) return null;
  return `${localDayKey(now)}-${hour}`;
}

export function readLastAlertKey(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(LAST_ALERT_KEY);
}

export function writeLastAlertKey(key: string): void {
  window.localStorage.setItem(LAST_ALERT_KEY, key);
}

export function msUntilNextSlot(now = new Date()): number {
  const t = now.getTime();
  for (const hour of DAILY_GOAL_HOURS) {
    const next = new Date(now);
    next.setHours(hour, 0, 0, 0);
    if (next.getTime() > t + 500) return next.getTime() - t;
  }
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);
  tomorrow.setHours(DAILY_GOAL_HOURS[0], 0, 0, 0);
  return Math.max(1000, tomorrow.getTime() - t);
}

export async function fetchTodayGoalState(enabled = readGoalEnabled()): Promise<DailyGoalState> {
  try {
    const { items } = await listCvHistory();
    const done = items.filter(
      (item) => isCreatedToday(item.created_at) && (item.status ?? "ready") === "ready",
    ).length;
    return goalFromCount(done, enabled);
  } catch {
    return goalFromCount(0, enabled);
  }
}
