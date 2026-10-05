"use client";

import { useCallback, useEffect, useState } from "react";
import { ExperienceEditor } from "@/components/experience-editor";
import { SectionCard } from "@/components/profile-form";
import { ProfilePreview } from "@/components/profile-preview";
import {
  CertificationEditor,
  EducationEditor,
  IdentityEditor,
  LanguageEditor,
  ProjectEditor,
} from "@/components/profile-record-editors";
import { getMasterProfile, putMasterPatch, putMasterValidation } from "@/lib/api";
import {
  emptyMasterSkills,
  MASTER_SKILL_KINDS,
  type MasterProfile,
  type MasterSkillKind,
  type MasterSkills,
} from "@/lib/cv-types";
import { validateMasterProfile } from "@/lib/master-profile.schema";
import {
  certificationFromProfile,
  contentFromDrafts,
  educationFromProfile,
  experienceFromProfile,
  identityFromProfile,
  languageFromProfile,
  projectFromProfile,
  type CertificationDraft,
  type EducationDraft,
  type ExperienceDraft,
  type IdentityDraft,
  type LanguageDraft,
  type ProjectDraft,
} from "@/lib/profile-draft";

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

const EMPTY_IDENTITY: IdentityDraft = {
  fullName: "",
  titlesText: "",
  summary: "",
  email: "",
  phone: "",
  linkedin: "",
  location: "",
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
  const [mode, setMode] = useState<"edit" | "preview">("edit");
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
  const [identity, setIdentity] = useState<IdentityDraft>(EMPTY_IDENTITY);
  const [experience, setExperience] = useState<ExperienceDraft[]>([]);
  const [projects, setProjects] = useState<ProjectDraft[]>([]);
  const [education, setEducation] = useState<EducationDraft[]>([]);
  const [certifications, setCertifications] = useState<CertificationDraft[]>([]);
  const [languages, setLanguages] = useState<LanguageDraft[]>([]);

  const applyLoaded = useCallback((data: MasterProfile) => {
    setProfile(data);
    const checked = validateMasterProfile(data);
    setSchemaErrors(checked.ok ? [] : checked.errors);
    setDraft(normalizeMasterSkills(data.skills));
    setIdentity(identityFromProfile(data));
    setExperience((data.experience ?? []).map(experienceFromProfile));
    setProjects((data.projects ?? []).map(projectFromProfile));
    setEducation((data.education ?? []).map(educationFromProfile));
    setCertifications((data.certifications ?? []).map(certificationFromProfile));
    setLanguages((data.languages ?? []).map(languageFromProfile));
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getMasterProfile()
      .then((data) => {
        if (cancelled) return;
        applyLoaded(data);
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
  }, [applyLoaded]);

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
      const content = contentFromDrafts({
        identity,
        experience,
        projects,
        education,
        certifications,
        languages,
      });
      const updated = await putMasterPatch({
        skills: normalizeMasterSkills(draft),
        content,
      });
      applyLoaded(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error guardando el perfil");
    } finally {
      setSaving(false);
    }
  }, [
    applyLoaded,
    certifications,
    draft,
    education,
    experience,
    identity,
    languages,
    projects,
  ]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== "s") return;
      event.preventDefault();
      if (!profile || saving) return;
      void onSave();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onSave, profile, saving]);

  const onResolve = useCallback(
    async (field: string, resolvedValue: string) => {
      setSaving(true);
      setError(null);
      try {
        const updated = await putMasterValidation({ field, resolvedValue });
        setProfile(updated);
        const checked = validateMasterProfile(updated);
        setSchemaErrors(checked.ok ? [] : checked.errors);
        if (field === "profile.contact.email") {
          setIdentity((prev) => ({ ...prev, email: resolvedValue }));
        } else if (field === "profile.contact.phone") {
          setIdentity((prev) => ({ ...prev, phone: resolvedValue }));
        } else if (field === "profile.contact.location") {
          setIdentity((prev) => ({ ...prev, location: resolvedValue }));
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Error guardando validación");
      } finally {
        setSaving(false);
      }
    },
    [],
  );

  const conflicts = (profile?.conflicts ?? []).filter((c) => !c.userValidated);

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-4 py-10">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">Skills</h1>
          <p className="max-w-2xl text-sm leading-relaxed text-zinc-600">
            Edita el perfil maestro: identidad, experiencia, proyectos, educación,
            certificaciones, idiomas y skills. Eso es lo que usa el generador.
            Ctrl + S (o ⌘ S) guarda en master_profile.json.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg border border-zinc-300 bg-white p-0.5">
            <button
              type="button"
              aria-pressed={mode === "edit"}
              onClick={() => setMode("edit")}
              className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                mode === "edit" ? "bg-zinc-900 text-white" : "text-zinc-700 hover:bg-zinc-100"
              }`}
            >
              Editar
            </button>
            <button
              type="button"
              aria-pressed={mode === "preview"}
              onClick={() => setMode("preview")}
              className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                mode === "preview" ? "bg-zinc-900 text-white" : "text-zinc-700 hover:bg-zinc-100"
              }`}
            >
              Vista previa
            </button>
          </div>
          <button
            type="button"
            onClick={onSave}
            disabled={!profile || saving}
            aria-keyshortcuts="Control+s"
            className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-60"
          >
            {saving ? "Guardando…" : "Guardar cambios"}
          </button>
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
                      {c.values.map((v, vi) => (
                        <button
                          key={v}
                          type="button"
                          disabled={saving}
                          autoFocus={conflicts[0] === c && vi === 0}
                          onClick={() => onResolve(c.field, v)}
                          className="rounded-full border border-amber-300 bg-white px-2.5 py-1 text-xs hover:bg-amber-100 disabled:opacity-50"
                          aria-label={`Usar ${v} para ${c.field}`}
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

          {mode === "preview" ? (
            <ProfilePreview
              identity={identity}
              experience={experience}
              projects={projects}
              education={education}
              certifications={certifications}
              languages={languages}
              skills={draft}
            />
          ) : (
            <>
          <IdentityEditor value={identity} onChange={setIdentity} />
          <ExperienceEditor items={experience} onChange={setExperience} />
          <ProjectEditor items={projects} onChange={setProjects} />
          <div className="grid gap-6 lg:grid-cols-2">
            <EducationEditor items={education} onChange={setEducation} />
            <CertificationEditor items={certifications} onChange={setCertifications} />
          </div>
          <LanguageEditor items={languages} onChange={setLanguages} />

          <SectionCard
            title={`Skills (${MASTER_SKILL_KINDS.reduce((sum, kind) => sum + (draft[kind]?.length ?? 0), 0)})`}
            summary={MASTER_SKILL_KINDS.flatMap((kind) => draft[kind] ?? []).slice(0, 8).join(" · ") || "Sin skills"}
          >
            <div className="grid gap-4 md:grid-cols-2">
              {MASTER_SKILL_KINDS.map((kind) => (
                <div key={kind} className="rounded-lg border border-zinc-200 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium text-zinc-900">{LABELS[kind]}</p>
                    <span className="text-xs text-zinc-500">{(draft[kind] ?? []).length} items</span>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {(draft[kind] ?? []).map((s) => (
                      <button
                        key={s}
                        type="button"
                        onClick={() => removeSkill(kind, s)}
                        className="rounded-full border border-zinc-300 bg-zinc-50 px-2.5 py-1 text-xs text-zinc-800 hover:bg-zinc-100"
                        aria-label={`Quitar ${s} de ${LABELS[kind]}`}
                      >
                        {s} <span aria-hidden className="text-zinc-500">×</span>
                      </button>
                    ))}
                    {(draft[kind] ?? []).length === 0 ? (
                      <p className="text-xs text-zinc-500">Aún no hay skills.</p>
                    ) : null}
                  </div>
                  <div className="mt-3 flex gap-2">
                    <input
                      value={inputs[kind] ?? ""}
                      aria-label={`Agregar skill a ${LABELS[kind]}`}
                      onChange={(e) => setInputs((p) => ({ ...p, [kind]: e.target.value }))}
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
          </SectionCard>
            </>
          )}
        </>
      ) : null}
    </div>
  );
}
