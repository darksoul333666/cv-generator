import type { CSSProperties, ReactNode } from "react";
import type { CVData } from "@/lib/cv-types";

const styles: Record<string, CSSProperties> = {
  page: {
    fontFamily: "Arial, sans-serif",
    padding: "40px",
    maxWidth: "800px",
    margin: "0 auto",
    color: "#111",
    background: "#fff",
  },
  name: {
    fontSize: "26px",
    fontWeight: "bold",
    marginBottom: "4px",
  },
  title: {
    fontSize: "13px",
    marginBottom: "14px",
    color: "#333",
  },
  contact: {
    display: "flex",
    flexWrap: "wrap",
    gap: "10px",
    marginBottom: "18px",
    fontSize: "11.5px",
    color: "#222",
  },
  section: {
    marginBottom: "18px",
  },
  sectionTitle: {
    fontSize: "13px",
    fontWeight: 700,
    letterSpacing: "0.04em",
    textTransform: "uppercase",
    borderBottom: "1px solid #111",
    paddingBottom: "6px",
    marginBottom: "10px",
  },
  job: {
    marginBottom: "12px",
  },
  jobTitle: {
    fontSize: "12.5px",
    fontWeight: 700,
  },
  period: {
    fontSize: "11px",
    marginBottom: "6px",
    color: "#333",
  },
  bullets: {
    margin: 0,
    paddingLeft: "18px",
  },
  paragraph: {
    margin: "0 0 8px",
  },
};

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div style={styles.section}>
      <h2 style={styles.sectionTitle}>{title}</h2>
      {children}
    </div>
  );
}

export function CVTemplate({ data }: { data: CVData }) {
  return (
    <div style={styles.page}>
      <h1 style={styles.name}>{data.name}</h1>
      <p style={styles.title}>{data.title}</p>

      <div style={styles.contact}>
        <span>📧 {data.email}</span>
        <span>📱 {data.phone}</span>
        <span>🔗 {data.linkedin}</span>
      </div>

      <Section title="Resumen Profesional">
        <p style={styles.paragraph}>{data.summary}</p>
      </Section>

      <Section title="Experiencia Profesional">
        {data.experience.map((job, i) => (
          <div key={i} style={styles.job}>
            <h3 style={styles.jobTitle}>
              {job.company} — {job.role}
            </h3>
            <p style={styles.period}>{job.period}</p>
            <ul style={styles.bullets}>
              {job.bullets.map((b, j) => (
                <li key={j}>{b}</li>
              ))}
            </ul>
          </div>
        ))}
      </Section>

      <Section title="Stack Tecnológico">
        <p style={styles.paragraph}>
          <strong>Frontend:</strong> {data.stack.frontend}
        </p>
        <p style={styles.paragraph}>
          <strong>Backend:</strong> {data.stack.backend}
        </p>
        <p style={styles.paragraph}>
          <strong>State Management:</strong> {data.stack.state}
        </p>
        <p style={styles.paragraph}>
          <strong>Cloud & DevOps:</strong> {data.stack.cloud}
        </p>
        <p style={styles.paragraph}>
          <strong>Mobile:</strong> {data.stack.mobile}
        </p>
        <p style={styles.paragraph}>
          <strong>Architecture:</strong> {data.stack.architecture}
        </p>
        <p style={styles.paragraph}>
          <strong>Testing:</strong> {data.stack.testing}
        </p>
        <p style={styles.paragraph}>
          <strong>Code Quality:</strong> {data.stack.quality}
        </p>
      </Section>

      <Section title="Formación Académica">
        <p style={styles.paragraph}>{data.education}</p>
      </Section>

      <Section title="Certifications and Achievements">
        <ul style={styles.bullets}>
          {data.certifications.map((c, i) => (
            <li key={i}>{c}</li>
          ))}
        </ul>
      </Section>
    </div>
  );
}
