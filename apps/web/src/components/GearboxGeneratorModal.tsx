"use client";

import { useCallback, useState } from "react";

import { buildGearboxBlueprintJson } from "@/lib/gearboxPreset";

type GearboxGeneratorModalProps = {
  open: boolean;
  onClose: () => void;
  onApplyJson: (json: string) => void;
};

export function GearboxGeneratorModal({
  open,
  onClose,
  onApplyJson,
}: GearboxGeneratorModalProps) {
  const [ratio, setRatio] = useState("3");
  const [module, setModule] = useState("2");
  const [thickness, setThickness] = useState("10");
  const [bore, setBore] = useState("8");
  const [highLod, setHighLod] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = useCallback(() => {
    setErr(null);
    const r = Number(ratio);
    const m = Number(module);
    const t = Number(thickness);
    const b = Number(bore);
    if (![r, m, t, b].every((x) => Number.isFinite(x))) {
      setErr("Введите числа во все поля.");
      return;
    }
    if (r < 1.5 || r > 10) {
      setErr("Передаточное число: допустимо 1.5…10 (MVP).");
      return;
    }
    const json = buildGearboxBlueprintJson({
      ratio: r,
      module: m,
      thickness: t,
      bore: b,
      highLod: highLod,
    });
    onApplyJson(json);
    onClose();
  }, [ratio, module, thickness, bore, highLod, onApplyJson, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[120] flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="gb-modal-title"
    >
      <div className="w-full max-w-md rounded-xl border border-neutral-700 bg-neutral-950 p-4 shadow-xl">
        <h2
          id="gb-modal-title"
          className="text-base font-semibold text-neutral-100"
        >
          ⚙️ Генератор редуктора (v4.3)
        </h2>
        <p className="mt-1 text-xs text-neutral-500">
          Одноступенчатая пара прямозубых шестерён, два вала, привязки constraints.
          Параметры попадут в{" "}
          <code className="text-neutral-400">global_variables</code> — их можно
          крутить в панели параметров после генерации.
        </p>
        <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
          <label className="col-span-2 flex flex-col gap-1 text-neutral-400">
            Передаточное число (ratio)
            <input
              type="text"
              inputMode="decimal"
              value={ratio}
              onChange={(e) => setRatio(e.target.value)}
              className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-neutral-100"
            />
          </label>
          <label className="flex flex-col gap-1 text-neutral-400">
            Модуль m (мм)
            <input
              type="text"
              inputMode="decimal"
              value={module}
              onChange={(e) => setModule(e.target.value)}
              className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-neutral-100"
            />
          </label>
          <label className="flex flex-col gap-1 text-neutral-400">
            Толщина (мм)
            <input
              type="text"
              inputMode="decimal"
              value={thickness}
              onChange={(e) => setThickness(e.target.value)}
              className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-neutral-100"
            />
          </label>
          <label className="col-span-2 flex flex-col gap-1 text-neutral-400">
            Посадочный диаметр bore (мм)
            <input
              type="text"
              inputMode="decimal"
              value={bore}
              onChange={(e) => setBore(e.target.value)}
              className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-neutral-100"
            />
          </label>
          <label className="col-span-2 flex cursor-pointer items-center gap-2 text-neutral-300">
            <input
              type="checkbox"
              checked={highLod}
              onChange={(e) => setHighLod(e.target.checked)}
            />
            high_lod (детальные зубья, дольше сборка)
          </label>
        </div>
        {err ? (
          <p className="mt-2 text-xs text-amber-400" role="alert">
            {err}
          </p>
        ) : null}
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-neutral-600 px-3 py-1.5 text-sm text-neutral-300 hover:bg-neutral-900"
          >
            Отмена
          </button>
          <button
            type="button"
            onClick={submit}
            className="rounded bg-sky-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-500"
          >
            Собрать JSON
          </button>
        </div>
      </div>
    </div>
  );
}
