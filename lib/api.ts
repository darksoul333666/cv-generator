import type { CvProfile, MatchResponse, TailorResponse, TechSkills } from "./cv-types";

const DEFAULT_API = "http://127.0.0.1:8000";

export function apiBase(): string {
  return process.env.NEXT_PUBLIC_PY_API_URL ?? DEFAULT_API;
}

export async function matchVacancy(input: {
  vacancy_text: string;
  vacancy_url?: string | null;
}): Promise<MatchResponse> {
  const res = await fetch(`${apiBase()}/v1/match`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      vacancy_text: input.vacancy_text,
      vacancy_url: input.vacancy_url || null,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    let detail = res.statusText;
    if (typeof err === "object" && err && "detail" in err) {
      const d = (err as { detail: unknown }).detail;
      if (typeof d === "string") detail = d;
      else if (Array.isArray(d))
        detail = d.map((x) => JSON.stringify(x)).join("; ");
      else if (d != null) detail = String(d);
    }
    throw new Error(detail || `Error ${res.status}`);
  }
  return res.json() as Promise<MatchResponse>;
}

export async function tailorCv(input: {
  vacancy_text: string;
  vacancy_url?: string | null;
  custom_instructions?: string;
  cv: CvProfile;
}): Promise<TailorResponse> {
  const res = await fetch(`${apiBase()}/v1/tailor`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      vacancy_text: input.vacancy_text,
      vacancy_url: input.vacancy_url || null,
      custom_instructions: input.custom_instructions?.trim() || "",
      cv: input.cv,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    let detail = res.statusText;
    if (typeof err === "object" && err && "detail" in err) {
      const d = (err as { detail: unknown }).detail;
      if (typeof d === "string") detail = d;
      else if (Array.isArray(d))
        detail = d.map((x) => JSON.stringify(x)).join("; ");
      else if (d != null) detail = String(d);
    }
    throw new Error(detail || `Error ${res.status}`);
  }
  return res.json() as Promise<TailorResponse>;
}

export async function listCvs(): Promise<CvProfile[]> {
  const res = await fetch(`${apiBase()}/v1/cvs`, { method: "GET" });
  if (!res.ok) throw new Error(res.statusText || `Error ${res.status}`);
  return res.json() as Promise<CvProfile[]>;
}

export async function getCv(cvId: string): Promise<CvProfile> {
  const res = await fetch(`${apiBase()}/v1/cvs/${encodeURIComponent(cvId)}`, {
    method: "GET",
  });
  if (!res.ok) throw new Error(res.statusText || `Error ${res.status}`);
  return res.json() as Promise<CvProfile>;
}

export async function putTechSkills(
  cvId: string,
  skills: TechSkills,
): Promise<CvProfile> {
  const res = await fetch(
    `${apiBase()}/v1/cvs/${encodeURIComponent(cvId)}/tech-skills`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(skills),
    },
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    if (typeof err === "object" && err && "detail" in err) {
      const d = (err as { detail: unknown }).detail;
      if (typeof d === "string") throw new Error(d);
    }
    throw new Error(res.statusText || `Error ${res.status}`);
  }
  return res.json() as Promise<CvProfile>;
}
