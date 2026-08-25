"use client";

import { useEffect, useMemo, useState } from "react";
import { putMasterExperience, type ExperiencePatchItem } from "@/lib/api";
import type { Experience, MasterProfile } from "@/lib/master-profile";
import { validateMasterProfile } from "@/lib/master-profile.schema";

const EMPLOYMENT_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "", label: "Sin definir" },
  { value: "full-time", label: "Empleo fijo" },
  { value: "freelance", label: "Freelance" },
  { value: "contract", label: "Contrato" },
  { value: "remote", label: "Remoto" },
  { value: "onsite", label: "Presencial" },
];

type DraftItem = {
  id: string;
  startDate: string;
  endDate: string;
  current: boolean;
  employmentType: string;
};

function toMonthInput(value: string | null | undefined): string {
  if (!value) return "";
  if (/^\d{4}-\d{2}$/.test(value)) return value;
  if (/^\d{4}$/.test(value)) return `${value}-01`;
  return "";
}

function fromExperience(ex: Experience): DraftItem {
  return {
    id: ex.id,
    startDate: toMonthInput(ex.startDate),
    endDate: toMonthInput(ex.endDate),
    current: Boolean(ex.current),
    employmentType: ex.employmentType ?? "",
  };
}

function experienceSignature(list: Experience[]): string {
  return JSON.stringify(
    list.map((ex) => ({
      id: ex.id,
      startDate: ex.startDate,
      endDate: ex.endDate,
      current: Boolean(ex.current),
      employmentType: ex.employmentType ?? "",
      sortOrder: ex.sortOrder ?? null,
    })),
  );
}

function toPatchItems(
  order: string[],
  draft: Record<string, DraftItem>,
): ExperiencePatchItem[] {
  return order.map((id) => {
    const row = draft[id];
    return {
      id,
      startDate: row.startDate || null,
      endDate: row.current ? null : row.endDate || null,
      current: row.current,
      employmentType: row.employmentType || null,
    };
  });
}

function sourceHint(ex: Experience): string | null {
  const src = ex.sourceValues;
  if (!src || typeof src !== "object") return null;
  const start = Array.isArray(src.startDate) ? src.startDate.join(" / ") : null;
  const ranges = Array.isArray(src.ranges) ? src.ranges.join(" / ") : null;
  if (ranges) return `Candidatos: ${ranges}`;
  if (start) return `Inicio en fuentes: ${start}`;
  return null;
}

type Props = {
  profile: MasterProfile;
  onSaved: (next: MasterProfile) => void;
  onError: (message: string | null) => void;
  onDraftChange?: (items: ExperiencePatchItem[]) => void;
};

export function ExperienceEditor({ profile, onSaved, onError, onDraftChange }: Props) {
  const [order, setOrder] = useState<string[]>(() =>
    profile.experience.map((ex) => ex.id),
  );
  const [draft, setDraft] = useState<Record<string, DraftItem>>(() =>
    Object.fromEntries(profile.experience.map((ex) => [ex.id, fromExperience(ex)])),
  );
  const [saving, setSaving] = useState(false);

  const serverSig = experienceSignature(profile.experience);

  useEffect(() => {
    setOrder(profile.experience.map((ex) => ex.id));
    setDraft(
      Object.fromEntries(profile.experience.map((ex) => [ex.id, fromExperience(ex)])),
    );
    // Solo resincroniza si cambian fechas/orden/tipo en servidor, no al guardar skills.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverSig]);

  useEffect(() => {
    onDraftChange?.(toPatchItems(order, draft));
  }, [order, draft, onDraftChange]);

  const byId = useMemo(
    () => Object.fromEntries(profile.experience.map((ex) => [ex.id, ex])),
    [profile.experience],
  );

  const move = (index: number, dir: -1 | 1) => {
    const next = index + dir;
    if (next < 0 || next >= order.length) return;
    setOrder((prev) => {
      const copy = [...prev];
      const tmp = copy[index];
      copy[index] = copy[next];
      copy[next] = tmp;
      return copy;
    });
  };

  const patch = (id: string, partial: Partial<DraftItem>) => {
    setDraft((prev) => ({ ...prev, [id]: { ...prev[id], ...partial } }));
  };

  const onSave = async () => {
    setSaving(true);
    onError(null);
    try {
      const items = toPatchItems(order, draft);
      const updated = await putMasterExperience(items);
      const checked = validateMasterProfile(updated);
      if (!checked.ok) {
        onError(checked.errors.slice(0, 4).join(" · "));
      }
      onSaved(updated);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Error guardando experiencia");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-xl border border-zinc-200 bg-zinc-50/80 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-zinc-900">
            Experiencia ({order.length})
          </h2>
          <p className="mt-0.5 text-xs text-zinc-500">
            Reordena, ajusta fechas y marca empleo fijo o freelance. El historial
            original no se borra.
          </p>
        </div>
        <button
          type="button"
          onClick={onSave}
          disabled={saving}
          className="rounded-lg bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
        >
          {saving ? "Guardando…" : "Guardar experiencia"}
        </button>
      </div>

      <div className="mt-3 space-y-3 text-sm">
        {order.map((id, index) => {
          const ex = byId[id];
          const row = draft[id];
          if (!ex || !row) return null;
          return (
            <div key={id} className="rounded-lg border border-zinc-200 bg-white p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium text-zinc-900">
                    {index + 1}. {ex.company}
                  </p>
                  <p className="mt-0.5 text-xs text-zinc-600">
                    {ex.roles.join(" / ")}
                  </p>
                </div>
                <div className="flex shrink-0 gap-1">
                  <button
                    type="button"
                    onClick={() => move(index, -1)}
                    disabled={index === 0}
                    className="rounded border border-zinc-300 px-2 py-1 text-xs hover:bg-zinc-50 disabled:opacity-40"
                    title="Subir"
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    onClick={() => move(index, 1)}
                    disabled={index === order.length - 1}
                    className="rounded border border-zinc-300 px-2 py-1 text-xs hover:bg-zinc-50 disabled:opacity-40"
                    title="Bajar"
                  >
                    ↓
                  </button>
                </div>
              </div>

              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <label className="flex flex-col gap-1 text-xs">
                  <span className="font-medium text-zinc-700">Tipo de empleo</span>
                  <select
                    value={row.employmentType}
                    onChange={(e) => patch(id, { employmentType: e.target.value })}
                    className="rounded-lg border border-zinc-300 bg-white px-2 py-1.5 text-sm text-zinc-900 outline-none ring-zinc-400 focus:ring-2"
                  >
                    {EMPLOYMENT_OPTIONS.map((opt) => (
                      <option key={opt.value || "none"} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex items-center gap-2 pt-5 text-xs text-zinc-700">
                  <input
                    type="checkbox"
                    checked={row.current}
                    onChange={(e) =>
                      patch(id, {
                        current: e.target.checked,
                        endDate: e.target.checked ? "" : row.endDate,
                      })
                    }
                  />
                  Trabajo actual (fin = Actualidad)
                </label>
                <label className="flex flex-col gap-1 text-xs">
                  <span className="font-medium text-zinc-700">Inicio</span>
                  <input
                    type="month"
                    value={row.startDate}
                    onChange={(e) => patch(id, { startDate: e.target.value })}
                    className="rounded-lg border border-zinc-300 px-2 py-1.5 text-sm text-zinc-900 outline-none ring-zinc-400 focus:ring-2"
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs">
                  <span className="font-medium text-zinc-700">Fin</span>
                  <input
                    type="month"
                    value={row.endDate}
                    disabled={row.current}
                    onChange={(e) => patch(id, { endDate: e.target.value })}
                    className="rounded-lg border border-zinc-300 px-2 py-1.5 text-sm text-zinc-900 outline-none ring-zinc-400 focus:ring-2 disabled:bg-zinc-100 disabled:text-zinc-400"
                  />
                </label>
              </div>

              {sourceHint(ex) ? (
                <p className="mt-2 text-xs text-amber-800">{sourceHint(ex)}</p>
              ) : null}
              {ex.dateStatus === "conflicted" || ex.conflicts.length ? (
                <p className="mt-1 text-[11px] text-amber-700">
                  Hay conflicto de fechas en las fuentes. Al guardar, tu valor queda
                  como canónico.
                </p>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
