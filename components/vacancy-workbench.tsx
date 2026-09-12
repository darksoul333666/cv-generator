"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { enqueueCv, renameCvHistoryItem } from "@/lib/api";
import { defaultCvSaveName, docxDownloadName, pdfDownloadName } from "@/lib/cv-filename";
import { pickCvData, type TailorResponse } from "@/lib/cv-types";
import { downloadCvDocx } from "@/lib/docx-client";
import { downloadCvPdfWithPuppeteer } from "@/lib/pdf-client";
import { CVTemplate } from "./cv-template";
import { useDailyGoal } from "./daily-goal";
import { VacancySourcePanel } from "./vacancy-source-panel";

export function VacancyWorkbench() {
  const [text, setText] = useState("");
  const [generating, setGenerating] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TailorResponse | null>(null);
  const [cvName, setCvName] = useState("");
  const [queueNote, setQueueNote] = useState<string | null>(null);
  const { refresh: refreshGoal } = useDailyGoal();
  const cvNameRef = useRef<HTMLInputElement>(null);

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

  useEffect(() => {
    if (!result) return;
    cvNameRef.current?.focus();
    cvNameRef.current?.select();
  }, [result]);

  const canGenerate = Boolean(text.trim());

  const persistName = useCallback(async (name: string, savedId?: string | null) => {
    const trimmed = name.trim();
    if (!trimmed || !savedId) return;
    try {
      await renameCvHistoryItem(savedId, trimmed);
    } catch {
      /* el PDF igual usa el nombre local */
    }
  }, []);

  const onGenerate = useCallback(async () => {
    if (!text.trim()) {
      setError("Pega la descripción de la vacante.");
      return;
    }
    setError(null);
    setGenerating(true);
    setResult(null);
    setCvName("");
    setQueueNote(null);
    try {
      const queued = await enqueueCv(text.trim());
      const n = queued.queued ?? queued.pending;
      const size = queued.batch_size ?? 5;
      setQueueNote(queued.message || `Lote ${n}/${size}`);
      void refreshGoal();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al encolar la vacante");
    } finally {
      setGenerating(false);
    }
  }, [text, refreshGoal]);

  const onDownload = useCallback(async () => {
    const cv = result?.cv;
    if (!cv) return;
    const name = cvName.trim() || defaultCvSaveName(cv.name, cv.title);
    await persistName(name, result.saved_id);
    try {
      await downloadCvPdfWithPuppeteer(cv, pdfDownloadName(name));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al generar PDF");
    }
  }, [result, cvName, persistName]);

  const onDownloadDocx = useCallback(async () => {
    const cv = result?.cv;
    if (!cv) return;
    const name = cvName.trim() || defaultCvSaveName(cv.name, cv.title);
    await persistName(name, result.saved_id);
    try {
      await downloadCvDocx(cv, docxDownloadName(name));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al generar DOCX");
    }
  }, [result, cvName, persistName]);

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-10 px-4 py-10">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">
          Generar CV
        </h1>
        <p className="max-w-2xl text-sm leading-relaxed text-zinc-600">
          Pega la vacante: entra al lote (hasta 5). Al llenarse se generan juntas;
          si hay menos, genera el lote desde Historial. Ctrl + Enter añade.
        </p>
      </header>

      <section
        className="flex flex-col gap-4 rounded-xl border border-zinc-200 bg-white p-6 shadow-sm"
        aria-busy={generating}
      >
        <VacancySourcePanel
          text={text}
          onTextChange={setText}
          disabled={generating}
          autoFocus
          onModEnter={() => {
            if (canGenerate && !generating) void onGenerate();
          }}
        />
        <div>
          <button
            type="button"
            onClick={onGenerate}
            disabled={generating || !canGenerate}
            aria-keyshortcuts="Control+Enter"
            aria-describedby="generate-hint"
            className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-60"
          >
            {generating ? "Añadiendo…" : "Añadir al lote"}
          </button>
          <p id="generate-hint" className="mt-2 text-xs text-zinc-500">
            Atajo: Ctrl + Enter · el lote se genera a 5 o desde Historial
          </p>
        </div>
        {queueNote ? (
          <p className="rounded-md bg-teal-50 px-3 py-2 text-sm text-teal-900">
            {queueNote}{" "}
            <Link href="/historial" className="font-medium underline hover:text-teal-950">
              Abrir historial
            </Link>
          </p>
        ) : null}
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
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                Nombre del CV
              </span>
              <input
                ref={cvNameRef}
                type="text"
                value={cvName}
                onChange={(e) => setCvName(e.target.value)}
                onBlur={() => persistName(cvName, result.saved_id)}
                className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm text-zinc-900 outline-none ring-zinc-400 focus:ring-2"
              />
            </label>
            <p className="text-zinc-700">
              <span className="font-medium">Perfil:</span> {result.cv.title || result.cv.label}
            </p>
            <p className="text-zinc-700">
              <span className="font-medium">Match:</span> {result.match_percent.toFixed(0)}%
            </p>
            {result.company_name ? (
              <p className="text-zinc-700">
                <span className="font-medium">Empresa:</span> {result.company_name}
              </p>
            ) : null}
            {result.vacancy_url ? (
              <p className="truncate text-zinc-700">
                <span className="font-medium">Vacante:</span>{" "}
                <a
                  href={result.vacancy_url}
                  target="_blank"
                  rel="noreferrer"
                  className="underline hover:text-zinc-900"
                >
                  {result.vacancy_url}
                </a>
              </p>
            ) : null}
            {result.reason ? (
              <p className="text-zinc-600">{result.reason}</p>
            ) : null}
            {result.saved_id ? (
              <p className="text-xs text-zinc-500">
                Guardado en{" "}
                <Link
                  href={`/historial?id=${encodeURIComponent(result.saved_id)}`}
                  className="underline hover:text-zinc-800"
                >
                  historial
                </Link>{" "}
                con la vacante, para revisarlo si hay entrevista.
              </p>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={onDownload}
                className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-900 hover:bg-zinc-100"
              >
                Descargar PDF
              </button>
              <button
                type="button"
                onClick={onDownloadDocx}
                className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-900 hover:bg-zinc-100"
              >
                Descargar DOCX
              </button>
            </div>
          </div>
          <div className="max-h-[720px] overflow-auto rounded-xl border border-zinc-200 bg-white shadow-inner">
            <CVTemplate data={pickCvData(result.cv)} />
          </div>
        </section>
      ) : null}
    </div>
  );
}
