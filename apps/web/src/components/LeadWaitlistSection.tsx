"use client";

import { useCallback, useState } from "react";

import { postLead, type LeadIntent } from "@/lib/api";

const INTENT_OPTIONS: { value: LeadIntent; label: string }[] = [
  { value: "hobby", label: "Hobby / личные проекты" },
  { value: "startup", label: "Startup / команда" },
  { value: "enterprise", label: "Enterprise / компания" },
];

export function LeadWaitlistSection() {
  const [email, setEmail] = useState("");
  const [intent, setIntent] = useState<LeadIntent>("startup");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const onSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setMsg(null);
      const em = email.trim();
      if (!em || !em.includes("@")) {
        setMsg("Укажите корректный email.");
        return;
      }
      setBusy(true);
      try {
        await postLead({
          email: em,
          source: "landing_waitlist",
          intent,
        });
        setMsg("Спасибо! Мы свяжемся, когда откроем ранний доступ.");
        setEmail("");
      } catch (err) {
        setMsg(err instanceof Error ? err.message : "Не удалось отправить.");
      } finally {
        setBusy(false);
      }
    },
    [email, intent],
  );

  return (
    <section className="border-t border-neutral-800 bg-gradient-to-b from-sky-950/20 to-neutral-950 py-16 md:py-20">
      <div className="mx-auto max-w-xl px-4">
        <h2 className="text-center text-2xl font-bold tracking-tight text-neutral-50 md:text-3xl">
          Получите ранний доступ к PRO-функциям
        </h2>
        <p className="mt-3 text-center text-sm leading-relaxed text-neutral-400 md:text-base">
          Оставьте email, чтобы первыми получить доступ к приватным рабочим
          пространствам, FEM-анализу и безлимитному экспорту КД.
        </p>
        <form
          onSubmit={onSubmit}
          className="mt-8 space-y-4 rounded-xl border border-sky-900/40 bg-neutral-900/40 p-6 shadow-lg shadow-black/20"
        >
          <div>
            <label
              htmlFor="waitlist-email"
              className="mb-1 block text-xs font-medium text-neutral-400"
            >
              Email
            </label>
            <input
              id="waitlist-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              className="w-full rounded border border-neutral-700 bg-neutral-950 px-3 py-2 text-sm text-neutral-100 placeholder:text-neutral-600 focus:border-sky-600 focus:outline-none"
            />
          </div>
          <div>
            <label
              htmlFor="waitlist-intent"
              className="mb-1 block text-xs font-medium text-neutral-400"
            >
              Ваша цель
            </label>
            <select
              id="waitlist-intent"
              value={intent}
              onChange={(e) => setIntent(e.target.value as LeadIntent)}
              className="w-full rounded border border-neutral-700 bg-neutral-950 px-3 py-2 text-sm text-neutral-100 focus:border-sky-600 focus:outline-none"
            >
              {INTENT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-sky-600 py-2.5 text-sm font-semibold text-white transition hover:bg-sky-500 disabled:opacity-50"
          >
            {busy ? "Отправка…" : "Запросить доступ"}
          </button>
          {msg ? (
            <p
              className={`text-center text-xs ${
                msg.startsWith("Спасибо") ? "text-emerald-400" : "text-amber-200"
              }`}
            >
              {msg}
            </p>
          ) : null}
        </form>
      </div>
    </section>
  );
}
