export type Experience = {
  company: string;
  role: string;
  period: string;
  bullets: string[];
};

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
  education: string;
  certifications: string[];
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

export function pickCvData(profile: CvProfile): CVData {
  const { id: _i, label: _l, keywords: _k, ...data } = profile;
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
