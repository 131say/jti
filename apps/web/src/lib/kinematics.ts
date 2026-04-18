import * as THREE from "three";

/** Описание шарнира для анимации после сборки pivot-дерева. */
export type KinematicPivot = {
  pivot: THREE.Group;
  kind: "hinge" | "slider";
  axisWorld: THREE.Vector3;
  angleMin: number;
  angleMax: number;
  slideMin: number;
  slideMax: number;
  /** Локальная позиция pivot сразу после attach (якорь). */
  baseLocalPos: THREE.Vector3;
};

export type KinematicBuildResult = {
  pivots: KinematicPivot[];
  warning: string | null;
};

export type SimulationJointRow = {
  joint_id: string;
  type: string;
  parent_part: string;
  child_part: string;
  anchor_point: [number, number, number];
  axis: [number, number, number];
  limits?: [number, number] | null;
};

type JointRow = SimulationJointRow;

/** Сырые строки joints из Blueprint (для кинематики и gizmo в viewer). */
export function parseSimulationJoints(
  blueprintJson: string | null | undefined,
): JointRow[] {
  return parseJoints(blueprintJson);
}

function parseJoints(blueprintJson: string | null | undefined): JointRow[] {
  if (!blueprintJson?.trim()) return [];
  try {
    const bp = JSON.parse(blueprintJson) as {
      simulation?: { joints?: unknown };
    };
    const raw = bp.simulation?.joints;
    if (!Array.isArray(raw)) return [];
    return raw.filter(
      (j): j is JointRow =>
        j != null &&
        typeof j === "object" &&
        typeof (j as JointRow).parent_part === "string" &&
        typeof (j as JointRow).child_part === "string" &&
        Array.isArray((j as JointRow).anchor_point) &&
        Array.isArray((j as JointRow).axis),
    );
  } catch {
    return [];
  }
}

function findDuplicateChild(joints: JointRow[]): boolean {
  const seen = new Set<string>();
  for (const j of joints) {
    if (seen.has(j.child_part)) return true;
    seen.add(j.child_part);
  }
  return false;
}

function hasDirectedCycle(joints: JointRow[]): boolean {
  if (joints.length === 0) return false;
  const adj = new Map<string, string[]>();
  const nodes = new Set<string>();
  for (const j of joints) {
    nodes.add(j.parent_part);
    nodes.add(j.child_part);
    if (!adj.has(j.parent_part)) adj.set(j.parent_part, []);
    adj.get(j.parent_part)!.push(j.child_part);
  }
  const visited = new Set<string>();
  const stack = new Set<string>();

  function dfs(u: string): boolean {
    if (stack.has(u)) return true;
    if (visited.has(u)) return false;
    visited.add(u);
    stack.add(u);
    for (const v of adj.get(u) || []) {
      if (dfs(v)) return true;
    }
    stack.delete(u);
    return false;
  }

  for (const n of nodes) {
    if (!visited.has(n) && dfs(n)) return true;
  }
  return false;
}

function sortJointsForAssembly(joints: JointRow[]): JointRow[] | null {
  const childSet = new Set(joints.map((j) => j.child_part));
  const roots = new Set(
    [...new Set(joints.map((j) => j.parent_part))].filter(
      (p) => !childSet.has(p),
    ),
  );
  const result: JointRow[] = [];
  const remaining = [...joints];
  while (remaining.length) {
    let idx = remaining.findIndex((j) => roots.has(j.parent_part));
    if (idx < 0) {
      idx = remaining.findIndex((j) =>
        result.some((r) => r.child_part === j.parent_part),
      );
    }
    if (idx < 0) return null;
    const j = remaining[idx]!;
    result.push(j);
    remaining.splice(idx, 1);
    roots.add(j.child_part);
  }
  return result;
}

function findMeshByPartId(
  scene: THREE.Object3D,
  partId: string,
): THREE.Mesh | null {
  let found: THREE.Mesh | null = null;
  scene.traverse((o) => {
    if (o.name === partId && (o as THREE.Mesh).isMesh) {
      found = o as THREE.Mesh;
    }
  });
  return found;
}

export function buildKinematicTree(
  scene: THREE.Object3D,
  blueprintJson: string | null | undefined,
): KinematicBuildResult {
  const joints = parseJoints(blueprintJson);
  const pivots: KinematicPivot[] = [];
  if (joints.length === 0) {
    return { pivots, warning: null };
  }

  if (findDuplicateChild(joints)) {
    return {
      pivots,
      warning:
        "Один и тот же child_part встречается в нескольких joints — кинематический превью недоступен.",
    };
  }

  if (hasDirectedCycle(joints)) {
    return {
      pivots,
      warning:
        "Обнаружен замкнутый контур в joints. Для полной анимации используйте MuJoCo.",
    };
  }

  const ordered = sortJointsForAssembly(joints);
  if (!ordered) {
    return {
      pivots,
      warning:
        "Не удалось упорядочить joints (возможна замкнутая цепь). Превью кинематики отключено.",
    };
  }

  for (const j of ordered) {
    if (j.type !== "hinge" && j.type !== "slider") {
      continue;
    }

    const parentMesh = findMeshByPartId(scene, j.parent_part);
    const childMesh = findMeshByPartId(scene, j.child_part);
    if (!parentMesh || !childMesh) {
      continue;
    }

    const axis = new THREE.Vector3(j.axis[0], j.axis[1], j.axis[2]);
    if (axis.lengthSq() < 1e-12) continue;
    axis.normalize();

    const pivot = new THREE.Group();
    pivot.name = `pivot_${j.joint_id}`;

    parentMesh.updateWorldMatrix(true, true);
    const anchorWorld = new THREE.Vector3(
      j.anchor_point[0],
      j.anchor_point[1],
      j.anchor_point[2],
    );
    const anchorLocal = anchorWorld.clone();
    parentMesh.worldToLocal(anchorLocal);
    pivot.position.copy(anchorLocal);

    parentMesh.add(pivot);
    pivot.attach(childMesh);

    const baseLocalPos = pivot.position.clone();

    const lim = j.limits;
    let angleMin = 0;
    let angleMax = Math.PI * 2;
    let slideMin = 0;
    let slideMax = 100;
    if (lim && lim.length === 2 && Number.isFinite(lim[0]) && Number.isFinite(lim[1])) {
      if (j.type === "hinge") {
        angleMin = lim[0];
        angleMax = lim[1];
      } else {
        slideMin = lim[0];
        slideMax = lim[1];
      }
    }

    pivots.push({
      pivot,
      kind: j.type === "hinge" ? "hinge" : "slider",
      axisWorld: axis,
      angleMin,
      angleMax,
      slideMin,
      slideMax,
      baseLocalPos,
    });
  }

  return { pivots, warning: null };
}

/** t ∈ [0,1] — положение слайдера «тест шарниров». */
export function applyKinematicPose(pivots: KinematicPivot[], t: number): void {
  const tt = Math.min(1, Math.max(0, t));
  for (const pj of pivots) {
    if (pj.kind === "hinge") {
      const angle = pj.angleMin + tt * (pj.angleMax - pj.angleMin);
      pj.pivot.quaternion.identity();
      pj.pivot.rotateOnWorldAxis(pj.axisWorld, angle);
    } else {
      const d = pj.slideMin + tt * (pj.slideMax - pj.slideMin);
      pj.pivot.quaternion.identity();
      const parent = pj.pivot.parent;
      if (parent) {
        const axisLocal = pj.axisWorld
          .clone()
          .transformDirection(
            new THREE.Matrix4().copy(parent.matrixWorld).invert(),
          );
        pj.pivot.position.copy(pj.baseLocalPos).add(axisLocal.multiplyScalar(d));
      } else {
        pj.pivot.position.copy(pj.baseLocalPos);
      }
    }
  }
}
