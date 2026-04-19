"use client";

import { X } from "lucide-react";
import { useCallback, useState } from "react";

import { postLead, type LeadIntent } from "@/lib/api";

const INTENT_OPTIONS: { value: LeadIntent; label: string }[] = [
  { value: "hobby", label: "Hobby" },
  { value: "startup", label: "Startup" },
  { value: "enterprise", label: "Enterprise" },
];

export function ProFeedbackModal({
  open,
  onClose,
  source,
}: {
  open: boolean;
  onClose: () => void;
  source: "live_demo" | "editor_free";
}) {
  const [email, setEmail] = useState("");
  const [intent, setIntent] = useState<LeadIntent>("startup");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const onSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setMsg(null);
      const em = email.trim();
      if (!em || !em.includes("@")) {
        setMsg("Укажите email.");
        return;
      }
      setBusy(true);
      try {
        await postLead({
          email: em,
          source,
          intent,
          message: message.trim() || undefined,
        });
        setMsg("Отправлено. Спасибо!");
        setMessage("");
        setEmail("");
      } catch (err) {
        setMsg(err instanceof Error ? err.message : "Ошибка отправки.");
      } finally {
        setBusy(false);
      }
    },
    [email, intent, message, source],
  );

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[120] flex items-center justify-center bg-black/70 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="pro-feedback-title"
    >
      <div className="relative w-full max-w-md rounded-lg border border-neutral-700 bg-neutral-950 p-6 shadow-xl">
        <button
          type="button"
          onClick={onClose}
          className="absolute right-3 top-3 rounded p-1 text-neutral-500 hover:bg-neutral-800 hover:text-neutral-200"
          aria-label="Закрыть"
        >
          <X className="h-5 w-5" />
        </button>
        <h2
          id="pro-feedback-title"
          className="text-lg font-semibold text-neutral-100"
        >
          Обратная связь / Request PRO
        </h2>
        <p className="mt-2 text-sm text-neutral-400">
          Ранний доступ к приватным workspace, FEM и расширенному экспорту.
          Расскажите, что вам нужно — ответим на email.
        </p>
        <form onSubmit={onSubmit} className="mt-5 space-y-3">
          <div>
            <label className="mb-1 block text-xs text-neutral-500">Email</label>
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 focus:border-sky-600 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-neutral-500">Цель</label>
            <select
              value={intent}
              onChange={(e) => setIntent(e.target.value as LeadIntent)}
              className="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 focus:border-sky-600 focus:outline-none"
            >
              {INTENT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-neutral-500">
              Сообщение (необязательно)
            </label>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={4}
              placeholder="Задача, объём, сроки…"
              className="w-full resize-none rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 focus:border-sky-600 focus:outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-sky-600 py-2 text-sm font-semibold text-white hover:bg-sky-500 disabled:opacity-50"
          >
            {busy ? "Отправка…" : "Отправить"}
          </button>
          {msg ? (
            <p
              className={`text-center text-xs ${
                msg.startsWith("Отправлено") ? "text-emerald-400" : "text-amber-200"
              }`}
            >
              {msg}
            </p>
          ) : null}
        </form>
      </div>
    </div>
  );
}
