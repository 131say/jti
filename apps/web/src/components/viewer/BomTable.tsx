"use client";

import { Download } from "lucide-react";

import type { JobBom } from "@/lib/api";

export function BomTable({
  bom,
  zipUrl,
}: {
  bom: JobBom | null;
  zipUrl: string | null;
}) {
  const parts = bom?.parts ?? [];

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-auto text-xs text-neutral-200">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-medium text-neutral-100">Спецификация (BOM)</div>
        {zipUrl ? (
          <a
            href={zipUrl}
            download
            className="inline-flex shrink-0 items-center gap-2 rounded bg-neutral-100 px-3 py-2 text-sm font-medium text-neutral-900"
          >
            <Download className="h-4 w-4 shrink-0" aria-hidden />
            Скачать Project ZIP
          </a>
        ) : null}
      </div>

      <div className="overflow-x-auto rounded border border-neutral-800">
        <table className="w-full min-w-[480px] border-collapse text-left">
          <thead>
            <tr className="border-b border-neutral-800 bg-neutral-900/80 text-[10px] uppercase tracking-wide text-neutral-500">
              <th className="px-2 py-1.5 font-medium">Деталь</th>
              <th className="px-2 py-1.5 font-medium">Материал</th>
              <th className="px-2 py-1.5 font-medium">Масса, г</th>
              <th className="px-2 py-1.5 font-medium">Объём, см³</th>
              <th className="px-2 py-1.5 font-medium">Сырьё, USD</th>
            </tr>
          </thead>
          <tbody>
            {parts.length === 0 ? (
              <tr>
                <td
                  colSpan={5}
                  className="px-2 py-4 text-center text-neutral-500"
                >
                  Нет данных BOM (задача ещё не завершена или детали не
                  посчитаны).
                </td>
              </tr>
            ) : (
              parts.map((row) => (
                <tr
                  key={row.part_id}
                  className="border-b border-neutral-800/80 hover:bg-neutral-900/40"
                >
                  <td className="px-2 py-1.5 font-mono text-[11px] text-neutral-100">
                    {row.part_id}
                  </td>
                  <td className="px-2 py-1.5 text-neutral-400">
                    {row.material ?? "—"}
                  </td>
                  <td className="px-2 py-1.5 tabular-nums">
                    {row.mass_g.toFixed(2)}
                  </td>
                  <td className="px-2 py-1.5 tabular-nums">
                    {row.volume_cm3.toFixed(2)}
                  </td>
                  <td className="px-2 py-1.5 tabular-nums">
                    {row.cost_usd.toFixed(2)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
          {bom && parts.length > 0 ? (
            <tfoot>
              <tr className="border-t border-neutral-700 bg-neutral-900/60 font-medium">
                <td className="px-2 py-2" colSpan={2}>
                  Итого
                </td>
                <td className="px-2 py-2 tabular-nums">
                  {bom.total_mass_g.toFixed(2)}
                </td>
                <td className="px-2 py-2 text-neutral-500">—</td>
                <td className="px-2 py-2 tabular-nums">
                  {bom.total_cost_usd.toFixed(2)}
                </td>
              </tr>
            </tfoot>
          ) : null}
        </table>
      </div>

      <p
        className="rounded border border-amber-800/60 bg-amber-950/35 px-2 py-2 text-[11px] leading-snug text-amber-100/95"
        role="note"
      >
        ⚠️ Оценка только по стоимости сырья, без учета технологической
        обработки, сборки и логистики.
      </p>
    </div>
  );
}
