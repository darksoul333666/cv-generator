export function defaultCvSaveName(personName: string, profileLabel: string): string {
  const name = personName.replace(/\s+/g, " ").trim();
  const profile = profileLabel.split(/[—–]/)[0].replace(/\s+/g, " ").trim();
  if (name && profile) return `${name} - ${profile}`;
  return name || profile || "CV";
}

export function pdfDownloadName(cvName: string): string {
  const safe =
    cvName.replace(/[\\/:*?"<>|]+/g, " ").replace(/\s+/g, " ").trim() || "CV";
  return /\.pdf$/i.test(safe) ? safe : `${safe}.pdf`;
}
