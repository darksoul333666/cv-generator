"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { listCvs, matchVacancy, tailorCv } from "@/lib/api";
import { CV_OPTIMIZE_ATS_INSTRUCTIONS } from "@/lib/cv-optimize-prompt";
import {
  pickCvData,
  type CvProfile,
  type MatchResponse,
  type TailorResponse,
} from "@/lib/cv-types";
import { downloadCvPdfWithPuppeteer } from "@/lib/pdf-client";
import { CVTemplate } from "./cv-template";
import {
  hasVacancyInput,
  VacancySourcePanel,
  type VacancyInputMode,
} from "./vacancy-source-panel";

type WorkbenchTab = "optimize" | "profile";

export function VacancyWorkbench() {
  const [activeTab, setActiveTab] = useState<WorkbenchTab>("optimize");

  const [vacancyMode, setVacancyMode] = useState<VacancyInputMode>("paste");
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");

  const [customInstructions, setCustomInstructions] = useState("");
  const [baseProfiles, setBaseProfiles] = useState<CvProfile[]>([]);
  const [selectedBaseId, setSelectedBaseId] = useState("");

  const [loadingMatch, setLoadingMatch] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [tailoring, setTailoring] = useState(false);
  const [generatingFromBase, setGeneratingFromBase] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [profileMatch, setProfileMatch] = useState<MatchResponse | null>(null);
  const [profileTailored, setProfileTailored] = useState<TailorResponse | null>(null);
  const [standalonePreview, setStandalonePreview] = useState<TailorResponse | null>(null);

  const [optimizeMatch, setOptimizeMatch] = useState<MatchResponse | null>(null);
  const [optimizeTailored, setOptimizeTailored] = useState<TailorResponse | null>(null);

  useEffect(() => {
    setError(null);
  }, [activeTab]);

  useEffect(() => {
    let cancelled = false;
    listCvs()
      .then((profiles) => {
        if (cancelled) return;
        setBaseProfiles(profiles);
        setSelectedBaseId((prev) => prev || profiles[0]?.id || "");
      })
      .catch(() => {
        if (cancelled) return;
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const vacancyPayload = useCallback(() => {
    const u = url.trim();
    const t = text.trim();
    if (vacancyMode === "url") {
      return { vacancy_text: "", vacancy_url: u || undefined };
    }
    return { vacancy_text: t, vacancy_url: u ? u : undefined };
  }, [text, url, vacancyMode]);

  const canRunVacancy = hasVacancyInput(vacancyMode, url, text);

  const onProfileMatch = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!canRunVacancy) {
        setError("Indica una URL o pega el texto de la vacante.");
        return;
      }
      setError(null);
      setLoadingMatch(true);
      setProfileMatch(null);
      setProfileTailored(null);
      setStandalonePreview(null);
      try {
        const data = await matchVacancy(vacancyPayload());
        setProfileMatch(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Error desconocido");
      } finally {
        setLoadingMatch(false);
      }
    },
    [canRunVacancy, vacancyPayload],
  );

  const onOptimizeGenerate = useCallback(async () => {
    if (!canRunVacancy) {
      setError("Indica una URL o pega el texto de la vacante.");
      return;
    }
    setError(null);
    setOptimizing(true);
    setOptimizeMatch(null);
    setOptimizeTailored(null);
    try {
      const payload = vacancyPayload();
      const match = await matchVacancy(payload);
      setOptimizeMatch(match);
      const tailored = await tailorCv({
        ...payload,
        custom_instructions: CV_OPTIMIZE_ATS_INSTRUCTIONS,
        cv: match.cv,
      });
      setOptimizeTailored(tailored);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al generar CV optimizado");
    } finally {
      setOptimizing(false);
    }
  }, [canRunVacancy, vacancyPayload]);

  const onDownload = useCallback(async () => {
    let cv: CvProfile | undefined;
    if (activeTab === "optimize") {
      cv = optimizeTailored?.cv ?? optimizeMatch?.cv;
    } else {
      cv =
        standalonePreview?.cv ??
        profileTailored?.cv ??
        profileMatch?.cv;
    }
    if (!cv) return;
    const safe = cv.name.replace(/\s+/g, "_");
    try {
      await downloadCvPdfWithPuppeteer(cv, `CV_${safe}_${cv.id}.pdf`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al generar PDF");
    }
  }, [
    activeTab,
    optimizeMatch,
    optimizeTailored,
    profileMatch,
    profileTailored,
    standalonePreview,
  ]);

  const onTailor = useCallback(async () => {
    if (!profileMatch) return;
    if (!canRunVacancy) {
      setError("Indica una URL o pega el texto de la vacante.");
      return;
    }
    setError(null);
    setTailoring(true);
    setStandalonePreview(null);
    try {
      const out = await tailorCv({
        ...vacancyPayload(),
        custom_instructions: customInstructions,
        cv: profileMatch.cv,
      });
      setProfileTailored(out);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al perfilar CV");
    } finally {
      setTailoring(false);
    }
  }, [canRunVacancy, customInstructions, profileMatch, vacancyPayload]);

  const selectedBaseProfile = baseProfiles.find((p) => p.id === selectedBaseId) ?? null;

  const onGenerateFromBase = useCallback(async () => {
    if (!selectedBaseProfile) {
      setError("No hay perfiles base cargados (¿está el backend en marcha?).");
      return;
    }
    if (!customInstructions.trim()) {
      setError("Escribe instrucciones en el cuadro de texto para generar el CV modificado.");
      return;
    }
    setError(null);
    setGeneratingFromBase(true);
    setProfileTailored(null);
    setProfileMatch(null);
    setStandalonePreview(null);
    try {
      const out = await tailorCv({
        vacancy_text: "",
        vacancy_url: undefined,
        custom_instructions: customInstructions,
        cv: selectedBaseProfile,
      });
      setStandalonePreview(out);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al generar CV");
    } finally {
      setGeneratingFromBase(false);
    }
  }, [customInstructions, selectedBaseProfile]);

  const busy = loadingMatch || optimizing || tailoring || generatingFromBase;

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-10 px-4 py-10">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">
            Generador de CV (plantilla React + PDF)
          </h1>
          <p className="max-w-2xl text-sm leading-relaxed text-zinc-600">
            Dos flujos: <strong className="font-medium text-zinc-800">Optimizar</strong> elige
            entre tus tres perfiles base con la vacante y genera un CV alineado a ATS;{" "}
            <strong className="font-medium text-zinc-800">Perfilar</strong> te deja revisar el
            match y aplicar instrucciones propias. En ambas pestañas defines la vacante igual:
            URL o texto pegado.
          </p>
        </div>
        <Link
          href="/skills"
          className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-900 hover:bg-zinc-100"
        >
          Editar skills técnicas
        </Link>
      </header>

      <div
        className="inline-flex rounded-xl border border-zinc-200 bg-zinc-50/90 p-1"
        role="tablist"
        aria-label="Vistas"
      >
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "optimize"}
          onClick={() => setActiveTab("optimize")}
          className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
            activeTab === "optimize"
              ? "bg-white text-zinc-900 shadow-sm"
              : "text-zinc-600 hover:text-zinc-900"
          }`}
        >
          Optimizar CV
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "profile"}
          onClick={() => setActiveTab("profile")}
          className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
            activeTab === "profile"
              ? "bg-white text-zinc-900 shadow-sm"
              : "text-zinc-600 hover:text-zinc-900"
          }`}
        >
          Perfilar CV
        </button>
      </div>

      {activeTab === "optimize" ? (
        <section
          className="flex flex-col gap-4 rounded-xl border border-zinc-200 bg-white p-6 shadow-sm"
          role="tabpanel"
        >
          <VacancySourcePanel
            mode={vacancyMode}
            onModeChange={setVacancyMode}
            url={url}
            onUrlChange={setUrl}
            text={text}
            onTextChange={setText}
            disabled={busy}
          />
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={onOptimizeGenerate}
              disabled={optimizing || !canRunVacancy}
              className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-60"
            >
              {optimizing ? "Generando…" : "Generar CV"}
            </button>
            <span className="text-xs text-zinc-500">
              Elige el perfil más alineado entre tus CV y aplica optimización ATS (Gemini).
            </span>
          </div>
          {error && activeTab === "optimize" ? (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
              {error}
            </p>
          ) : null}
        </section>
      ) : (
        <form
          onSubmit={onProfileMatch}
          className="flex flex-col gap-4 rounded-xl border border-zinc-200 bg-white p-6 shadow-sm"
          role="tabpanel"
        >
          <VacancySourcePanel
            mode={vacancyMode}
            onModeChange={setVacancyMode}
            url={url}
            onUrlChange={setUrl}
            text={text}
            onTextChange={setText}
            disabled={busy}
          />
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="font-medium text-zinc-800">
              Instrucciones para perfilar el CV
            </span>
            <textarea
              name="custom_instructions"
              value={customInstructions}
              onChange={(e) => setCustomInstructions(e.target.value)}
              rows={6}
              disabled={busy}
              placeholder="Ej.: enfatiza liderazgo técnico y Kubernetes; acorta el resumen; alinea bullets con métricas; tono más formal… Se usan al pulsar «Perfilar CV»."
              className="rounded-lg border border-zinc-300 px-3 py-2 text-sm text-zinc-900 outline-none ring-zinc-400 focus:ring-2 disabled:bg-zinc-100"
            />
          </label>

          <div className="rounded-lg border border-dashed border-zinc-300 bg-zinc-50/80 p-4">
            <p className="text-sm font-medium text-zinc-800">
              Generar CV solo desde el JSON base + instrucciones
            </p>
            <p className="mt-1 text-xs text-zinc-600">
              Elige un perfil de{" "}
              <code className="rounded bg-white px-1">knowledge_base</code> y las modificaciones
              del cuadro de arriba. Requiere{" "}
              <code className="rounded bg-white px-1">GEMINI_API_KEY</code> en el backend.
            </p>
            <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-end">
              <label className="flex flex-1 flex-col gap-1.5 text-sm">
                <span className="font-medium text-zinc-800">Perfil base (JSON)</span>
                <select
                  value={selectedBaseId}
                  onChange={(e) => setSelectedBaseId(e.target.value)}
                  className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-zinc-900 outline-none ring-zinc-400 focus:ring-2"
                  disabled={!baseProfiles.length || busy}
                >
                  {baseProfiles.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label || p.id}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                onClick={onGenerateFromBase}
                disabled={generatingFromBase || !baseProfiles.length || busy}
                className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-60"
              >
                {generatingFromBase ? "Generando…" : "Generar CV modificado"}
              </button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={loadingMatch || busy}
              className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-60"
            >
              {loadingMatch ? "Analizando…" : "Obtener CV recomendado"}
            </button>
            <span className="text-xs text-zinc-500">
              API: <code className="rounded bg-zinc-100 px-1">/v1/match</code>
            </span>
          </div>
          {error && activeTab === "profile" ? (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
              {error}
            </p>
          ) : null}
        </form>
      )}

      {activeTab === "optimize" && (optimizeMatch || optimizeTailored) ? (
        <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <div className="space-y-3 rounded-xl border border-zinc-200 bg-zinc-50/80 p-5 text-sm">
            <h2 className="text-base font-semibold text-zinc-900">CV optimizado para la vacante</h2>
            {optimizeMatch ? (
              <>
                <p className="text-zinc-700">
                  <span className="font-medium">Perfil base elegido:</span>{" "}
                  {optimizeMatch.cv.label}{" "}
                  <span className="text-zinc-500">({optimizeMatch.chosen_cv_id})</span>
                </p>
                <p className="text-zinc-700">
                  <span className="font-medium">Puntuación de match:</span>{" "}
                  {optimizeMatch.match_score.toFixed(1)}
                </p>
                <p className="text-zinc-600">{optimizeMatch.match_reason}</p>
              </>
            ) : null}
            {optimizeTailored ? (
              <div className="rounded-lg border border-zinc-200 bg-white p-3">
                <p className="text-sm text-zinc-800">
                  <span className="font-medium">Match estimado (IA):</span>{" "}
                  {optimizeTailored.match_percent.toFixed(1)}%
                </p>
                {optimizeTailored.reason ? (
                  <p className="mt-1 text-xs text-zinc-600">{optimizeTailored.reason}</p>
                ) : null}
                {optimizeTailored.notes_to_verify?.length ? (
                  <div className="mt-2">
                    <p className="text-xs font-medium text-zinc-700">Para validar:</p>
                    <ul className="mt-1 list-disc pl-5 text-xs text-zinc-600">
                      {optimizeTailored.notes_to_verify.slice(0, 8).map((n, i) => (
                        <li key={i}>{n}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={onDownload}
                disabled={!optimizeTailored?.cv && !optimizeMatch?.cv}
                className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-900 hover:bg-zinc-100 disabled:opacity-60"
              >
                Descargar PDF
              </button>
            </div>
          </div>
          <div className="max-h-[720px] overflow-auto rounded-xl border border-zinc-200 bg-white shadow-inner">
            {(() => {
              const preview = optimizeTailored?.cv ?? optimizeMatch?.cv;
              return preview ? <CVTemplate data={pickCvData(preview)} /> : null;
            })()}
          </div>
        </section>
      ) : null}

      {activeTab === "profile" && standalonePreview ? (
        <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <div className="space-y-3 rounded-xl border border-zinc-200 bg-zinc-50/80 p-5 text-sm">
            <h2 className="text-base font-semibold text-zinc-900">
              CV generado (base + instrucciones)
            </h2>
            <p className="text-zinc-700">
              <span className="font-medium">Perfil base:</span> {selectedBaseProfile?.label}{" "}
              <span className="text-zinc-500">({selectedBaseProfile?.id})</span>
            </p>
            <p className="text-zinc-700">
              <span className="font-medium">Match estimado:</span>{" "}
              {standalonePreview.match_percent.toFixed(1)}%
            </p>
            {standalonePreview.reason ? (
              <p className="text-zinc-600">{standalonePreview.reason}</p>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={onDownload}
                className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-900 hover:bg-zinc-100"
              >
                Descargar PDF
              </button>
            </div>
          </div>
          <div className="max-h-[720px] overflow-auto rounded-xl border border-zinc-200 bg-white shadow-inner">
            <CVTemplate data={pickCvData(standalonePreview.cv)} />
          </div>
        </section>
      ) : null}

      {activeTab === "profile" && profileMatch ? (
        <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <div className="space-y-3 rounded-xl border border-zinc-200 bg-zinc-50/80 p-5 text-sm">
            <h2 className="text-base font-semibold text-zinc-900">Resultado</h2>
            <p className="text-zinc-700">
              <span className="font-medium">Perfil elegido:</span> {profileMatch.cv.label}{" "}
              <span className="text-zinc-500">({profileMatch.chosen_cv_id})</span>
            </p>
            <p className="text-zinc-700">
              <span className="font-medium">Puntuación:</span>{" "}
              {profileMatch.match_score.toFixed(1)}
            </p>
            <p className="text-zinc-600">{profileMatch.match_reason}</p>
            {profileMatch.raw_meta?.matcher ? (
              <p className="text-xs text-zinc-500">
                Motor:{" "}
                <span className="font-medium text-zinc-600">
                  {String(profileMatch.raw_meta.matcher)}
                </span>
                {profileMatch.raw_meta.gemini_model
                  ? ` (${String(profileMatch.raw_meta.gemini_model)})`
                  : null}
              </p>
            ) : null}
            <div className="mt-2 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={onTailor}
                disabled={tailoring || busy}
                className="rounded-lg bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
              >
                {tailoring ? "Perfilando…" : "Perfilar CV"}
              </button>
              <button
                type="button"
                onClick={onDownload}
                className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-900 hover:bg-zinc-100"
              >
                Descargar PDF
              </button>
            </div>

            {profileTailored ? (
              <div className="mt-3 rounded-lg border border-zinc-200 bg-white p-3">
                <p className="text-sm text-zinc-800">
                  <span className="font-medium">Match IA:</span>{" "}
                  {profileTailored.match_percent.toFixed(1)}%
                </p>
                {profileTailored.reason ? (
                  <p className="mt-1 text-xs text-zinc-600">{profileTailored.reason}</p>
                ) : null}
                {profileTailored.notes_to_verify?.length ? (
                  <div className="mt-2">
                    <p className="text-xs font-medium text-zinc-700">Para validar:</p>
                    <ul className="mt-1 list-disc pl-5 text-xs text-zinc-600">
                      {profileTailored.notes_to_verify.slice(0, 8).map((n, i) => (
                        <li key={i}>{n}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {profileTailored.gaps?.length ? (
                  <div className="mt-3">
                    <p className="text-xs font-medium text-zinc-700">Brechas detectadas:</p>
                    <ul className="mt-1 list-disc pl-5 text-xs text-zinc-600">
                      {profileTailored.gaps.slice(0, 10).map((g, i) => (
                        <li key={i}>{g}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {profileTailored.reinforcement_plan?.length ? (
                  <div className="mt-3">
                    <p className="text-xs font-medium text-zinc-700">Plan de refuerzo rápido:</p>
                    <ul className="mt-1 list-disc pl-5 text-xs text-zinc-600">
                      {profileTailored.reinforcement_plan.slice(0, 10).map((p, i) => (
                        <li key={i}>{p}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
          <div className="max-h-[720px] overflow-auto rounded-xl border border-zinc-200 bg-white shadow-inner">
            <CVTemplate data={pickCvData(profileTailored?.cv ?? profileMatch.cv)} />
          </div>
        </section>
      ) : null}
    </div>
  );
}
