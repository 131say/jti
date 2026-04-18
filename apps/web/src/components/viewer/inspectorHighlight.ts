import * as THREE from "three";

/** Подсветка выбранной детали и диагностики (целиком по part_id, не по граням). */
export function applyInspectorHighlight(
  root: THREE.Object3D,
  selectedPartId: string | null,
  hiddenParts: Record<string, boolean>,
  diagnosticPartIds: string[] | null = null,
): void {
  const diagSet =
    diagnosticPartIds && diagnosticPartIds.length > 0
      ? new Set(diagnosticPartIds)
      : null;

  root.traverse((o) => {
    if (!(o as THREE.Mesh).isMesh) return;
    const mesh = o as THREE.Mesh;
    const pid = (mesh.userData.part_id as string) || mesh.name;
    if (!pid) return;
    mesh.visible = !hiddenParts[pid];

    const mat = mesh.material;
    if (Array.isArray(mat)) return;
    if (!mat || !(mat as THREE.MeshStandardMaterial).isMeshStandardMaterial)
      return;
    const m = mat as THREE.MeshStandardMaterial;

    if (mesh.userData._inspectorBaseEmissive === undefined) {
      mesh.userData._inspectorBaseEmissive = m.emissive.clone();
      mesh.userData._inspectorBaseEmissiveIntensity = m.emissiveIntensity ?? 1;
    }

    if (diagSet?.has(pid)) {
      m.emissive.setHex(0x661010);
      m.emissiveIntensity = 0.65;
      return;
    }

    if (selectedPartId && pid === selectedPartId) {
      m.emissive.setHex(0x334466);
      m.emissiveIntensity = 0.5;
    } else {
      m.emissive.copy(mesh.userData._inspectorBaseEmissive as THREE.Color);
      m.emissiveIntensity =
        (mesh.userData._inspectorBaseEmissiveIntensity as number) ?? 1;
    }
  });
}
