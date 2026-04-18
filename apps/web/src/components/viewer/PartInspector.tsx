"use client";

import type { PartMetricEntry } from "@/components/viewer/PartMetricsComputer";
import {
  estimateMassKg,
  parseSimulationMaterials,
  parseSimulationNodes,
  type BlueprintPartRow,
} from "@/lib/blueprintDiagnostics";
import { resolvePartViewerMaterial } from "@/lib/materialPresets";

function fmtMm3(v: number) {
  if (v >= 1e9) return `${(v / 1e9).toFixed(3)}×10⁹`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(3)}×10⁶`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(2)}×10³`;
  return v.toFixed(1);
}

function fmtKg(kg: number | null) {
  if (kg == null || !Number.isFinite(kg)) return "—";
  if (kg < 1e-3) return `${(kg * 1e6).toFixed(2)} мг`;
  if (kg < 1) return `${(kg * 1e3).toFixed(2)} г`;
  return `${kg.toFixed(4)} кг`;
}

export function PartInspector({
  blueprintJson,
  parts,
  selectedPartId,
  metricsByPart,
}: {
  blueprintJson: string | null | undefined;
  parts: BlueprintPartRow[];
  selectedPartId: string | null;
  metricsByPart: Map<string, PartMetricEntry> | null;
}) {
  if (!selectedPartId) {
    return (
      <div className="text-[11px] text-neutral-500">
        Выберите деталь в дереве или кликом по модели.
      </div>
    );
  }

  const partRow = parts.find((p) => p.part_id === selectedPartId);
  const materials = parseSimulationMaterials(blueprintJson);
  const nodes = parseSimulationNodes(blueprintJson);
  const node = nodes.get(selectedPartId);

  let partObj: unknown;
  try {
    const bp = blueprintJson ? JSON.parse(blueprintJson) : null;
    const arr = bp?.geometry?.parts;
    if (Array.isArray(arr)) {
      partObj = arr.find(
        (x: { part_id?: string }) => x?.part_id === selectedPartId,
      );
    }
  } catch {
    partObj = undefined;
  }

  const pbr = resolvePartViewerMaterial(partObj ?? {});
  const matLabel = pbr
    ? `${pbr.color} · rough ${pbr.roughness.toFixed(2)} · metal ${pbr.metalness.toFixed(2)}`
    : "— (нет пресета / visual в Blueprint)";

  const m = metricsByPart?.get(selectedPartId);
  const volMm3 = m?.volumeMm3 ?? null;
  const massEst = estimateMassKg(
    volMm3,
    node,
    materials,
  );

  const com = m?.comWorld;
  const comStr =
    com != null
      ? `${com.x.toFixed(2)}, ${com.y.toFixed(2)}, ${com.z.toFixed(2)}`
      : "—";

  return (
    <div className="flex min-h-0 flex-col gap-2 text-[11px] text-neutral-300">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-neutral-500">
        Деталь
      </div>
      <div className="font-medium text-neutral-100">{selectedPartId}</div>
      {partRow?.base_shape ? (
        <div className="text-neutral-500">Форма: {partRow.base_shape}</div>
      ) : null}
      <dl className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-1">
        <dt className="text-neutral-500">Материал (viewer)</dt>
        <dd className="break-words text-neutral-200">{matLabel}</dd>
        <dt className="text-neutral-500">Мат. sim</dt>
        <dd className="text-neutral-200">
          {node ? (
            <>
              {node.mat_id}
              {massEst.densityKgM3 != null ? (
                <span className="text-neutral-500">
                  {" "}
                  (ρ {massEst.densityKgM3} кг/м³)
                </span>
              ) : null}
            </>
          ) : (
            "—"
          )}
        </dd>
        <dt className="text-neutral-500">Объём</dt>
        <dd>
          {volMm3 != null && Number.isFinite(volMm3) ? (
            <>
              {fmtMm3(volMm3)} мм³
              <span className="ml-1 text-neutral-600">
                ({(volMm3 / 1000).toFixed(2)} см³)
              </span>
            </>
          ) : (
            "— (нет сетки или невалидная геометрия)"
          )}
        </dd>
        <dt className="text-neutral-500">Масса</dt>
        <dd className="text-neutral-200">
          {fmtKg(massEst.massKg)}
          {massEst.note === "mass_override" ? (
            <span className="ml-1 text-neutral-500">(override)</span>
          ) : null}
          {massEst.note === "no_node" || massEst.note === "unknown_mat" ? (
            <span className="ml-1 text-neutral-500">
              (нужен simulation.nodes + материал)
            </span>
          ) : null}
        </dd>
        <dt className="text-neutral-500">COM (мир)</dt>
        <dd className="font-mono text-[10px] text-neutral-200">{comStr}</dd>
      </dl>
      <p className="text-[10px] leading-snug text-neutral-600">
        Объём/COM из треугольной сетки GLB; масса — из ρ и объёма либо
        mass_override. При движении FK положение COM в мире меняется — значение
        обновляется при изменении слайдера кинематики.
      </p>
    </div>
  );
}
