import { MASTER_SKILL_KINDS, type MasterSkillKind, type MasterSkills } from "@/lib/cv-types";
import { splitLines, type CertificationDraft, type EducationDraft, type ExperienceDraft, type IdentityDraft, type LanguageDraft, type ProjectDraft } from "@/lib/profile-draft";

const SKILL_LABELS: Record<MasterSkillKind, string> = {
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

type Props = {
  identity: IdentityDraft;
  experience: ExperienceDraft[];
  projects: ProjectDraft[];
  education: EducationDraft[];
  certifications: CertificationDraft[];
  languages: LanguageDraft[];
  skills: MasterSkills;
};

function period(row: ExperienceDraft): string {
  const end = row.current ? "Actualidad" : row.endDate.trim();
  const start = row.startDate.trim();
  if (start && end) return `${start} – ${end}`;
  return start || end;
}

function bullets(row: ExperienceDraft): string[] {
  const lines = splitLines(row.responsibilitiesText);
  for (const ach of row.achievements) {
    const description = ach.description.trim();
    if (!description) continue;
    const metric = [ach.metricValue.trim(), ach.metricUnit.trim()].filter(Boolean).join(" ");
    lines.push(metric ? `${description} (${metric})` : description);
  }
  return lines;
}

function Heading({ children }: { children: string }) {
  return (
    <h2 className="mt-4 border-b border-[#CBD5E0] pb-1 text-[11px] font-bold uppercase tracking-wide text-[#1A365D]">
      {children}
    </h2>
  );
}

export function ProfilePreview({
  identity,
  experience,
  projects,
  education,
  certifications,
  languages,
  skills,
}: Props) {
  const titles = splitLines(identity.titlesText);
  const contact = [identity.email, identity.phone, identity.linkedin, identity.location]
    .map((item) => item.trim())
    .filter((item) => item && !item.toLowerCase().startsWith("omitido"));
  const skillRows = MASTER_SKILL_KINDS.map((kind) => ({
    label: SKILL_LABELS[kind],
    values: skills[kind] ?? [],
  })).filter((row) => row.values.length > 0);

  return (
    <div className="mx-auto max-w-[8.5in] bg-white px-8 py-10 text-[#222] shadow-sm ring-1 ring-zinc-200 sm:px-12">
      <h1 className="text-center text-2xl font-bold uppercase tracking-wide text-[#1A365D]">
        {identity.fullName.trim() || "Sin nombre"}
      </h1>
      {titles.length ? (
        <p className="mt-1 text-center text-sm font-bold text-[#2B6CB0]">{titles[0]}</p>
      ) : null}
      {titles.length > 1 ? (
        <p className="mt-1 text-center text-xs text-zinc-500">{titles.slice(1).join(" · ")}</p>
      ) : null}
      {contact.length ? (
        <p className="mt-2 text-center text-xs text-[#4A5568]">{contact.join("  |  ")}</p>
      ) : null}

      <Heading>Resumen</Heading>
      <p className="mt-2 text-sm leading-relaxed">
        {identity.summary.trim() || "Sin resumen."}
      </p>

      <Heading>Experiencia</Heading>
      <div className="mt-2 space-y-3">
        {experience.length === 0 ? <p className="text-sm text-zinc-500">Sin empleos.</p> : null}
        {experience.map((job) => {
          const roles = splitLines(job.rolesText);
          const lines = bullets(job);
          return (
            <article key={job.id}>
              <div className="flex items-baseline justify-between gap-3">
                <h3 className="text-sm font-bold text-[#2D3748]">
                  {job.company.trim() || "Empresa"}
                  {roles[0] ? ` — ${roles[0]}` : ""}
                </h3>
                <p className="shrink-0 text-xs font-bold text-[#718096]">{period(job)}</p>
              </div>
              {roles.length > 1 ? (
                <p className="text-xs text-zinc-500">{roles.slice(1).join(" · ")}</p>
              ) : null}
              {lines.length ? (
                <ul className="mt-1 list-disc pl-5 text-sm">
                  {lines.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              ) : null}
            </article>
          );
        })}
      </div>

      {skillRows.length ? (
        <>
          <Heading>Skills</Heading>
          <div className="mt-2 space-y-1">
            {skillRows.map((row) => (
              <p key={row.label} className="text-sm">
                <span className="font-bold">{row.label}:</span> {row.values.join(", ")}
              </p>
            ))}
          </div>
        </>
      ) : null}

      {projects.some((row) => row.name.trim()) ? (
        <>
          <Heading>Proyectos</Heading>
          <div className="mt-2 space-y-2">
            {projects
              .filter((row) => row.name.trim())
              .map((row) => (
                <article key={row.id}>
                  <h3 className="text-sm font-bold text-[#2D3748]">
                    {row.name.trim()}
                    {row.type.trim() ? ` — ${row.type.trim()}` : ""}
                  </h3>
                  {row.description.trim() ? (
                    <p className="text-sm">{row.description.trim()}</p>
                  ) : null}
                </article>
              ))}
          </div>
        </>
      ) : null}

      <Heading>Educación</Heading>
      <div className="mt-2 space-y-1 text-sm">
        {education.length === 0 ? <p className="text-zinc-500">Sin estudios.</p> : null}
        {education.map((row) => {
          const year = row.graduationYear.trim() || row.endDate.trim();
          const line = [row.degree.trim(), row.institution.trim()].filter(Boolean).join(" — ");
          return (
            <p key={row.id}>
              {line || "Estudio"}
              {year ? ` (${year})` : ""}
            </p>
          );
        })}
      </div>

      <Heading>Certificaciones</Heading>
      <ul className="mt-2 list-disc pl-5 text-sm">
        {certifications.length === 0 ? <li className="list-none pl-0 text-zinc-500">Sin certificaciones.</li> : null}
        {certifications.map((row) => (
          <li key={row.id}>
            {[row.name.trim() || "Certificación", row.issuer.trim()].filter(Boolean).join(" — ")}
            {row.year.trim() ? ` (${row.year.trim()})` : ""}
          </li>
        ))}
      </ul>

      {languages.some((row) => row.language.trim()) ? (
        <>
          <Heading>Idiomas</Heading>
          <p className="mt-2 text-sm">
            {languages
              .filter((row) => row.language.trim())
              .map((row) => [row.language.trim(), row.level.trim()].filter(Boolean).join(" · "))
              .join("  |  ")}
          </p>
        </>
      ) : null}
    </div>
  );
}
