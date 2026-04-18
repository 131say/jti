import * as THREE from "three";

import { applyBlueprintMaterialsToGltfScene } from "@/lib/applyGltfMaterials";
import {
  buildKinematicTree,
  type KinematicPivot,
} from "@/lib/kinematics";

/** Имя узла GLB = part_id (CadQuery assembly); дублируем в userData для picker/highlight. */
export function tagMeshesWithPartId(scene: THREE.Object3D): void {
  scene.traverse((child) => {
    if (!(child as THREE.Mesh).isMesh || !child.name) return;
    const mesh = child as THREE.Mesh;
    mesh.userData.part_id = mesh.name;
  });
}

/**
 * Материалы из Blueprint + пересборка FK-дерева по simulation.joints.
 */
export function setupBlueprintGltfScene(
  scene: THREE.Object3D,
  blueprintJson: string | null | undefined,
): {
  pivots: KinematicPivot[];
  warning: string | null;
} {
  applyBlueprintMaterialsToGltfScene(scene, blueprintJson);
  tagMeshesWithPartId(scene);
  return buildKinematicTree(scene, blueprintJson);
}
