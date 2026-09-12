function shortTemplateLabel(label: string): string {
  return label.split(/[—–]/)[0].replace(/\s+/g, " ").trim();
}

function safeBaseName(cvName: string): string {
  return (
    cvName
      .replace(/[\\/:*?"<>|]+/g, "-")
      .replace(/\s+/g, " ")
      .replace(/\s*-\s*/g, " - ")
      .trim() || "CV"
  );
}

export function defaultCvSaveName(personName: string, profileTitle: string): string {
  const name = personName.replace(/\s+/g, " ").trim();
  const title = profileTitle.replace(/\s+/g, " ").trim();
  if (name && title) return `${name} - ${title}`;
  return name || title || "CV";
}

/** Prefers the tailored title; ignores legacy names built from the template label. */
export function resolveCvSaveName(opts: {
  personName: string;
  title: string;
  label?: string | null;
  stored?: string | null;
}): string {
  const auto = defaultCvSaveName(opts.personName, opts.title);
  const stored = opts.stored?.trim() || "";
  if (!stored) return auto;
  const legacy = defaultCvSaveName(
    opts.personName,
    shortTemplateLabel(opts.label || ""),
  );
  if (stored === legacy) return auto;
  return stored;
}

export function pdfDownloadName(cvName: string): string {
  const safe = safeBaseName(cvName);
  return /\.pdf$/i.test(safe) ? safe : `${safe}.pdf`;
}

export function docxDownloadName(cvName: string): string {
  const safe = safeBaseName(cvName).replace(/\.pdf$/i, "");
  return /\.docx$/i.test(safe) ? safe : `${safe}.docx`;
}
