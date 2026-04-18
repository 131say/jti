"use client";

import { useEffect, useMemo, useState } from "react";

/** Ключи пресетов синхронизированы с `services/worker/core/materials.py`. */
export const MATERIAL_PRESET_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "— (только simulation)" },
  { value: "steel", label: "Steel (сталь)" },
  { value: "aluminum_6061", label: "Aluminum 6061" },
  { value: "abs_plastic", label: "ABS plastic" },
  { value: "rubber", label: "Rubber (резина)" },
];

type PartDraft = {
  part_id?: string;
  base_shape?: string;
  parameters?: Record<string, number>;
  material?: string;
};

function getPartMaterial(jsonStr: string, partIndex: number): string | undefined {
  try {
    const bp = JSON.parse(jsonStr) as {
      geometry?: { parts?: PartDraft[] };
    };
    const m = bp.geometry?.parts?.[partIndex]?.material;
    return typeof m === "string" && m.length > 0 ? m : undefined;
  } catch {
    return undefined;
  }
}

function getPartParam(
  jsonStr: string,
  partIndex: number,
  key: string,
): number | undefined {
  try {
    const bp = JSON.parse(jsonStr) as {
      geometry?: { parts?: PartDraft[] };
    };
    const v = bp.geometry?.parts?.[partIndex]?.parameters?.[key];
    return typeof v === "number" ? v : undefined;
  } catch {
    return undefined;
  }
}

function getGlobalVar(jsonStr: string, key: string): number | undefined {
  try {
    const bp = JSON.parse(jsonStr) as {
      global_variables?: Record<string, number>;
    };
    const v = bp.global_variables?.[key];
    return typeof v === "number" ? v : undefined;
  } catch {
    return undefined;
  }
}

export function ParametricPanel({
  jsonText,
  baselineJson,
  onApply,
  disabled,
}: {
  jsonText: string;
  /** Предыдущая версия JSON для подсветки неожиданного дрейфа параметров */
  baselineJson?: string | null;
  onApply: (obj: object) => void;
  disabled?: boolean;
}) {
  const [draft, setDraft] = useState<PartDraft[]>([]);
  const [draftGlobals, setDraftGlobals] = useState<Record<string, number>>({});
  const [parseError, setParseError] = useState<string | null>(null);

  const hasGlobalVars = useMemo(() => {
    try {
      const bp = JSON.parse(jsonText) as {
        global_variables?: Record<string, unknown>;
      };
      const gv = bp.global_variables;
      return (
        gv != null &&
        typeof gv === "object" &&
        !Array.isArray(gv) &&
        Object.keys(gv).length > 0
      );
    } catch {
      return false;
    }
  }, [jsonText]);

  useEffect(() => {
    try {
      const bp = JSON.parse(jsonText) as {
        geometry?: { parts?: PartDraft[] };
        global_variables?: Record<string, unknown>;
      };
      const parts = bp.geometry?.parts ?? [];
      setDraft(JSON.parse(JSON.stringify(parts)) as PartDraft[]);
      const gv = bp.global_variables;
      const next: Record<string, number> = {};
      if (gv && typeof gv === "object" && !Array.isArray(gv)) {
        for (const [k, v] of Object.entries(gv)) {
          if (typeof v === "number" && Number.isFinite(v)) {
            next[k] = v;
          }
        }
      }
      setDraftGlobals(next);
      setParseError(null);
    } catch (e) {
      setDraft([]);
      setDraftGlobals({});
      setParseError(e instanceof Error ? e.message : String(e));
    }
  }, [jsonText]);

  const setMaterial = (partIndex: number, value: string) => {
    setDraft((prev) => {
      const next = [...prev];
      const p = next[partIndex];
      if (!p) return prev;
      const updated = { ...p };
      if (!value) {
        delete updated.material;
      } else {
        updated.material = value;
      }
      next[partIndex] = updated;
      return next;
    });
  };

  const setParam = (partIndex: number, key: string, value: number) => {
    setDraft((prev) => {
      const next = [...prev];
      const p = next[partIndex];
      if (!p) return prev;
      const params = { ...p.parameters, [key]: value };
      next[partIndex] = { ...p, parameters: params };
      return next;
    });
  };

  const handleUpdate = () => {
    if (parseError) return;
    try {
      const bp = JSON.parse(jsonText) as {
        geometry: { parts: PartDraft[] };
        global_variables?: Record<string, number>;
      };
      const clone = JSON.parse(JSON.stringify(bp)) as typeof bp;
      if (hasGlobalVars && Object.keys(draftGlobals).length > 0) {
        clone.global_variables = {
          ...(clone.global_variables ?? {}),
          ...draftGlobals,
        };
      }
      draft.forEach((p, i) => {
        if (!clone.geometry.parts[i]) return;
        const base = clone.geometry.parts[i] as PartDraft & Record<string, unknown>;
        const nextPart: Record<string, unknown> = {
          ...base,
          parameters: {
            ...(base.parameters as Record<string, number>),
            ...(p.parameters ?? {}),
          },
        };
        if (p.material) {
          nextPart.material = p.material;
        } else {
          delete nextPart.material;
        }
        clone.geometry.parts[i] = nextPart as (typeof clone.geometry.parts)[number];
      });
      onApply(clone);
    } catch (e) {
      alert(
        `Не удалось применить параметры: ${e instanceof Error ? e.message : String(e)}`,
      );
    }
  };

  const fieldsFor = (p: PartDraft): { key: string; label: string }[] => {
    if (p.base_shape === "cylinder") {
      return [
        { key: "radius", label: "radius" },
        { key: "height", label: "height" },
      ];
    }
    if (p.base_shape === "box") {
      return [
        { key: "length", label: "length" },
        { key: "width", label: "width" },
        { key: "height", label: "height" },
      ];
    }
    return [];
  };

  if (parseError) {
    return null;
  }

  if (draft.length === 0 && !hasGlobalVars) {
    return null;
  }

  return (
    <div className="border-t border-neutral-800 bg-neutral-950 p-4">
      <div className="mb-2 text-sm font-medium text-neutral-100">
        Параметры детали
      </div>
      <p className="mb-3 text-xs text-neutral-500">
        Числа в мм (как в JSON). Материал — пресет для цвета STEP и физики MuJoCo.
        Обновление отправляет Blueprint в воркер без LLM.
        {baselineJson ? (
          <span className="text-amber-600/90">
            {" "}
            Жёлтая рамка — значение отличается от предыдущей версии (возможный
            дрейф).
          </span>
        ) : null}
      </p>

      {hasGlobalVars ? (
        <div className="mb-4 rounded border border-cyan-900/60 bg-neutral-900/40 p-3">
          <div className="mb-2 text-xs font-medium text-cyan-200/90">
            Глобальные переменные
          </div>
          <p className="mb-2 text-[11px] text-neutral-500">
            Меняйте константы — формулы с $ в JSON пересчитаются на сервере при
            сборке.
          </p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {Object.keys(draftGlobals).map((gkey) => {
              const cur = draftGlobals[gkey];
              const base =
                baselineJson != null
                  ? getGlobalVar(baselineJson, gkey)
                  : undefined;
              const drift =
                baselineJson != null &&
                base !== undefined &&
                Math.abs(base - cur) > 1e-6;
              return (
                <label
                  key={gkey}
                  className="flex flex-col gap-1 text-xs text-neutral-400"
                >
                  {`$${gkey}`}
                  <input
                    type="number"
                    step="any"
                    title={
                      drift
                        ? "Значение отличается от предыдущей версии"
                        : undefined
                    }
                    className={`rounded border bg-neutral-900 px-2 py-1 text-neutral-100 ${
                      drift
                        ? "border-amber-600/90 ring-1 ring-amber-700/50"
                        : "border-neutral-700"
                    }`}
                    value={cur ?? ""}
                    onChange={(e) => {
                      const v = parseFloat(e.target.value);
                      if (!Number.isNaN(v)) {
                        setDraftGlobals((prev) => ({ ...prev, [gkey]: v }));
                      }
                    }}
                  />
                </label>
              );
            })}
          </div>
        </div>
      ) : null}

      <div className="flex max-h-[40vh] flex-col gap-4 overflow-y-auto">
        {draft.map((part, pi) => (
          <div
            key={`${part.part_id ?? "part"}-${pi}`}
            className="rounded border border-neutral-800 p-3"
          >
            <div className="mb-2 text-xs font-medium text-neutral-300">
              {part.part_id ?? `part[${pi}]`} · {part.base_shape ?? "?"}
            </div>
            <label className="mb-2 flex flex-col gap-1 text-xs text-neutral-400">
              Материал (пресет)
              <select
                className={`rounded border bg-neutral-900 px-2 py-1 text-neutral-100 ${
                  baselineJson != null &&
                  (getPartMaterial(baselineJson, pi) ?? "") !==
                    (part.material ?? "")
                    ? "border-amber-600/90 ring-1 ring-amber-700/50"
                    : "border-neutral-700"
                }`}
                value={part.material ?? ""}
                onChange={(e) => setMaterial(pi, e.target.value)}
              >
                {MATERIAL_PRESET_OPTIONS.map((opt) => (
                  <option key={opt.value || "none"} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {fieldsFor(part).map(({ key, label }) => {
                const cur = part.parameters?.[key];
                const base =
                  baselineJson != null
                    ? getPartParam(baselineJson, pi, key)
                    : undefined;
                const drift =
                  baselineJson != null &&
                  base !== undefined &&
                  cur !== undefined &&
                  Math.abs(base - cur) > 1e-6;
                return (
                  <label
                    key={key}
                    className="flex flex-col gap-1 text-xs text-neutral-400"
                  >
                    {label}
                    <input
                      type="number"
                      step="any"
                      title={
                        drift
                          ? "Параметр изменился относительно предыдущей версии"
                          : undefined
                      }
                      className={`rounded border bg-neutral-900 px-2 py-1 text-neutral-100 ${
                        drift
                          ? "border-amber-600/90 ring-1 ring-amber-700/50"
                          : "border-neutral-700"
                      }`}
                      value={cur ?? ""}
                      onChange={(e) => {
                        const v = parseFloat(e.target.value);
                        if (!Number.isNaN(v)) setParam(pi, key, v);
                      }}
                    />
                  </label>
                );
              })}
            </div>
          </div>
        ))}
      </div>
      <button
        type="button"
        disabled={disabled}
        onClick={handleUpdate}
        className="mt-3 rounded border border-neutral-600 bg-neutral-900 px-4 py-2 text-sm text-neutral-100 hover:bg-neutral-800 disabled:opacity-50"
      >
        Обновить модель
      </button>
    </div>
  );
}
