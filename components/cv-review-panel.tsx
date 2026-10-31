"use client";

import type { CvReview } from "@/lib/cv-types";

function scoreTone(score: number): string {
  if (score >= 9) return "border-emerald-200 bg-emerald-50 text-emerald-900";
  if (score >= 7) return "border-amber-200 bg-amber-50 text-amber-900";
  return "border-red-200 bg-red-50 text-red-900";
}

function coverageTone(percent: number): string {
  if (percent >= 80) return "border-emerald-200 bg-emerald-50 text-emerald-900";
  if (percent >= 60) return "border-amber-200 bg-amber-50 text-amber-900";
  return "border-red-200 bg-red-50 text-red-900";
}

/** Nota de redacción y palabras clave de la vacante, para revisar el CV antes de descargarlo. */
export function CvReviewPanel({ review }: { review: CvReview }) {
  const score = review.quality_score;
  const cov = review.coverage ?? { matched: [], missing: [], percent: null };
  const total = cov.matched.length + cov.missing.length;
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {score != null ? (
        <section className={`rounded-md border p-3 text-xs ${scoreTone(score)}`}>
          <p className="text-sm font-semibold">Redacción: {score.toFixed(1)}/10</p>
          <p className="mt-0.5">
            {review.quality_errors} errores · {review.quality_warnings} avisos
          </p>
          {review.quality_issues.length ? (
            <details className="mt-2">
              <summary className="cursor-pointer font-medium">Ver detalle</summary>
              <ul className="mt-1 list-disc space-y-1 pl-4">
                {review.quality_issues.map((issue, i) => (
                  <li key={i}>{issue}</li>
                ))}
              </ul>
            </details>
          ) : (
            <p className="mt-2">Sin problemas de redacción.</p>
          )}
        </section>
      ) : null}
      {cov.percent != null ? (
        <section className={`rounded-md border p-3 text-xs ${coverageTone(cov.percent)}`}>
          <p className="text-sm font-semibold">
            Palabras clave: {cov.matched.length} de {total} ({cov.percent}%)
          </p>
          {cov.missing.length ? (
            <p className="mt-1">
              <span className="font-medium">Faltan:</span> {cov.missing.join(", ")}
            </p>
          ) : (
            <p className="mt-1">El CV incluye todas las palabras clave detectadas.</p>
          )}
          {cov.matched.length ? (
            <details className="mt-2">
              <summary className="cursor-pointer font-medium">Incluidas</summary>
              <p className="mt-1">{cov.matched.join(", ")}</p>
            </details>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
