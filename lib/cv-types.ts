export type Experience = {
  company: string;
  role: string;
  period: string;
  bullets: string[];
};

export type TechSkills = {
  front: string[];
  back: string[];
  ux: string[];
  test: string[];
};

export type {
  Conflict as MasterConflict,
  Experience as MasterExperience,
  MasterProfile,
  MasterSkillKind,
  MasterSkills,
} from "./master-profile";

export {
  emptyMasterSkills,
  MASTER_SKILL_KINDS,
} from "./master-profile";

export type CVStack = {
  frontend: string;
  backend: string;
  state: string;
  cloud: string;
  mobile: string;
  architecture: string;
  testing: string;
  quality: string;
};

export type CVData = {
  name: string;
  title: string;
  email: string;
  phone: string;
  linkedin: string;
  summary: string;
  experience: Experience[];
  stack: CVStack;
  tech_skills: TechSkills;
  education: string;
  certifications: string[];
  locale?: "en" | "es";
};

/** Perfil en knowledge base: datos del template + metadatos para el matcher. */
export type CvProfile = CVData & {
  id: string;
  label: string;
  keywords: string[];
};

export type MatchResponse = {
  chosen_cv_id: string;
  match_score: number;
  match_reason: string;
  cv: CvProfile;
  vacancy_excerpt: string;
  raw_meta?: Record<string, unknown>;
};

export type TailorResponse = {
  cv: CvProfile;
  match_percent: number;
  reason: string;
  notes_to_verify: string[];
  gaps: string[];
  reinforcement_plan: string[];
  raw_meta?: Record<string, unknown>;
  saved_id?: string | null;
};

export type HistorySummary = {
  id: string;
  vacancy_title: string;
  created_at: string;
  match_percent: number;
  target_role: string;
};

export type HistoryDetail = {
  id: string;
  vacancy_title: string;
  vacancy_text: string;
  created_at: string;
  match_percent: number;
  reason: string;
  cv: CvProfile;
};

export function pickCvData(profile: CvProfile): CVData {
  const { id: _i, label: _l, keywords: _k, ...data } = profile;
  void _i;
  void _l;
  void _k;
  return data;
}

export const emptyStack = (): CVStack => ({
  frontend: "",
  backend: "",
  state: "",
  cloud: "",
  mobile: "",
  architecture: "",
  testing: "",
  quality: "",
});

export const emptyTechSkills = (): TechSkills => ({
  front: [],
  back: [],
  ux: [],
  test: [],
});

/** Lista en `/extension-jobs` y respuesta de `POST /v1/extension/optimize`. */
export type ExtensionJobSummary = {
  id: string;
  vacancy_title: string;
  source_site: string;
  created_at: string;
  chosen_cv_id: string;
  match_score: number;
  tailor_match_percent: number;
};

/** Respuesta completa de POST/GET `/v1/extension/...` (incluye CV generado). */
export type ExtensionOptimizeJob = {
  id: string;
  vacancy_title: string;
  source_site: string;
  created_at: string;
  match: MatchResponse;
  tailor: TailorResponse;
};
