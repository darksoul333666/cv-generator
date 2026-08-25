/** Metadatos de la extensión (Empresa / URL). No deben ir al modelo. */

const EMPRESA_RE = /^(empresa|company)\s*:\s*(.+)$/i;
const URL_RE = /^(url|enlace|link)\s*:\s*(\S+)$/i;

export type VacancyMeta = {
  text: string;
  companyName: string | null;
  vacancyUrl: string | null;
};

export function splitVacancyMeta(raw: string): VacancyMeta {
  let companyName: string | null = null;
  let vacancyUrl: string | null = null;
  const kept: string[] = [];
  for (const line of (raw || "").split(/\r?\n/)) {
    const trimmed = line.trim();
    const company = trimmed.match(EMPRESA_RE);
    if (company) {
      companyName = company[2].trim() || null;
      continue;
    }
    const url = trimmed.match(URL_RE);
    if (url) {
      const candidate = url[2].trim().replace(/[.,)]+$/, "");
      if (/^https?:\/\//i.test(candidate)) vacancyUrl = candidate;
      continue;
    }
    kept.push(line);
  }
  return {
    text: kept.join("\n").replace(/\n{3,}/g, "\n\n").trim(),
    companyName,
    vacancyUrl,
  };
}
