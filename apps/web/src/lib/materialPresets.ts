/**
 * Пресеты материалов — зеркало `services/worker/core/materials.py`
 * для визуала STL (формат не хранит цвет; красим MeshStandardMaterial на фронте).
 */

export type ViewerPbrParams = {
  color: string;
  roughness: number;
  metalness: number;
};

const PRESETS: Record<
  string,
  { r: number; g: number; b: number; roughness: number }
> = {
  steel: { r: 0.42, g: 0.44, b: 0.47, roughness: 0.28 },
  aluminum_6061: { r: 0.65, g: 0.66, b: 0.7, roughness: 0.48 },
  abs_plastic: { r: 0.18, g: 0.35, b: 0.65, roughness: 0.82 },
  rubber: { r: 0.12, g: 0.12, b: 0.12, roughness: 0.94 },
};

const DEFAULT_VIEWER: ViewerPbrParams = {
  color: "#a3a3a3",
  roughness: 0.45,
  metalness: 0.25,
};

function hexToRgb01(hex: string): { r: number; g: number; b: number } {
  let s = hex.trim();
  if (s.startsWith("#")) s = s.slice(1);
  if (s.length !== 6) throw new Error(`hex: ${hex}`);
  return {
    r: parseInt(s.slice(0, 2), 16) / 255,
    g: parseInt(s.slice(2, 4), 16) / 255,
    b: parseInt(s.slice(4, 6), 16) / 255,
  };
}

function rgb01ToHex(r: number, g: number, b: number): string {
  const toHex = (x: number) =>
    Math.round(Math.min(255, Math.max(0, x * 255)))
      .toString(16)
      .padStart(2, "0");
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

function metalnessHint(
  presetKey: string | undefined,
  roughness: number,
): number {
  if (presetKey === "steel" || presetKey === "aluminum_6061") {
    return Math.min(0.92, 0.55 + (0.55 - roughness) * 0.6);
  }
  if (presetKey === "abs_plastic" || presetKey === "rubber") {
    return 0.04;
  }
  return Math.max(0.08, Math.min(0.45, 0.5 - roughness * 0.35));
}

/** Одна деталь Blueprint → PBR (пресет и/или visual). */
export function resolvePartViewerMaterial(part: unknown): ViewerPbrParams | null {
  if (!part || typeof part !== "object") return null;
  const p = part as Record<string, unknown>;
  const key =
    typeof p.material === "string" && p.material.trim()
      ? p.material.trim()
      : null;
  const vis =
    p.visual && typeof p.visual === "object"
      ? (p.visual as Record<string, unknown>)
      : null;

  let r: number;
  let g: number;
  let b: number;
  let roughness: number;
  let presetKey: string | undefined;

  if (key && PRESETS[key]) {
    presetKey = key;
    const pr = PRESETS[key];
    r = pr.r;
    g = pr.g;
    b = pr.b;
    roughness = pr.roughness;
  } else if (vis?.color && typeof vis.color === "string") {
    try {
      const rgb = hexToRgb01(vis.color);
      r = rgb.r;
      g = rgb.g;
      b = rgb.b;
      roughness =
        typeof vis.roughness === "number" && Number.isFinite(vis.roughness)
          ? Math.min(1, Math.max(0, vis.roughness))
          : 0.55;
    } catch {
      return null;
    }
  } else {
    return null;
  }

  if (vis && typeof vis.roughness === "number" && Number.isFinite(vis.roughness)) {
    roughness = Math.min(1, Math.max(0, vis.roughness));
  }
  if (vis?.color && typeof vis.color === "string" && presetKey && PRESETS[presetKey]) {
    try {
      const rgb = hexToRgb01(vis.color);
      r = rgb.r;
      g = rgb.g;
      b = rgb.b;
    } catch {
      /* оставить цвет пресета */
    }
  }

  const metalness = metalnessHint(presetKey, roughness);
  return {
    color: rgb01ToHex(r, g, b),
    roughness,
    metalness,
  };
}

/**
 * STL с бэкенда — один компаунд на всю сборку: среднее по деталям с заданным материалом.
 * Полноценная покраска по part_id потребует отдельных STL/GLB на деталь.
 */
export function resolveMergedStlMaterial(
  blueprintJson: string | null | undefined,
): ViewerPbrParams {
  if (!blueprintJson?.trim()) return DEFAULT_VIEWER;
  try {
    const bp = JSON.parse(blueprintJson) as {
      geometry?: { parts?: unknown[] };
    };
    const parts = bp.geometry?.parts;
    if (!Array.isArray(parts) || parts.length === 0) return DEFAULT_VIEWER;

    const resolved = parts
      .map((part) => resolvePartViewerMaterial(part))
      .filter((x): x is ViewerPbrParams => x !== null);

    if (resolved.length === 0) return DEFAULT_VIEWER;
    if (resolved.length === 1) return resolved[0];

    let rSum = 0;
    let gSum = 0;
    let bSum = 0;
    for (const m of resolved) {
      const rgb = hexToRgb01(m.color);
      rSum += rgb.r;
      gSum += rgb.g;
      bSum += rgb.b;
    }
    const n = resolved.length;
    const color = rgb01ToHex(rSum / n, gSum / n, bSum / n);
    const roughness =
      resolved.reduce((s, m) => s + m.roughness, 0) / resolved.length;
    const metalness =
      resolved.reduce((s, m) => s + m.metalness, 0) / resolved.length;
    return { color, roughness, metalness };
  } catch {
    return DEFAULT_VIEWER;
  }
}
