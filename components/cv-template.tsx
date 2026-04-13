import type { CSSProperties, ReactNode } from "react";
import type { CVData } from "@/lib/cv-types";

const styles: Record<string, CSSProperties> = {
  page: {
    fontFamily: "Arial, sans-serif",
    padding: "40px",
    maxWidth: "800px",
    margin: "0 auto",
    color: "#000",
    background: "#fff",
  },
  name: {
    fontSize: "26px",
    fontWeight: "bold",
    marginBottom: "4px",
  },
  title: {
    fontSize: "14px",
    marginBottom: "10px",
  },
  contact: {
    display: "flex",
    flexDirection: "column",
    gap: "2px",
    marginBottom: "20px",
    fontSize: "12px",
  },
  section: {
    marginBottom: "20px",
  },
  sectionTitle: {
    fontSize: "16px",
    fontWeight: "bold",
    borderBottom: "1px solid #000",
    marginBottom: "8px",
  },
  job: {
    marginBottom: "12px",
  },
  jobTitle: {
    fontSize: "14px",
    fontWeight: "bold",
  },
  period: {
    fontSize: "12px",
    marginBottom: "6px",
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
        <p>{data.summary}</p>
      </Section>

      <Section title="Experiencia Profesional">
        {data.experience.map((job, i) => (
          <div key={i} style={styles.job}>
            <h3 style={styles.jobTitle}>
              {job.company} — {job.role}
            </h3>
            <p style={styles.period}>{job.period}</p>
            <ul>
              {job.bullets.map((b, j) => (
                <li key={j}>{b}</li>
              ))}
            </ul>
          </div>
        ))}
      </Section>

      <Section title="Stack Tecnológico">
        <p>
          <strong>Frontend:</strong> {data.stack.frontend}
        </p>
        <p>
          <strong>Backend:</strong> {data.stack.backend}
        </p>
        <p>
          <strong>State Management:</strong> {data.stack.state}
        </p>
        <p>
          <strong>Cloud & DevOps:</strong> {data.stack.cloud}
        </p>
        <p>
          <strong>Mobile:</strong> {data.stack.mobile}
        </p>
        <p>
          <strong>Architecture:</strong> {data.stack.architecture}
        </p>
        <p>
          <strong>Testing:</strong> {data.stack.testing}
        </p>
        <p>
          <strong>Code Quality:</strong> {data.stack.quality}
        </p>
      </Section>

      <Section title="Formación Académica">
        <p>{data.education}</p>
      </Section>

      <Section title="Certifications and Achievements">
        <ul>
          {data.certifications.map((c, i) => (
            <li key={i}>{c}</li>
          ))}
        </ul>
      </Section>
    </div>
  );
}
