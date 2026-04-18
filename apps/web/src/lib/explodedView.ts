/**
 * Интерактивный разнесённый вид (MVP): векторы из assembly_mates + direction hole в Blueprint.
 * Корневые детали (не source в mates) неподвижны; зависимые смещаются по оси отверстия.
 */

import * as THREE from "three";

/** Результат разбора assembly_mates для UI разнесения. */
export type ExplodeMateInfo = {
  /** part_id → нормализованный вектор разлёта в мировых осях (как в JSON после поворота цели). */
  sourceDirections: Map<string, THREE.Vector3>;
  /** part_id, которые не являются source ни в одном mate — не двигаем. */
  roots: Set<string>;
  hasExplode: boolean;
};

type BpPart = {
  part_id?: string;
  position?: [number, number, number];
  rotation?: [number, number, number];
  operations?: unknown[];
};

type BpMate = {
  type?: string;
  source_part?: string;
  target_part?: string;
  target_operation_index?: number;
  reverse_direction?: boolean;
};

/** Локальный direction hole → мировой, если задан rotation детали (градусы, порядок XYZ как cq.Rot). */
export function holeDirectionToWorld(
  dir: [number, number, number],
  rotationDeg?: [number, number, number] | null,
): THREE.Vector3 {
  const v = new THREE.Vector3(dir[0], dir[1], dir[2]);
  if (v.lengthSq() < 1e-12) return new THREE.Vector3(0, 0, 1);
  v.normalize();
  if (rotationDeg && rotationDeg.length === 3) {
    const e = new THREE.Euler(
      THREE.MathUtils.degToRad(rotationDeg[0]),
      THREE.MathUtils.degToRad(rotationDeg[1]),
      THREE.MathUtils.degToRad(rotationDeg[2]),
      "XYZ",
    );
    v.applyEuler(e);
  }
  return v.normalize();
}

function findHoleOperation(
  part: BpPart | undefined,
  index: number,
): { direction: [number, number, number] } | null {
  const ops = part?.operations;
  if (!Array.isArray(ops) || index < 0 || index >= ops.length) return null;
  const op = ops[index] as { type?: string; direction?: number[] };
  if (op?.type !== "hole" || !Array.isArray(op.direction) || op.direction.length !== 3) {
    return null;
  }
  return {
    direction: [op.direction[0], op.direction[1], op.direction[2]],
  };
}

/**
 * Разбор Blueprint: первый mate на каждый source_part; направление из operations[target][idx].
 */
export function parseExplodeBlueprint(
  blueprintJson: string | null | undefined,
): ExplodeMateInfo {
  const empty: ExplodeMateInfo = {
    sourceDirections: new Map(),
    roots: new Set(),
    hasExplode: false,
  };
  if (!blueprintJson?.trim()) return empty;
  try {
    const bp = JSON.parse(blueprintJson) as {
      geometry?: { parts?: BpPart[] };
      assembly_mates?: BpMate[];
    };
    const parts = bp.geometry?.parts;
    const mates = bp.assembly_mates;
    if (!Array.isArray(parts) || parts.length === 0) return empty;
    if (!Array.isArray(mates) || mates.length === 0) return empty;

    const byId = new Map<string, BpPart>();
    for (const p of parts) {
      const id = p.part_id;
      if (typeof id === "string" && id) byId.set(id, p);
    }

    const firstMateBySource = new Map<string, BpMate>();
    for (const m of mates) {
      if (!m || typeof m !== "object") continue;
      if (m.type !== "snap_to_operation") continue;
      const src = m.source_part;
      if (typeof src !== "string" || !src) continue;
      if (!firstMateBySource.has(src)) firstMateBySource.set(src, m);
    }

    const sourceDirections = new Map<string, THREE.Vector3>();
    for (const [src, m] of firstMateBySource) {
      const tgt = m.target_part;
      const idx = m.target_operation_index;
      if (typeof tgt !== "string" || !tgt || typeof idx !== "number" || idx < 0) continue;
      const targetPart = byId.get(tgt);
      const hole = findHoleOperation(targetPart, idx);
      if (!hole) continue;
      const rot = targetPart?.rotation as [number, number, number] | undefined;
      let w = holeDirectionToWorld(hole.direction, rot ?? null);
      if (m.reverse_direction) w.multiplyScalar(-1);
      sourceDirections.set(src, w.normalize());
    }

    if (sourceDirections.size === 0) return empty;

    const roots = new Set<string>();
    for (const p of parts) {
      const id = p.part_id;
      if (typeof id !== "string" || !id) continue;
      if (!sourceDirections.has(id)) roots.add(id);
    }

    return {
      sourceDirections,
      roots,
      hasExplode: true,
    };
  } catch {
    return empty;
  }
}

export function findMeshesByPartId(
  scene: THREE.Object3D,
  partId: string,
): THREE.Mesh[] {
  const out: THREE.Mesh[] = [];
  scene.traverse((o) => {
    if (o.name === partId && (o as THREE.Mesh).isMesh) {
      out.push(o as THREE.Mesh);
    }
  });
  return out;
}

/**
 * Вставляет группу __explode_<partId> между родителем и мешами источника (один раз).
 */
export function wrapMeshesForExplode(
  scene: THREE.Object3D,
  sourcePartIds: string[],
): void {
  for (const partId of sourcePartIds) {
    const meshes = findMeshesByPartId(scene, partId);
    if (meshes.length === 0) continue;
    if (meshes.some((m) => m.parent?.name?.startsWith("__explode_"))) continue;
    const parent = meshes[0]!.parent;
    if (!parent) continue;
    const g = new THREE.Group();
    g.name = `__explode_${partId}`;
    for (const mesh of meshes) {
      if (mesh.parent !== parent) continue;
      parent.remove(mesh);
      g.add(mesh);
    }
    parent.add(g);
  }
}

/** Максимальное смещение (мм) при 100% ползунка; масштабируется от диагонали сцены. */
export function computeExplodeMaxMm(scene: THREE.Object3D): number {
  const box = new THREE.Box3().setFromObject(scene);
  const size = new THREE.Vector3();
  box.getSize(size);
  const diag = size.length();
  if (!Number.isFinite(diag) || diag < 1e-6) return 80;
  return Math.min(200, Math.max(40, diag * 0.35));
}

/**
 * После kinematic: задаёт локальное смещение группы __explode_* вдоль мирового вектора.
 */
export function applyExplodeOffsets(
  scene: THREE.Object3D,
  sourceDirections: Map<string, THREE.Vector3>,
  explodeT: number,
  maxMm: number,
): void {
  const t = Math.min(1, Math.max(0, explodeT));
  const dist = t * maxMm;
  scene.traverse((o) => {
    if (!o.name.startsWith("__explode_")) return;
    const partId = o.name.slice("__explode_".length);
    const dir = sourceDirections.get(partId);
    if (!dir) return;
    const parent = o.parent;
    if (!parent) return;
    parent.updateWorldMatrix(true, true);
    const worldOffset = dir.clone().multiplyScalar(dist);
    const q = new THREE.Quaternion();
    parent.getWorldQuaternion(q);
    const invQ = q.clone().invert();
    const local = worldOffset.applyQuaternion(invQ);
    if (o instanceof THREE.Group) {
      o.position.copy(local);
    }
  });
}
