import type {
  ContactField,
  Experience,
  MasterProfile,
  MasterSkills,
  Metric,
  SkillAliasEntry,
} from "./master-profile";

export function contactFieldDisplay(field: ContactField | undefined): string {
  if (!field) return "—";
  if (field.value) return field.value;
  const values = field.candidates.map((c) => c.value).filter(Boolean);
  if (values.length) return `${values.join(" · ")} (pendiente)`;
  return "requiere validación";
}

export function resolveCanonicalSkill(
  raw: string,
  aliases: Record<string, SkillAliasEntry>,
  aliasIndex: Record<string, string>,
): string {
  const trimmed = raw.trim();
  if (!trimmed) return trimmed;
  if (aliasIndex[trimmed]) return aliasIndex[trimmed];
  const lower = trimmed.toLowerCase();
  for (const [canonical, entry] of Object.entries(aliases)) {
    if (canonical.toLowerCase() === lower) return entry.canonical;
    if (entry.aliases.some((a) => a.toLowerCase() === lower)) return entry.canonical;
  }
  return trimmed;
}

export function metricSafeForCv(metric: Metric): boolean {
  if (metric.evidenceLevel === "inferred" || metric.evidenceLevel === "conflicted") {
    return false;
  }
  return metric.safeForCV === true;
}

export function pendingConflicts(profile: MasterProfile) {
  return profile.conflicts.filter((c) => !c.userValidated);
}

export function experienceDateLabel(ex: Pick<Experience, "startDate" | "endDate" | "dateStatus"> & { current?: boolean }): string {
  const start = ex.startDate ?? "?";
  const end = ex.current ? "Actualidad" : (ex.endDate ?? "?");
  return `${start} – ${end}`;
}

export function skillsFromCatalogCategories(skills: MasterSkills): MasterSkills {
  return skills;
}
