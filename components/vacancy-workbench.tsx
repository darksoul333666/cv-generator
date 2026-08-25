"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { optimizeCv } from "@/lib/api";
import { pickCvData, type TailorResponse } from "@/lib/cv-types";
import { downloadCvPdfWithPuppeteer } from "@/lib/pdf-client";
import { CVTemplate } from "./cv-template";
import { VacancySourcePanel } from "./vacancy-source-panel";

export function VacancyWorkbench() {
  const [text, setText] = useState("");
  const [generating, setGenerating] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TailorResponse | null>(null);

  useEffect(() => {
    if (!generating) {
      setElapsed(0);
      return;
    }
    const started = Date.now();
    const id = window.setInterval(() => {
      setElapsed(Math.floor((Date.now() - started) / 1000));
    }, 500);
    return () => window.clearInterval(id);
  }, [generating]);

  const canGenerate = Boolean(text.trim());

  const onGenerate = useCallback(async () => {
    if (!text.trim()) {
      setError("Pega la descripción de la vacante.");
      return;
    }
    setError(null);
    setGenerating(true);
    setResult(null);
    try {
      const tailored = await optimizeCv(text.trim());
      setResult(tailored);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al generar el CV");
    } finally {
      setGenerating(false);
    }
  }, [text]);

  const onDownload = useCallback(async () => {
    const cv = result?.cv;
    if (!cv) return;
    const safe = cv.name.replace(/\s+/g, "_");
    try {
      await downloadCvPdfWithPuppeteer(cv, `CV_${safe}.pdf`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al generar PDF");
    }
  }, [result]);

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-10 px-4 py-10">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">
            Generar CV
          </h1>
          <p className="max-w-2xl text-sm leading-relaxed text-zinc-600">
            Pega la vacante. Ollama arma el CV con tu perfil maestro, sin inventar
            experiencia.
          </p>
        </div>
        <Link
          href="/skills"
          className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-900 hover:bg-zinc-100"
        >
          Skills
        </Link>
      </header>

      <section className="flex flex-col gap-4 rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
        <VacancySourcePanel
          text={text}
          onTextChange={setText}
          disabled={generating}
        />
        <div>
          <button
            type="button"
            onClick={onGenerate}
            disabled={generating || !canGenerate}
            className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-60"
          >
            {generating ? `Generando… ${elapsed}s` : "Generar CV"}
          </button>
        </div>
        {error ? (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
            {error}
          </p>
        ) : null}
      </section>

      {result ? (
        <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <div className="space-y-3 rounded-xl border border-zinc-200 bg-zinc-50/80 p-5 text-sm">
            <h2 className="text-base font-semibold text-zinc-900">CV para esta vacante</h2>
            <p className="text-zinc-700">
              <span className="font-medium">Match:</span> {result.match_percent.toFixed(0)}%
            </p>
            {result.reason ? (
              <p className="text-zinc-600">{result.reason}</p>
            ) : null}
            {result.gaps?.length ? (
              <div>
                <p className="text-xs font-medium text-zinc-700">La vacante pide y no está en tu perfil:</p>
                <ul className="mt-1 list-disc pl-5 text-xs text-zinc-600">
                  {result.gaps.slice(0, 8).map((g, i) => (
                    <li key={i}>{g}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            <button
              type="button"
              onClick={onDownload}
              className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-900 hover:bg-zinc-100"
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
