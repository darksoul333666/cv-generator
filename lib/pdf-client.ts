import type { CvProfile } from "./cv-types";

export async function downloadCvPdfWithPuppeteer(
  cv: CvProfile,
  filename: string,
): Promise<void> {
  const res = await fetch("/api/pdf", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cv }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const msg =
      typeof err === "object" && err && "error" in err
        ? String((err as { error: unknown }).error)
        : res.statusText;
    throw new Error(msg || `Error ${res.status}`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
