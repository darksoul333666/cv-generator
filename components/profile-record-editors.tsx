"use client";

import type {
  CertificationDraft,
  EducationDraft,
  IdentityDraft,
  LanguageDraft,
  ProjectDraft,
} from "@/lib/profile-draft";
import { newProfileId } from "@/lib/profile-draft";
import { CollapseRow, Field, SectionCard, TextButton, fieldClass } from "@/components/profile-form";

type IdentityProps = {
  value: IdentityDraft;
  onChange: (value: IdentityDraft) => void;
};

export function IdentityEditor({ value, onChange }: IdentityProps) {
  const patch = (partial: Partial<IdentityDraft>) => onChange({ ...value, ...partial });
  return (
    <SectionCard
      title="Identidad y contacto"
      summary={[value.fullName, value.email].filter(Boolean).join(" · ") || "Sin nombre"}
      hint="Este nombre, estos títulos y este contacto son los que salen en el CV. Un título profesional por línea."
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Nombre completo">
          <input
            value={value.fullName}
            onChange={(e) => patch({ fullName: e.target.value })}
            className={fieldClass}
          />
        </Field>
        <Field label="Email">
          <input
            value={value.email}
            onChange={(e) => patch({ email: e.target.value })}
            className={fieldClass}
          />
        </Field>
        <Field label="Teléfono">
          <input
            value={value.phone}
            onChange={(e) => patch({ phone: e.target.value })}
            className={fieldClass}
          />
        </Field>
        <Field label="LinkedIn">
          <input
            value={value.linkedin}
            onChange={(e) => patch({ linkedin: e.target.value })}
            className={fieldClass}
          />
        </Field>
        <Field label="Ubicación">
          <input
            value={value.location}
            onChange={(e) => patch({ location: e.target.value })}
            className={fieldClass}
          />
        </Field>
        <div className="sm:col-span-2">
          <Field label="Títulos profesionales (uno por línea)">
            <textarea
              value={value.titlesText}
              rows={4}
              onChange={(e) => patch({ titlesText: e.target.value })}
              className={fieldClass}
            />
          </Field>
        </div>
        <div className="sm:col-span-2">
          <Field label="Resumen base">
            <textarea
              value={value.summary}
              rows={5}
              onChange={(e) => patch({ summary: e.target.value })}
              className={fieldClass}
            />
          </Field>
        </div>
      </div>
    </SectionCard>
  );
}

type ListProps<T> = {
  items: T[];
  onChange: (items: T[]) => void;
};

export function ProjectEditor({ items, onChange }: ListProps<ProjectDraft>) {
  const patch = (id: string, partial: Partial<ProjectDraft>) => {
    onChange(items.map((row) => (row.id === id ? { ...row, ...partial } : row)));
  };
  return (
    <SectionCard
      title={`Proyectos (${items.length})`}
      summary={items.map((row) => row.name.trim()).filter(Boolean).slice(0, 3).join(" · ") || "Sin proyectos"}
      hint="No son empleos. Si los dejas, el generador puede mencionarlos. Quita los que no sean tuyos."
      action={
        <TextButton
          onClick={() =>
            onChange([
              ...items,
              {
                id: newProfileId("project"),
                name: "",
                type: "",
                description: "",
                technologiesText: "",
              },
            ])
          }
        >
          Agregar proyecto
        </TextButton>
      }
    >
      <div className="space-y-4">
        {items.length === 0 ? <p className="text-sm text-zinc-500">Sin proyectos.</p> : null}
        {items.map((row) => (
          <CollapseRow
            key={row.id}
            title={row.name.trim() || "Nuevo proyecto"}
            meta={row.type.trim()}
            actions={
              <TextButton onClick={() => onChange(items.filter((item) => item.id !== row.id))}>
                Quitar
              </TextButton>
            }
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Nombre">
                <input value={row.name} onChange={(e) => patch(row.id, { name: e.target.value })} className={fieldClass} />
              </Field>
              <Field label="Tipo">
                <input
                  value={row.type}
                  placeholder="mobile-app, web, personal-product"
                  onChange={(e) => patch(row.id, { type: e.target.value })}
                  className={fieldClass}
                />
              </Field>
              <div className="sm:col-span-2">
                <Field label="Descripción">
                  <textarea
                    value={row.description}
                    rows={3}
                    onChange={(e) => patch(row.id, { description: e.target.value })}
                    className={fieldClass}
                  />
                </Field>
              </div>
              <div className="sm:col-span-2">
                <Field label="Tecnologías (una por línea)">
                  <textarea
                    value={row.technologiesText}
                    rows={2}
                    onChange={(e) => patch(row.id, { technologiesText: e.target.value })}
                    className={fieldClass}
                  />
                </Field>
              </div>
            </div>
          </CollapseRow>
        ))}
      </div>
    </SectionCard>
  );
}

export function EducationEditor({ items, onChange }: ListProps<EducationDraft>) {
  const patch = (id: string, partial: Partial<EducationDraft>) => {
    onChange(items.map((row) => (row.id === id ? { ...row, ...partial } : row)));
  };
  return (
    <SectionCard
      title={`Educación (${items.length})`}
      summary={items.map((row) => row.degree.trim()).filter(Boolean).slice(0, 2).join(" · ") || "Sin estudios"}
      hint="Sale fija en el CV. Fechas como 2019 o 2019-06."
      action={
        <TextButton
          onClick={() =>
            onChange([
              ...items,
              {
                id: newProfileId("edu"),
                degree: "",
                institution: "",
                startDate: "",
                endDate: "",
                graduationYear: "",
              },
            ])
          }
        >
          Agregar estudio
        </TextButton>
      }
    >
      <div className="space-y-4">
        {items.map((row) => (
          <CollapseRow
            key={row.id}
            title={row.degree.trim() || "Nuevo estudio"}
            meta={row.institution.trim()}
            actions={
              <TextButton onClick={() => onChange(items.filter((item) => item.id !== row.id))}>
                Quitar
              </TextButton>
            }
          >
            <div className="grid gap-3 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Field label="Grado o título">
                <input value={row.degree} onChange={(e) => patch(row.id, { degree: e.target.value })} className={fieldClass} />
              </Field>
            </div>
            <div className="sm:col-span-2">
              <Field label="Institución">
                <input
                  value={row.institution}
                  onChange={(e) => patch(row.id, { institution: e.target.value })}
                  className={fieldClass}
                />
              </Field>
            </div>
            <Field label="Inicio">
              <input value={row.startDate} onChange={(e) => patch(row.id, { startDate: e.target.value })} className={fieldClass} />
            </Field>
            <Field label="Fin">
              <input value={row.endDate} onChange={(e) => patch(row.id, { endDate: e.target.value })} className={fieldClass} />
            </Field>
            <Field label="Año de graduación">
              <input
                value={row.graduationYear}
                onChange={(e) => patch(row.id, { graduationYear: e.target.value })}
                className={fieldClass}
              />
            </Field>
            </div>
          </CollapseRow>
        ))}
      </div>
    </SectionCard>
  );
}

export function CertificationEditor({ items, onChange }: ListProps<CertificationDraft>) {
  const patch = (id: string, partial: Partial<CertificationDraft>) => {
    onChange(items.map((row) => (row.id === id ? { ...row, ...partial } : row)));
  };
  return (
    <SectionCard
      title={`Certificaciones (${items.length})`}
      summary={items.map((row) => row.name.trim()).filter(Boolean).slice(0, 3).join(" · ") || "Sin certificaciones"}
      action={
        <TextButton
          onClick={() =>
            onChange([...items, { id: newProfileId("cert"), name: "", issuer: "", year: "" }])
          }
        >
          Agregar certificación
        </TextButton>
      }
    >
      <div className="space-y-4">
        {items.map((row) => (
          <CollapseRow
            key={row.id}
            title={row.name.trim() || "Nueva certificación"}
            meta={[row.issuer.trim(), row.year.trim()].filter(Boolean).join(" · ")}
            actions={
              <TextButton onClick={() => onChange(items.filter((item) => item.id !== row.id))}>
                Quitar
              </TextButton>
            }
          >
            <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Nombre">
              <input value={row.name} onChange={(e) => patch(row.id, { name: e.target.value })} className={fieldClass} />
            </Field>
            <Field label="Emisor">
              <input value={row.issuer} onChange={(e) => patch(row.id, { issuer: e.target.value })} className={fieldClass} />
            </Field>
            <Field label="Año">
              <input value={row.year} onChange={(e) => patch(row.id, { year: e.target.value })} className={fieldClass} />
            </Field>
            </div>
          </CollapseRow>
        ))}
      </div>
    </SectionCard>
  );
}

export function LanguageEditor({ items, onChange }: ListProps<LanguageDraft>) {
  const patch = (id: string, partial: Partial<LanguageDraft>) => {
    onChange(items.map((row) => (row.id === id ? { ...row, ...partial } : row)));
  };
  return (
    <SectionCard
      title={`Idiomas (${items.length})`}
      summary={
        items
          .map((row) => [row.language.trim(), row.level.trim()].filter(Boolean).join(" "))
          .filter(Boolean)
          .slice(0, 3)
          .join(" · ") || "Sin idiomas"
      }
      hint="Sin nivel no aparecen en el CV. Ejemplo de nivel: professional proficiency, nativo, B2."
      action={
        <TextButton
          onClick={() => onChange([...items, { id: newProfileId("lang"), language: "", level: "" }])}
        >
          Agregar idioma
        </TextButton>
      }
    >
      <div className="space-y-3">
        {items.map((row) => (
          <div key={row.id} className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
            <Field label="Idioma">
              <input
                value={row.language}
                onChange={(e) => patch(row.id, { language: e.target.value })}
                className={fieldClass}
              />
            </Field>
            <Field label="Nivel">
              <input value={row.level} onChange={(e) => patch(row.id, { level: e.target.value })} className={fieldClass} />
            </Field>
            <div className="flex items-end">
              <TextButton onClick={() => onChange(items.filter((item) => item.id !== row.id))}>
                Quitar
              </TextButton>
            </div>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}
