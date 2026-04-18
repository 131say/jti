"use client";

import { Link2, Loader2, Save } from "lucide-react";

export function ProjectTopBar({
  projectName,
  onProjectNameChange,
  onSave,
  onShare,
  saving,
  disabled,
  hasProjectId,
}: {
  projectName: string;
  onProjectNameChange: (name: string) => void;
  onSave: () => void;
  onShare: () => void;
  saving: boolean;
  disabled: boolean;
  hasProjectId: boolean;
}) {
  return (
    <header className="flex shrink-0 flex-wrap items-center gap-2 border-b border-neutral-800 bg-neutral-950 px-3 py-2 md:px-4">
      <div className="min-w-0 flex-1">
        <label className="sr-only" htmlFor="project-name-input">
          Название проекта
        </label>
        <input
          id="project-name-input"
          type="text"
          value={projectName}
          onChange={(e) => onProjectNameChange(e.target.value)}
          disabled={disabled}
          placeholder="Название проекта"
          className="w-full min-w-[120px] max-w-md rounded border border-neutral-800 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100 placeholder:text-neutral-600 focus:border-neutral-600 focus:outline-none disabled:opacity-50"
        />
      </div>
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          title={hasProjectId ? "Сохранить изменения" : "Сохранить проект"}
          disabled={disabled || saving}
          onClick={onSave}
          className="inline-flex items-center gap-1.5 rounded border border-neutral-700 bg-neutral-900 px-3 py-1.5 text-xs font-medium text-neutral-100 hover:bg-neutral-800 disabled:opacity-40"
        >
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          ) : (
            <Save className="h-4 w-4" aria-hidden />
          )}
          Сохранить
        </button>
        <button
          type="button"
          title="Скопировать ссылку на проект"
          disabled={disabled || !hasProjectId}
          onClick={onShare}
          className="inline-flex items-center gap-1.5 rounded border border-neutral-700 bg-neutral-900 px-3 py-1.5 text-xs font-medium text-neutral-100 hover:bg-neutral-800 disabled:opacity-40"
        >
          <Link2 className="h-4 w-4" aria-hidden />
          Поделиться
        </button>
      </div>
    </header>
  );
}
