import * as THREE from "three";

/**
 * Объём и центр масс замкнутой треугольной сетки (предполагается ориентированная оболочка).
 * Единицы — как у вершин (обычно мм³ для mm-моделей).
 */
export function computeMeshVolumeAndCom(
  geometry: THREE.BufferGeometry,
): { volume: number; com: THREE.Vector3 } | null {
  const pos = geometry.attributes.position;
  if (!pos) return null;

  const index = geometry.index;
  let vol = 0;
  const com = new THREE.Vector3();
  const a = new THREE.Vector3();
  const b = new THREE.Vector3();
  const c = new THREE.Vector3();

  const addTri = (i0: number, i1: number, i2: number) => {
    a.fromBufferAttribute(pos, i0);
    b.fromBufferAttribute(pos, i1);
    c.fromBufferAttribute(pos, i2);
    const v = a.dot(b.clone().cross(c)) / 6;
    vol += v;
    const ctr = a.clone().add(b).add(c).divideScalar(4);
    com.add(ctr.multiplyScalar(v));
  };

  if (index) {
    for (let i = 0; i < index.count; i += 3) {
      addTri(index.getX(i), index.getX(i + 1), index.getX(i + 2));
    }
  } else {
    const n = pos.count;
    for (let i = 0; i < n; i += 3) {
      addTri(i, i + 1, i + 2);
    }
  }

  if (!Number.isFinite(vol) || Math.abs(vol) < 1e-24) return null;
  com.divideScalar(vol);
  return { volume: Math.abs(vol), com };
}
