"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { getExtensionJob, listExtensionJobs } from "@/lib/api";
import type { CvProfile, ExtensionJobSummary } from "@/lib/cv-types";
import { pickCvData } from "@/lib/cv-types";
import { downloadCvPdfWithPuppeteer } from "@/lib/pdf-client";
import { CVTemplate } from "@/components/cv-template";

function formatDate(iso: string) {
  try {
    const d = new Date(iso);
    return d.toLocaleString("es", {
      dateStyle: "short",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

export default function ExtensionJobsPage() {
  const [jobs, setJobs] = useState<ExtensionJobSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const { jobs: list } = await listExtensionJobs();
      setJobs(list);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "No se pudo cargar la lista (¿backend en :8000?)",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onDownload = async (job: ExtensionJobSummary) => {
    setDownloadingId(job.id);
    setError(null);
    try {
      const full = await getExtensionJob(job.id);
      const cv = full.tailor.cv;
      const safe = cv.name.replace(/\s+/g, "_");
      await downloadCvPdfWithPuppeteer(
        cv,
        `CV_${safe}_${job.source_site}_${job.id.slice(0, 8)}.pdf`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al descargar PDF");
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-4 py-10">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">
            Vacantes desde la extensión
          </h1>
          <p className="max-w-2xl text-sm leading-relaxed text-zinc-600">
            CV generados con el mismo flujo que «Optimizar CV», guardados en caché del
            backend (archivo en <code className="rounded bg-zinc-100 px-1">backend/.cache/</code>
            , máximo 100 entradas).
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void load()}
            className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-900 hover:bg-zinc-100"
          >
            Actualizar
          </button>
          <Link
            href="/"
            className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-900 hover:bg-zinc-100"
          >
            Volver al generador
          </Link>
        </div>
      </header>

      {error ? (
        <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
          {error}
        </p>
      ) : null}

      {loading ? (
        <p className="text-sm text-zinc-600">Cargando…</p>
      ) : jobs.length === 0 ? (
        <p className="rounded-xl border border-dashed border-zinc-300 bg-zinc-50/80 p-8 text-center text-sm text-zinc-600">
          Aún no hay vacantes en caché. Usa la extensión de Chrome (o{" "}
          <code className="rounded bg-white px-1">POST /v1/extension/optimize</code> con{" "}
          <code className="rounded bg-white px-1">vacancy_text</code>) para enviar la descripción
          de una oferta.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white shadow-sm">
          <table className="w-full min-w-[520px] text-left text-sm">
            <thead className="border-b border-zinc-200 bg-zinc-50 text-xs font-medium uppercase tracking-wide text-zinc-600">
              <tr>
                <th className="px-4 py-3">Vacante</th>
                <th className="px-4 py-3">Origen</th>
                <th className="px-4 py-3">Fecha</th>
                <th className="px-4 py-3 text-right">Acción</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {jobs.map((job) => (
                <tr key={job.id} className="text-zinc-800">
                  <td className="max-w-xs px-4 py-3">
                    <p className="font-medium text-zinc-900">{job.vacancy_title}</p>
                    <p className="mt-0.5 text-xs text-zinc-500">
                      Match {job.match_score.toFixed(1)} · IA {job.tailor_match_percent.toFixed(0)}%
                    </p>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 capitalize">{job.source_site}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-zinc-600">
                    {formatDate(job.created_at)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      type="button"
                      onClick={() => void onDownload(job)}
                      disabled={downloadingId === job.id}
                      className="rounded-lg bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
                    >
                      {downloadingId === job.id ? "PDF…" : "Descargar PDF"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <section className="rounded-xl border border-zinc-200 bg-zinc-50/80 p-5 text-xs text-zinc-600">
        <p className="font-medium text-zinc-800">Vista previa rápida (último CV de la lista)</p>
        {jobs[0] ? (
          <LastJobPreview jobId={jobs[0].id} />
        ) : (
          <p className="mt-2">Genera al menos una vacante para ver la vista previa.</p>
        )}
      </section>
    </div>
  );
}

function LastJobPreview({ jobId }: { jobId: string }) {
  const [cv, setCv] = useState<CvProfile | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const full = await getExtensionJob(jobId);
        if (cancelled) return;
        setCv(full.tailor.cv);
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : "Error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  if (err) return <p className="mt-2 text-red-700">{err}</p>;
  if (!cv) return <p className="mt-2">Cargando vista previa…</p>;
  return (
    <div className="mt-3 max-h-[480px] overflow-auto rounded-lg border border-zinc-200 bg-white shadow-inner">
      <CVTemplate data={pickCvData(cv)} />
    </div>
  );
}
