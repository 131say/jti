"use client";

export function AssemblyGuidePanel({ pdfUrl }: { pdfUrl: string }) {
  return (
    <div className="flex h-full min-h-[220px] flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <a
          href={pdfUrl}
          download
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 rounded border border-sky-500/40 bg-sky-950/40 px-4 py-2 text-sm font-medium text-sky-100 hover:bg-sky-900/50"
        >
          📥 Скачать PDF
        </a>
        <span className="text-[11px] text-neutral-500">
          Сгенерировано воркером (BOM + шаги по assembly_mates)
        </span>
      </div>
      <iframe
        title="Инструкция по сборке"
        src={pdfUrl}
        className="min-h-[240px] w-full flex-1 rounded border border-neutral-800 bg-neutral-900"
      />
    </div>
  );
}
