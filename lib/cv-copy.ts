import type { CVData } from "./cv-types";

export type CvLocale = "en" | "es";

export type CvCopy = {
  summary: string;
  experience: string;
  skills: string;
  education: string;
  certifications: string;
  frontend: string;
  styling: string;
  backend: string;
  architecture: string;
  cloud: string;
  mobile: string;
  testing: string;
  quality: string;
  state: string;
};

const COPY: Record<CvLocale, CvCopy> = {
  en: {
    summary: "PROFESSIONAL SUMMARY",
    experience: "PROFESSIONAL EXPERIENCE",
    skills: "TECHNICAL SKILLS",
    education: "EDUCATION",
    certifications: "CERTIFICATIONS & ACHIEVEMENTS",
    frontend: "Frontend",
    styling: "Styling",
    backend: "Backend & APIs",
    architecture: "Architecture",
    cloud: "Cloud & DevOps",
    mobile: "Mobile",
    testing: "Testing",
    quality: "Code Quality",
    state: "State Management",
  },
  es: {
    summary: "RESUMEN PROFESIONAL",
    experience: "EXPERIENCIA PROFESIONAL",
    skills: "HABILIDADES TÉCNICAS",
    education: "FORMACIÓN ACADÉMICA",
    certifications: "CERTIFICACIONES Y LOGROS",
    frontend: "Frontend",
    styling: "Styling",
    backend: "Backend y APIs",
    architecture: "Arquitectura",
    cloud: "Cloud y DevOps",
    mobile: "Móvil",
    testing: "Testing",
    quality: "Calidad de código",
    state: "Gestión de estado",
  },
};

export function cvLocale(data: Pick<CVData, "locale" | "title" | "summary"> | { locale?: string; title?: string; summary?: string }): CvLocale {
  if (data.locale === "en" || data.locale === "es") return data.locale;
  const blob = `${data.title || ""} ${data.summary || ""}`.toLowerCase();
  if (/[áéíóúñ¿¡]/.test(blob) || /\b(experiencia|desarrollador|resumen)\b/.test(blob)) {
    return "es";
  }
  if (/\b(experienced|developer|engineer|professional)\b/.test(blob)) {
    return "en";
  }
  return "es";
}

export function cvCopy(locale: CvLocale): CvCopy {
  return COPY[locale];
}
