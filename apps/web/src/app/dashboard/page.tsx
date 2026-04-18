"use client";

import Link from "next/link";
import { Loader2, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { LoginModal } from "@/components/LoginModal";
import { useAuth } from "@/context/AuthContext";
import {
  deleteProject,
  listMyProjects,
  type ProjectSummary,
} from "@/lib/api";

export default function DashboardPage() {
  const { user, ready, logout } = useAuth();
  const [loginOpen, setLoginOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<ProjectSummary[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    if (!ready || !user) {
      setItems(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      setLoading(true);
      setErr(null);
      try {
        const r = await listMyProjects();
        if (!cancelled) setItems(r.projects);
      } catch (e) {
        if (!cancelled)
          setErr(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [ready, user]);

  const handleDelete = useCallback(
    async (projectId: string) => {
      if (
        !window.confirm(
          "Вы уверены, что хотите удалить проект?",
        )
      ) {
        return;
      }
      setDeletingId(projectId);
      try {
        await deleteProject(projectId);
        setItems((prev) =>
          prev ? prev.filter((p) => p.project_id !== projectId) : prev,
        );
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      } finally {
        setDeletingId(null);
      }
    },
    [],
  );

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-neutral-800 px-4 py-3">
        <div className="flex items-center gap-3">
          <Link
            href="/editor"
            className="text-sm text-neutral-400 hover:text-neutral-200"
          >
            ← Редактор
          </Link>
          <h1 className="text-lg font-semibold">Мои проекты</h1>
        </div>
        {user ? (
          <div className="flex items-center gap-2 text-xs text-neutral-500">
            <span className="truncate max-w-[240px]">{user.email}</span>
            <button
              type="button"
              onClick={() => logout()}
              className="rounded border border-neutral-700 px-2 py-1 hover:bg-neutral-900"
            >
              Выйти
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setLoginOpen(true)}
            className="rounded border border-neutral-600 px-3 py-1 text-sm hover:bg-neutral-900"
          >
            Войти
          </button>
        )}
      </header>

      <LoginModal
        open={loginOpen}
        onClose={() => setLoginOpen(false)}
        onLoggedIn={() => setLoginOpen(false)}
      />

      <main className="mx-auto max-w-3xl px-4 py-6">
        {!ready ? (
          <div className="flex items-center gap-2 text-sm text-neutral-500">
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
            Загрузка…
          </div>
        ) : !user ? (
          <p className="text-sm text-neutral-500">
            Войдите, чтобы увидеть сохранённые проекты.
          </p>
        ) : loading ? (
          <div className="flex items-center gap-2 text-sm text-neutral-500">
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
            Загружаем список…
          </div>
        ) : err ? (
          <p className="text-sm text-red-400">{err}</p>
        ) : items && items.length === 0 ? (
          <p className="text-sm text-neutral-500">
            Пока нет сохранённых проектов. Создайте модель в{" "}
            <Link href="/editor" className="underline">
              редакторе
            </Link>{" "}
            и нажмите «Сохранить».
          </p>
        ) : (
          <ul className="space-y-2">
            {items?.map((p) => (
              <li key={p.project_id}>
                <div className="flex items-stretch gap-2 rounded border border-neutral-800 bg-neutral-900/40 hover:border-neutral-600">
                  <Link
                    href={`/editor?project=${encodeURIComponent(p.project_id)}`}
                    className="flex min-w-0 flex-1 flex-col px-4 py-3"
                  >
                    <span className="font-medium text-neutral-100">{p.name}</span>
                    <span className="mt-1 text-[11px] text-neutral-500">
                      {p.is_public ? "Публичный" : "Приватный"} ·{" "}
                      {new Date(p.updated_at).toLocaleString()}
                    </span>
                  </Link>
                  <button
                    type="button"
                    title="Удалить проект"
                    disabled={deletingId === p.project_id}
                    onClick={() => void handleDelete(p.project_id)}
                    className="shrink-0 px-3 text-neutral-500 hover:bg-red-950/50 hover:text-red-300 disabled:opacity-40"
                  >
                    {deletingId === p.project_id ? (
                      <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
                    ) : (
                      <Trash2 className="h-5 w-5" aria-hidden />
                    )}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
