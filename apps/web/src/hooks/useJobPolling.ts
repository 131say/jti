"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type {
  JobArtifacts,
  JobBom,
  JobDiagnostics,
  JobPromptBody,
} from "@/lib/api";
import { getJob, postJob } from "@/lib/api";

export type JobPhase =
  | "idle"
  | "submitting"
  | "polling"
  | "loading_asset"
  | "success"
  | "error";

export type JobFinishedInfo = {
  ok: boolean;
  warnings?: string[] | null;
  error?: string | null;
};

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

export interface UseJobPollingOptions {
  pollMs?: number;
  timeoutMs?: number;
  /** Вызывается один раз при успешном завершении, если API вернул blueprint. */
  onBlueprintReady?: (blueprint: object) => void;
  /**
   * Вызывается при завершении задачи (успех или ошибка), если runForge передан logToChat: true.
   * Для Copilot: честные статусы без выдуманного текста от фронта кроме фиксированных строк.
   */
  onJobFinishedForChat?: (info: JobFinishedInfo) => void;
}

export type RunForgeOptions = {
  /** Логировать результат в чат Copilot (один колбэк на задачу). */
  logToChat?: boolean;
};

export function useJobPolling(options?: UseJobPollingOptions) {
  const pollMs = options?.pollMs ?? 2000;
  const timeoutMs = options?.timeoutMs ?? 60_000;
  const onBlueprintReadyRef = useRef(options?.onBlueprintReady);
  const onJobFinishedForChatRef = useRef(options?.onJobFinishedForChat);
  useEffect(() => {
    onBlueprintReadyRef.current = options?.onBlueprintReady;
  }, [options?.onBlueprintReady]);
  useEffect(() => {
    onJobFinishedForChatRef.current = options?.onJobFinishedForChat;
  }, [options?.onJobFinishedForChat]);

  const [phase, setPhase] = useState<JobPhase>("idle");
  const [jobId, setJobId] = useState<string | null>(null);
  const [artifacts, setArtifacts] = useState<JobArtifacts | null>(null);
  const [bom, setBom] = useState<JobBom | null>(null);
  const [diagnostics, setDiagnostics] = useState<JobDiagnostics | null>(null);
  const [warnings, setWarnings] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [apiStatus, setApiStatus] = useState<string | null>(null);

  const cancelledRef = useRef(false);
  const logToChatRef = useRef(false);

  const reset = useCallback(() => {
    cancelledRef.current = true;
    setPhase("idle");
    setJobId(null);
    setArtifacts(null);
    setBom(null);
    setDiagnostics(null);
    setWarnings(null);
    setError(null);
    setApiStatus(null);
  }, []);

  const runForge = useCallback(
    async (
      blueprint: object | JobPromptBody,
      opts?: RunForgeOptions,
    ) => {
      cancelledRef.current = false;
      logToChatRef.current = opts?.logToChat ?? false;
      setArtifacts(null);
      setBom(null);
      setDiagnostics(null);
      setWarnings(null);
      setError(null);
      setApiStatus(null);
      setPhase("submitting");

      const notifyChat = (info: JobFinishedInfo) => {
        if (logToChatRef.current) {
          onJobFinishedForChatRef.current?.(info);
        }
      };

      try {
        const created = await postJob(blueprint);
        if (cancelledRef.current) return;

        setJobId(created.job_id);
        setPhase("polling");
        setApiStatus("queued");

        const start = Date.now();

        while (Date.now() - start < timeoutMs) {
          if (cancelledRef.current) return;

          await sleep(pollMs);
          if (cancelledRef.current) return;

          const j = await getJob(created.job_id);
          setApiStatus(j.status);

          if (j.status === "failed") {
            const errText = j.error ?? "Задача завершилась с ошибкой";
            setPhase("error");
            setError(errText);
            notifyChat({ ok: false, error: errText });
            return;
          }

          if (j.status === "completed" && j.artifacts?.glb_url) {
            setArtifacts(j.artifacts);
            setBom(j.bom ?? null);
            setDiagnostics(j.diagnostics ?? null);
            const w = j.warnings?.length ? j.warnings : null;
            setWarnings(w);
            if (j.blueprint && typeof j.blueprint === "object") {
              onBlueprintReadyRef.current?.(j.blueprint as object);
            }
            notifyChat({
              ok: true,
              warnings: w,
            });
            setPhase("loading_asset");
            return;
          }
        }

        const timeoutMsg = "Превышен таймаут ожидания (60 с)";
        setPhase("error");
        setError(timeoutMsg);
        notifyChat({ ok: false, error: timeoutMsg });
      } catch (e) {
        if (cancelledRef.current) return;
        const msg = e instanceof Error ? e.message : String(e);
        setPhase("error");
        setError(msg);
        notifyChat({ ok: false, error: msg });
      }
    },
    [pollMs, timeoutMs],
  );

  const markAssetLoaded = useCallback(() => {
    setPhase("success");
  }, []);

  return {
    phase,
    jobId,
    artifacts,
    bom,
    diagnostics,
    warnings,
    error,
    apiStatus,
    runForge,
    reset,
    markAssetLoaded,
  };
}
