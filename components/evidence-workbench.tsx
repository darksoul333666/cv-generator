"use client";

import { useCallback, useEffect, useState } from "react";
import { getEvidenceGaps, putEvidence, type EvidenceGap, type EvidenceInput } from "@/lib/api";

const inputClass =
  "rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm text-zinc-900 outline-none ring-zinc-400 focus:ring-2";

function lines(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function commaList(text: string): string[] {
  return text
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function str(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function gapKey(gap: EvidenceGap): string {
  return `${gap.experienceId}:${gap.kind}:${gap.achievementIndex ?? ""}`;
}

type Draft = Record<string, string | boolean>;

function initialDraft(gap: EvidenceGap): Draft {
  const current = gap.current ?? {};
  if (gap.kind === "achievement") {
    return {
      action: str(current.action),
      measurement: str(current.measurement),
      context: str(current.context),
      technologies: Array.isArray(current.technologies) ? current.technologies.join(", ") : "",
      before: "",
      after: "",
    };
  }
  if (gap.kind === "scope") {
    return {
      teamSize: current.teamSize != null ? String(current.teamSize) : "",
      highlights: Array.isArray(current.highlights) ? current.highlights.join("\n") : "",
    };
  }
  return { role: "", responsibilities: "", technologies: "", showInCv: false };
}

function payload(gap: EvidenceGap, draft: Draft): EvidenceInput {
  const base = { experienceId: gap.experienceId };
  if (gap.kind === "achievement") {
    return {
      ...base,
      achievementIndex: gap.achievementIndex ?? null,
      action: String(draft.action || ""),
      measurement: String(draft.measurement || ""),
      context: String(draft.context || ""),
      technologies: commaList(String(draft.technologies || "")),
      before: String(draft.before || ""),
      after: String(draft.after || ""),
    };
  }
  if (gap.kind === "scope") {
    return {
      ...base,
      teamSize: String(draft.teamSize || ""),
      highlights: lines(String(draft.highlights || "")),
    };
  }
  return {
    ...base,
    roles: lines(String(draft.role || "")),
    responsibilities: lines(String(draft.responsibilities || "")),
    technologies: commaList(String(draft.technologies || "")),
    showInCv: Boolean(draft.showInCv),
  };
}

function Field({
  label,
  hint,
  value,
  onChange,
  multiline = false,
}: {
  label: string;
  hint?: string;
  value: string;
  onChange: (value: string) => void;
  multiline?: boolean;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</span>
      {multiline ? (
        <textarea rows={3} value={value} onChange={(e) => onChange(e.target.value)} className={inputClass} />
      ) : (
        <input type="text" value={value} onChange={(e) => onChange(e.target.value)} className={inputClass} />
      )}
      {hint ? <span className="text-[11px] text-zinc-500">{hint}</span> : null}
    </label>
  );
}

function GapCard({ gap, onSaved }: { gap: EvidenceGap; onSaved: (gaps: EvidenceGap[]) => void }) {
  const [draft, setDraft] = useState<Draft>(() => initialDraft(gap));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (key: string) => (value: string | boolean) => setDraft((prev) => ({ ...prev, [key]: value }));

  const onSave = async () => {
    setSaving(true);
    setError(null);
    try {
      onSaved(await putEvidence(payload(gap, draft)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar");
    } finally {
      setSaving(false);
    }
  };

  return (
    <article className="space-y-3 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
      <header className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
          {gap.company}
          {gap.metric ? ` · ${gap.metric}` : ""}
        </p>
        <h2 className="text-sm font-medium text-zinc-900">{gap.question}</h2>
      </header>

      {gap.kind === "achievement" ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Field
              label="¿Qué hiciste? (el cómo)"
              hint="Técnica o cambio concreto: p. ej. caché en Redis, paginación, índices en la base de datos."
              value={String(draft.action)}
              onChange={set("action")}
              multiline
            />
          </div>
          <Field
            label="¿Cómo se midió?"
            hint="Herramienta o fuente: DevTools, Sentry, logs, story points…"
            value={String(draft.measurement)}
            onChange={set("measurement")}
          />
          <Field label="Contexto (opcional)" hint="Qué era, para quién, tamaño." value={String(draft.context)} onChange={set("context")} />
          <Field label="Antes (opcional)" hint="Ej. 800 ms o 8 s" value={String(draft.before)} onChange={set("before")} />
          <Field label="Después (opcional)" hint="Ej. 300 ms o 3 s" value={String(draft.after)} onChange={set("after")} />
          <div className="sm:col-span-2">
            <Field
              label="Herramientas (opcional)"
              hint="Separadas por coma."
              value={String(draft.technologies)}
              onChange={set("technologies")}
            />
          </div>
        </div>
      ) : gap.kind === "scope" ? (
        <div className="grid gap-3">
          <Field label="Tamaño del equipo" hint="Número o rango, p. ej. 4 o 6–8." value={String(draft.teamSize)} onChange={set("teamSize")} />
          <Field
            label="Qué demuestra el cargo"
            hint="Una línea por punto: responsabilidad, liderazgo, decisiones, mentoría. Solo lo que realmente hiciste."
            value={String(draft.highlights)}
            onChange={set("highlights")}
            multiline
          />
        </div>
      ) : (
        <div className="grid gap-3">
          <Field label="Cargo" value={String(draft.role)} onChange={set("role")} />
          <Field
            label="Qué hiciste"
            hint="Una línea por actividad."
            value={String(draft.responsibilities)}
            onChange={set("responsibilities")}
            multiline
          />
          <Field label="Tecnologías" hint="Separadas por coma." value={String(draft.technologies)} onChange={set("technologies")} />
          <label className="flex items-center gap-2 text-sm text-zinc-700">
            <input
              type="checkbox"
              checked={Boolean(draft.showInCv)}
              onChange={(e) => set("showInCv")(e.target.checked)}
              className="h-4 w-4 accent-zinc-900"
            />
            Mostrar en CVs
          </label>
        </div>
      )}

      {error ? <p className="text-sm text-red-700">{error}</p> : null}
      <button
        type="button"
        onClick={() => void onSave()}
        disabled={saving}
        className="rounded-lg bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
      >
        {saving ? "Guardando…" : "Guardar"}
      </button>
    </article>
  );
}

export function EvidenceWorkbench() {
  const [gaps, setGaps] = useState<EvidenceGap[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getEvidenceGaps()
      .then((next) => {
        if (!cancelled) setGaps(next);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "No se pudo cargar la evidencia");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const onSaved = useCallback((next: EvidenceGap[]) => {
    setGaps(next);
    setSaved((n) => n + 1);
  }, []);

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-10">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">Evidencia</h1>
        <p className="text-sm leading-relaxed text-zinc-600">
          Tus CVs solo pueden argumentar lo que está aquí. Cada cifra necesita qué hiciste y cómo se
          midió; cada cargo, el tamaño del equipo y qué demuestra. Si algo no lo sabes, déjalo vacío:
          el generador no lo inventa.
        </p>
        {saved > 0 ? (
          <p className="text-sm text-teal-800">Guardado. Regenera tus CVs en Historial para ver el cambio.</p>
        ) : null}
      </header>

      {error ? (
        <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
          {error}
        </p>
      ) : null}

      {gaps === null ? (
        <p className="text-sm text-zinc-500">Cargando…</p>
      ) : gaps.length === 0 ? (
        <p className="rounded-xl border border-teal-200 bg-teal-50 px-4 py-6 text-sm text-teal-900">
          No falta evidencia: todas tus cifras tienen su cómo y todos tus cargos su alcance.
        </p>
      ) : (
        <>
          <p className="text-sm text-zinc-700">
            {gaps.length} pendiente{gaps.length === 1 ? "" : "s"}
          </p>
          {gaps.map((gap) => (
            <GapCard key={gapKey(gap)} gap={gap} onSaved={onSaved} />
          ))}
        </>
      )}
    </div>
  );
}
