"use client";

import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "ai_forge_demo_tour_dismissed_v1";

type DemoOnboardingOverlayProps = {
  /** Показывать только когда демо загружено и готово к просмотру */
  visible: boolean;
};

/**
 * Одноразовый тур (на сессию) для live demo: подсказки Exploded / BOM / PDF.
 */
export function DemoOnboardingOverlay({ visible }: DemoOnboardingOverlayProps) {
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (!visible || typeof window === "undefined") return;
    try {
      if (sessionStorage.getItem(STORAGE_KEY) === "1") return;
    } catch {
      /* ignore */
    }
    setShow(true);
  }, [visible]);

  const dismiss = useCallback(() => {
    setShow(false);
    try {
      sessionStorage.setItem(STORAGE_KEY, "1");
    } catch {
      /* ignore */
    }
  }, []);

  if (!show) return null;

  return (
    <div
      className="pointer-events-none fixed inset-0 z-[100] flex items-end justify-center p-4 md:items-center md:justify-end md:p-8"
      role="dialog"
      aria-labelledby="demo-tour-title"
      aria-modal="true"
    >
      <div className="pointer-events-auto max-w-md rounded-xl border border-sky-500/40 bg-neutral-950/95 p-4 shadow-2xl shadow-black/50 backdrop-blur-md md:max-w-lg">
        <p
          id="demo-tour-title"
          className="text-sm font-semibold text-sky-100"
        >
          👋 Это демо AI-Forge
        </p>
        <p className="mt-2 text-xs leading-relaxed text-neutral-300">
          Попробуй:
        </p>
        <ol className="mt-2 list-decimal space-y-2 pl-4 text-xs leading-relaxed text-neutral-200">
          <li>
            Включить <strong className="text-neutral-100">Exploded View</strong>{" "}
            (ползунок под 3D).
          </li>
          <li>
            Открыть вкладку{" "}
            <strong className="text-neutral-100">BOM &amp; Производство</strong>.
          </li>
          <li>
            После сборки модели — вкладку{" "}
            <strong className="text-neutral-100">Инструкции</strong> и скачать
            PDF (если воркер уже отдал артефакты).
          </li>
        </ol>
        <p className="mt-3 text-[11px] text-neutral-500">
          Сценарий: плита, вал, подшипник, шкив, болты — координаты через{" "}
          <code className="text-neutral-400">assembly_mates</code>.
        </p>
        <button
          type="button"
          onClick={dismiss}
          className="mt-4 w-full rounded-lg bg-sky-600 py-2.5 text-sm font-medium text-white hover:bg-sky-500"
        >
          Понятно, вперёд
        </button>
      </div>
    </div>
  );
}
