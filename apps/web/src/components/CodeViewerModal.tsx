"use client";

import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useCallback, useEffect, useState } from "react";

export function CodeViewerModal({
  open,
  onClose,
  url,
}: {
  open: boolean;
  onClose: () => void;
  url: string | null;
}) {
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !url) return;
    setLoading(true);
    setErr(null);
    setContent(null);
    const ac = new AbortController();
    fetch(url, { signal: ac.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.text();
      })
      .then(setContent)
      .catch((e: unknown) => {
        if ((e as Error).name === "AbortError") return;
        setErr(e instanceof Error ? e.message : String(e));
      })
      .finally(() => setLoading(false));
    return () => ac.abort();
  }, [open, url]);

  const copy = useCallback(() => {
    if (!content) return;
    void navigator.clipboard.writeText(content);
  }, [content]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-3"
      role="dialog"
      aria-modal="true"
      aria-labelledby="code-viewer-title"
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-lg border border-neutral-700 bg-neutral-950 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex flex-wrap items-center gap-2 border-b border-neutral-800 px-3 py-2">
          <h2
            id="code-viewer-title"
            className="flex-1 text-sm font-medium text-neutral-100"
          >
            Eject to Python (build_model.py)
          </h2>
          <button
            type="button"
            disabled={!content}
            onClick={copy}
            className="rounded border border-neutral-600 px-2 py-1 text-xs text-neutral-200 hover:bg-neutral-800 disabled:opacity-40"
          >
            Скопировать код
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-neutral-600 px-2 py-1 text-xs text-neutral-200 hover:bg-neutral-800"
          >
            Закрыть
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-auto">
          {loading ? (
            <div className="p-4 text-sm text-neutral-400">Загрузка…</div>
          ) : err ? (
            <div className="p-4 text-sm text-red-400">{err}</div>
          ) : (
            <SyntaxHighlighter
              language="python"
              style={oneDark}
              showLineNumbers
              wrapLines
              customStyle={{
                margin: 0,
                maxHeight: "75vh",
                fontSize: "12px",
                borderRadius: 0,
              }}
            >
              {content ?? ""}
            </SyntaxHighlighter>
          )}
        </div>
      </div>
    </div>
  );
}
