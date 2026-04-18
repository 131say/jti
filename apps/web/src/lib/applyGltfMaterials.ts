import * as THREE from "three";

import { resolvePartViewerMaterial } from "@/lib/materialPresets";

function disposeMaterial(m: THREE.Material | THREE.Material[]): void {
  if (Array.isArray(m)) {
    m.forEach((x) => x.dispose());
  } else {
    m.dispose();
  }
}

/**
 * Накладывает PBR-материалы из Blueprint на меши GLB (имя меша = part_id из CadQuery).
 */
export function applyBlueprintMaterialsToGltfScene(
  scene: THREE.Object3D,
  blueprintJson: string | null | undefined,
): void {
  if (!blueprintJson?.trim()) return;
  let bp: { geometry?: { parts?: unknown[] } };
  try {
    bp = JSON.parse(blueprintJson) as { geometry?: { parts?: unknown[] } };
  } catch {
    return;
  }
  const parts = bp.geometry?.parts;
  if (!Array.isArray(parts)) return;

  const byPartId = new Map<string, unknown>();
  for (const p of parts) {
    if (p && typeof p === "object") {
      const id = (p as { part_id?: string }).part_id;
      if (typeof id === "string" && id.length > 0) {
        byPartId.set(id, p);
      }
    }
  }
  if (byPartId.size === 0) return;

  scene.traverse((child) => {
    if (!child.name || !(child as THREE.Mesh).isMesh) return;
    const mesh = child as THREE.Mesh;
    const part = byPartId.get(mesh.name);
    if (part === undefined) return;

    const pbr = resolvePartViewerMaterial(part);
    if (!pbr) return;

    const mat = new THREE.MeshStandardMaterial({
      color: pbr.color,
      roughness: pbr.roughness,
      metalness: pbr.metalness,
      envMapIntensity: 1.15,
    });
    disposeMaterial(mesh.material);
    mesh.material = mat;
    mesh.userData.part_id = mesh.name;
  });
}
