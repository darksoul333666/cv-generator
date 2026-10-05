import type {
  Achievement,
  Certification,
  Education,
  Experience,
  Language,
  MasterProfile,
  Project,
} from "./master-profile";

export type AchievementDraft = {
  description: string;
  metricValue: string;
  metricUnit: string;
};

export type ExperienceDraft = {
  id: string;
  company: string;
  rolesText: string;
  employmentType: string;
  startDate: string;
  endDate: string;
  current: boolean;
  responsibilitiesText: string;
  technologiesText: string;
  achievements: AchievementDraft[];
};

export type ProjectDraft = {
  id: string;
  name: string;
  type: string;
  description: string;
  technologiesText: string;
};

export type EducationDraft = {
  id: string;
  degree: string;
  institution: string;
  startDate: string;
  endDate: string;
  graduationYear: string;
};

export type CertificationDraft = {
  id: string;
  name: string;
  issuer: string;
  year: string;
};

export type LanguageDraft = {
  id: string;
  language: string;
  level: string;
};

export type IdentityDraft = {
  fullName: string;
  titlesText: string;
  summary: string;
  email: string;
  phone: string;
  linkedin: string;
  location: string;
};

export type ProfileContentPayload = {
  profile: {
    fullName: string;
    professionalTitles: string[];
    summary: string;
    email: string;
    phone: string;
    linkedin: string;
    location: string;
  };
  experience: Array<{
    id: string;
    company: string;
    roles: string[];
    employmentType: string | null;
    startDate: string | null;
    endDate: string | null;
    current: boolean;
    responsibilities: string[];
    technologies: string[];
    achievements: Array<{
      description: string;
      metricValue: number | null;
      metricUnit: string;
    }>;
  }>;
  projects: Array<{
    id: string;
    name: string;
    type: string;
    description: string;
    technologies: string[];
  }>;
  education: Array<{
    id: string;
    degree: string;
    institution: string;
    startDate: string | null;
    endDate: string | null;
    graduationYear: number | null;
  }>;
  certifications: Array<{
    id: string;
    name: string;
    issuer: string;
    year: number | null;
  }>;
  languages: Array<{
    id: string;
    language: string;
    level: string | null;
  }>;
};

export function newProfileId(prefix: string): string {
  const rand = Math.random().toString(36).slice(2, 10);
  return `${prefix}_${rand}`;
}

export function splitLines(text: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of text.split("\n")) {
    const line = raw.trim().replace(/\s+/g, " ");
    if (!line) continue;
    const key = line.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(line);
  }
  return out;
}

function dateInput(value: string | null | undefined): string {
  if (!value) return "";
  return /^\d{4}(-\d{2})?$/.test(value) ? value : "";
}

function achievementDraft(ach: Achievement): AchievementDraft {
  return {
    description: ach.description ?? "",
    metricValue: ach.metric?.value == null ? "" : String(ach.metric.value),
    metricUnit: ach.metric?.unit ?? "",
  };
}

export function identityFromProfile(profile: MasterProfile): IdentityDraft {
  const contact = profile.profile.contact;
  return {
    fullName: profile.profile.fullName ?? "",
    titlesText: (profile.profile.professionalTitles ?? []).join("\n"),
    summary: profile.profile.summary ?? "",
    email: contact?.email?.value ?? "",
    phone: contact?.phone?.value ?? "",
    linkedin: contact?.linkedin?.value ?? "",
    location: contact?.location?.value ?? "",
  };
}

export function experienceFromProfile(ex: Experience): ExperienceDraft {
  return {
    id: ex.id,
    company: ex.company ?? "",
    rolesText: (ex.roles ?? []).join("\n"),
    employmentType: ex.employmentType ?? "",
    startDate: dateInput(ex.startDate),
    endDate: dateInput(ex.endDate),
    current: Boolean(ex.current),
    responsibilitiesText: (ex.responsibilities ?? []).join("\n"),
    technologiesText: (ex.technologies ?? []).join("\n"),
    achievements: (ex.achievements ?? []).map(achievementDraft),
  };
}

export function projectFromProfile(project: Project): ProjectDraft {
  return {
    id: project.id,
    name: project.name ?? "",
    type: project.type ?? "",
    description: project.description ?? "",
    technologiesText: (project.technologies ?? []).join("\n"),
  };
}

export function educationFromProfile(item: Education): EducationDraft {
  return {
    id: item.id,
    degree: item.degree ?? "",
    institution: item.institution ?? "",
    startDate: item.startDate ?? "",
    endDate: item.endDate ?? "",
    graduationYear: item.graduationYear == null ? "" : String(item.graduationYear),
  };
}

export function certificationFromProfile(item: Certification): CertificationDraft {
  return {
    id: item.id,
    name: item.name ?? "",
    issuer: item.issuer ?? "",
    year: item.year == null ? "" : String(item.year),
  };
}

export function languageFromProfile(item: Language): LanguageDraft {
  return {
    id: item.id,
    language: item.language ?? "",
    level: item.level ?? "",
  };
}

function emptyToNull(value: string): string | null {
  const text = value.trim();
  return text || null;
}

function optionalYear(value: string): number | null {
  const text = value.trim();
  if (!text) return null;
  const year = Number(text);
  if (!Number.isInteger(year)) {
    throw new Error(`Año inválido: ${value}`);
  }
  return year;
}

function optionalMetric(value: string): number | null {
  const text = value.trim();
  if (!text) return null;
  const num = Number(text);
  if (!Number.isFinite(num)) {
    throw new Error(`Métrica inválida: ${value}`);
  }
  return num;
}

export function contentFromDrafts(input: {
  identity: IdentityDraft;
  experience: ExperienceDraft[];
  projects: ProjectDraft[];
  education: EducationDraft[];
  certifications: CertificationDraft[];
  languages: LanguageDraft[];
}): ProfileContentPayload {
  return {
    profile: {
      fullName: input.identity.fullName.trim(),
      professionalTitles: splitLines(input.identity.titlesText),
      summary: input.identity.summary.trim(),
      email: input.identity.email.trim(),
      phone: input.identity.phone.trim(),
      linkedin: input.identity.linkedin.trim(),
      location: input.identity.location.trim(),
    },
    experience: input.experience.map((row) => ({
      id: row.id,
      company: row.company.trim(),
      roles: splitLines(row.rolesText),
      employmentType: row.employmentType.trim() || null,
      startDate: emptyToNull(row.startDate),
      endDate: row.current ? null : emptyToNull(row.endDate),
      current: row.current,
      responsibilities: splitLines(row.responsibilitiesText),
      technologies: splitLines(row.technologiesText),
      achievements: row.achievements
        .map((ach) => ({
          description: ach.description.trim(),
          metricValue: optionalMetric(ach.metricValue),
          metricUnit: ach.metricUnit.trim(),
        }))
        .filter((ach) => ach.description || ach.metricValue != null),
    })),
    projects: input.projects.map((row) => ({
      id: row.id,
      name: row.name.trim(),
      type: row.type.trim(),
      description: row.description.trim(),
      technologies: splitLines(row.technologiesText),
    })),
    education: input.education.map((row) => ({
      id: row.id,
      degree: row.degree.trim(),
      institution: row.institution.trim(),
      startDate: emptyToNull(row.startDate),
      endDate: emptyToNull(row.endDate),
      graduationYear: optionalYear(row.graduationYear),
    })),
    certifications: input.certifications.map((row) => ({
      id: row.id,
      name: row.name.trim(),
      issuer: row.issuer.trim(),
      year: optionalYear(row.year),
    })),
    languages: input.languages.map((row) => ({
      id: row.id,
      language: row.language.trim(),
      level: emptyToNull(row.level),
    })),
  };
}
