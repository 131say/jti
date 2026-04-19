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

/** Синхронизировано с `services/worker/core/bearings.py` (BEARING_TABLE). */
export const BEARING_SERIES_OPTIONS: { value: string; label: string }[] = [
  { value: "608", label: "608" },
  { value: "608zz", label: "608 ZZ" },
  { value: "6000", label: "6000" },
  { value: "6000zz", label: "6000 ZZ" },
  { value: "6001", label: "6001" },
  { value: "6001zz", label: "6001 ZZ" },
  { value: "6200", label: "6200" },
  { value: "6200zz", label: "6200 ZZ" },
  { value: "6201", label: "6201" },
  { value: "6201zz", label: "6201 ZZ" },
  { value: "6202", label: "6202" },
  { value: "6202zz", label: "6202 ZZ" },
];

/** Выпадающий список форм для ручного наброска (Blueprint v3.2 — bearing, gear). */
export const BASE_SHAPE_OPTIONS: { value: string; label: string }[] = [
  { value: "cylinder", label: "cylinder — цилиндр / гладкий вал" },
  { value: "box", label: "box — параллелепипед" },
  { value: "extruded_profile", label: "extruded_profile — пластина по контуру" },
  { value: "revolved_profile", label: "revolved_profile — ступенчатый вал (вращение)" },
  { value: "fastener", label: "fastener — болт / гайка / шайба" },
  { value: "bearing", label: "bearing — подшипник (каталог, BOM purchased)" },
  { value: "gear", label: "gear — прямозубая (preview / high_lod)" },
];

type ParamScalar = number | string | boolean;

type PartDraft = {
  part_id?: string;
  base_shape?: string;
  parameters?: Record<string, ParamScalar>;
  material?: string;
};

type FieldDef =
  | { kind: "number"; key: string; label: string; step?: string }
  | {
      kind: "select";
      key: string;
      label: string;
      options: { value: string; label: string }[];
    }
  | { kind: "boolean"; key: string; label: string };

function defaultParametersForShape(
  shape: string,
): Record<string, ParamScalar> {
  switch (shape) {
    case "cylinder":
      return { radius: 5, height: 10 };
    case "box":
      return { length: 20, width: 20, height: 10 };
    case "bearing":
      return { series: "608zz" };
    case "gear":
      return {
        module: 2,
        teeth: 20,
        thickness: 10,
        bore_diameter: 8,
        high_lod: false,
      };
    default:
      return {};
  }
}

function getPartBaseShape(
  jsonStr: string,
  partIndex: number,
): string | undefined {
  try {
    const bp = JSON.parse(jsonStr) as {
      geometry?: { parts?: PartDraft[] };
    };
    const s = bp.geometry?.parts?.[partIndex]?.base_shape;
    return typeof s === "string" && s.length > 0 ? s : undefined;
  } catch {
    return undefined;
  }
}

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

function getPartParamValue(
  jsonStr: string,
  partIndex: number,
  key: string,
): ParamScalar | undefined {
  try {
    const bp = JSON.parse(jsonStr) as {
      geometry?: { parts?: PartDraft[] };
    };
    const v = bp.geometry?.parts?.[partIndex]?.parameters?.[key];
    if (typeof v === "number" && Number.isFinite(v)) return v;
    if (typeof v === "string") return v;
    if (typeof v === "boolean") return v;
    return undefined;
  } catch {
    return undefined;
  }
}

function valuesDrift(
  base: ParamScalar | undefined,
  cur: ParamScalar | undefined,
): boolean {
  if (base === undefined || cur === undefined) return false;
  if (typeof base === "number" && typeof cur === "number") {
    return Math.abs(base - cur) > 1e-6;
  }
  return base !== cur;
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

  const setPartParam = (partIndex: number, key: string, value: ParamScalar) => {
    setDraft((prev) => {
      const next = [...prev];
      const p = next[partIndex];
      if (!p) return prev;
      const params = { ...p.parameters, [key]: value };
      next[partIndex] = { ...p, parameters: params };
      return next;
    });
  };

  const setBaseShape = (partIndex: number, shape: string) => {
    setDraft((prev) => {
      const next = [...prev];
      const p = next[partIndex];
      if (!p) return prev;
      next[partIndex] = {
        ...p,
        base_shape: shape,
        parameters: defaultParametersForShape(shape),
      };
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
            ...((base.parameters ?? {}) as Record<string, ParamScalar>),
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

  const fieldsFor = (p: PartDraft): FieldDef[] => {
    if (p.base_shape === "cylinder") {
      return [
        { kind: "number", key: "radius", label: "radius" },
        { kind: "number", key: "height", label: "height" },
      ];
    }
    if (p.base_shape === "box") {
      return [
        { kind: "number", key: "length", label: "length" },
        { kind: "number", key: "width", label: "width" },
        { kind: "number", key: "height", label: "height" },
      ];
    }
    if (p.base_shape === "bearing") {
      return [
        {
          kind: "select",
          key: "series",
          label: "Серия (каталог)",
          options: BEARING_SERIES_OPTIONS,
        },
      ];
    }
    if (p.base_shape === "gear") {
      return [
        { kind: "number", key: "module", label: "module (мм)" },
        { kind: "number", key: "teeth", label: "teeth (z)", step: "1" },
        { kind: "number", key: "thickness", label: "thickness (мм)" },
        { kind: "number", key: "bore_diameter", label: "bore_diameter (мм)" },
        {
          kind: "boolean",
          key: "high_lod",
          label: "high_lod (процедурные зубья для печати/экспорта)",
        },
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
        Формы <strong className="text-neutral-400">bearing</strong> и{" "}
        <strong className="text-neutral-400">gear</strong> (схема v3.2) — на
        виду: подшипник из каталога (BOM purchased), шестерня: preview или{" "}
        <code className="text-neutral-400">high_lod=true</code> (процедурный
        венец для печати).
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
              Базовая форма (base_shape)
              <select
                title="Смена формы сбрасывает parameters к значениям по умолчанию для этой формы"
                className={`rounded border bg-neutral-900 px-2 py-1 text-neutral-100 ${
                  baselineJson != null &&
                  (getPartBaseShape(baselineJson, pi) ?? "") !==
                    (part.base_shape ?? "")
                    ? "border-amber-600/90 ring-1 ring-amber-700/50"
                    : "border-neutral-700"
                }`}
                value={part.base_shape ?? ""}
                onChange={(e) => setBaseShape(pi, e.target.value)}
              >
                <option value="" disabled>
                  Выберите форму…
                </option>
                {part.base_shape &&
                !BASE_SHAPE_OPTIONS.some((o) => o.value === part.base_shape) ? (
                  <option value={part.base_shape}>
                    {part.base_shape} (из JSON, не в списке UI)
                  </option>
                ) : null}
                {BASE_SHAPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>
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
              {fieldsFor(part).map((field) => {
                const key = field.key;
                const cur = part.parameters?.[key];
                const base =
                  baselineJson != null
                    ? getPartParamValue(baselineJson, pi, key)
                    : undefined;
                const drift =
                  baselineJson != null &&
                  valuesDrift(base, cur as ParamScalar | undefined);

                if (field.kind === "number") {
                  const num =
                    typeof cur === "number"
                      ? cur
                      : typeof cur === "string"
                        ? parseFloat(cur)
                        : undefined;
                  return (
                    <label
                      key={key}
                      className="flex flex-col gap-1 text-xs text-neutral-400"
                    >
                      {field.label}
                      <input
                        type="number"
                        step={field.step ?? "any"}
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
                        value={
                          num !== undefined && !Number.isNaN(num) ? num : ""
                        }
                        onChange={(e) => {
                          const v = parseFloat(e.target.value);
                          if (!Number.isNaN(v)) {
                            const rounded =
                              field.step === "1" ? Math.round(v) : v;
                            setPartParam(pi, key, rounded);
                          }
                        }}
                      />
                    </label>
                  );
                }

                if (field.kind === "select") {
                  const strVal =
                    typeof cur === "string"
                      ? cur
                      : field.options[0]?.value ?? "";
                  return (
                    <label
                      key={key}
                      className="flex flex-col gap-1 text-xs text-neutral-400"
                    >
                      {field.label}
                      <select
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
                        value={strVal}
                        onChange={(e) =>
                          setPartParam(pi, key, e.target.value)
                        }
                      >
                        {field.options.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  );
                }

                if (field.kind === "boolean") {
                  const checked = cur === true;
                  return (
                    <label
                      key={key}
                      className="flex cursor-pointer items-center gap-2 text-xs text-neutral-400 sm:col-span-2"
                    >
                      <input
                        type="checkbox"
                        title={
                          drift
                            ? "Параметр изменился относительно предыдущей версии"
                            : undefined
                        }
                        className={`rounded border bg-neutral-900 ${
                          drift
                            ? "border-amber-600/90 ring-1 ring-amber-700/50"
                            : "border-neutral-700"
                        }`}
                        checked={checked}
                        onChange={(e) =>
                          setPartParam(pi, key, e.target.checked)
                        }
                      />
                      {field.label}
                    </label>
                  );
                }

                return null;
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
