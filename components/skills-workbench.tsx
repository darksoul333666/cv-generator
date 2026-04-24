"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { listCvs, putTechSkills } from "@/lib/api";
import { emptyTechSkills, type CvProfile, type TechSkills } from "@/lib/cv-types";

type SkillKind = keyof TechSkills;

const LABELS: Record<SkillKind, string> = {
  front: "Front",
  back: "Back",
  ux: "UX",
  test: "Test",
};

function normalizeSkill(s: string): string {
  return s.trim().replace(/\s+/g, " ");
}

function uniqNormalized(items: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of items) {
    const n = normalizeSkill(raw);
    if (!n) continue;
    const key = n.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(n);
  }
  return out;
}

export function SkillsWorkbench() {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [cvs, setCvs] = useState<CvProfile[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");

  const selected = useMemo(
    () => cvs.find((c) => c.id === selectedId) ?? null,
    [cvs, selectedId],
  );

  const [draft, setDraft] = useState<TechSkills>(emptyTechSkills());
  const [inputs, setInputs] = useState<Record<SkillKind, string>>({
    front: "",
    back: "",
    ux: "",
    test: "",
  });

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listCvs()
      .then((data) => {
        if (cancelled) return;
        setCvs(data);
        const first = data[0]?.id ?? "";
        setSelectedId((prev) => prev || first);
      })
      .catch((e) => {
        if (cancelled) return;
        const msg = e instanceof Error ? e.message : "Error cargando perfiles";
        setError(
          msg === "Failed to fetch"
            ? "No se pudo conectar con el backend (http://127.0.0.1:8000). En la carpeta backend, ejecuta: uvicorn app.main:app --reload --port 8000"
            : msg,
        );
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selected) return;
    setDraft(selected.tech_skills ?? emptyTechSkills());
  }, [selected]);

  const addSkill = useCallback((kind: SkillKind) => {
    const raw = inputs[kind] ?? "";
    const next = normalizeSkill(raw);
    if (!next) return;
    setDraft((prev) => ({
      ...prev,
      [kind]: uniqNormalized([...(prev[kind] ?? []), next]),
    }));
    setInputs((p) => ({ ...p, [kind]: "" }));
  }, [inputs]);

  const removeSkill = useCallback((kind: SkillKind, value: string) => {
    setDraft((prev) => ({
      ...prev,
      [kind]: (prev[kind] ?? []).filter((x) => x !== value),
    }));
  }, []);

  const onSave = useCallback(async () => {
    if (!selected) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await putTechSkills(selected.id, {
        front: uniqNormalized(draft.front ?? []),
        back: uniqNormalized(draft.back ?? []),
        ux: uniqNormalized(draft.ux ?? []),
        test: uniqNormalized(draft.test ?? []),
      });
      setCvs((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error guardando skills");
    } finally {
      setSaving(false);
    }
  }, [draft, selected]);

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-4 py-10">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">
            Experiencia + skills técnicas
          </h1>
          <p className="max-w-2xl text-sm leading-relaxed text-zinc-600">
            Consume tus perfiles desde el backend (JSON en{" "}
            <code className="rounded bg-zinc-100 px-1">
              backend/knowledge_base
            </code>
            ) y permite editar/añadir skills por tipo.
          </p>
        </div>
        <Link
          href="/"
          className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-900 hover:bg-zinc-100"
        >
          Volver al generador
        </Link>
      </header>

      <section className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <label className="flex flex-1 flex-col gap-1.5 text-sm">
            <span className="font-medium text-zinc-800">Perfil</span>
            <select
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
              className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-zinc-900 outline-none ring-zinc-400 focus:ring-2"
              disabled={loading}
            >
              {cvs.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label || c.id}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={onSave}
            disabled={!selected || saving}
            className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-60"
          >
            {saving ? "Guardando…" : "Guardar skills"}
          </button>
        </div>

        {error ? (
          <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
            {error}
          </p>
        ) : null}

        {selected ? (
          <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <div className="rounded-xl border border-zinc-200 bg-zinc-50/80 p-5">
              <h2 className="text-base font-semibold text-zinc-900">
                Experiencia ({selected.experience.length})
              </h2>
              <div className="mt-3 space-y-4 text-sm">
                {selected.experience.map((ex, i) => (
                  <div key={i} className="rounded-lg border border-zinc-200 bg-white p-4">
                    <p className="font-medium text-zinc-900">
                      {ex.company} — {ex.role}
                    </p>
                    {ex.period ? (
                      <p className="mt-0.5 text-xs text-zinc-500">{ex.period}</p>
                    ) : null}
                    {ex.bullets?.length ? (
                      <ul className="mt-2 list-disc pl-5 text-sm text-zinc-700">
                        {ex.bullets.map((b, j) => (
                          <li key={j}>{b}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-xs text-zinc-500">Sin bullets.</p>
                    )}
                  </div>
                ))}
                {!selected.experience.length ? (
                  <p className="text-sm text-zinc-600">Este perfil no tiene experiencia cargada.</p>
                ) : null}
              </div>
            </div>

            <div className="rounded-xl border border-zinc-200 bg-white p-5">
              <h2 className="text-base font-semibold text-zinc-900">
                Skills técnicas (por tipo)
              </h2>
              <div className="mt-4 grid gap-4">
                {(Object.keys(LABELS) as SkillKind[]).map((kind) => (
                  <div key={kind} className="rounded-lg border border-zinc-200 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-medium text-zinc-900">
                        {LABELS[kind]}
                      </p>
                      <span className="text-xs text-zinc-500">
                        {(draft[kind] ?? []).length} items
                      </span>
                    </div>

                    <div className="mt-3 flex flex-wrap gap-2">
                      {(draft[kind] ?? []).map((s) => (
                        <button
                          key={s}
                          type="button"
                          onClick={() => removeSkill(kind, s)}
                          className="rounded-full border border-zinc-300 bg-zinc-50 px-2.5 py-1 text-xs text-zinc-800 hover:bg-zinc-100"
                          title="Quitar"
                        >
                          {s} <span className="text-zinc-500">×</span>
                        </button>
                      ))}
                      {(draft[kind] ?? []).length === 0 ? (
                        <p className="text-xs text-zinc-500">Aún no hay skills.</p>
                      ) : null}
                    </div>

                    <div className="mt-3 flex gap-2">
                      <input
                        value={inputs[kind] ?? ""}
                        onChange={(e) =>
                          setInputs((p) => ({ ...p, [kind]: e.target.value }))
                        }
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            addSkill(kind);
                          }
                        }}
                        placeholder="Ej: React, FastAPI, Figma, Playwright…"
                        className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm text-zinc-900 outline-none ring-zinc-400 focus:ring-2"
                      />
                      <button
                        type="button"
                        onClick={() => addSkill(kind)}
                        className="shrink-0 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm font-medium text-zinc-900 hover:bg-zinc-100"
                      >
                        Agregar
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : loading ? (
          <p className="mt-6 text-sm text-zinc-600">Cargando perfiles…</p>
        ) : (
          <p className="mt-6 text-sm text-zinc-600">No hay perfiles disponibles.</p>
        )}
      </section>
    </div>
  );
}

