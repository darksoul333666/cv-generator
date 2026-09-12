/** Metadatos de la extensión (Empresa / URL). No deben ir al modelo. */

const EMPRESA_RE = /^(empresa|company)\s*:\s*(.+)$/i;
const URL_RE = /^(url|enlace|link)\s*:\s*(\S+)$/i;

export type VacancyMeta = {
  text: string;
  companyName: string | null;
  vacancyUrl: string | null;
};

function normalizeVacancyUrl(url: string): string | null {
  const raw = url.trim().replace(/[.,)]+$/, "");
  if (!raw) return null;
  const view = raw.match(/https?:\/\/(?:www\.)?linkedin\.com\/jobs\/view\/(\d+)/i);
  if (view) return `https://www.linkedin.com/jobs/view/${view[1]}`;
  const current = raw.match(/[?&]currentJobId=(\d+)/i);
  if (current && /linkedin\.com/i.test(raw)) {
    return `https://www.linkedin.com/jobs/view/${current[1]}`;
  }
  const occOffer = raw.match(
    /https?:\/\/(?:www\.)?occ\.com\.mx\/empleo\/oferta\/(\d+)/i,
  );
  if (occOffer) return `https://www.occ.com.mx/empleo/oferta/${occOffer[1]}`;
  const occJobId = raw.match(/[?&]jobid=(\d+)/i);
  if (occJobId && /occ\.com\.mx/i.test(raw)) {
    return `https://www.occ.com.mx/empleo/oferta/${occJobId[1]}`;
  }
  return /^https?:\/\//i.test(raw) ? raw : null;
}

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
      vacancyUrl = normalizeVacancyUrl(url[2]);
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
