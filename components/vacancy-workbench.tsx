"use client";

import { useCallback, useState } from "react";
import { matchVacancy } from "@/lib/api";
import { pickCvData, type MatchResponse } from "@/lib/cv-types";
import { CVTemplate } from "./cv-template";
import { downloadCvPdfWithPuppeteer } from "@/lib/pdf-client";

export function VacancyWorkbench() {
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MatchResponse | null>(null);

  const onSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);
      setLoading(true);
      setResult(null);
      try {
        const data = await matchVacancy({
          vacancy_text: text,
          vacancy_url: url.trim() || undefined,
        });
        setResult(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Error desconocido");
      } finally {
        setLoading(false);
      }
    },
    [text, url],
  );

  const onDownload = useCallback(async () => {
    if (!result) return;
    const safe = result.cv.name.replace(/\s+/g, "_");
    try {
      await downloadCvPdfWithPuppeteer(
        result.cv,
        `CV_${safe}_${result.chosen_cv_id}.pdf`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al generar PDF");
    }
  }, [result]);

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-10 px-4 py-10">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">
          Generador de CV (plantilla React + PDF)
        </h1>
        <p className="max-w-2xl text-sm leading-relaxed text-zinc-600">
          Pega el texto de la vacante y, si quieres, una URL para que el backend
          extraiga más contexto. La API elige el perfil base más alineado entre
          tus tres CV; la vista previa y el PDF usan la misma plantilla React
          (HTML vía{" "}
          <code className="rounded bg-zinc-100 px-1">cv-template-html</code> y
          Puppeteer en{" "}
          <code className="rounded bg-zinc-100 px-1">/api/pdf</code>).
        </p>
      </header>

      <form
        onSubmit={onSubmit}
        className="flex flex-col gap-4 rounded-xl border border-zinc-200 bg-white p-6 shadow-sm"
      >
        <label className="flex flex-col gap-1.5 text-sm">
          <span className="font-medium text-zinc-800">URL de la vacante (opcional)</span>
          <input
            type="url"
            name="vacancy_url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://..."
            className="rounded-lg border border-zinc-300 px-3 py-2 text-zinc-900 outline-none ring-zinc-400 focus:ring-2"
          />
        </label>
        <label className="flex flex-col gap-1.5 text-sm">
          <span className="font-medium text-zinc-800">Texto de la vacante</span>
          <textarea
            name="vacancy_text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={10}
            placeholder="Pega aquí el enunciado completo de la oferta..."
            className="rounded-lg border border-zinc-300 px-3 py-2 font-mono text-sm text-zinc-900 outline-none ring-zinc-400 focus:ring-2"
          />
        </label>
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-60"
          >
            {loading ? "Analizando…" : "Obtener CV recomendado"}
          </button>
          <span className="text-xs text-zinc-500">
            API Python: <code className="rounded bg-zinc-100 px-1">/v1/match</code>
          </span>
        </div>
        {error ? (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
            {error}
          </p>
        ) : null}
      </form>

      {result ? (
        <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <div className="space-y-3 rounded-xl border border-zinc-200 bg-zinc-50/80 p-5 text-sm">
            <h2 className="text-base font-semibold text-zinc-900">Resultado</h2>
            <p className="text-zinc-700">
              <span className="font-medium">Perfil elegido:</span>{" "}
              {result.cv.label}{" "}
              <span className="text-zinc-500">({result.chosen_cv_id})</span>
            </p>
            <p className="text-zinc-700">
              <span className="font-medium">Puntuación:</span>{" "}
              {result.match_score.toFixed(1)}
            </p>
            <p className="text-zinc-600">{result.match_reason}</p>
            {result.raw_meta?.matcher ? (
              <p className="text-xs text-zinc-500">
                Motor:{" "}
                <span className="font-medium text-zinc-600">
                  {String(result.raw_meta.matcher)}
                </span>
                {result.raw_meta.gemini_model
                  ? ` (${String(result.raw_meta.gemini_model)})`
                  : null}
              </p>
            ) : null}
            <button
              type="button"
              onClick={onDownload}
              className="mt-2 rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-900 hover:bg-zinc-100"
            >
              Descargar PDF
            </button>
          </div>
          <div className="max-h-[720px] overflow-auto rounded-xl border border-zinc-200 bg-white shadow-inner">
            <CVTemplate data={pickCvData(result.cv)} />
          </div>
        </section>
      ) : null}
    </div>
  );
}
