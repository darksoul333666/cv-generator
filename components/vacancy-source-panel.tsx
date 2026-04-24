"use client";

import { useCallback, useId } from "react";

export type VacancyInputMode = "url" | "paste";

type VacancySourcePanelProps = {
  mode: VacancyInputMode;
  onModeChange: (mode: VacancyInputMode) => void;
  url: string;
  onUrlChange: (url: string) => void;
  text: string;
  onTextChange: (text: string) => void;
  disabled?: boolean;
};

export function VacancySourcePanel({
  mode,
  onModeChange,
  url,
  onUrlChange,
  text,
  onTextChange,
  disabled = false,
}: VacancySourcePanelProps) {
  const baseId = useId();

  const onQuickPaste = useCallback(async () => {
    if (disabled || typeof navigator === "undefined" || !navigator.clipboard?.readText) {
      return;
    }
    try {
      const clip = (await navigator.clipboard.readText()).trim();
      if (!clip) return;
      if (mode === "url") {
        if (/^https?:\/\//i.test(clip)) {
          onUrlChange(clip);
        } else {
          onModeChange("paste");
          onTextChange(clip);
        }
      } else {
        onTextChange(text ? `${text.trimEnd()}\n\n${clip}` : clip);
      }
    } catch {
      /* permiso denegado o clipboard vacío */
    }
  }, [disabled, mode, onModeChange, onTextChange, onUrlChange, text]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <span className="text-sm font-medium text-zinc-800">Fuente de la vacante</span>
        <div className="flex flex-wrap items-center gap-2">
          <div
            className="inline-flex rounded-lg border border-zinc-200 bg-zinc-50 p-0.5"
            role="group"
            aria-label="Modo de entrada"
          >
            <button
              type="button"
              disabled={disabled}
              onClick={() => onModeChange("url")}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                mode === "url"
                  ? "bg-white text-zinc-900 shadow-sm"
                  : "text-zinc-600 hover:text-zinc-900"
              } disabled:opacity-50`}
            >
              URL
            </button>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onModeChange("paste")}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                mode === "paste"
                  ? "bg-white text-zinc-900 shadow-sm"
                  : "text-zinc-600 hover:text-zinc-900"
              } disabled:opacity-50`}
            >
              Texto de la vacante
            </button>
          </div>
          <button
            type="button"
            disabled={disabled}
            onClick={onQuickPaste}
            className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-900 hover:bg-zinc-100 disabled:opacity-50"
            title="Pegar desde el portapapeles"
          >
            Pegar
          </button>
        </div>
      </div>

      {mode === "url" ? (
        <label className="flex flex-col gap-1.5 text-sm">
          <span className="font-medium text-zinc-800">URL de la vacante</span>
          <input
            id={`${baseId}-url`}
            type="url"
            name="vacancy_url"
            value={url}
            onChange={(e) => onUrlChange(e.target.value)}
            placeholder="https://..."
            disabled={disabled}
            className="rounded-lg border border-zinc-300 px-3 py-2 text-zinc-900 outline-none ring-zinc-400 focus:ring-2 disabled:bg-zinc-100"
          />
          <span className="text-xs text-zinc-500">
            El servidor extraerá el texto de la página. Puedes cambiar a «Texto» si la URL no es legible.
          </span>
        </label>
      ) : (
        <label className="flex flex-col gap-1.5 text-sm">
          <span className="font-medium text-zinc-800">Texto de la vacante</span>
          <textarea
            id={`${baseId}-text`}
            name="vacancy_text"
            value={text}
            onChange={(e) => onTextChange(e.target.value)}
            rows={12}
            disabled={disabled}
            placeholder="Pega aquí el enunciado completo de la oferta…"
            className="rounded-lg border border-zinc-300 px-3 py-2 font-mono text-sm text-zinc-900 outline-none ring-zinc-400 focus:ring-2 disabled:bg-zinc-100"
          />
        </label>
      )}
    </div>
  );
}

/** True si hay URL en modo url, o texto no vacío en modo paste. */
export function hasVacancyInput(
  mode: VacancyInputMode,
  url: string,
  text: string,
): boolean {
  if (mode === "url") return Boolean(url.trim());
  return Boolean(text.trim());
}
