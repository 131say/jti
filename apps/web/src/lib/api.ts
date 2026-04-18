const baseUrl = () =>
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8899";

export type JobStatus = "queued" | "in_progress" | "completed" | "failed";

export interface JobArtifacts {
  glb_url: string;
  step_url: string;
  mjcf_url?: string | null;
  zip_url?: string | null;
  video_url?: string | null;
  /** Presigned URL для build_model.py (CadQuery eject). */
  script_url?: string | null;
}

export interface JobBomPart {
  part_id: string;
  material?: string | null;
  mass_g: number;
  volume_cm3: number;
  cost_usd: number;
}

/** BOM с воркера (без парсинга CSV на клиенте). */
export interface JobBom {
  parts: JobBomPart[];
  total_mass_g: number;
  total_cost_usd: number;
}

export interface JobCreateResponse {
  job_id: string;
  status: "queued";
}

/** Тело POST /jobs при вызове только из текста (опционально с контекстом редактирования). */
export type JobPromptBody = {
  prompt: string;
  current_blueprint?: object;
  /** Контекст для Copilot: последняя диагностика с воркера. */
  diagnostics_context?: JobDiagnostics | null;
};

/** Одна проверка DFM (воркер). */
export interface JobDiagnosticCheck {
  type: string;
  severity: "pass" | "warning" | "fail";
  message: string;
  part_ids: string[];
  /** Количественные метрики (объём пересечения, min толщина, …). */
  metrics?: Record<string, unknown> | null;
}

export interface JobDiagnostics {
  status: "pass" | "warning" | "fail";
  checks: JobDiagnosticCheck[];
}

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  artifacts: JobArtifacts | null;
  error: string | null;
  warnings?: string[] | null;
  /** Blueprint, с которым отработал воркер (после успешной генерации). */
  blueprint?: Record<string, unknown> | null;
  bom?: JobBom | null;
  diagnostics?: JobDiagnostics | null;
}

async function parseJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!res.ok) {
    let detail = text;
    try {
      const j = JSON.parse(text) as { detail?: unknown };
      if (j.detail !== undefined) detail = JSON.stringify(j.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return JSON.parse(text) as T;
}

export async function postJob(
  blueprint: object | JobPromptBody,
): Promise<JobCreateResponse> {
  const res = await fetch(`${baseUrl()}/api/v1/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(blueprint),
  });
  return parseJson<JobCreateResponse>(res);
}

export async function getJob(jobId: string): Promise<JobStatusResponse> {
  const res = await fetch(`${baseUrl()}/api/v1/jobs/${encodeURIComponent(jobId)}`);
  return parseJson<JobStatusResponse>(res);
}

// --- Cloud projects ---

export interface ProjectLastArtifacts {
  glb_url?: string | null;
  step_url?: string | null;
  mjcf_url?: string | null;
  zip_url?: string | null;
  video_url?: string | null;
  script_url?: string | null;
  bom?: JobBom | null;
}

export interface ProjectRecord {
  project_id: string;
  name: string;
  version: "2.0";
  blueprint: Record<string, unknown>;
  last_artifacts: ProjectLastArtifacts | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreateRequest {
  name: string;
  blueprint: object;
  last_artifacts?: ProjectLastArtifacts | null;
}

export interface ProjectCreateResponse {
  project_id: string;
}

export interface ProjectUpdateRequest {
  name?: string;
  blueprint?: object;
  last_artifacts?: ProjectLastArtifacts | null;
}

export async function getProject(projectId: string): Promise<ProjectRecord> {
  const res = await fetch(
    `${baseUrl()}/api/v1/projects/${encodeURIComponent(projectId)}`,
  );
  return parseJson<ProjectRecord>(res);
}

export async function postProject(
  body: ProjectCreateRequest,
): Promise<ProjectCreateResponse> {
  const res = await fetch(`${baseUrl()}/api/v1/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseJson<ProjectCreateResponse>(res);
}

export async function putProject(
  projectId: string,
  body: ProjectUpdateRequest,
): Promise<ProjectRecord> {
  const res = await fetch(
    `${baseUrl()}/api/v1/projects/${encodeURIComponent(projectId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  return parseJson<ProjectRecord>(res);
}
