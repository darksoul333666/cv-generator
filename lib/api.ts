import type { MatchResponse } from "./cv-types";

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
