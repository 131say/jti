"use client";

import { Canvas, useFrame, useLoader } from "@react-three/fiber";
import { Html, OrbitControls, Stage, useGLTF, useProgress } from "@react-three/drei";
import {
  Suspense,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import * as THREE from "three";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";

import { parseBlueprintParts } from "@/lib/blueprintDiagnostics";
import { setupBlueprintGltfScene } from "@/lib/blueprintScene";
import {
  applyKinematicPose,
  parseSimulationJoints,
  type KinematicPivot,
} from "@/lib/kinematics";
import {
  type ViewerPbrParams,
  resolveMergedStlMaterial,
} from "@/lib/materialPresets";
import {
  applyExplodeOffsets,
  computeExplodeMaxMm,
  type ExplodeMateInfo,
  wrapMeshesForExplode,
} from "@/lib/explodedView";
import { useExplodedView } from "@/hooks/useExplodedView";

import { BomTable } from "@/components/viewer/BomTable";
import { DrawingsViewer } from "@/components/viewer/DrawingsViewer";
import { DiagnosticsPanel } from "@/components/viewer/DiagnosticsPanel";
import { JointGizmos } from "@/components/viewer/JointGizmos";
import { PartInspector } from "@/components/viewer/PartInspector";
import { PartRaycastPicker } from "@/components/viewer/PartRaycastPicker";
import {
  computePartMetricsMap,
  type PartMetricEntry,
} from "@/components/viewer/PartMetricsComputer";
import { SceneTree } from "@/components/viewer/SceneTree";
import { applyInspectorHighlight } from "@/components/viewer/inspectorHighlight";
import type { JobBom, JobDiagnostics } from "@/lib/api";

function Loader() {
  const { progress } = useProgress();
  return (
    <Html center>
      <div className="rounded bg-neutral-900/90 px-3 py-2 text-sm text-white shadow">
        Загрузка: {progress.toFixed(0)}%
      </div>
    </Html>
  );
}

export function isStlUrl(url: string) {
  const path = url.split("?")[0].toLowerCase();
  return path.endsWith(".stl");
}

function StlMesh({
  url,
  pbr,
  onLoaded,
}: {
  url: string;
  pbr: ViewerPbrParams;
  onLoaded?: () => void;
}) {
  const geometry = useLoader(STLLoader, url);
  useLayoutEffect(() => {
    onLoaded?.();
  }, [geometry, onLoaded]);
  return (
    <mesh geometry={geometry}>
      <meshStandardMaterial
        color={pbr.color}
        metalness={pbr.metalness}
        roughness={pbr.roughness}
        envMapIntensity={1.15}
      />
    </mesh>
  );
}

function disposeObject3D(root: THREE.Object3D) {
  root.traverse((o) => {
    if ((o as THREE.Mesh).isMesh) {
      const m = o as THREE.Mesh;
      m.geometry?.dispose();
      const mat = m.material;
      if (Array.isArray(mat)) mat.forEach((x) => x.dispose());
      else mat?.dispose();
    }
  });
}

/** GLB: клон сцены + материалы + pivot-дерево; покадровая FK по слайдеру. */
function GltfBlueprintMesh({
  url,
  blueprintJson,
  kinematicSlider,
  explodeSlider,
  explodeMateInfo,
  onKinematicReady,
  onLoaded,
  selectedPartId,
  hiddenParts,
  diagnosticPartIds,
  onPartMetricsReady,
  onSelectPartFromCanvas,
}: {
  url: string;
  blueprintJson?: string | null;
  kinematicSlider: number;
  explodeSlider: number;
  explodeMateInfo: ExplodeMateInfo;
  onKinematicReady: (info: {
    pivots: number;
    warning: string | null;
  }) => void;
  onLoaded?: () => void;
  selectedPartId: string | null;
  hiddenParts: Record<string, boolean>;
  diagnosticPartIds: string[] | null;
  onPartMetricsReady: (m: Map<string, PartMetricEntry>) => void;
  onSelectPartFromCanvas: (id: string | null) => void;
}) {
  const gltf = useGLTF(url);
  const [root, setRoot] = useState<THREE.Group | null>(null);
  const pivotsRef = useRef<KinematicPivot[]>([]);
  const explodeMaxMmRef = useRef(80);

  useLayoutEffect(() => {
    const cloned = gltf.scene.clone(true);
    const { pivots, warning } = setupBlueprintGltfScene(cloned, blueprintJson);
    pivotsRef.current = pivots;
    onKinematicReady({ pivots: pivots.length, warning });
    if (explodeMateInfo.hasExplode) {
      wrapMeshesForExplode(
        cloned,
        [...explodeMateInfo.sourceDirections.keys()],
      );
      explodeMaxMmRef.current = computeExplodeMaxMm(cloned);
    }
    setRoot(cloned);
    onLoaded?.();
    return () => {
      disposeObject3D(cloned);
    };
  }, [gltf, blueprintJson, onKinematicReady, onLoaded, explodeMateInfo]);

  useLayoutEffect(() => {
    if (!root) return;
    applyInspectorHighlight(
      root,
      selectedPartId,
      hiddenParts,
      diagnosticPartIds,
    );
  }, [root, selectedPartId, hiddenParts, diagnosticPartIds]);

  useLayoutEffect(() => {
    if (!root) return;
    applyKinematicPose(pivotsRef.current, kinematicSlider / 100);
    if (explodeMateInfo.hasExplode) {
      applyExplodeOffsets(
        root,
        explodeMateInfo.sourceDirections,
        explodeSlider / 100,
        explodeMaxMmRef.current,
      );
    }
    root.updateWorldMatrix(true, true);
    onPartMetricsReady(computePartMetricsMap(root));
  }, [
    root,
    kinematicSlider,
    explodeSlider,
    explodeMateInfo,
    onPartMetricsReady,
  ]);

  useFrame(() => {
    applyKinematicPose(pivotsRef.current, kinematicSlider / 100);
    if (root && explodeMateInfo.hasExplode) {
      applyExplodeOffsets(
        root,
        explodeMateInfo.sourceDirections,
        explodeSlider / 100,
        explodeMaxMmRef.current,
      );
    }
  });

  if (!root) return null;
  return (
    <>
      <primitive object={root} />
      <PartRaycastPicker
        root={root}
        enabled
        onSelectPart={onSelectPartFromCanvas}
      />
    </>
  );
}

function SceneContent({
  url,
  blueprintJson,
  kinematicSlider,
  explodeSlider,
  explodeMateInfo,
  onKinematicReady,
  onLoaded,
  selectedPartId,
  hiddenParts,
  diagnosticPartIds,
  onPartMetricsReady,
  onSelectPartFromCanvas,
}: {
  url: string;
  blueprintJson?: string | null;
  kinematicSlider: number;
  explodeSlider: number;
  explodeMateInfo: ExplodeMateInfo;
  onKinematicReady: (info: {
    pivots: number;
    warning: string | null;
  }) => void;
  onLoaded?: () => void;
  selectedPartId: string | null;
  hiddenParts: Record<string, boolean>;
  diagnosticPartIds: string[] | null;
  onPartMetricsReady: (m: Map<string, PartMetricEntry>) => void;
  onSelectPartFromCanvas: (id: string | null) => void;
}) {
  useLayoutEffect(() => {
    if (isStlUrl(url)) {
      onKinematicReady({ pivots: 0, warning: null });
    }
  }, [url, onKinematicReady]);

  const pbrMerged = useMemo(
    () => resolveMergedStlMaterial(blueprintJson ?? null),
    [blueprintJson],
  );
  if (isStlUrl(url)) {
    return <StlMesh url={url} pbr={pbrMerged} onLoaded={onLoaded} />;
  }
  return (
    <GltfBlueprintMesh
      url={url}
      blueprintJson={blueprintJson}
      kinematicSlider={kinematicSlider}
      explodeSlider={explodeSlider}
      explodeMateInfo={explodeMateInfo}
      onKinematicReady={onKinematicReady}
      onLoaded={onLoaded}
      selectedPartId={selectedPartId}
      hiddenParts={hiddenParts}
      diagnosticPartIds={diagnosticPartIds}
      onPartMetricsReady={onPartMetricsReady}
      onSelectPartFromCanvas={onSelectPartFromCanvas}
    />
  );
}

export function ModelViewer({
  url,
  blueprintJson,
  bom,
  zipUrl,
  drawingsUrls,
  diagnostics,
  onLoaded,
}: {
  url: string;
  blueprintJson?: string | null;
  /** BOM с API (после успешной генерации). */
  bom?: JobBom | null;
  zipUrl?: string | null;
  /** Presigned URL SVG 2D-превью (по одному на вид). */
  drawingsUrls?: string[] | null;
  /** Результаты DFM с воркера. */
  diagnostics?: JobDiagnostics | null;
  onLoaded?: () => void;
}) {
  const [kinematicSlider, setKinematicSlider] = useState(0);
  const [explodeSlider, setExplodeSlider] = useState(0);
  const [kinematicInfo, setKinematicInfo] = useState<{
    pivots: number;
    warning: string | null;
  }>({ pivots: 0, warning: null });

  const [selectedPartId, setSelectedPartId] = useState<string | null>(null);
  const [jointFocusId, setJointFocusId] = useState<string | null>(null);
  const [hiddenParts, setHiddenParts] = useState<Record<string, boolean>>({});
  const [metricsByPart, setMetricsByPart] = useState<Map<
    string,
    PartMetricEntry
  > | null>(null);
  const [viewerTab, setViewerTab] = useState<
    "scene" | "bom" | "diagnostics" | "drawings"
  >("scene");
  const [diagnosticHighlightIds, setDiagnosticHighlightIds] = useState<
    string[] | null
  >(null);
  const [diagnosticSelectedIndex, setDiagnosticSelectedIndex] = useState<
    number | null
  >(null);

  const hasBomPanel = Boolean(bom != null || zipUrl);
  const hasDiagnosticsPanel = diagnostics != null;
  const hasDrawingsPanel = Boolean(drawingsUrls?.length);

  useEffect(() => {
    setSelectedPartId(null);
    setJointFocusId(null);
    setHiddenParts({});
    setMetricsByPart(null);
    setViewerTab("scene");
    setDiagnosticHighlightIds(null);
    setDiagnosticSelectedIndex(null);
    setExplodeSlider(0);
  }, [url, blueprintJson]);

  const onKinematicReady = useCallback(
    (info: { pivots: number; warning: string | null }) => {
      setKinematicInfo(info);
    },
    [],
  );

  const onPartMetricsReady = useCallback((m: Map<string, PartMetricEntry>) => {
    setMetricsByPart(m);
  }, []);

  const onSelectPartFromCanvas = useCallback((id: string | null) => {
    setSelectedPartId(id);
    setJointFocusId(null);
    setDiagnosticHighlightIds(null);
    setDiagnosticSelectedIndex(null);
  }, []);

  const toggleHidden = useCallback((pid: string) => {
    setHiddenParts((h) => ({ ...h, [pid]: !h[pid] }));
  }, []);

  const parts = useMemo(
    () => parseBlueprintParts(blueprintJson),
    [blueprintJson],
  );
  const joints = useMemo(
    () => parseSimulationJoints(blueprintJson),
    [blueprintJson],
  );

  const showKinematic =
    !isStlUrl(url) && kinematicInfo.pivots > 0 && !kinematicInfo.warning;

  const { canExplode, info: explodeMateInfo } = useExplodedView(blueprintJson);
  const showExplode = !isStlUrl(url) && canExplode;

  const showInspector = !isStlUrl(url);

  useEffect(() => {
    if (hasBomPanel && isStlUrl(url)) {
      setViewerTab("bom");
    } else if (
      hasDrawingsPanel &&
      !hasBomPanel &&
      !hasDiagnosticsPanel &&
      isStlUrl(url)
    ) {
      setViewerTab("drawings");
    }
  }, [hasBomPanel, hasDrawingsPanel, hasDiagnosticsPanel, url]);

  const useTabs =
    (showInspector &&
      (hasBomPanel || hasDiagnosticsPanel || hasDrawingsPanel)) ||
    (!showInspector &&
      hasDrawingsPanel &&
      (hasBomPanel || hasDiagnosticsPanel));

  const showBottomPanel =
    showInspector ||
    hasBomPanel ||
    hasDiagnosticsPanel ||
    hasDrawingsPanel;

  const onDiagnosticSelectCheck = useCallback(
    (index: number | null, partIds: string[]) => {
      setDiagnosticSelectedIndex(index);
      setDiagnosticHighlightIds(partIds.length > 0 ? partIds : null);
    },
    [],
  );

  return (
    <div className="flex h-full min-h-[420px] w-full flex-col bg-neutral-950">
      <div className="relative min-h-0 flex-1">
        <Canvas
          className="h-full w-full"
          camera={{ position: [2, 2, 2], fov: 45 }}
          gl={{ preserveDrawingBuffer: true }}
        >
          <color attach="background" args={["#0a0a0a"]} />
          <ambientLight intensity={0.38} />
          <directionalLight position={[6, 14, 10]} intensity={1.15} />
          <directionalLight position={[-4, 6, -2]} intensity={0.35} />
          <Suspense fallback={<Loader />}>
            <Stage intensity={0.35} adjustCamera={1.1} environment="city">
              <SceneContent
                url={url}
                blueprintJson={blueprintJson}
                kinematicSlider={kinematicSlider}
                explodeSlider={explodeSlider}
                explodeMateInfo={explodeMateInfo}
                onKinematicReady={onKinematicReady}
                onLoaded={onLoaded}
                selectedPartId={selectedPartId}
                hiddenParts={hiddenParts}
                diagnosticPartIds={diagnosticHighlightIds}
                onPartMetricsReady={onPartMetricsReady}
                onSelectPartFromCanvas={onSelectPartFromCanvas}
              />
              {showInspector ? (
                <JointGizmos
                  blueprintJson={blueprintJson}
                  selectedPartId={selectedPartId}
                  jointFocusId={jointFocusId}
                />
              ) : null}
            </Stage>
          </Suspense>
          <OrbitControls makeDefault enableDamping />
        </Canvas>
      </div>
      {showBottomPanel ? (
        <div className="flex max-h-[280px] min-h-0 shrink-0 flex-col border-t border-neutral-800 bg-neutral-950/95">
          {useTabs ? (
            <div
              className="flex shrink-0 flex-wrap border-b border-neutral-800"
              role="tablist"
              aria-label="Панель просмотра"
            >
              {showInspector ? (
                <button
                  type="button"
                  role="tab"
                  aria-selected={viewerTab === "scene"}
                  onClick={() => {
                    setViewerTab("scene");
                    setDiagnosticHighlightIds(null);
                    setDiagnosticSelectedIndex(null);
                  }}
                  className={`px-3 py-2 text-[11px] font-medium transition-colors ${
                    viewerTab === "scene"
                      ? "border-b-2 border-neutral-200 text-neutral-100"
                      : "text-neutral-500 hover:text-neutral-300"
                  }`}
                >
                  Сцена
                </button>
              ) : null}
              {hasBomPanel ? (
                <button
                  type="button"
                  role="tab"
                  aria-selected={viewerTab === "bom"}
                  onClick={() => {
                    setViewerTab("bom");
                    setDiagnosticHighlightIds(null);
                    setDiagnosticSelectedIndex(null);
                  }}
                  className={`px-3 py-2 text-[11px] font-medium transition-colors ${
                    viewerTab === "bom"
                      ? "border-b-2 border-neutral-200 text-neutral-100"
                      : "text-neutral-500 hover:text-neutral-300"
                  }`}
                >
                  BOM &amp; Производство
                </button>
              ) : null}
              {hasDiagnosticsPanel ? (
                <button
                  type="button"
                  role="tab"
                  aria-selected={viewerTab === "diagnostics"}
                  onClick={() => setViewerTab("diagnostics")}
                  className={`px-3 py-2 text-[11px] font-medium transition-colors ${
                    viewerTab === "diagnostics"
                      ? "border-b-2 border-neutral-200 text-neutral-100"
                      : "text-neutral-500 hover:text-neutral-300"
                  }`}
                >
                  Диагностика
                </button>
              ) : null}
              {hasDrawingsPanel ? (
                <button
                  type="button"
                  role="tab"
                  aria-selected={viewerTab === "drawings"}
                  onClick={() => {
                    setViewerTab("drawings");
                    setDiagnosticHighlightIds(null);
                    setDiagnosticSelectedIndex(null);
                  }}
                  className={`px-3 py-2 text-[11px] font-medium transition-colors ${
                    viewerTab === "drawings"
                      ? "border-b-2 border-neutral-200 text-neutral-100"
                      : "text-neutral-500 hover:text-neutral-300"
                  }`}
                >
                  Чертежи (2D)
                </button>
              ) : null}
            </div>
          ) : null}
          <div className="min-h-0 flex-1 overflow-auto p-2">
            {showInspector && useTabs && viewerTab === "scene" ? (
              <div className="grid min-h-[160px] grid-cols-1 gap-2 md:grid-cols-2">
                <SceneTree
                  parts={parts}
                  joints={joints}
                  selectedPartId={selectedPartId}
                  jointFocusId={jointFocusId}
                  hiddenParts={hiddenParts}
                  onSelectPart={(id) => {
                    setSelectedPartId(id);
                    setJointFocusId(null);
                    setDiagnosticHighlightIds(null);
                    setDiagnosticSelectedIndex(null);
                  }}
                  onToggleHidden={toggleHidden}
                  onSelectJoint={setJointFocusId}
                />
                <PartInspector
                  blueprintJson={blueprintJson}
                  parts={parts}
                  selectedPartId={selectedPartId}
                  metricsByPart={metricsByPart}
                />
              </div>
            ) : null}
            {showInspector && !useTabs ? (
              <div className="grid min-h-[160px] grid-cols-1 gap-2 md:grid-cols-2">
                <SceneTree
                  parts={parts}
                  joints={joints}
                  selectedPartId={selectedPartId}
                  jointFocusId={jointFocusId}
                  hiddenParts={hiddenParts}
                  onSelectPart={(id) => {
                    setSelectedPartId(id);
                    setJointFocusId(null);
                  }}
                  onToggleHidden={toggleHidden}
                  onSelectJoint={setJointFocusId}
                />
                <PartInspector
                  blueprintJson={blueprintJson}
                  parts={parts}
                  selectedPartId={selectedPartId}
                  metricsByPart={metricsByPart}
                />
              </div>
            ) : null}
            {useTabs && hasBomPanel && viewerTab === "bom" ? (
              <BomTable bom={bom ?? null} zipUrl={zipUrl ?? null} />
            ) : null}
            {useTabs && hasDiagnosticsPanel && viewerTab === "diagnostics" ? (
              <DiagnosticsPanel
                diagnostics={diagnostics ?? null}
                selectedIndex={diagnosticSelectedIndex}
                onSelectCheck={onDiagnosticSelectCheck}
              />
            ) : null}
            {useTabs && hasDrawingsPanel && viewerTab === "drawings" ? (
              <DrawingsViewer
                urls={drawingsUrls ?? []}
                zipUrl={zipUrl ?? null}
              />
            ) : null}
            {!useTabs && !showInspector && hasBomPanel ? (
              <BomTable bom={bom ?? null} zipUrl={zipUrl ?? null} />
            ) : null}
            {!useTabs && !showInspector && hasDiagnosticsPanel ? (
              <DiagnosticsPanel
                diagnostics={diagnostics ?? null}
                selectedIndex={diagnosticSelectedIndex}
                onSelectCheck={onDiagnosticSelectCheck}
              />
            ) : null}
            {!useTabs && !showInspector && hasDrawingsPanel ? (
              <DrawingsViewer
                urls={drawingsUrls ?? []}
                zipUrl={zipUrl ?? null}
              />
            ) : null}
          </div>
        </div>
      ) : null}
      {!isStlUrl(url) && kinematicInfo.warning ? (
        <div
          className="border-t border-amber-800/80 bg-amber-950/50 px-3 py-2 text-[11px] text-amber-100/95"
          role="status"
        >
          Кинематика: {kinematicInfo.warning}
        </div>
      ) : null}
      {showKinematic ? (
        <div className="border-t border-neutral-800 bg-neutral-900/90 px-3 py-2">
          <label className="flex flex-col gap-1 text-[11px] text-neutral-400">
            Тест шарниров (FK)
            <input
              type="range"
              min={0}
              max={100}
              value={kinematicSlider}
              onChange={(e) =>
                setKinematicSlider(Number.parseInt(e.target.value, 10))
              }
              className="w-full accent-neutral-300"
            />
          </label>
        </div>
      ) : null}
      {showExplode ? (
        <div className="border-t border-neutral-800 bg-neutral-900/90 px-3 py-2">
          <label className="flex flex-col gap-1 text-[11px] text-neutral-400">
            Разнесённый вид (Explode, v3.1) — {explodeSlider}%
            <input
              type="range"
              min={0}
              max={100}
              value={explodeSlider}
              onChange={(e) =>
                setExplodeSlider(Number.parseInt(e.target.value, 10))
              }
              className="w-full accent-sky-500/90"
            />
          </label>
        </div>
      ) : null}
    </div>
  );
}
