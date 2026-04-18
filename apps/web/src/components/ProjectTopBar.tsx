"use client";

import Link from "next/link";
import {
  GitFork,
  Link2,
  Loader2,
  LogIn,
  LogOut,
  Save,
  Shield,
  ShieldOff,
} from "lucide-react";

import type { AuthUser } from "@/lib/api";

export function ProjectTopBar({
  projectName,
  onProjectNameChange,
  onSave,
  onShare,
  saving,
  disabled,
  hasProjectId,
  user,
  onLoginClick,
  onLogout,
  workspaceReadOnly,
  isProjectOwner,
  isPublic,
  onIsPublicChange,
  publicBusy,
  onFork,
  forkBusy,
  onLoginForFork,
}: {
  projectName: string;
  onProjectNameChange: (name: string) => void;
  onSave: () => void;
  onShare: () => void;
  saving: boolean;
  disabled: boolean;
  hasProjectId: boolean;
  user: AuthUser | null;
  onLoginClick: () => void;
  onLogout: () => void;
  workspaceReadOnly: boolean;
  /** владелец (или legacy без owner до claim) */
  isProjectOwner: boolean;
  isPublic: boolean;
  onIsPublicChange: (v: boolean) => void;
  publicBusy: boolean;
  onFork: () => void;
  forkBusy: boolean;
  /** Для гостя на чужом публичном проекте */
  onLoginForFork?: () => void;
}) {
  const showSave = !workspaceReadOnly && (!hasProjectId ? Boolean(user) : true);
  const showFork =
    workspaceReadOnly &&
    hasProjectId &&
    Boolean(user) &&
    !isProjectOwner;
  const showForkLogin =
    workspaceReadOnly && hasProjectId && !user && !isProjectOwner;
  const showOwnerToggle = Boolean(
    user && hasProjectId && isProjectOwner && !workspaceReadOnly,
  );

  return (
    <header className="flex shrink-0 flex-wrap items-center gap-2 border-b border-neutral-800 bg-neutral-950 px-3 py-2 md:px-4">
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
        <Link
          href="/dashboard"
          className="shrink-0 rounded border border-neutral-800 px-2 py-1 text-[11px] text-neutral-400 hover:border-neutral-600 hover:text-neutral-200"
        >
          Мои проекты
        </Link>
        <label className="sr-only" htmlFor="project-name-input">
          Название проекта
        </label>
        <input
          id="project-name-input"
          type="text"
          value={projectName}
          onChange={(e) => onProjectNameChange(e.target.value)}
          disabled={disabled || workspaceReadOnly}
          placeholder="Название проекта"
          className="min-w-[120px] max-w-md flex-1 rounded border border-neutral-800 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100 placeholder:text-neutral-600 focus:border-neutral-600 focus:outline-none disabled:opacity-50"
        />
      </div>

      {showOwnerToggle ? (
        <label className="flex cursor-pointer items-center gap-2 text-[11px] text-neutral-400">
          <input
            type="checkbox"
            checked={isPublic}
            disabled={publicBusy || disabled}
            onChange={(e) => onIsPublicChange(e.target.checked)}
            className="rounded border-neutral-600 accent-neutral-200"
          />
          <span className="flex items-center gap-1">
            {isPublic ? (
              <Shield className="h-3.5 w-3.5 text-emerald-400/90" aria-hidden />
            ) : (
              <ShieldOff className="h-3.5 w-3.5 text-neutral-500" aria-hidden />
            )}
            Публичный просмотр по ссылке
          </span>
        </label>
      ) : null}

      <div className="flex flex-wrap items-center gap-1.5">
        {showFork ? (
          <button
            type="button"
            title="Скопировать проект в свой workspace"
            disabled={forkBusy || disabled}
            onClick={onFork}
            className="inline-flex items-center gap-1.5 rounded border border-emerald-800 bg-emerald-950/50 px-3 py-1.5 text-xs font-semibold text-emerald-100 hover:bg-emerald-900/50 disabled:opacity-40"
          >
            {forkBusy ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <GitFork className="h-4 w-4" aria-hidden />
            )}
            Fork (копировать себе)
          </button>
        ) : null}
        {showForkLogin ? (
          <button
            type="button"
            title="Войдите, чтобы скопировать проект"
            disabled={disabled}
            onClick={onLoginForFork}
            className="inline-flex items-center gap-1.5 rounded border border-emerald-800 bg-emerald-950/50 px-3 py-1.5 text-xs font-semibold text-emerald-100 hover:bg-emerald-900/50 disabled:opacity-40"
          >
            <GitFork className="h-4 w-4" aria-hidden />
            Войти для Fork
          </button>
        ) : null}

        {showSave ? (
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
        ) : null}

        {!user ? (
          <button
            type="button"
            onClick={onLoginClick}
            className="inline-flex items-center gap-1.5 rounded border border-neutral-600 bg-neutral-900 px-3 py-1.5 text-xs font-medium text-neutral-100 hover:bg-neutral-800"
          >
            <LogIn className="h-4 w-4" aria-hidden />
            Войти
          </button>
        ) : (
          <div className="flex items-center gap-1.5">
            <div
              className="flex max-w-[200px] items-center gap-1.5 text-[11px] text-neutral-400"
              title={user.email}
            >
              {user.avatar_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={user.avatar_url}
                  alt=""
                  width={24}
                  height={24}
                  className="rounded-full"
                />
              ) : null}
              <span className="truncate">{user.name || user.email}</span>
            </div>
            <button
              type="button"
              onClick={onLogout}
              className="inline-flex items-center gap-1 rounded border border-neutral-800 px-2 py-1 text-[11px] text-neutral-400 hover:bg-neutral-900 hover:text-neutral-200"
            >
              <LogOut className="h-3.5 w-3.5" aria-hidden />
              Выйти
            </button>
          </div>
        )}

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
