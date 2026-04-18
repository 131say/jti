"use client";

import { Eye, EyeOff } from "lucide-react";

import type { BlueprintPartRow } from "@/lib/blueprintDiagnostics";
import type { SimulationJointRow } from "@/lib/kinematics";

export function SceneTree({
  parts,
  joints,
  selectedPartId,
  jointFocusId,
  hiddenParts,
  onSelectPart,
  onToggleHidden,
  onSelectJoint,
}: {
  parts: BlueprintPartRow[];
  joints: SimulationJointRow[];
  selectedPartId: string | null;
  jointFocusId: string | null;
  hiddenParts: Record<string, boolean>;
  onSelectPart: (id: string | null) => void;
  onToggleHidden: (partId: string) => void;
  onSelectJoint: (jointId: string | null) => void;
}) {
  if (parts.length === 0) {
    return (
      <div className="text-[11px] text-neutral-500">
        Нет списка деталей (нужен валидный Blueprint с geometry.parts).
      </div>
    );
  }

  const jointsForPart = (pid: string) =>
    joints.filter(
      (j) => j.parent_part === pid || j.child_part === pid,
    );

  return (
    <div className="flex min-h-0 flex-col gap-1">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-neutral-500">
        Сцена
      </div>
      <ul className="max-h-[140px] space-y-0.5 overflow-y-auto pr-1 text-[11px]">
        {parts.map((p) => {
          const sel = selectedPartId === p.part_id;
          const hid = !!hiddenParts[p.part_id];
          return (
            <li key={p.part_id}>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  title={hid ? "Показать" : "Скрыть"}
                  className="shrink-0 rounded p-0.5 text-neutral-400 hover:bg-neutral-800 hover:text-neutral-100"
                  onClick={(e) => {
                    e.stopPropagation();
                    onToggleHidden(p.part_id);
                  }}
                >
                  {hid ? (
                    <EyeOff className="h-3.5 w-3.5" aria-hidden />
                  ) : (
                    <Eye className="h-3.5 w-3.5" aria-hidden />
                  )}
                </button>
                <button
                  type="button"
                  className={`min-w-0 flex-1 truncate rounded px-1.5 py-0.5 text-left ${
                    sel
                      ? "bg-neutral-700 text-neutral-50"
                      : "text-neutral-300 hover:bg-neutral-800/80"
                  }`}
                  onClick={() => {
                    onSelectPart(p.part_id);
                    onSelectJoint(null);
                  }}
                >
                  <span className="font-medium">{p.part_id}</span>
                  {p.base_shape ? (
                    <span className="ml-1 text-neutral-500">
                      ({p.base_shape})
                    </span>
                  ) : null}
                </button>
              </div>
              {sel && jointsForPart(p.part_id).length > 0 ? (
                <ul className="ml-6 mt-0.5 space-y-0.5 border-l border-neutral-700 pl-2">
                  {jointsForPart(p.part_id).map((j) => (
                    <li key={j.joint_id}>
                      <button
                        type="button"
                        className={`truncate rounded px-1 py-0.5 text-left text-[10px] ${
                          jointFocusId === j.joint_id
                            ? "text-amber-200"
                            : "text-neutral-500 hover:text-neutral-300"
                        }`}
                        onClick={() => onSelectJoint(j.joint_id)}
                      >
                        {j.joint_id}{" "}
                        <span className="text-neutral-600">({j.type})</span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
