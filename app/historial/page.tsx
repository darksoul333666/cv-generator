import { Suspense } from "react";
import { HistoryWorkbench } from "@/components/history-workbench";

export default function HistorialPage() {
  return (
    <div className="min-h-full flex-1 bg-zinc-100">
      <Suspense
        fallback={
          <p className="px-4 py-10 text-sm text-zinc-500">Cargando historial…</p>
        }
      >
        <HistoryWorkbench />
      </Suspense>
    </div>
  );
}
