"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { useSearchParams } from "next/navigation";
import { getCvHistoryItem, listCvHistory, renameCvHistoryItem, retryQueuedCv, flushQueueBatch } from "@/lib/api";
import { defaultCvSaveName, docxDownloadName, pdfDownloadName, resolveCvSaveName } from "@/lib/cv-filename";
import {
  pickCvData,
  type HistoryDetail,
  type HistoryJobStatus,
  type HistorySummary,
} from "@/lib/cv-types";
import { localDayKey } from "@/lib/daily-goal";
import { downloadCvDocx } from "@/lib/docx-client";
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

function jobStatus(item: { status?: HistoryJobStatus | string | null }): HistoryJobStatus {
  const s = item.status;
  if (s === "queued" || s === "generating" || s === "error") return s;
  return "ready";
}

function statusLabel(status: HistoryJobStatus, position?: number | null): string {
  if (status === "queued") {
    return position ? `En lote · #${position}` : "En lote";
  }
  if (status === "generating") return "Generando…";
  if (status === "error") return "Error";
  return "Listo";
}

function itemDayKey(iso: string): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "";
  return localDayKey(new Date(t));
}

function uniqueSorted(values: string[]): string[] {
  return [...new Set(values.map((v) => v.trim()).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b, "es"),
  );
}

function matchesFilters(
  item: HistorySummary,
  filters: { dateFrom: string; dateTo: string; company: string; role: string },
): boolean {
  const day = itemDayKey(item.created_at);
  if (filters.dateFrom && day && day < filters.dateFrom) return false;
  if (filters.dateTo && day && day > filters.dateTo) return false;
  if (filters.dateFrom && !day) return false;
  if (filters.company && (item.company_name || "").trim() !== filters.company) {
    return false;
  }
  if (filters.role) {
    const title = (item.vacancy_title || "").trim();
    const target = (item.target_role || "").trim();
    if (title !== filters.role && target !== filters.role) return false;
  }
  return true;
}

export function HistoryWorkbench() {
  const searchParams = useSearchParams();
  const requestedId = searchParams.get("id");
  const [items, setItems] = useState<HistorySummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(requestedId);
  const [detail, setDetail] = useState<HistoryDetail | null>(null);
  const [cvName, setCvName] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [flushing, setFlushing] = useState(false);
  const [batchSize, setBatchSize] = useState(5);
  const [queuedCount, setQueuedCount] = useState(0);
  const [generatingCount, setGeneratingCount] = useState(0);
  const dateFromRef = useRef<HTMLInputElement>(null);
  const itemRefs = useRef(new Map<string, HTMLButtonElement>());
  const didAutofocus = useRef(false);

  const refreshList = useCallback(async (silent = false) => {
    if (!silent) setLoadingList(true);
    try {
      const res = await listCvHistory();
      setItems(res.items);
      setBatchSize(res.batch_size || 5);
      setQueuedCount(res.queued_count ?? 0);
      setGeneratingCount(res.generating_count ?? 0);
      setSelectedId((current) => current || requestedId || res.items[0]?.id || null);
    } catch (err) {
      if (!silent) {
        setError(err instanceof Error ? err.message : "No se pudo cargar el historial");
      }
    } finally {
      if (!silent) setLoadingList(false);
    }
  }, [requestedId]);

  useEffect(() => {
    void refreshList(false);
  }, [refreshList]);

  const hasPending = items.some((item) => {
    const s = jobStatus(item);
    return s === "queued" || s === "generating";
  });

  useEffect(() => {
    if (!hasPending) return;
    const timer = window.setInterval(() => {
      void refreshList(true);
    }, 4000);
    return () => window.clearInterval(timer);
  }, [hasPending, refreshList]);

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
        if (cancelled) return;
        setDetail(item);
        if (item.cv) {
          setCvName(
            resolveCvSaveName({
              personName: item.cv.name,
              title: item.cv.title,
              label: item.cv.label,
              stored: item.cv_name,
            }),
          );
        } else {
          setCvName(item.cv_name || item.vacancy_title || "");
        }
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
  }, [selectedId, items.find((item) => item.id === selectedId)?.status]);

  const persistName = useCallback(async (name: string, id?: string | null) => {
    const trimmed = name.trim();
    if (!trimmed || !id) return;
    try {
      const updated = await renameCvHistoryItem(id, trimmed);
      setItems((prev) =>
        prev.map((item) =>
          item.id === id ? { ...item, cv_name: updated.cv_name } : item,
        ),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar el nombre");
    }
  }, []);

  const onDownload = useCallback(async () => {
    const cv = detail?.cv;
    if (!cv) return;
    const name =
      cvName.trim() || defaultCvSaveName(cv.name, cv.title);
    await persistName(name, detail.id);
    try {
      await downloadCvPdfWithPuppeteer(cv, pdfDownloadName(name));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al generar PDF");
    }
  }, [detail, cvName, persistName]);

  const onDownloadDocx = useCallback(async () => {
    const cv = detail?.cv;
    if (!cv) return;
    const name =
      cvName.trim() || defaultCvSaveName(cv.name, cv.title);
    await persistName(name, detail.id);
    try {
      await downloadCvDocx(cv, docxDownloadName(name));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al generar DOCX");
    }
  }, [detail, cvName, persistName]);

  const onFlushBatch = useCallback(async () => {
    setFlushing(true);
    setError(null);
    try {
      await flushQueueBatch();
      await refreshList(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo generar el lote");
    } finally {
      setFlushing(false);
    }
  }, [refreshList]);

  const onRetry = useCallback(async () => {
    if (!detail || jobStatus(detail) !== "error") return;
    setRetrying(true);
    setError(null);
    try {
      await retryQueuedCv(detail.id);
      await refreshList(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo reintentar");
    } finally {
      setRetrying(false);
    }
  }, [detail, refreshList]);

  const selected = useMemo(
    () => items.find((item) => item.id === selectedId) || null,
    [items, selectedId],
  );

  const companies = useMemo(
    () => uniqueSorted(items.map((item) => item.company_name || "")),
    [items],
  );
  const roles = useMemo(
    () =>
      uniqueSorted([
        ...items.map((item) => item.vacancy_title || ""),
        ...items.map((item) => item.target_role || ""),
      ]),
    [items],
  );
  const hasActiveFilters = Boolean(dateFrom || dateTo || company || role);

  const filtered = useMemo(
    () =>
      items
        .filter((item) =>
          matchesFilters(item, { dateFrom, dateTo, company, role }),
        )
        .sort((a, b) => {
          const ta = Date.parse(a.created_at) || 0;
          const tb = Date.parse(b.created_at) || 0;
          return tb - ta;
        }),
    [items, dateFrom, dateTo, company, role],
  );

  const clearFilters = useCallback(() => {
    setDateFrom("");
    setDateTo("");
    setCompany("");
    setRole("");
    dateFromRef.current?.focus();
  }, []);

  const focusItem = useCallback((id: string) => {
    const el = itemRefs.current.get(id);
    el?.focus();
    el?.scrollIntoView({ block: "nearest" });
  }, []);

  const onListKeyDown = useCallback(
    (event: KeyboardEvent<HTMLButtonElement>, fromId: string) => {
      if (!filtered.length) return;
      const idx = filtered.findIndex((item) => item.id === fromId);
      if (idx < 0) return;
      let next = idx;
      if (event.key === "ArrowDown") next = Math.min(filtered.length - 1, idx + 1);
      else if (event.key === "ArrowUp") next = Math.max(0, idx - 1);
      else if (event.key === "Home") next = 0;
      else if (event.key === "End") next = filtered.length - 1;
      else if (event.key === "Escape") {
        event.preventDefault();
        dateFromRef.current?.focus();
        return;
      } else return;
      event.preventDefault();
      const item = filtered[next];
      if (!item) return;
      setSelectedId(item.id);
      requestAnimationFrame(() => focusItem(item.id));
    },
    [filtered, focusItem],
  );

  useEffect(() => {
    if (loadingList || items.length === 0 || didAutofocus.current) return;
    didAutofocus.current = true;
    dateFromRef.current?.focus();
  }, [loadingList, items.length]);

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 py-10">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">
          Historial
        </h1>
        <p className="max-w-2xl text-sm leading-relaxed text-zinc-600">
          Las vacantes se acumulan en un lote de 5. Al llenarse se generan
          juntas; si hay menos, pulsa Generar lote. Flechas, Inicio y Fin
          recorren la lista.
        </p>
        {queuedCount > 0 || generatingCount > 0 ? (
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <p className="text-sm text-zinc-700">
              {generatingCount > 0
                ? `Generando lote de ${generatingCount}…`
                : `Lote ${queuedCount}/${batchSize}`}
            </p>
            {queuedCount > 0 && generatingCount === 0 ? (
              <button
                type="button"
                onClick={() => void onFlushBatch()}
                disabled={flushing}
                className="rounded-lg bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
              >
                {flushing
                  ? "Enviando…"
                  : `Generar ${queuedCount} ahora`}
              </button>
            ) : null}
          </div>
        ) : null}
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
        <section className="grid gap-6 lg:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)]">
          <div className="flex max-h-[720px] flex-col gap-2 rounded-xl border border-zinc-200 bg-white p-3">
            <form
              className="flex flex-col gap-2"
              aria-label="Filtros del historial"
              onSubmit={(e) => e.preventDefault()}
              onKeyDown={(e) => {
                if (e.key === "Escape" && hasActiveFilters) {
                  e.preventDefault();
                  clearFilters();
                }
              }}
            >
                <div className="grid grid-cols-2 gap-2">
                  <label className="flex flex-col gap-1">
                    <span className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">
                      Desde
                    </span>
                    <input
                      ref={dateFromRef}
                      type="date"
                      value={dateFrom}
                      onChange={(e) => setDateFrom(e.target.value)}
                      className="rounded-lg border border-zinc-300 bg-white px-2 py-1.5 text-sm text-zinc-900 outline-none ring-zinc-400 focus:ring-2"
                    />
                  </label>
                  <label className="flex flex-col gap-1">
                    <span className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">
                      Hasta
                    </span>
                    <input
                      type="date"
                      value={dateTo}
                      min={dateFrom || undefined}
                      onChange={(e) => setDateTo(e.target.value)}
                      className="rounded-lg border border-zinc-300 bg-white px-2 py-1.5 text-sm text-zinc-900 outline-none ring-zinc-400 focus:ring-2"
                    />
                  </label>
                </div>
                <label className="flex flex-col gap-1">
                  <span className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">
                    Empresa
                  </span>
                  <select
                    value={company}
                    onChange={(e) => setCompany(e.target.value)}
                    className="rounded-lg border border-zinc-300 bg-white px-2 py-1.5 text-sm text-zinc-900 outline-none ring-zinc-400 focus:ring-2"
                  >
                    <option value="">Todas</option>
                    {companies.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1">
                  <span className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">
                    Puesto
                  </span>
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    className="rounded-lg border border-zinc-300 bg-white px-2 py-1.5 text-sm text-zinc-900 outline-none ring-zinc-400 focus:ring-2"
                  >
                    <option value="">Todos</option>
                    {roles.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                </label>
            </form>
            {hasActiveFilters ? (
              <button
                type="button"
                onClick={clearFilters}
                className="self-start text-xs font-medium text-zinc-600 underline underline-offset-2 hover:text-zinc-900"
              >
                Quitar filtros
              </button>
            ) : null}
            {filtered.length === 0 ? (
              <p className="px-1 py-2 text-sm text-zinc-500">
                {hasActiveFilters
                  ? "Nada coincide con esos filtros."
                  : "No hay CVs en el historial."}
              </p>
            ) : (
              <ul
                className="min-h-0 flex-1 space-y-2 overflow-auto"
                role="listbox"
                aria-label="CVs generados"
              >
                {filtered.map((item) => {
                  const active = item.id === selectedId;
                  const tabStop =
                    selectedId && filtered.some((entry) => entry.id === selectedId)
                      ? item.id === selectedId
                      : item.id === filtered[0]?.id;
                  return (
                    <li key={item.id} role="presentation">
                      <button
                        id={`historial-${item.id}`}
                        ref={(el) => {
                          if (el) itemRefs.current.set(item.id, el);
                          else itemRefs.current.delete(item.id);
                        }}
                        type="button"
                        role="option"
                        aria-selected={active}
                        tabIndex={tabStop ? 0 : -1}
                        onClick={() => setSelectedId(item.id)}
                        onKeyDown={(e) => onListKeyDown(e, item.id)}
                        className={`w-full rounded-lg px-3 py-2 text-left text-sm transition ${
                          active
                            ? "bg-zinc-900 text-white"
                            : "bg-zinc-50 text-zinc-800 hover:bg-zinc-100"
                        }`}
                      >
                        <span className="line-clamp-2 font-medium">
                          {item.cv_name || item.target_role || item.vacancy_title}
                        </span>
                        {jobStatus(item) !== "ready" ? (
                          <span
                            className={`mt-1 inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                              jobStatus(item) === "error"
                                ? active
                                  ? "bg-red-500/30 text-red-100"
                                  : "bg-red-100 text-red-800"
                                : jobStatus(item) === "generating"
                                  ? active
                                    ? "bg-teal-500/30 text-teal-100"
                                    : "bg-teal-100 text-teal-800"
                                  : active
                                    ? "bg-amber-400/30 text-amber-100"
                                    : "bg-amber-100 text-amber-800"
                            }`}
                          >
                            {statusLabel(jobStatus(item), item.queue_position)}
                          </span>
                        ) : null}
                        {item.company_name ? (
                          <span className={`mt-1 block text-xs ${active ? "text-zinc-300" : "text-zinc-700"}`}>
                            {item.company_name}
                          </span>
                        ) : null}
                        {item.vacancy_url ? (
                          <span
                            className={`mt-0.5 block truncate text-[11px] ${active ? "text-zinc-400" : "text-zinc-500"}`}
                            title={item.vacancy_url}
                          >
                            {item.vacancy_url}
                          </span>
                        ) : null}
                        <span className={`mt-1 block text-xs ${active ? "text-zinc-400" : "text-zinc-500"}`}>
                          {formatWhen(item.created_at)}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          <div className="space-y-4">
            {loadingDetail ? (
              <p className="text-sm text-zinc-500">Cargando CV…</p>
            ) : detail ? (
              <>
                <div className="space-y-3 rounded-xl border border-zinc-200 bg-zinc-50/80 p-5 text-sm">
                  <label className="flex flex-col gap-1">
                    <span className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                      Nombre del CV
                    </span>
                    <input
                      type="text"
                      value={cvName}
                      onChange={(e) => setCvName(e.target.value)}
                      onBlur={() => persistName(cvName, detail.id)}
                      disabled={!detail.cv}
                      className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm text-zinc-900 outline-none ring-zinc-400 focus:ring-2 disabled:bg-zinc-100"
                    />
                  </label>
                  <h2 className="text-base font-semibold text-zinc-900">
                    {detail.vacancy_title}
                  </h2>
                  {selected ? (
                    <p className="text-xs text-zinc-500">{formatWhen(detail.created_at)}</p>
                  ) : null}
                  {detail.company_name ? (
                    <p className="text-zinc-700">
                      <span className="font-medium">Empresa:</span> {detail.company_name}
                    </p>
                  ) : null}
                  {detail.vacancy_url ? (
                    <p className="truncate text-zinc-700">
                      <span className="font-medium">Vacante:</span>{" "}
                      <a
                        href={detail.vacancy_url}
                        target="_blank"
                        rel="noreferrer"
                        className="underline hover:text-zinc-900"
                      >
                        {detail.vacancy_url}
                      </a>
                    </p>
                  ) : null}
                  {jobStatus(detail) !== "ready" ? (
                    <p
                      className={
                        jobStatus(detail) === "error"
                          ? "text-red-700"
                          : "text-teal-800"
                      }
                    >
                      <span className="font-medium">Estado:</span>{" "}
                      {statusLabel(jobStatus(detail), detail.queue_position)}
                      {detail.error ? ` · ${detail.error}` : ""}
                    </p>
                  ) : (
                    <p className="text-zinc-700">
                      <span className="font-medium">Match:</span>{" "}
                      {detail.match_percent.toFixed(0)}%
                      {detail.reason ? ` · ${detail.reason}` : ""}
                    </p>
                  )}
                  <div>
                    <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                      Vacante
                    </p>
                    <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded-md border border-zinc-200 bg-white p-3 text-xs text-zinc-700">
                      {detail.vacancy_text}
                    </pre>
                  </div>
                  {jobStatus(detail) === "error" ? (
                    <button
                      type="button"
                      onClick={() => void onRetry()}
                      disabled={retrying}
                      className="rounded-lg bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
                    >
                      {retrying ? "Reencolando…" : "Reintentar generación"}
                    </button>
                  ) : null}
                  {detail.cv ? (
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
                  ) : null}
                </div>
                {detail.cv ? (
                  <div className="max-h-[720px] overflow-auto rounded-xl border border-zinc-200 bg-white shadow-inner">
                    <CVTemplate data={pickCvData(detail.cv)} />
                  </div>
                ) : (
                  <p className="rounded-xl border border-dashed border-zinc-300 bg-white px-4 py-8 text-sm text-zinc-600">
                    {jobStatus(detail) === "error"
                      ? "Falló la generación. Puedes reintentar; entra otra vez a la cola."
                      : "El worker está generando este CV. La lista se actualiza sola."}
                  </p>
                )}
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
