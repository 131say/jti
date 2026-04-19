"use client";

import type { JobDiagnosticCheck, JobDiagnostics } from "@/lib/api";

function severityIcon(sev: string) {
  if (sev === "fail") return "🔴";
  if (sev === "warning") return "🟡";
  if (sev === "info") return "🔵";
  return "🟢";
}

function statusLabel(status: string) {
  if (status === "fail") return "🔴 Fail";
  if (status === "warning") return "🟡 Warning";
  return "🟢 Pass";
}

export function DiagnosticsPanel({
  diagnostics,
  selectedIndex,
  onSelectCheck,
}: {
  diagnostics: JobDiagnostics | null;
  selectedIndex: number | null;
  onSelectCheck: (index: number | null, partIds: string[]) => void;
}) {
  const checks = diagnostics?.checks ?? [];

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-auto text-xs text-neutral-200">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-medium text-neutral-100">
          Инженерная диагностика (эвристики)
        </div>
        {diagnostics ? (
          <span className="rounded border border-neutral-700 bg-neutral-900 px-2 py-0.5 text-[10px] text-neutral-400">
            {statusLabel(diagnostics.status)}
          </span>
        ) : null}
      </div>
      <p className="text-[11px] leading-snug text-neutral-500">
        Проверки выполняются на воркере после генерации. Interference — критично;
        предупреждения DFM — жёлтые; синие (info) — положительные инженерные
        подсказки (например, корректная зубчатая пара).
      </p>
      {checks.length === 0 ? (
        <p className="rounded border border-neutral-800 bg-neutral-900/40 px-2 py-3 text-center text-[11px] text-neutral-500">
          {diagnostics
            ? "Нет замечаний по текущим эвристикам."
            : "Запустите Forge — после завершения здесь появятся результаты проверок."}
        </p>
      ) : (
        <ul className="space-y-1.5">
          {checks.map((c: JobDiagnosticCheck, i: number) => {
            const active = selectedIndex === i;
            const isInfo = c.severity === "info";
            const isFail = c.severity === "fail";
            const activeBorder = isFail
              ? "border-red-800/80 bg-red-950/35"
              : isInfo
                ? "border-sky-700/80 bg-sky-950/40"
                : "border-amber-800/70 bg-amber-950/25";
            return (
              <li key={`${c.type}-${i}-${c.message.slice(0, 24)}`}>
                <button
                  type="button"
                  onClick={() => {
                    if (active) {
                      onSelectCheck(null, []);
                    } else {
                      onSelectCheck(i, c.part_ids ?? []);
                    }
                  }}
                  className={`w-full rounded border px-2 py-2 text-left transition-colors ${
                    active
                      ? `${activeBorder} text-neutral-100`
                      : "border-neutral-800 bg-neutral-900/50 hover:border-neutral-600"
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <span className="shrink-0 pt-0.5" aria-hidden>
                      {severityIcon(c.severity)}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="font-mono text-[10px] uppercase text-neutral-500">
                        {c.type}
                      </div>
                      <div className="mt-0.5 leading-snug">{c.message}</div>
                      {c.metrics && Object.keys(c.metrics).length > 0 ? (
                        <pre className="mt-1 overflow-x-auto rounded bg-black/30 p-1.5 font-mono text-[10px] text-neutral-400">
                          {JSON.stringify(c.metrics, null, 2)}
                        </pre>
                      ) : null}
                    </div>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
