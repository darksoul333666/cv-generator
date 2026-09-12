import {
  AlignmentType,
  BorderStyle,
  Document,
  LevelFormat,
  Packer,
  Paragraph,
  TabStopPosition,
  TabStopType,
  TextRun,
} from "docx";
import type { CVData } from "./cv-types";
import { cvCopy, cvLocale } from "./cv-copy";

const NAVY = "1A365D";
const BLUE = "2B6CB0";
const MUTED = "4A5568";
const JOB = "2D3748";
const PERIOD = "718096";
const BODY = "222222";
const RULE = "CBD5E0";

function run(
  text: string,
  opts: {
    bold?: boolean;
    size: number;
    color?: string;
    allCaps?: boolean;
  },
): TextRun {
  return new TextRun({
    text,
    font: "Arial",
    bold: opts.bold,
    size: opts.size,
    color: opts.color || BODY,
    allCaps: opts.allCaps,
  });
}

function sectionTitle(text: string): Paragraph {
  return new Paragraph({
    spacing: { before: 240, after: 120 },
    border: {
      bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE, space: 4 },
    },
    children: [run(text, { bold: true, size: 21, color: NAVY, allCaps: true })],
  });
}

function bullet(text: string): Paragraph {
  return new Paragraph({
    numbering: { reference: "cv-bullets", level: 0 },
    spacing: { after: 40 },
    children: [run(text, { size: 18 })],
  });
}

export function buildCvDocument(data: CVData): Document {
  const locale = cvLocale(data);
  const copy = cvCopy(locale);
  const contact = [data.email, data.phone, data.linkedin]
    .map((x) => x.trim())
    .filter(Boolean)
    .join("  |  ");
  const children: Paragraph[] = [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 40 },
      children: [run(data.name, { bold: true, size: 36, color: NAVY, allCaps: true })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 80 },
      children: [run(data.title, { bold: true, size: 22, color: BLUE })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 200 },
      children: [run(contact, { size: 17, color: MUTED })],
    }),
    sectionTitle(copy.summary),
    new Paragraph({
      spacing: { after: 160 },
      children: [run(data.summary, { size: 19 })],
    }),
    sectionTitle(copy.experience),
  ];

  for (const job of data.experience) {
    children.push(
      new Paragraph({
        spacing: { before: 80, after: 40 },
        tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
        children: [
          run(`${job.company} — ${job.role}`, { bold: true, size: 19, color: JOB }),
          run(`\t${job.period}`, { bold: true, size: 17, color: PERIOD }),
        ],
      }),
    );
    for (const item of job.bullets) {
      children.push(bullet(item));
    }
  }

  children.push(sectionTitle(copy.skills));
  const skillRows: [string, string][] = [
    [copy.frontend, data.stack.frontend],
    [copy.styling, data.stack.styling],
    [copy.backend, data.stack.backend],
    [copy.state, data.stack.state],
    [copy.cloud, data.stack.cloud],
    [copy.mobile, data.stack.mobile],
    [copy.architecture, data.stack.architecture],
    [copy.testing, data.stack.testing],
    [copy.quality, data.stack.quality],
  ];
  for (const [label, val] of skillRows) {
    if (!val?.trim()) continue;
    children.push(
      new Paragraph({
        spacing: { after: 80 },
        children: [
          run(`${label}: `, { bold: true, size: 19 }),
          run(val, { size: 19 }),
        ],
      }),
    );
  }

  children.push(sectionTitle(copy.education));
  children.push(
    new Paragraph({
      spacing: { after: 160 },
      children: [run(data.education, { size: 19 })],
    }),
  );
  children.push(sectionTitle(copy.certifications));
  for (const cert of data.certifications) {
    children.push(bullet(cert));
  }

  return new Document({
    styles: {
      default: {
        document: {
          run: { font: "Arial" },
        },
      },
    },
    numbering: {
      config: [
        {
          reference: "cv-bullets",
          levels: [
            {
              level: 0,
              format: LevelFormat.BULLET,
              text: "•",
              alignment: AlignmentType.LEFT,
              style: {
                paragraph: { indent: { left: 288, hanging: 180 } },
              },
            },
          ],
        },
      ],
    },
    sections: [
      {
        properties: {
          page: {
            size: { width: 12240, height: 15840 },
            margin: { top: 1008, right: 1008, bottom: 1008, left: 1008 },
          },
        },
        children,
      },
    ],
  });
}

export async function cvToDocxBlob(data: CVData): Promise<Blob> {
  return Packer.toBlob(buildCvDocument(data));
}
