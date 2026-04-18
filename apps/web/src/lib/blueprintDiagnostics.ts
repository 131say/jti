/**
 * Разбор Blueprint для панели диагностики (материалы, узлы симуляции).
 */

export type BlueprintPartRow = {
  part_id: string;
  base_shape?: string;
};

export type SimMaterialRow = {
  mat_id: string;
  density: number;
  friction?: number;
};

export type SimNodeRow = {
  part_id: string;
  mat_id: string;
  mass_override?: number | null;
};

export function parseBlueprintParts(
  blueprintJson: string | null | undefined,
): BlueprintPartRow[] {
  if (!blueprintJson?.trim()) return [];
  try {
    const bp = JSON.parse(blueprintJson) as {
      geometry?: { parts?: unknown[] };
    };
    const parts = bp.geometry?.parts;
    if (!Array.isArray(parts)) return [];
    const out: BlueprintPartRow[] = [];
    for (const p of parts) {
      if (!p || typeof p !== "object") continue;
      const id = (p as { part_id?: string }).part_id;
      if (typeof id === "string" && id.length > 0) {
        out.push({
          part_id: id,
          base_shape:
            typeof (p as { base_shape?: string }).base_shape === "string"
              ? (p as { base_shape: string }).base_shape
              : undefined,
        });
      }
    }
    return out;
  } catch {
    return [];
  }
}

export function parseSimulationMaterials(
  blueprintJson: string | null | undefined,
): Map<string, SimMaterialRow> {
  const map = new Map<string, SimMaterialRow>();
  if (!blueprintJson?.trim()) return map;
  try {
    const bp = JSON.parse(blueprintJson) as {
      simulation?: { materials?: unknown[] };
    };
    const mats = bp.simulation?.materials;
    if (!Array.isArray(mats)) return map;
    for (const m of mats) {
      if (!m || typeof m !== "object") continue;
      const row = m as Record<string, unknown>;
      const mat_id = row.mat_id;
      const density = row.density;
      if (typeof mat_id !== "string" || typeof density !== "number") continue;
      map.set(mat_id, {
        mat_id,
        density,
        friction:
          typeof row.friction === "number" ? row.friction : undefined,
      });
    }
  } catch {
    /* ignore */
  }
  return map;
}

export function parseSimulationNodes(
  blueprintJson: string | null | undefined,
): Map<string, SimNodeRow> {
  const map = new Map<string, SimNodeRow>();
  if (!blueprintJson?.trim()) return map;
  try {
    const bp = JSON.parse(blueprintJson) as {
      simulation?: { nodes?: unknown[] };
    };
    const nodes = bp.simulation?.nodes;
    if (!Array.isArray(nodes)) return map;
    for (const n of nodes) {
      if (!n || typeof n !== "object") continue;
      const row = n as Record<string, unknown>;
      const part_id = row.part_id;
      const mat_id = row.mat_id;
      if (typeof part_id !== "string" || typeof mat_id !== "string") continue;
      const mo = row.mass_override;
      map.set(part_id, {
        part_id,
        mat_id,
        mass_override:
          typeof mo === "number" && mo > 0 ? mo : null,
      });
    }
  } catch {
    /* ignore */
  }
  return map;
}

/** Плотность кг/м³ и масса кг по объёму мм³ (или null если нет данных). */
export function estimateMassKg(
  volumeMm3: number | null,
  node: SimNodeRow | undefined,
  materials: Map<string, SimMaterialRow>,
): { massKg: number | null; densityKgM3: number | null; note?: string } {
  if (node?.mass_override != null && node.mass_override > 0) {
    return { massKg: node.mass_override, densityKgM3: null, note: "override" };
  }
  if (volumeMm3 == null || !Number.isFinite(volumeMm3) || volumeMm3 <= 0) {
    return { massKg: null, densityKgM3: null };
  }
  if (!node) {
    return { massKg: null, densityKgM3: null, note: "no_node" };
  }
  const mat = materials.get(node.mat_id);
  if (!mat) {
    return { massKg: null, densityKgM3: null, note: "unknown_mat" };
  }
  const volM3 = volumeMm3 * 1e-9;
  return { massKg: volM3 * mat.density, densityKgM3: mat.density };
}
