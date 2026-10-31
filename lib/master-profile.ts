/** Career Knowledge Base / master profile — single source of truth. */

export type EvidenceLevel =
  | "verified"
  | "documented"
  | "claimed"
  | "mentioned"
  | "inferred"
  | "conflicted";

export type ConflictImpact = "critical" | "high" | "medium" | "low";

export type DateStatus =
  | "verified"
  | "documented"
  | "claimed"
  | "mentioned"
  | "conflicted"
  | "requires_validation";

export type ValidationStatus =
  | "requires_validation"
  | "user_validated"
  | "documented"
  | "verified"
  | "claimed"
  | "mentioned"
  | "inferred"
  | "conflicted";

export type Evidence = {
  evidenceLevel: EvidenceLevel;
  sourceCount?: number | null;
  userValidated?: boolean;
  sourceRefs?: string[];
};

export type ContactCandidate = {
  value: string;
  evidenceLevel: EvidenceLevel;
  sourceRefs: string[];
  userValidated: boolean;
};

export type ContactField = {
  value: string | null;
  status: ValidationStatus;
  evidenceLevel?: EvidenceLevel;
  sourceCount?: number | null;
  userValidated: boolean;
  candidates: ContactCandidate[];
};

export type ContactProfile = {
  email: ContactField;
  phone: ContactField;
  linkedin: ContactField;
  location: ContactField;
};

export type MasterSkills = {
  languages: string[];
  frontend: string[];
  backend: string[];
  mobile: string[];
  databases: string[];
  cloud: string[];
  devops: string[];
  testing: string[];
  architecture: string[];
  payments: string[];
  security: string[];
  ai: string[];
  softSkills: string[];
};

export type MasterSkillKind = keyof MasterSkills;

export type Skill = {
  id: string;
  canonical: string;
  aliases: string[];
  categories: MasterSkillKind[];
  evidenceLevel: EvidenceLevel;
  sourceCount?: number | null;
  userValidated: boolean;
};

export type SkillAliasEntry = {
  id: string;
  canonical: string;
  aliases: string[];
};

export type Achievement = {
  description: string;
  metric: { value: number | null; unit: string; type: string };
  status: string;
  evidenceLevel?: EvidenceLevel;
  safeForCV?: boolean;
  requiresUserValidation?: boolean;
};

export type EmploymentType =
  | "full-time"
  | "freelance"
  | "contract"
  | "remote"
  | "onsite"
  | null;

export type Experience = {
  id: string;
  company: string;
  roles: string[];
  employmentType: string | null;
  startDate: string | null;
  endDate: string | null;
  current?: boolean;
  sortOrder?: number;
  dateStatus: DateStatus | string;
  sourceValues: Record<string, unknown>;
  originalValues?: Record<string, unknown>;
  userValidated: boolean;
  conflicts: string[];
  domain: string[];
  responsibilities: string[];
  technologies: string[];
  achievements: Achievement[];
  evidence: string[];
  sourceRefs: string[];
  evidenceLevel: EvidenceLevel;
  sourceCount: number;
};

export type ProjectContribution = "" | "full" | "frontend" | "backend" | "lead";

export const PROJECT_CONTRIBUTION_LABELS: Record<ProjectContribution, string> = {
  "": "Sin definir",
  full: "Desarrollo completo",
  frontend: "Solo frontend",
  backend: "Solo backend",
  lead: "Liderazgo técnico",
};

export type Project = {
  id: string;
  name: string;
  type: string;
  description: string;
  domain: string[];
  platforms: string[];
  features: string[];
  technologies: string[];
  scale: string | null;
  status: string;
  evidenceLevel: EvidenceLevel;
  sourceCount: number;
  userValidated: boolean;
  evidence: string[];
  sourceRefs: string[];
  isEmployment: boolean;
  contribution?: ProjectContribution;
  relevantForRoles?: string[];
  relevantWhenVacancyNeeds?: string[];
};

export type Education = {
  id: string;
  degree: string;
  institution: string;
  startDate: string | null;
  endDate: string | null;
  graduationYear: number | null;
  status: string;
  evidenceLevel: EvidenceLevel;
  sourceCount: number;
  userValidated: boolean;
  sourceRefs: string[];
  evidence?: string[];
  showInCv?: boolean;
  showInCvNote?: string;
};

export type Certification = {
  id: string;
  name: string;
  issuer: string;
  year: number | null;
  status: string;
  evidenceLevel: EvidenceLevel;
  sourceCount: number;
  userValidated: boolean;
  sourceRefs: string[];
};

export type Language = {
  id: string;
  language: string;
  level: string | null;
  status: string;
  evidenceLevel: EvidenceLevel;
  sourceCount: number;
  userValidated: boolean;
  conflicts: string[];
  sourceValues?: string[];
  originalValues?: Record<string, unknown>;
  sourceRefs: string[];
};

export type Metric = {
  id: string;
  value: number | null;
  unit: string;
  type: string;
  description: string;
  company: string;
  project: string;
  status: string;
  confidence: string;
  evidenceLevel: EvidenceLevel;
  sourceCount: number;
  userValidated: boolean;
  safeForCV: boolean;
  requiresUserValidation: boolean;
  experienceId?: string | null;
  projectId?: string | null;
  sourceRefs?: string[];
};

export type CareerTimelineEntry = {
  id: string;
  experienceId: string;
  company: string;
  role: string;
  roles: string[];
  startDate: string | null;
  endDate: string | null;
  dateStatus: string;
  sourceValues: Record<string, unknown>;
  userValidated: boolean;
  kind: string;
  current?: boolean;
};

export type PositioningProfile = {
  id: string;
  preferredTitle: string;
  prioritySkills: string[];
  priorityExperience: string[];
  priorityExperienceLabels?: string[];
  priorityProjects: string[];
  priorityProjectLabels?: string[];
  secondarySkills: string[];
  sellingPoints: string[];
  avoidUnlessRelevant: string[];
  summaryFocus: string[];
  keywordStrategy: string[];
};

export type Conflict = {
  id: string;
  field: string;
  values: string[];
  preferredValue: string | null;
  resolution: string;
  userValidated: boolean;
  impact: ConflictImpact;
  evidenceLevel: EvidenceLevel;
};

export type UserValidationResolved = {
  field: string;
  previousValues: string[];
  resolvedValue: string;
  resolvedAt: string;
  source: "user";
};

export type UserValidation = {
  pending: string[];
  resolved: UserValidationResolved[];
  lastUpdated: string | null;
};

export type CvGenerationRules = {
  neverInvent: boolean;
  neverResolveConflictsAutomatically: boolean;
  neverUseInferredAsFact: boolean;
  preferUserValidated: boolean;
  preferDocumentedEvidence: boolean;
  adaptToJobDescription: boolean;
  suppressIrrelevantSkills: boolean;
  preserveCareerHistory: boolean;
  omitContactFields?: string[];
  omitContactFieldsNote?: string;
  overlappingEmploymentNote?: string;
};

export type Source = {
  id: string;
  name: string;
  type: string;
  language: string;
  scope: string[];
  status?: string;
  note?: string;
};

export type YearsOfExperience = {
  value: number | null;
  source: string | null;
  status: string;
  evidenceLevel?: EvidenceLevel;
  sourceValues?: string[];
  userValidated?: boolean;
  note?: string;
};

export type MasterProfile = {
  schemaVersion: string;
  profile: {
    fullName: string;
    professionalTitles: string[];
    contact: ContactProfile;
    summary: string;
  };
  skills: MasterSkills;
  skillCatalog: Skill[];
  experience: Experience[];
  projects: Project[];
  education: Education[];
  certifications: Certification[];
  languages: Language[];
  metrics: Metric[];
  skillAliases: Record<string, SkillAliasEntry>;
  positioningProfiles: Record<string, PositioningProfile>;
  conflicts: Conflict[];
  careerTimeline: CareerTimelineEntry[];
  yearsOfExperience: YearsOfExperience;
  userValidation: UserValidation;
  cvGenerationRules: CvGenerationRules;
  sources: Source[];
};

/** Alias used by the skills workbench. */
export type MasterExperience = Experience;
export type MasterConflict = Conflict;

export const MASTER_SKILL_KINDS: MasterSkillKind[] = [
  "languages",
  "frontend",
  "backend",
  "mobile",
  "databases",
  "cloud",
  "devops",
  "testing",
  "architecture",
  "payments",
  "security",
  "ai",
  "softSkills",
];

export const emptyMasterSkills = (): MasterSkills => ({
  languages: [],
  frontend: [],
  backend: [],
  mobile: [],
  databases: [],
  cloud: [],
  devops: [],
  testing: [],
  architecture: [],
  payments: [],
  security: [],
  ai: [],
  softSkills: [],
});

