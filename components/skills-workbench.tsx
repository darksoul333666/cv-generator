"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { ExperienceEditor } from "@/components/experience-editor";
import {
  getMasterProfile,
  putMasterPatch,
  putMasterValidation,
  type ExperiencePatchItem,
} from "@/lib/api";
import {
  emptyMasterSkills,
  MASTER_SKILL_KINDS,
  type MasterProfile,
  type MasterSkillKind,
  type MasterSkills,
} from "@/lib/cv-types";
import { validateMasterProfile } from "@/lib/master-profile.schema";
import { contactFieldDisplay } from "@/lib/master-profile-utils";

const LABELS: Record<MasterSkillKind, string> = {
  languages: "Lenguajes",
  frontend: "Frontend",
  backend: "Backend",
  mobile: "Mobile",
  databases: "Bases de datos",
  cloud: "Cloud",
  devops: "DevOps",
  testing: "Testing",
  architecture: "Arquitectura",
  payments: "Pagos",
  security: "Security",
  ai: "AI",
  softSkills: "Soft skills",
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

function normalizeMasterSkills(skills: MasterSkills | undefined): MasterSkills {
  const empty = emptyMasterSkills();
  if (!skills) return empty;
  const next = { ...empty };
  for (const kind of MASTER_SKILL_KINDS) {
    next[kind] = uniqNormalized(skills[kind] ?? []);
  }
  return next;
}

const IMPACT_CLASS: Record<string, string> = {
  critical: "bg-red-100 text-red-800",
  high: "bg-amber-100 text-amber-900",
  medium: "bg-zinc-100 text-zinc-700",
  low: "bg-zinc-50 text-zinc-500",
};

export function SkillsWorkbench() {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [profile, setProfile] = useState<MasterProfile | null>(null);
  const [schemaErrors, setSchemaErrors] = useState<string[]>([]);
  const [draft, setDraft] = useState<MasterSkills>(emptyMasterSkills());
  const [inputs, setInputs] = useState<Record<MasterSkillKind, string>>(
    () =>
      Object.fromEntries(MASTER_SKILL_KINDS.map((k) => [k, ""])) as Record<
        MasterSkillKind,
        string
      >,
  );
  const experienceDraftRef = useRef<ExperiencePatchItem[] | null>(null);

  const onExperienceDraftChange = useCallback((items: ExperiencePatchItem[]) => {
    experienceDraftRef.current = items;
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getMasterProfile()
      .then((data) => {
        if (cancelled) return;
        setProfile(data);
        const checked = validateMasterProfile(data);
        setSchemaErrors(checked.ok ? [] : checked.errors);
        setDraft(normalizeMasterSkills(data.skills));
      })
      .catch((e) => {
        if (cancelled) return;
        const msg = e instanceof Error ? e.message : "Error cargando perfil maestro";
        setError(
          msg === "Failed to fetch"
            ? "No se pudo conectar con el backend (http://127.0.0.1:8000)."
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

  const addSkill = useCallback(
    (kind: MasterSkillKind) => {
      const raw = inputs[kind] ?? "";
      const next = normalizeSkill(raw);
      if (!next) return;
      setDraft((prev) => ({
        ...prev,
        [kind]: uniqNormalized([...(prev[kind] ?? []), next]),
      }));
      setInputs((p) => ({ ...p, [kind]: "" }));
    },
    [inputs],
  );

  const removeSkill = useCallback((kind: MasterSkillKind, value: string) => {
    setDraft((prev) => ({
      ...prev,
      [kind]: (prev[kind] ?? []).filter((x) => x !== value),
    }));
  }, []);

  const onSave = useCallback(async () => {
    setSaving(true);
    setError(null);
    try {
      const updated = await putMasterPatch({
        skills: normalizeMasterSkills(draft),
        experience: experienceDraftRef.current ?? undefined,
      });
      setProfile(updated);
      const checked = validateMasterProfile(updated);
      setSchemaErrors(checked.ok ? [] : checked.errors);
      setDraft(normalizeMasterSkills(updated.skills));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error guardando skills");
    } finally {
      setSaving(false);
    }
  }, [draft]);

  const onResolve = useCallback(async (field: string, resolvedValue: string) => {
    setSaving(true);
    setError(null);
    try {
      const updated = await putMasterValidation({ field, resolvedValue });
      setProfile(updated);
      const checked = validateMasterProfile(updated);
      setSchemaErrors(checked.ok ? [] : checked.errors);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error guardando validación");
    } finally {
      setSaving(false);
    }
  }, []);

  const conflicts = (profile?.conflicts ?? []).filter((c) => !c.userValidated);
  const contact = profile?.profile.contact;

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 py-10">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">
            Skills
          </h1>
          <p className="max-w-2xl text-sm leading-relaxed text-zinc-600">
            Edita experiencia y skills del perfil que usa Ollama para generar el CV.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onSave}
            disabled={!profile || saving}
            className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-60"
          >
            {saving ? "Guardando…" : "Guardar cambios"}
          </button>
          <Link
            href="/"
            className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-900 hover:bg-zinc-100"
          >
            Volver al generador
          </Link>
        </div>
      </header>

      {error ? (
        <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
          {error}
        </p>
      ) : null}

      {loading && !profile ? (
        <p className="text-sm text-zinc-600">Cargando perfil maestro…</p>
      ) : null}

      {profile ? (
        <>
          <section className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
            <p className="text-lg font-semibold text-zinc-900">
              {profile.profile.fullName}
            </p>
            <p className="mt-1 text-sm text-zinc-600">
              {profile.profile.professionalTitles.join(" · ")}
            </p>
            <p className="mt-3 text-sm leading-relaxed text-zinc-700">
              {profile.profile.summary}
            </p>
            <p className="mt-3 text-xs text-zinc-500">
              {contact
                ? [
                    contactFieldDisplay(contact.email),
                    contactFieldDisplay(contact.phone),
                    contactFieldDisplay(contact.linkedin),
                    contactFieldDisplay(contact.location),
                  ].join(" · ")
                : null}
            </p>
            {profile.yearsOfExperience ? (
              <p className="mt-2 text-xs text-amber-800">
                Años de experiencia:{" "}
                {profile.yearsOfExperience.value ?? "sin calcular"} ·{" "}
                {profile.yearsOfExperience.status}
                {profile.yearsOfExperience.sourceValues?.length
                  ? ` · candidatos: ${profile.yearsOfExperience.sourceValues.join(", ")}`
                  : ""}
              </p>
            ) : null}
          </section>

          {schemaErrors.length ? (
            <section className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">
              <p className="font-medium">El JSON maestro no pasó validación Zod</p>
              <ul className="mt-2 list-disc pl-5 text-xs">
                {schemaErrors.slice(0, 12).map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
            </section>
          ) : null}

          {conflicts.length ? (
            <section className="rounded-xl border border-amber-200 bg-amber-50 p-6">
              <h2 className="text-base font-semibold text-amber-950">
                Conflictos por validar ({conflicts.length})
              </h2>
              <ul className="mt-3 space-y-2 text-sm text-amber-950">
                {conflicts.map((c) => (
                  <li key={c.id || c.field} className="rounded-lg border border-amber-200 bg-white/70 p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium">{c.field}</p>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                          IMPACT_CLASS[c.impact] ?? IMPACT_CLASS.medium
                        }`}
                      >
                        {c.impact}
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {c.values.map((v) => (
                        <button
                          key={v}
                          type="button"
                          disabled={saving}
                          onClick={() => onResolve(c.field, v)}
                          className="rounded-full border border-amber-300 bg-white px-2.5 py-1 text-xs hover:bg-amber-100 disabled:opacity-50"
                          title="Validar este valor"
                        >
                          Usar: {v}
                        </button>
                      ))}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
            <ExperienceEditor
              profile={profile}
              onDraftChange={onExperienceDraftChange}
              onError={setError}
              onSaved={(updated) => {
                setProfile(updated);
                const checked = validateMasterProfile(updated);
                setSchemaErrors(checked.ok ? [] : checked.errors);
              }}
            />

            <div className="rounded-xl border border-zinc-200 bg-white p-5">
              <h2 className="text-base font-semibold text-zinc-900">
                Skills del JSON maestro
              </h2>
              <div className="mt-4 grid gap-4">
                {MASTER_SKILL_KINDS.map((kind) => (
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
                        placeholder={`Agregar a ${LABELS[kind]}…`}
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
          </section>
        </>
      ) : null}
    </div>
  );
}
