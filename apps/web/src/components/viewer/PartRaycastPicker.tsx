"use client";

import { useThree } from "@react-three/fiber";
import { useEffect, useRef } from "react";
import * as THREE from "three";

const DRAG_PX2 = 64;

/**
 * Клик по мешу (без заметного drag) → part_id из userData/name.
 */
export function PartRaycastPicker({
  root,
  enabled,
  onSelectPart,
}: {
  root: THREE.Object3D | null;
  enabled: boolean;
  onSelectPart: (id: string | null) => void;
}) {
  const { camera, gl } = useThree();
  const drag = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    if (!enabled || !root) return;
    const el = gl.domElement;
    const down = (e: PointerEvent) => {
      drag.current = { x: e.clientX, y: e.clientY };
    };
    const up = (e: PointerEvent) => {
      if (!drag.current) return;
      const dx = e.clientX - drag.current.x;
      const dy = e.clientY - drag.current.y;
      drag.current = null;
      if (dx * dx + dy * dy > DRAG_PX2) return;

      const rect = el.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      const raycaster = new THREE.Raycaster();
      raycaster.setFromCamera(new THREE.Vector2(x, y), camera);
      const hits = raycaster.intersectObject(root, true);
      if (hits.length === 0) {
        onSelectPart(null);
        return;
      }
      let o: THREE.Object3D | null = hits[0].object;
      while (o) {
        const mesh = o as THREE.Mesh;
        if (mesh.isMesh) {
          const pid = (mesh.userData.part_id as string) || mesh.name;
          if (pid) {
            onSelectPart(pid);
            return;
          }
        }
        o = o.parent;
      }
      onSelectPart(null);
    };
    el.addEventListener("pointerdown", down);
    el.addEventListener("pointerup", up);
    return () => {
      el.removeEventListener("pointerdown", down);
      el.removeEventListener("pointerup", up);
    };
  }, [root, camera, gl, enabled, onSelectPart]);

  return null;
}
