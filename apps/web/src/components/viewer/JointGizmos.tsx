"use client";

import { Line } from "@react-three/drei";
import { useMemo } from "react";
import * as THREE from "three";

import { parseSimulationJoints } from "@/lib/kinematics";

const ANCHOR_COLOR = "#ffd966";
const AXIS_COLOR = "#66aaff";

function JointGizmoItem({
  anchor,
  axis,
  axisLength,
}: {
  anchor: THREE.Vector3;
  axis: THREE.Vector3;
  axisLength: number;
}) {
  const end = useMemo(() => {
    const d = axis.clone();
    if (d.lengthSq() < 1e-12) return anchor.clone();
    d.normalize().multiplyScalar(axisLength);
    return anchor.clone().add(d);
  }, [anchor, axis, axisLength]);

  return (
    <group>
      <mesh position={anchor}>
        <sphereGeometry args={[2, 12, 12]} />
        <meshBasicMaterial color={ANCHOR_COLOR} depthTest depthWrite />
      </mesh>
      <Line points={[anchor, end]} color={AXIS_COLOR} lineWidth={2} />
    </group>
  );
}

export function JointGizmos({
  blueprintJson,
  selectedPartId,
  jointFocusId,
}: {
  blueprintJson: string | null | undefined;
  selectedPartId: string | null;
  jointFocusId: string | null;
}) {
  const joints = useMemo(
    () => parseSimulationJoints(blueprintJson),
    [blueprintJson],
  );

  const toShow = useMemo(() => {
    if (jointFocusId) {
      return joints.filter((j) => j.joint_id === jointFocusId);
    }
    if (!selectedPartId) return [];
    return joints.filter(
      (j) =>
        j.parent_part === selectedPartId || j.child_part === selectedPartId,
    );
  }, [joints, selectedPartId, jointFocusId]);

  if (toShow.length === 0) return null;

  return (
    <group name="joint_gizmos">
      {toShow.map((j) => {
        const ax = new THREE.Vector3(j.axis[0], j.axis[1], j.axis[2]);
        if (ax.lengthSq() < 1e-12) return null;
        const anchor = new THREE.Vector3(
          j.anchor_point[0],
          j.anchor_point[1],
          j.anchor_point[2],
        );
        const axisLen = Math.min(80, Math.max(15, ax.length() * 8));
        return (
          <JointGizmoItem
            key={j.joint_id}
            anchor={anchor}
            axis={ax}
            axisLength={axisLen}
          />
        );
      })}
    </group>
  );
}
