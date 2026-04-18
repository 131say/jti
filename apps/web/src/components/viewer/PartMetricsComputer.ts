import * as THREE from "three";

import { computeMeshVolumeAndCom } from "@/lib/meshMetrics";

export type PartMetricEntry = {
  volumeMm3: number;
  comWorld: THREE.Vector3;
};

/** После FK-сборки: объём и COM в мировых координатах (мм / мм). */
export function computePartMetricsMap(
  root: THREE.Object3D,
): Map<string, PartMetricEntry> {
  const m = new Map<string, PartMetricEntry>();
  root.updateWorldMatrix(true, true);
  root.traverse((o) => {
    if (!(o as THREE.Mesh).isMesh || !o.name) return;
    const mesh = o as THREE.Mesh;
    const pid = (mesh.userData.part_id as string) || mesh.name;
    const r = computeMeshVolumeAndCom(mesh.geometry);
    if (!r) return;
    const comWorld = r.com.clone().applyMatrix4(mesh.matrixWorld);
    m.set(pid, { volumeMm3: r.volume, comWorld });
  });
  return m;
}
