import { NextResponse } from "next/server";
import { cvTemplateToBodyHtml } from "@/lib/cv-template-html";
import {
  emptyStack,
  pickCvData,
  type CVStack,
  type CvProfile,
} from "@/lib/cv-types";

export const runtime = "nodejs";
export const maxDuration = 60;

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function normalizeStack(raw: unknown): CVStack {
  const d = emptyStack();
  if (!isRecord(raw)) return d;
  for (const k of Object.keys(d) as (keyof CVStack)[]) {
    const v = raw[k as string];
    if (typeof v === "string") d[k] = v;
  }
  return d;
}

function normalizeCvProfile(raw: unknown): CvProfile | null {
  if (!isRecord(raw)) return null;
  if (typeof raw.name !== "string" || typeof raw.email !== "string") return null;
  if (typeof raw.id !== "string") return null;

  const experience = Array.isArray(raw.experience)
    ? raw.experience
        .filter(isRecord)
        .map((e) => ({
          company: typeof e.company === "string" ? e.company : "",
          role: typeof e.role === "string" ? e.role : "",
          period: typeof e.period === "string" ? e.period : "",
          bullets: Array.isArray(e.bullets)
            ? e.bullets.filter((b): b is string => typeof b === "string")
            : [],
        }))
    : [];

  const certifications = Array.isArray(raw.certifications)
    ? raw.certifications.filter((c): c is string => typeof c === "string")
    : [];

  const keywords = Array.isArray(raw.keywords)
    ? raw.keywords.filter((k): k is string => typeof k === "string")
    : [];

  const profile: CvProfile = {
    id: raw.id,
    label: typeof raw.label === "string" ? raw.label : "",
    keywords,
    name: raw.name,
    title: typeof raw.title === "string" ? raw.title : "",
    email: raw.email,
    phone: typeof raw.phone === "string" ? raw.phone : "",
    linkedin: typeof raw.linkedin === "string" ? raw.linkedin : "",
    summary: typeof raw.summary === "string" ? raw.summary : "",
    experience,
    stack: normalizeStack(raw.stack),
    education: typeof raw.education === "string" ? raw.education : "",
    certifications,
  };
  return profile;
}

function buildHtml(markup: string): string {
  return `<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; background: #fff; }
    @page { size: A4; margin: 14mm; }
  </style>
</head>
<body>${markup}</body>
</html>`;
}

export async function POST(request: Request) {
  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return NextResponse.json({ error: "JSON inválido" }, { status: 400 });
  }

  const cvRaw = (json as { cv?: unknown })?.cv;
  const profile = normalizeCvProfile(cvRaw);
  if (!profile) {
    return NextResponse.json(
      { error: "Falta un cv válido (id, name, email y estructura CVData)." },
      { status: 400 },
    );
  }

  const data = pickCvData(profile);
  const markup = cvTemplateToBodyHtml(data);
  const html = buildHtml(markup);

  const puppeteer = await import("puppeteer");
  const browser = await puppeteer.default.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });

  try {
    const page = await browser.newPage();
    await page.setContent(html, { waitUntil: "networkidle0", timeout: 30_000 });
    const pdf = await page.pdf({
      format: "A4",
      printBackground: true,
      preferCSSPageSize: true,
      margin: { top: "0", right: "0", bottom: "0", left: "0" },
    });
    return new NextResponse(Buffer.from(pdf), {
      status: 200,
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": 'attachment; filename="cv.pdf"',
        "Cache-Control": "no-store",
      },
    });
  } finally {
    await browser.close();
  }
}
