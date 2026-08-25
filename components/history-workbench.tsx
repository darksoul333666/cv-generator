"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { getCvHistoryItem, listCvHistory } from "@/lib/api";
import { pickCvData, type HistoryDetail, type HistorySummary } from "@/lib/cv-types";
import { downloadCvPdfWithPuppeteer } from "@/lib/pdf-client";
import { CVTemplate } from "./cv-template";

function formatWhen(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("es-MX", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function HistoryWorkbench() {
  const searchParams = useSearchParams();
  const requestedId = searchParams.get("id");
  const [items, setItems] = useState<HistorySummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(requestedId);
  const [detail, setDetail] = useState<HistoryDetail | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoadingList(true);
    listCvHistory()
      .then((res) => {
        if (cancelled) return;
        setItems(res.items);
        setSelectedId((current) => current || requestedId || res.items[0]?.id || null);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "No se pudo cargar el historial");
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingList(false);
      });
    return () => {
      cancelled = true;
    };
  }, [requestedId]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    setLoadingDetail(true);
    setError(null);
    getCvHistoryItem(selectedId)
      .then((item) => {
        if (!cancelled) setDetail(item);
      })
      .catch((err) => {
        if (!cancelled) {
          setDetail(null);
          setError(err instanceof Error ? err.message : "No se pudo abrir ese CV");
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingDetail(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const onDownload = useCallback(async () => {
    const cv = detail?.cv;
    if (!cv) return;
    const safe = cv.name.replace(/\s+/g, "_");
    try {
      await downloadCvPdfWithPuppeteer(cv, `CV_${safe}.pdf`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al generar PDF");
    }
  }, [detail]);

  const selected = useMemo(
    () => items.find((item) => item.id === selectedId) || null,
    [items, selectedId],
  );

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 py-10">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">
            Historial
          </h1>
          <p className="max-w-2xl text-sm leading-relaxed text-zinc-600">
            Cada CV generado se guarda con la vacante. Úsalo para recordar a qué
            puesto aplicaste si concretan una entrevista.
          </p>
        </div>
        <Link
          href="/"
          className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-900 hover:bg-zinc-100"
        >
          Volver al generador
        </Link>
      </header>

      {error ? (
        <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
          {error}
        </p>
      ) : null}

      {loadingList ? (
        <p className="text-sm text-zinc-500">Cargando historial…</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-zinc-600">
          Aún no hay CVs guardados. Genera uno desde la vacante y aparecerá aquí.
        </p>
      ) : (
        <section className="grid gap-6 lg:grid-cols-[minmax(16rem,18rem)_minmax(0,1fr)]">
          <ul className="max-h-[720px] space-y-2 overflow-auto rounded-xl border border-zinc-200 bg-white p-3">
            {items.map((item) => {
              const active = item.id === selectedId;
              return (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(item.id)}
                    className={`w-full rounded-lg px-3 py-2 text-left text-sm transition ${
                      active
                        ? "bg-zinc-900 text-white"
                        : "bg-zinc-50 text-zinc-800 hover:bg-zinc-100"
                    }`}
                  >
                    <span className="line-clamp-2 font-medium">{item.vacancy_title}</span>
                    <span className={`mt-1 block text-xs ${active ? "text-zinc-300" : "text-zinc-500"}`}>
                      {formatWhen(item.created_at)}
                      {item.target_role ? ` · ${item.target_role}` : ""}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>

          <div className="space-y-4">
            {loadingDetail ? (
              <p className="text-sm text-zinc-500">Cargando CV…</p>
            ) : detail ? (
              <>
                <div className="space-y-3 rounded-xl border border-zinc-200 bg-zinc-50/80 p-5 text-sm">
                  <h2 className="text-base font-semibold text-zinc-900">
                    {detail.vacancy_title}
                  </h2>
                  {selected ? (
                    <p className="text-xs text-zinc-500">{formatWhen(detail.created_at)}</p>
                  ) : null}
                  <p className="text-zinc-700">
                    <span className="font-medium">Match:</span>{" "}
                    {detail.match_percent.toFixed(0)}%
                    {detail.reason ? ` · ${detail.reason}` : ""}
                  </p>
                  <div>
                    <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                      Vacante
                    </p>
                    <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded-md border border-zinc-200 bg-white p-3 text-xs text-zinc-700">
                      {detail.vacancy_text}
                    </pre>
                  </div>
                  <button
                    type="button"
                    onClick={onDownload}
                    className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-900 hover:bg-zinc-100"
                  >
                    Descargar PDF
                  </button>
                </div>
                <div className="max-h-[720px] overflow-auto rounded-xl border border-zinc-200 bg-white shadow-inner">
                  <CVTemplate data={pickCvData(detail.cv)} />
                </div>
              </>
            ) : (
              <p className="text-sm text-zinc-600">Selecciona un CV de la lista.</p>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
