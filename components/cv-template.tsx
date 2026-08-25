import type { CVData } from "@/lib/cv-types";
import { cvTemplateToBodyHtml } from "@/lib/cv-template-html";

export function CVTemplate({ data }: { data: CVData }) {
  return (
    <div dangerouslySetInnerHTML={{ __html: cvTemplateToBodyHtml(data) }} />
  );
}
