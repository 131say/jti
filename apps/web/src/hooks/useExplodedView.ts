import { useMemo } from "react";

import {
  type ExplodeMateInfo,
  parseExplodeBlueprint,
} from "@/lib/explodedView";

export type UseExplodedViewResult = {
  /** Есть ли assembly_mates с hole для разнесения. */
  canExplode: boolean;
  info: ExplodeMateInfo;
};

/**
 * Разбор Blueprint для интерактивного разнесённого вида (v3.1 UI).
 * Корневые детали (не source в mates) не смещаются; вектор — из direction hole + reverse_direction.
 */
export function useExplodedView(
  blueprintJson: string | null | undefined,
): UseExplodedViewResult {
  const info = useMemo(
    () => parseExplodeBlueprint(blueprintJson ?? null),
    [blueprintJson],
  );
  return { canExplode: info.hasExplode, info };
}
