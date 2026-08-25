import type { CVData } from "./cv-types";

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Misma estructura y estilos que `CVTemplate` para Puppeteer. */
export function cvTemplateToBodyHtml(data: CVData): string {
  const s = data.stack;
  const parts: string[] = [];

  parts.push(
    `<div style="font-family:Arial,sans-serif;padding:40px;max-width:800px;margin:0 auto;color:#111;background:#fff;">`,
  );
  parts.push(
    `<h1 style="font-size:26px;font-weight:bold;margin-bottom:4px;">${esc(data.name)}</h1>`,
  );
  parts.push(
    `<p style="font-size:13px;margin-bottom:14px;color:#333;">${esc(data.title)}</p>`,
  );

  parts.push(
    `<div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:18px;font-size:11.5px;color:#222;">`,
  );
  parts.push(`<span>📧 ${esc(data.email)}</span>`);
  parts.push(`<span>📱 ${esc(data.phone)}</span>`);
  parts.push(`<span>🔗 ${esc(data.linkedin)}</span>`);
  parts.push(`</div>`);

  const sectionTitle = (t: string) =>
    `<h2 style="font-size:13px;font-weight:700;letter-spacing:0.04em;text-transform:uppercase;border-bottom:1px solid #111;padding-bottom:6px;margin-bottom:10px;">${esc(t)}</h2>`;

  parts.push(`<div style="margin-bottom:18px;">`);
  parts.push(sectionTitle("Resumen Profesional"));
  parts.push(`<p style="margin:0 0 8px;">${esc(data.summary)}</p>`);
  parts.push(`</div>`);

  parts.push(`<div style="margin-bottom:18px;">`);
  parts.push(sectionTitle("Experiencia Profesional"));
  for (const job of data.experience) {
    parts.push(`<div style="margin-bottom:12px;">`);
    parts.push(
      `<h3 style="font-size:12.5px;font-weight:700;">${esc(job.company)} — ${esc(job.role)}</h3>`,
    );
    parts.push(
      `<p style="font-size:11px;margin-bottom:6px;color:#333;">${esc(job.period)}</p>`,
    );
    parts.push(`<ul style="margin:0;padding-left:18px;">`);
    for (const b of job.bullets) {
      parts.push(`<li>${esc(b)}</li>`);
    }
    parts.push(`</ul></div>`);
  }
  parts.push(`</div>`);

  parts.push(`<div style="margin-bottom:18px;">`);
  parts.push(sectionTitle("Stack Tecnológico"));
  const stackRows: [string, string][] = [
    ["Frontend", s.frontend],
    ["Backend", s.backend],
    ["State Management", s.state],
    ["Cloud & DevOps", s.cloud],
    ["Mobile", s.mobile],
    ["Architecture", s.architecture],
    ["Testing", s.testing],
    ["Code Quality", s.quality],
  ];
  for (const [label, val] of stackRows) {
    if (!val?.trim()) continue;
    parts.push(
      `<p style="margin:0 0 8px;"><strong>${esc(label)}:</strong> ${esc(val)}</p>`,
    );
  }
  parts.push(`</div>`);

  parts.push(`<div style="margin-bottom:18px;">`);
  parts.push(sectionTitle("Formación Académica"));
  parts.push(`<p style="margin:0 0 8px;">${esc(data.education)}</p>`);
  parts.push(`</div>`);

  parts.push(`<div style="margin-bottom:18px;">`);
  parts.push(sectionTitle("Certifications and Achievements"));
  parts.push(`<ul style="margin:0;padding-left:18px;">`);
  for (const c of data.certifications) {
    parts.push(`<li>${esc(c)}</li>`);
  }
  parts.push(`</ul></div>`);

  parts.push(`</div>`);
  return parts.join("");
}
