"use client";

import { useCallback, useId } from "react";

type VacancySourcePanelProps = {
  text: string;
  onTextChange: (text: string) => void;
  disabled?: boolean;
  autoFocus?: boolean;
  onModEnter?: () => void;
};

export function VacancySourcePanel({
  text,
  onTextChange,
  disabled = false,
  autoFocus = false,
  onModEnter,
}: VacancySourcePanelProps) {
  const textId = useId();

  const onPasteClipboard = useCallback(async () => {
    if (disabled || typeof navigator === "undefined" || !navigator.clipboard?.readText) {
      return;
    }
    try {
      const clip = (await navigator.clipboard.readText()).trim();
      if (clip) onTextChange(clip);
    } catch {
      /* permiso denegado o clipboard vacío */
    }
  }, [disabled, onTextChange]);

  return (
    <div className="flex flex-col gap-1.5 text-sm">
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={textId} className="font-medium text-zinc-800">
          Descripción de la vacante
        </label>
        <button
          type="button"
          disabled={disabled}
          onClick={onPasteClipboard}
          className="rounded-lg border border-zinc-300 bg-white px-3 py-1 text-xs font-medium text-zinc-900 hover:bg-zinc-100 disabled:opacity-50"
        >
          Pegar
        </button>
      </div>
      <textarea
        id={textId}
        name="vacancy_text"
        value={text}
        autoFocus={autoFocus}
        onChange={(e) => onTextChange(e.target.value)}
        onKeyDown={(e) => {
          if (onModEnter && (e.metaKey || e.ctrlKey) && e.key === "Enter") {
            e.preventDefault();
            onModEnter();
          }
        }}
        rows={14}
        disabled={disabled}
        placeholder="Pega aquí el anuncio completo de la oferta…"
        className="rounded-lg border border-zinc-300 px-3 py-2 font-mono text-sm text-zinc-900 outline-none ring-zinc-400 focus:ring-2 disabled:bg-zinc-100"
      />
    </div>
  );
}
