import { useState, type ReactNode } from "react";

export const fieldClass =
  "w-full rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-900 outline-none ring-zinc-400 focus:bg-white focus:ring-2";

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      viewBox="0 0 20 20"
      aria-hidden
      className={`mt-0.5 h-4 w-4 shrink-0 text-zinc-400 transition ${open ? "rotate-90" : ""}`}
    >
      <path
        d="M7 5l6 5-6 5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="font-medium text-zinc-700">{label}</span>
      {children}
    </label>
  );
}

export function SectionCard({
  title,
  hint,
  summary,
  action,
  children,
  defaultOpen = false,
}: {
  title: string;
  hint?: string;
  summary?: string;
  action?: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm">
      <div className="flex items-start gap-2 px-4 py-3">
        <button
          type="button"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
          className="flex min-w-0 flex-1 items-start gap-2 text-left"
        >
          <Chevron open={open} />
          <span className="min-w-0">
            <span className="block text-sm font-semibold text-zinc-900">{title}</span>
            {open && hint ? (
              <span className="mt-1 block text-xs leading-relaxed text-zinc-500">{hint}</span>
            ) : null}
            {!open && summary ? (
              <span className="mt-0.5 block truncate text-xs text-zinc-500">{summary}</span>
            ) : null}
          </span>
        </button>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      {open ? <div className="border-t border-zinc-100 px-4 py-4">{children}</div> : null}
    </section>
  );
}

export function CollapseRow({
  title,
  meta,
  actions,
  children,
  defaultOpen = false,
}: {
  title: string;
  meta?: string;
  actions?: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <article className="overflow-hidden rounded-lg border border-zinc-200 bg-white">
      <div className="flex items-center gap-2 px-3 py-2.5">
        <button
          type="button"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
        >
          <Chevron open={open} />
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium text-zinc-900">{title}</span>
            {!open && meta ? (
              <span className="block truncate text-xs text-zinc-500">{meta}</span>
            ) : null}
          </span>
        </button>
        {actions ? <div className="flex shrink-0 gap-1">{actions}</div> : null}
      </div>
      {open ? <div className="border-t border-zinc-100 px-3 py-3">{children}</div> : null}
    </article>
  );
}

export function TextButton({
  children,
  onClick,
  disabled,
}: {
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-900 hover:bg-zinc-100 disabled:opacity-50"
    >
      {children}
    </button>
  );
}
