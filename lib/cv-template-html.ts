import type { CVData } from "./cv-types";
import { cvCopy, cvLocale } from "./cv-copy";

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Layout ATS alineado a Jairo_Camarillo_CV_ATS.docx (Arial, navy, Letter 0.5in). */
export function cvTemplateToBodyHtml(data: CVData): string {
  const locale = cvLocale(data);
  const copy = cvCopy(locale);
  const s = data.stack;
  const parts: string[] = [];

  const contact = [data.email, data.phone, data.linkedin]
    .map((x) => x.trim())
    .filter(Boolean)
    .join("  |  ");

  parts.push(
    `<div style="font-family:Arial,Helvetica,sans-serif;padding:0.5in;max-width:8.5in;margin:0 auto;color:#222222;background:#fff;line-height:1.15;">`,
  );
  parts.push(
    `<h1 style="font-size:18pt;font-weight:700;margin:0 0 2pt;text-align:center;color:#1A365D;letter-spacing:0.02em;text-transform:uppercase;">${esc(data.name)}</h1>`,
  );
  parts.push(
    `<p style="font-size:11pt;font-weight:700;margin:0 0 4pt;text-align:center;color:#2B6CB0;">${esc(data.title)}</p>`,
  );
  parts.push(
    `<p style="font-size:8.5pt;margin:0 0 10pt;text-align:center;color:#4A5568;">${esc(contact)}</p>`,
  );

  const sectionTitle = (t: string) =>
    `<h2 style="font-size:10.5pt;font-weight:700;margin:12pt 0 6pt;color:#1A365D;text-transform:uppercase;letter-spacing:0.04em;border-bottom:1px solid #CBD5E0;padding-bottom:3pt;">${esc(t)}</h2>`;

  parts.push(sectionTitle(copy.summary));
  parts.push(
    `<p style="font-size:9.5pt;margin:0 0 8pt;color:#222;">${esc(data.summary)}</p>`,
  );

  parts.push(sectionTitle(copy.experience));
  for (const job of data.experience) {
    parts.push(`<div style="margin:0 0 8pt;">`);
    parts.push(
      `<div style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;">`,
    );
    parts.push(
      `<h3 style="font-size:9.5pt;font-weight:700;margin:0;color:#2D3748;">${esc(job.company)} — ${esc(job.role)}</h3>`,
    );
    parts.push(
      `<p style="font-size:8.5pt;font-weight:700;margin:0;color:#718096;white-space:nowrap;">${esc(job.period)}</p>`,
    );
    parts.push(`</div>`);
    parts.push(
      `<ul style="margin:3pt 0 0;padding-left:16px;font-size:9pt;color:#222;">`,
    );
    for (const b of job.bullets) {
      parts.push(`<li style="margin:0 0 2pt;">${esc(b)}</li>`);
    }
    parts.push(`</ul></div>`);
  }

  const skillRows: [string, string][] = [
    [copy.frontend, s.frontend],
    [copy.styling, s.styling],
    [copy.backend, s.backend],
    [copy.state, s.state],
    [copy.cloud, s.cloud],
    [copy.mobile, s.mobile],
    [copy.architecture, s.architecture],
    [copy.testing, s.testing],
    [copy.quality, s.quality],
  ];

  parts.push(sectionTitle(copy.skills));
  for (const [label, val] of skillRows) {
    if (!val?.trim()) continue;
    parts.push(
      `<p style="font-size:9.5pt;margin:0 0 4pt;color:#222;"><strong>${esc(label)}:</strong> ${esc(val)}</p>`,
    );
  }

  parts.push(sectionTitle(copy.education));
  parts.push(
    `<p style="font-size:9.5pt;margin:0 0 8pt;color:#222;">${esc(data.education)}</p>`,
  );

  parts.push(sectionTitle(copy.certifications));
  parts.push(
    `<ul style="margin:0;padding-left:16px;font-size:9pt;color:#222;">`,
  );
  for (const c of data.certifications) {
    parts.push(`<li style="margin:0 0 2pt;">${esc(c)}</li>`);
  }
  parts.push(`</ul></div>`);

  return parts.join("");
}
