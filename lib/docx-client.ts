import { pickCvData, type CvProfile } from "./cv-types";
import { cvToDocxBlob } from "./cv-docx";

export async function downloadCvDocx(cv: CvProfile, filename: string): Promise<void> {
  const blob = await cvToDocxBlob(pickCvData(cv));
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
