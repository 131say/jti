"use client";

import { Code2, Loader2, Redo2, Undo2 } from "lucide-react";
import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { type ChatMessage, CopilotSidebar } from "@/components/CopilotSidebar";
import { CodeViewerModal } from "@/components/CodeViewerModal";
import { LoginModal } from "@/components/LoginModal";
import { ParametricPanel } from "@/components/ParametricPanel";
import { ProjectTopBar } from "@/components/ProjectTopBar";
import { useAuth } from "@/context/AuthContext";
import { ModelViewer } from "@/components/viewer/ModelViewer";
import { useBlueprintHistory } from "@/hooks/useBlueprintHistory";
import {
  type JobFinishedInfo,
  useJobPolling,
} from "@/hooks/useJobPolling";
import type { JobArtifacts, JobBom, ProjectLastArtifacts } from "@/lib/api";
import {
  forkProject,
  getProject,
  postProject,
  putProject,
  type ProjectRecord,
} from "@/lib/api";

/** Минимальная проверка «похоже на Blueprint v1» для прикрепления к промпту. */
function tryParseBlueprintJson(text: string): object | null {
  try {
    const o = JSON.parse(text) as unknown;
    if (!o || typeof o !== "object" || Array.isArray(o)) return null;
    const r = o as Record<string, unknown>;
    if (
      "metadata" in r &&
      "geometry" in r &&
      "simulation" in r &&
      "global_settings" in r
    ) {
      return o as object;
    }
  } catch {
    /* ignore */
  }
  return null;
}

function cloudArtifactsFromLast(
  la: ProjectLastArtifacts | null | undefined,
): JobArtifacts | null {
  if (!la?.glb_url) return null;
  return {
    glb_url: la.glb_url,
    step_url: la.step_url ?? "",
    mjcf_url: la.mjcf_url,
    zip_url: la.zip_url,
    video_url: la.video_url,
    script_url: la.script_url,
    drawings_urls: la.drawings_urls ?? undefined,
    pdf_url: la.pdf_url ?? undefined,
  };
}

const phaseLabels: Record<string, string> = {
  idle: "Ожидание",
  submitting: "Отправка Blueprint на API…",
  polling: "Ожидание воркера (поллинг GET /jobs)…",
  loading_asset: "Загрузка GLB в браузер (Three.js)…",
  success: "Модель отображена",
  error: "Ошибка",
};

function HomePageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectIdParam = searchParams.get("project");

  const [aiMode, setAiMode] = useState(true);
  const [diffMode, setDiffMode] = useState(false);
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const [codeModalOpen, setCodeModalOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);

  const [projectName, setProjectName] = useState("Untitled Project");
  const [projectLoadStatus, setProjectLoadStatus] = useState<
    "idle" | "loading" | "error" | "ready"
  >("idle");
  const [projectLoadError, setProjectLoadError] = useState<string | null>(
    null,
  );
  const [cloudArtifacts, setCloudArtifacts] = useState<JobArtifacts | null>(
    null,
  );
  const [cloudBom, setCloudBom] = useState<JobBom | null>(null);
  const [savingProject, setSavingProject] = useState(false);
  const [loginOpen, setLoginOpen] = useState(false);
  const [remoteProject, setRemoteProject] = useState<ProjectRecord | null>(
    null,
  );
  const [publicBusy, setPublicBusy] = useState(false);
  const [forkBusy, setForkBusy] = useState(false);

  const { user, logout } = useAuth();

  const workspaceReadOnly = useMemo(() => {
    if (!remoteProject) return false;
    if (!user) return true;
    if (!remoteProject.owner_id) return false;
    return remoteProject.owner_id !== user.id;
  }, [remoteProject, user]);

  const isProjectOwner = useMemo(() => {
    if (!remoteProject || !user) return false;
    if (!remoteProject.owner_id) return true;
    return remoteProject.owner_id === user.id;
  }, [remoteProject, user]);

  const loadedIdRef = useRef<string | null>(null);
  const demoLoadedRef = useRef(false);

  const {
    present,
    setPresent,
    commit,
    undo,
    redo,
    reset,
    canUndo,
    canRedo,
    previousCommitted,
  } = useBlueprintHistory("");

  const onBlueprintReady = useCallback(
    (bp: object) => {
      commit(JSON.stringify(bp, null, 2));
    },
    [commit],
  );

  const onJobFinishedForChat = useCallback((info: JobFinishedInfo) => {
    setChatMessages((prev) => {
      if (info.ok) {
        if (info.warnings?.length) {
          return [
            ...prev,
            {
              role: "assistant" as const,
              content:
                "⚠️ Модель обновлена с предупреждениями (телеметрия геометрии).",
              warnings: [...info.warnings],
            },
          ];
        }
        return [
          ...prev,
          { role: "assistant" as const, content: "✅ Модель обновлена" },
        ];
      }
      return [
        ...prev,
        {
          role: "assistant" as const,
          content: `❌ Ошибка применения изменений: ${info.error ?? "неизвестно"}`,
        },
      ];
    });
  }, []);

  const {
    phase,
    jobId,
    error,
    apiStatus,
    artifacts,
    bom,
    diagnostics,
    warnings,
    runForge,
    markAssetLoaded,
  } = useJobPolling({
    pollMs: 2000,
    timeoutMs: 60_000,
    onBlueprintReady,
    onJobFinishedForChat,
  });

  const handleUndo = useCallback(() => {
    undo();
    setChatMessages((prev) => [
      ...prev,
      { role: "system", content: "↩️ Откат к предыдущей версии модели" },
    ]);
  }, [undo]);

  const handleRedo = useCallback(() => {
    redo();
    setChatMessages((prev) => [
      ...prev,
      { role: "system", content: "↪️ Возврат к следующей версии модели" },
    ]);
  }, [redo]);

  const handleCopilotSend = useCallback(
    (text: string) => {
      setChatMessages((prev) => [...prev, { role: "user", content: text }]);
      const ctx = tryParseBlueprintJson(present);
      if (ctx) {
        void runForge(
          {
            prompt: text,
            current_blueprint: ctx,
            ...(diagnostics ? { diagnostics_context: diagnostics } : {}),
          },
          { logToChat: true },
        );
      } else {
        void runForge({ prompt: text }, { logToChat: true });
      }
    },
    [present, runForge, diagnostics],
  );

  const loadDemoPiston = useCallback(() => {
    fetch("/piston-assembly.blueprint.json")
      .then((r) => r.text())
      .then((t) => reset(t))
      .catch(() => reset("{}"));
  }, [reset]);

  const loadDemoMaterials = useCallback(() => {
    fetch("/demo-fillets-materials.json")
      .then((r) => r.text())
      .then((t) => reset(t))
      .catch(() => reset("{}"));
  }, [reset]);

  const loadDemoParametric = useCallback(() => {
    fetch("/demo-parametric-box.json")
      .then((r) => r.text())
      .then((t) => reset(t))
      .catch(() => reset("{}"));
  }, [reset]);

  useEffect(() => {
    if (projectIdParam) return;
    if (demoLoadedRef.current) return;
    demoLoadedRef.current = true;
    loadDemoPiston();
  }, [loadDemoPiston, projectIdParam]);

  useEffect(() => {
    if (!projectIdParam) {
      loadedIdRef.current = null;
      setRemoteProject(null);
      setCloudArtifacts(null);
      setCloudBom(null);
      setProjectLoadStatus("idle");
      setProjectLoadError(null);
      setProjectName("Untitled Project");
      return;
    }

    let cancelled = false;
    setProjectLoadStatus("loading");
    setProjectLoadError(null);

    void (async () => {
      try {
        const rec = await getProject(projectIdParam);
        if (cancelled) return;
        setRemoteProject(rec);
        setProjectName(rec.name);
        reset(JSON.stringify(rec.blueprint, null, 2));
        setChatMessages([]);
        const ca = cloudArtifactsFromLast(rec.last_artifacts);
        setCloudArtifacts(ca);
        setCloudBom(rec.last_artifacts?.bom ?? null);
        loadedIdRef.current = projectIdParam;
        setProjectLoadStatus("ready");
      } catch (e) {
        if (cancelled) return;
        setProjectLoadStatus("error");
        setProjectLoadError(
          e instanceof Error ? e.message : String(e),
        );
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [projectIdParam, reset, user?.id]);

  useEffect(() => {
    if (phase !== "error" || !error) return;
    const friendly =
      /422|502|503|Gemini|validation|валидац/i.test(error) || error.length > 200
        ? "AI не смог применить изменения. Попробуйте переформулировать запрос. Детали в панели статуса."
        : error;
    setToastMsg(friendly);
    const t = setTimeout(() => setToastMsg(null), 8000);
    return () => clearTimeout(t);
  }, [phase, error]);

  const busy = phase === "submitting" || phase === "polling";
  const copilotPending = busy;
  const projectBusy = projectLoadStatus === "loading";

  const jobRunning = phase === "submitting" || phase === "polling";
  const jobDisplay =
    !jobRunning &&
    Boolean(artifacts?.glb_url) &&
    (phase === "loading_asset" || phase === "success");

  const displayArtifacts: JobArtifacts | null = jobDisplay
    ? artifacts
    : cloudArtifacts;
  const displayBom: JobBom | null = jobDisplay ? bom : cloudBom;

  const buildLastArtifactsPayload = useCallback((): ProjectLastArtifacts | null => {
    const a = jobDisplay ? artifacts : cloudArtifacts;
    const b = jobDisplay ? bom : cloudBom;
    if (!a?.glb_url) return null;
    return {
      glb_url: a.glb_url,
      step_url: a.step_url,
      mjcf_url: a.mjcf_url ?? undefined,
      zip_url: a.zip_url ?? undefined,
      video_url: a.video_url ?? undefined,
      script_url: a.script_url ?? undefined,
      drawings_urls: a.drawings_urls ?? undefined,
      pdf_url: a.pdf_url ?? undefined,
      bom: b ?? undefined,
    };
  }, [jobDisplay, artifacts, cloudArtifacts, bom, cloudBom]);

  const handlePublicToggle = useCallback(
    async (v: boolean) => {
      if (!projectIdParam || !user || !isProjectOwner) return;
      setPublicBusy(true);
      try {
        const rec = await putProject(projectIdParam, { is_public: v });
        setRemoteProject(rec);
      } catch (e) {
        setToastMsg(e instanceof Error ? e.message : String(e));
      } finally {
        setPublicBusy(false);
      }
    },
    [projectIdParam, user, isProjectOwner],
  );

  const handleFork = useCallback(async () => {
    if (!projectIdParam || !user) {
      setLoginOpen(true);
      return;
    }
    setForkBusy(true);
    try {
      const r = await forkProject(projectIdParam);
      loadedIdRef.current = null;
      router.replace(`/?project=${encodeURIComponent(r.project_id)}`, {
        scroll: false,
      });
      setToastMsg("Копия проекта создана в вашем workspace");
    } catch (e) {
      setToastMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setForkBusy(false);
    }
  }, [projectIdParam, user, router]);

  const handleSaveProject = useCallback(async () => {
    if (!user) {
      setLoginOpen(true);
      setToastMsg("Войдите, чтобы сохранить проект в облаке");
      return;
    }
    if (workspaceReadOnly) {
      setToastMsg("Нет прав на изменение этого проекта.");
      return;
    }
    let bp: object;
    try {
      bp = JSON.parse(present) as object;
    } catch {
      setToastMsg("Некорректный JSON: исправьте Blueprint перед сохранением.");
      return;
    }
    const la = buildLastArtifactsPayload();
    setSavingProject(true);
    try {
      if (projectIdParam) {
        const updated = await putProject(projectIdParam, {
          name: projectName,
          blueprint: bp,
          ...(la !== null ? { last_artifacts: la } : {}),
        });
        setRemoteProject(updated);
        loadedIdRef.current = projectIdParam;
        setToastMsg("Проект сохранён");
      } else {
        const r = await postProject({
          name: projectName,
          blueprint: bp,
          ...(la !== null ? { last_artifacts: la } : {}),
        });
        loadedIdRef.current = r.project_id;
        router.replace(`/?project=${encodeURIComponent(r.project_id)}`, {
          scroll: false,
        });
        setToastMsg("Проект создан и сохранён");
      }
    } catch (e) {
      setToastMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setSavingProject(false);
    }
  }, [
    present,
    projectName,
    projectIdParam,
    router,
    buildLastArtifactsPayload,
    user,
    workspaceReadOnly,
  ]);

  const handleShareProject = useCallback(() => {
    if (!projectIdParam) return;
    const url = `${window.location.origin}${window.location.pathname}?project=${encodeURIComponent(projectIdParam)}`;
    void navigator.clipboard.writeText(url);
    setToastMsg("Ссылка скопирована");
  }, [projectIdParam]);

  const statusLine = useMemo(() => {
    const parts = [phaseLabels[phase] ?? phase];
    if (apiStatus) parts.push(`API: ${apiStatus}`);
    if (jobId) parts.push(`job_id: ${jobId}`);
    return parts.join(" · ");
  }, [phase, apiStatus, jobId]);

  const hasBlueprintContext = useMemo(
    () => tryParseBlueprintJson(present) !== null,
    [present],
  );

  const onRunCode = () => {
    if (workspaceReadOnly) {
      setToastMsg("Режим только просмотра: Fork или откройте свой проект.");
      return;
    }
    try {
      const bp = JSON.parse(present) as object;
      void runForge(bp);
    } catch (e) {
      alert(
        `Некорректный JSON: ${e instanceof Error ? e.message : String(e)}`,
      );
    }
  };

  const glbUrl = jobRunning
    ? null
    : (displayArtifacts?.glb_url ?? null);

  const videoUrl = jobRunning
    ? null
    : (displayArtifacts?.video_url ?? null);

  const zipUrlForViewer =
    displayArtifacts?.zip_url &&
    (phase === "loading_asset" || phase === "success" || !jobDisplay)
      ? displayArtifacts.zip_url
      : null;

  const pretty = (s: string) => {
    try {
      return JSON.stringify(JSON.parse(s), null, 2);
    } catch {
      return s;
    }
  };

  const showArtifactSidebar =
    Boolean(displayArtifacts?.zip_url) &&
    !jobRunning &&
    projectLoadStatus !== "loading";

  return (
    <div className="flex min-h-screen flex-col">
      <LoginModal
        open={loginOpen}
        onClose={() => setLoginOpen(false)}
        onLoggedIn={() => setLoginOpen(false)}
      />
      <ProjectTopBar
        projectName={projectName}
        onProjectNameChange={setProjectName}
        onSave={handleSaveProject}
        onShare={handleShareProject}
        saving={savingProject}
        disabled={projectBusy || projectLoadStatus === "error"}
        hasProjectId={Boolean(projectIdParam)}
        user={user}
        onLoginClick={() => setLoginOpen(true)}
        onLogout={logout}
        workspaceReadOnly={workspaceReadOnly}
        isProjectOwner={isProjectOwner}
        isPublic={Boolean(remoteProject?.is_public)}
        onIsPublicChange={handlePublicToggle}
        publicBusy={publicBusy}
        onFork={handleFork}
        forkBusy={forkBusy}
        onLoginForFork={() => setLoginOpen(true)}
      />
      <CodeViewerModal
        open={codeModalOpen}
        onClose={() => setCodeModalOpen(false)}
        url={displayArtifacts?.script_url ?? null}
      />
      {toastMsg ? (
        <div
          className="fixed bottom-4 left-1/2 z-50 max-w-md -translate-x-1/2 rounded border border-amber-800 bg-amber-950 px-4 py-2 text-center text-xs text-amber-100 shadow-lg md:left-auto md:right-4 md:translate-x-0"
          role="alert"
        >
          {toastMsg}
        </div>
      ) : null}

      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        <aside className="flex w-full flex-col gap-3 border-b border-neutral-800 p-4 md:h-[calc(100vh-49px)] md:w-[400px] md:min-w-[320px] md:border-b-0 md:border-r">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">
              AI-Forge Workspace
            </h1>
            <p className="mt-1 text-sm text-neutral-500">
              Blueprint JSON, параметры и статус. Диалог с AI — панель справа.
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => loadDemoPiston()}
                className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-[11px] text-neutral-200 hover:bg-neutral-800"
              >
                Загрузить демо (Поршень)
              </button>
              <button
                type="button"
                onClick={() => loadDemoMaterials()}
                className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-[11px] text-neutral-200 hover:bg-neutral-800"
              >
                Загрузить демо (Материалы)
              </button>
              <button
                type="button"
                onClick={() => loadDemoParametric()}
                className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-[11px] text-neutral-200 hover:bg-neutral-800"
              >
                Загрузить демо (Параметрика)
              </button>
            </div>
          </div>

          <div className="flex items-center gap-2 text-xs text-neutral-400">
            <span className="font-medium uppercase tracking-wide">Режим</span>
            <button
              type="button"
              onClick={() => setAiMode(true)}
              className={`rounded px-2 py-1 ${aiMode ? "bg-neutral-100 text-neutral-900" : "bg-neutral-800 text-neutral-300"}`}
            >
              AI
            </button>
            <button
              type="button"
              onClick={() => setAiMode(false)}
              className={`rounded px-2 py-1 ${!aiMode ? "bg-neutral-100 text-neutral-900" : "bg-neutral-800 text-neutral-300"}`}
            >
              Код
            </button>
          </div>

          {aiMode ? (
            <p className="text-[11px] leading-snug text-neutral-500">
              {hasBlueprintContext
                ? "Запросы к модели — в чате справа; к промпту прикладывается JSON из редактора."
                : "Нет валидного Blueprint в редакторе — чат отправит только текст запроса."}
            </p>
          ) : (
            <p className="text-[11px] leading-snug text-neutral-500">
              Прямая отправка JSON на воркер без Gemini (кнопка ниже).
            </p>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <label className="text-xs font-medium uppercase text-neutral-500">
              Blueprint JSON
            </label>
            <div className="ml-auto flex items-center gap-1">
              <button
                type="button"
                title="Отменить"
                disabled={!canUndo}
                onClick={handleUndo}
                className="rounded border border-neutral-700 p-1.5 text-neutral-300 hover:bg-neutral-800 disabled:opacity-30"
              >
                <Undo2 className="h-4 w-4" aria-hidden />
              </button>
              <button
                type="button"
                title="Повторить"
                disabled={!canRedo}
                onClick={handleRedo}
                className="rounded border border-neutral-700 p-1.5 text-neutral-300 hover:bg-neutral-800 disabled:opacity-30"
              >
                <Redo2 className="h-4 w-4" aria-hidden />
              </button>
              <label className="ml-1 flex cursor-pointer items-center gap-1 text-[11px] text-neutral-500">
                <input
                  type="checkbox"
                  checked={diffMode}
                  onChange={(e) => setDiffMode(e.target.checked)}
                />
                Diff
              </label>
            </div>
          </div>

          {diffMode && previousCommitted ? (
            <div className="grid min-h-[200px] flex-1 grid-cols-1 gap-2 font-mono text-[10px] md:grid-cols-2">
              <div className="flex flex-col gap-1">
                <span className="text-neutral-500">Предыдущая версия</span>
                <textarea
                  readOnly
                  className="min-h-[200px] flex-1 rounded border border-neutral-800 bg-neutral-900/50 p-2 text-neutral-400"
                  value={pretty(previousCommitted)}
                />
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-neutral-500">Текущая (present)</span>
                <textarea
                  readOnly
                  className="min-h-[200px] flex-1 rounded border border-neutral-800 bg-neutral-950 p-2 text-neutral-200"
                  value={pretty(present)}
                />
              </div>
            </div>
          ) : (
            <textarea
              className="min-h-[220px] flex-1 rounded border border-neutral-800 bg-neutral-950 p-3 font-mono text-xs text-neutral-100 disabled:opacity-60"
              spellCheck={false}
              value={present}
              onChange={(e) => setPresent(e.target.value)}
              disabled={workspaceReadOnly || projectBusy}
            />
          )}

          {!aiMode ? (
            <button
              type="button"
              onClick={onRunCode}
              disabled={busy || projectBusy || workspaceReadOnly}
              className="rounded bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-900 disabled:opacity-50"
            >
              {busy ? "Выполняется…" : "Run Forge (JSON)"}
            </button>
          ) : (
            <p className="text-[11px] text-neutral-600">
              В режиме AI используйте чат справа — поле ввода там блокируется на время
              генерации.
            </p>
          )}

          <div className="rounded border border-neutral-800 bg-neutral-950 p-3 text-xs text-neutral-300">
            <div className="font-medium text-neutral-100">Статус</div>
            <div className="mt-1">{statusLine}</div>
            {error ? (
              <div className="mt-2 text-red-400">{error}</div>
            ) : null}
          </div>

          {showArtifactSidebar ? (
            <div className="rounded border border-neutral-800 bg-neutral-950 p-3 text-xs">
              <div className="font-medium text-neutral-100">Артефакты</div>
              <div className="mt-2 flex flex-col gap-2">
                {displayArtifacts?.script_url ? (
                  <button
                    type="button"
                    onClick={() => setCodeModalOpen(true)}
                    className="inline-flex w-full items-center justify-center gap-2 rounded border border-neutral-600 bg-neutral-900 px-3 py-2 text-sm font-medium text-neutral-100 hover:bg-neutral-800"
                  >
                    <Code2 className="h-4 w-4 shrink-0" aria-hidden />
                    Eject to Python / View Code
                  </button>
                ) : null}
                <a
                  href="https://mujoco.org/play"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-center text-neutral-400 underline decoration-neutral-600 underline-offset-2 hover:text-neutral-200"
                >
                  Открыть MuJoCo Play (перетащите simulation/simulation.xml из ZIP)
                </a>
              </div>
            </div>
          ) : null}
        </aside>

        <div className="flex min-h-0 min-w-0 flex-1 flex-col md:flex-row">
          <main className="relative flex min-h-[50vh] min-w-0 flex-1 flex-col md:min-h-[calc(100vh-49px)]">
            {projectLoadStatus === "loading" ? (
              <div
                className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-3 bg-neutral-950/90"
                role="status"
                aria-live="polite"
              >
                <Loader2
                  className="h-10 w-10 animate-spin text-neutral-400"
                  aria-hidden
                />
                <p className="text-sm text-neutral-300">Загружаем проект…</p>
              </div>
            ) : null}
            {projectLoadStatus === "error" && projectLoadError ? (
              <div
                className="border-b border-red-900/60 bg-red-950/50 px-4 py-3 text-xs text-red-100"
                role="alert"
              >
                Не удалось загрузить проект: {projectLoadError}
              </div>
            ) : null}
            <div className="relative min-h-[420px] flex-1">
              {glbUrl ? (
                <ModelViewer
                  url={glbUrl}
                  blueprintJson={present}
                  bom={displayBom}
                  zipUrl={zipUrlForViewer}
                  drawingsUrls={displayArtifacts?.drawings_urls ?? null}
                  pdfUrl={displayArtifacts?.pdf_url ?? null}
                  diagnostics={
                    jobDisplay ? diagnostics : null
                  }
                  onLoaded={
                    phase === "loading_asset" ? markAssetLoaded : undefined
                  }
                />
              ) : (
                <div className="flex h-full min-h-[420px] items-center justify-center bg-neutral-950 text-sm text-neutral-500">
                  {jobRunning
                    ? "Генерация модели…"
                    : "Здесь появится 3D после успешной генерации или при открытии сохранённого проекта"}
                </div>
              )}
            </div>
            {videoUrl ? (
              <div className="border-b border-neutral-800 bg-neutral-950 px-4 py-3">
                <div className="mb-2 text-xs font-medium text-neutral-400">
                  Physics preview (MuJoCo)
                </div>
                <video
                  src={videoUrl}
                  autoPlay
                  loop
                  muted
                  playsInline
                  className="max-h-[320px] w-full max-w-3xl rounded border border-neutral-800 bg-black object-contain"
                />
              </div>
            ) : null}
            {warnings && warnings.length > 0 && jobDisplay ? (
              <div
                className="border-b border-amber-800/80 bg-amber-950/40 px-4 py-3 text-xs text-amber-100"
                role="status"
              >
                <div className="mb-1 font-semibold text-amber-200">
                  Предупреждения геометрии (ядро скорректировало запрос)
                </div>
                <ul className="list-inside list-disc space-y-1 text-amber-100/90">
                  {warnings.map((w, i) => (
                    <li key={`${i}-${w.slice(0, 48)}`}>{w}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            <ParametricPanel
              jsonText={present}
              baselineJson={previousCommitted}
              disabled={busy || projectBusy || workspaceReadOnly}
              onApply={(obj) => {
                commit(JSON.stringify(obj, null, 2));
                void runForge(obj);
              }}
            />
          </main>

          <CopilotSidebar
            messages={chatMessages}
            aiMode={aiMode}
            pending={copilotPending}
            hasBlueprintContext={hasBlueprintContext}
            onSend={handleCopilotSend}
            readOnly={workspaceReadOnly}
          />
        </div>
      </div>
    </div>
  );
}

export default function HomePage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-neutral-950 text-neutral-400">
          <Loader2 className="h-10 w-10 animate-spin" aria-hidden />
          <p className="text-sm">Загрузка приложения…</p>
        </div>
      }
    >
      <HomePageInner />
    </Suspense>
  );
}
