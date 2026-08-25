"use client";

import { useCallback, useId } from "react";

type VacancySourcePanelProps = {
  text: string;
  onTextChange: (text: string) => void;
  disabled?: boolean;
};

export function VacancySourcePanel({
  text,
  onTextChange,
  disabled = false,
}: VacancySourcePanelProps) {
  const baseId = useId();

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
    <label className="flex flex-col gap-1.5 text-sm">
      <span className="flex items-center justify-between gap-2">
        <span className="font-medium text-zinc-800">Descripción de la vacante</span>
        <button
          type="button"
          disabled={disabled}
          onClick={onPasteClipboard}
          className="rounded-lg border border-zinc-300 bg-white px-3 py-1 text-xs font-medium text-zinc-900 hover:bg-zinc-100 disabled:opacity-50"
        >
          Pegar
        </button>
      </span>
      <textarea
        id={`${baseId}-text`}
        name="vacancy_text"
        value={text}
        onChange={(e) => onTextChange(e.target.value)}
        rows={14}
        disabled={disabled}
        placeholder="Pega aquí el anuncio completo de la oferta…"
        className="rounded-lg border border-zinc-300 px-3 py-2 font-mono text-sm text-zinc-900 outline-none ring-zinc-400 focus:ring-2 disabled:bg-zinc-100"
      />
    </label>
  );
}
