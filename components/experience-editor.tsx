"use client";

import type { AchievementDraft, ExperienceDraft } from "@/lib/profile-draft";
import { newProfileId } from "@/lib/profile-draft";
import { CollapseRow, Field, SectionCard, TextButton, fieldClass } from "@/components/profile-form";
import { useState } from "react";

const EMPLOYMENT_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "", label: "Sin definir" },
  { value: "full-time", label: "Empleo fijo" },
  { value: "freelance", label: "Freelance" },
  { value: "contract", label: "Contrato" },
  { value: "remote", label: "Remoto" },
  { value: "onsite", label: "Presencial" },
];

function blankExperience(): ExperienceDraft {
  return {
    id: newProfileId("exp"),
    company: "",
    rolesText: "",
    employmentType: "",
    startDate: "",
    endDate: "",
    current: false,
    responsibilitiesText: "",
    technologiesText: "",
    achievements: [],
  };
}

function blankAchievement(): AchievementDraft {
  return { description: "", metricValue: "", metricUnit: "" };
}

type Props = {
  items: ExperienceDraft[];
  onChange: (items: ExperienceDraft[]) => void;
};

function jobMeta(row: ExperienceDraft): string {
  const role = row.rolesText.split("\n").map((line) => line.trim()).find(Boolean) ?? "";
  const end = row.current ? "Actualidad" : row.endDate;
  const dates = [row.startDate, end].filter(Boolean).join(" – ");
  return [role, dates].filter(Boolean).join(" · ");
}

export function ExperienceEditor({ items, onChange }: Props) {
  const [freshId, setFreshId] = useState<string | null>(null);
  const patch = (id: string, partial: Partial<ExperienceDraft>) => {
    onChange(items.map((row) => (row.id === id ? { ...row, ...partial } : row)));
  };

  const move = (index: number, dir: -1 | 1) => {
    const next = index + dir;
    if (next < 0 || next >= items.length) return;
    const copy = [...items];
    const tmp = copy[index];
    copy[index] = copy[next];
    copy[next] = tmp;
    onChange(copy);
  };

  return (
    <SectionCard
      title={`Experiencia (${items.length})`}
      summary={items.map((row) => row.company.trim()).filter(Boolean).slice(0, 4).join(" · ") || "Sin empleos"}
      hint="Empresa, roles, fechas, responsabilidades y logros. El generador solo usa empresas que estén aquí. Una línea por rol, responsabilidad o tecnología."
      action={
        <TextButton
          onClick={() => {
            const row = blankExperience();
            setFreshId(row.id);
            onChange([row, ...items]);
          }}
        >
          Agregar empleo
        </TextButton>
      }
    >
      <div className="space-y-4">
        {items.length === 0 ? (
          <p className="text-sm text-zinc-500">Todavía no hay empleos.</p>
        ) : null}
        {items.map((row, index) => (
          <CollapseRow
            key={row.id}
            defaultOpen={row.id === freshId}
            title={`${index + 1}. ${row.company.trim() || "Nuevo empleo"}`}
            meta={jobMeta(row)}
            actions={
              <>
                <TextButton onClick={() => move(index, -1)} disabled={index === 0}>
                  Subir
                </TextButton>
                <TextButton onClick={() => move(index, 1)} disabled={index === items.length - 1}>
                  Bajar
                </TextButton>
                <TextButton onClick={() => onChange(items.filter((item) => item.id !== row.id))}>
                  Quitar
                </TextButton>
              </>
            }
          >
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <Field label="Empresa">
                <input
                  value={row.company}
                  onChange={(e) => patch(row.id, { company: e.target.value })}
                  className={fieldClass}
                />
              </Field>
              <Field label="Tipo de empleo">
                <select
                  value={row.employmentType}
                  onChange={(e) => patch(row.id, { employmentType: e.target.value })}
                  className={fieldClass}
                >
                  {EMPLOYMENT_OPTIONS.map((opt) => (
                    <option key={opt.value || "none"} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Inicio (YYYY o YYYY-MM)">
                <input
                  value={row.startDate}
                  placeholder="2024-01"
                  onChange={(e) => patch(row.id, { startDate: e.target.value })}
                  className={fieldClass}
                />
              </Field>
              <Field label="Fin (YYYY o YYYY-MM)">
                <input
                  value={row.endDate}
                  placeholder="2025-06"
                  disabled={row.current}
                  onChange={(e) => patch(row.id, { endDate: e.target.value })}
                  className={`${fieldClass} disabled:bg-zinc-100 disabled:text-zinc-400`}
                />
              </Field>
            </div>
            <label className="mt-3 flex items-center gap-2 text-xs text-zinc-700">
              <input
                type="checkbox"
                checked={row.current}
                onChange={(e) =>
                  patch(row.id, {
                    current: e.target.checked,
                    endDate: e.target.checked ? "" : row.endDate,
                  })
                }
              />
              Trabajo actual
            </label>

            <div className="mt-3 grid gap-3">
              <Field label="Roles (uno por línea)">
                <textarea
                  value={row.rolesText}
                  rows={3}
                  onChange={(e) => patch(row.id, { rolesText: e.target.value })}
                  className={fieldClass}
                />
              </Field>
              <Field label="Responsabilidades (una por línea)">
                <textarea
                  value={row.responsibilitiesText}
                  rows={4}
                  onChange={(e) => patch(row.id, { responsibilitiesText: e.target.value })}
                  className={fieldClass}
                />
              </Field>
              <Field label="Tecnologías (una por línea)">
                <textarea
                  value={row.technologiesText}
                  rows={3}
                  onChange={(e) => patch(row.id, { technologiesText: e.target.value })}
                  className={fieldClass}
                />
              </Field>
            </div>

            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs font-medium text-zinc-700">Logros y métricas</p>
                <TextButton
                  onClick={() =>
                    patch(row.id, { achievements: [...row.achievements, blankAchievement()] })
                  }
                >
                  Agregar logro
                </TextButton>
              </div>
              {row.achievements.map((ach, achIndex) => (
                <div key={`${row.id}-ach-${achIndex}`} className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_6rem_6rem_auto]">
                  <input
                    value={ach.description}
                    aria-label={`Descripción del logro ${achIndex + 1}`}
                    placeholder="Qué lograste"
                    onChange={(e) => {
                      const achievements = row.achievements.map((item, i) =>
                        i === achIndex ? { ...item, description: e.target.value } : item,
                      );
                      patch(row.id, { achievements });
                    }}
                    className={fieldClass}
                  />
                  <input
                    value={ach.metricValue}
                    aria-label={`Valor del logro ${achIndex + 1}`}
                    placeholder="Valor"
                    inputMode="decimal"
                    onChange={(e) => {
                      const achievements = row.achievements.map((item, i) =>
                        i === achIndex ? { ...item, metricValue: e.target.value } : item,
                      );
                      patch(row.id, { achievements });
                    }}
                    className={fieldClass}
                  />
                  <input
                    value={ach.metricUnit}
                    aria-label={`Unidad del logro ${achIndex + 1}`}
                    placeholder="percent"
                    onChange={(e) => {
                      const achievements = row.achievements.map((item, i) =>
                        i === achIndex ? { ...item, metricUnit: e.target.value } : item,
                      );
                      patch(row.id, { achievements });
                    }}
                    className={fieldClass}
                  />
                  <TextButton
                    onClick={() =>
                      patch(row.id, {
                        achievements: row.achievements.filter((_, i) => i !== achIndex),
                      })
                    }
                  >
                    Quitar
                  </TextButton>
                </div>
              ))}
            </div>
          </CollapseRow>
        ))}
      </div>
    </SectionCard>
  );
}
