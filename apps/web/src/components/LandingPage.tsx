"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { LeadWaitlistSection } from "@/components/LeadWaitlistSection";
import { LoginModal } from "@/components/LoginModal";
import { useAuth } from "@/context/AuthContext";

import { LIVE_DEMO_PROJECT_SLUG } from "@/lib/demo";
import { track } from "@/lib/track";

export function LandingPage() {
  const router = useRouter();
  const { user, ready } = useAuth();
  const [loginOpen, setLoginOpen] = useState(false);

  useEffect(() => {
    track("landing_page_viewed", {});
  }, []);

  const goWorkspaceOrLogin = useCallback(() => {
    if (!ready) return;
    if (user) {
      router.push("/dashboard");
    } else {
      setLoginOpen(true);
    }
  }, [ready, user, router]);

  const onStartDesign = useCallback(() => {
    track("cta_start_forging_clicked", { surface: "landing_hero" });
    goWorkspaceOrLogin();
  }, [goWorkspaceOrLogin]);

  const onStartFree = useCallback(() => {
    track("cta_start_forging_clicked", { surface: "landing_final_cta" });
    goWorkspaceOrLogin();
  }, [goWorkspaceOrLogin]);

  const onLoggedIn = useCallback(() => {
    setLoginOpen(false);
    router.push("/dashboard");
  }, [router]);

  const demoHref = `/editor?project=${LIVE_DEMO_PROJECT_SLUG}`;

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      <LoginModal
        open={loginOpen}
        onClose={() => setLoginOpen(false)}
        onLoggedIn={onLoggedIn}
      />

      <header className="border-b border-neutral-800/80 bg-neutral-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-4">
          <Link href="/" className="text-sm font-semibold tracking-tight">
            AI-Forge
          </Link>
          <nav className="flex items-center gap-3 text-sm">
            <Link
              href="/editor"
              className="text-neutral-400 hover:text-neutral-200"
            >
              Редактор
            </Link>
            <Link
              href="/dashboard"
              className="text-neutral-400 hover:text-neutral-200"
            >
              Проекты
            </Link>
            <button
              type="button"
              onClick={() => (user ? router.push("/dashboard") : setLoginOpen(true))}
              className="rounded border border-neutral-600 px-3 py-1.5 text-neutral-200 hover:bg-neutral-900"
            >
              {user ? "Аккаунт" : "Войти"}
            </button>
          </nav>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="mx-auto max-w-5xl px-4 pb-16 pt-12 md:pt-20">
          <p className="mb-3 text-xs font-medium uppercase tracking-widest text-sky-400/90">
            AI Mechanical Design Platform
          </p>
          <h1 className="text-balance text-3xl font-bold leading-tight tracking-tight md:text-5xl">
            От идеи до готовой сборки — за 60 секунд
          </h1>
          <p className="mt-4 max-w-2xl text-pretty text-lg text-neutral-300 md:text-xl">
            Создавай механизмы с помощью ИИ и сразу получай 3D-модель,
            спецификацию (BOM), симуляцию и PDF-инструкции для производства.
            Без CAD-боли. Без ручного моделирования.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={onStartDesign}
              disabled={!ready}
              className="rounded-lg bg-sky-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-sky-900/30 transition hover:bg-sky-500 disabled:opacity-50"
            >
              🚀 Начать проектировать
            </button>
            <Link
              href={demoHref}
              onClick={() => {
                track("live_demo_opened", { surface: "landing_hero" });
                try {
                  sessionStorage.setItem("jti_live_demo_from_landing", "1");
                } catch {
                  /* ignore */
                }
              }}
              className="inline-flex items-center rounded-lg border border-neutral-600 bg-neutral-900/80 px-6 py-3 text-sm font-medium text-neutral-100 hover:border-neutral-500 hover:bg-neutral-800"
            >
              ▶️ Смотреть демо
            </Link>
          </div>
          <p className="mt-4 text-sm text-neutral-400">
            Бесплатно. Без установки. Работает в браузере.
          </p>

          <div className="mt-14 rounded-xl border border-neutral-800 bg-gradient-to-b from-neutral-900/80 to-neutral-950 p-4 md:p-6">
            <p className="mb-3 text-center text-[11px] font-medium uppercase tracking-wider text-neutral-500">
              Пример пайплайна
            </p>
            <div className="flex flex-col gap-3 md:flex-row md:items-stretch md:justify-between md:gap-4">
              <div className="flex-1 rounded-lg border border-neutral-800 bg-neutral-950/60 p-3">
                <div className="text-xs text-neutral-500">Prompt</div>
                <p className="mt-1 font-mono text-[13px] text-sky-200/95">
                  «Собери редуктор с валом, подшипниками и креплением»
                </p>
              </div>
              <div className="hidden items-center justify-center text-neutral-600 md:flex">
                →
              </div>
              <div className="flex-1 rounded-lg border border-emerald-900/50 bg-emerald-950/20 p-3">
                <div className="text-xs text-neutral-500">Результат</div>
                <p className="mt-1 text-sm text-neutral-300">
                  3D · BOM · симуляция · PDF-сборка
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Aha */}
        <section className="border-t border-neutral-800 bg-neutral-900/30 py-16 md:py-20">
          <div className="mx-auto max-w-5xl px-4">
            <h2 className="text-center text-2xl font-bold tracking-tight md:text-4xl">
              Ты описываешь. AI-Forge строит.
            </h2>
            <div className="mt-12 grid gap-8 md:grid-cols-3">
              <div className="rounded-xl border border-neutral-800 bg-neutral-950/50 p-6">
                <div className="text-2xl">💬</div>
                <h3 className="mt-3 text-sm font-semibold uppercase tracking-wide text-neutral-400">
                  Step 1 — Prompt
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-neutral-300">
                  Опиши задачу:{" "}
                  <span className="italic text-neutral-400">
                    «Собери редуктор с валом, подшипниками и креплением»
                  </span>
                </p>
              </div>
              <div className="rounded-xl border border-neutral-800 bg-neutral-950/50 p-6">
                <div className="text-2xl">⚙️</div>
                <h3 className="mt-3 text-sm font-semibold uppercase tracking-wide text-neutral-400">
                  Step 2 — AI Engine
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-neutral-300">
                  AI превращает текст в инженерную модель: параметрический CAD,
                  логика сборки, проверки DFM.
                </p>
              </div>
              <div className="rounded-xl border border-neutral-800 bg-neutral-950/50 p-6">
                <div className="text-2xl">📦</div>
                <h3 className="mt-3 text-sm font-semibold uppercase tracking-wide text-neutral-400">
                  Step 3 — Production Ready
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-neutral-300">
                  3D-модель, BOM, симуляция механики, PDF-инструкция сборки —
                  готово к производству.
                </p>
              </div>
            </div>
            <p className="mt-10 text-center text-base font-medium text-sky-200/90 md:text-lg">
              Не просто модель. Готовый инженерный результат.
            </p>
          </div>
        </section>

        {/* Features */}
        <section className="py-16 md:py-20">
          <div className="mx-auto max-w-5xl px-4">
            <h2 className="text-center text-2xl font-bold md:text-3xl">
              Киллер-фичи
            </h2>
            <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {[
                {
                  icon: "🧠",
                  title: "Conversational Copilot",
                  sub: "Проектируй, как думаешь",
                  body: "Напиши: «Увеличь диаметр», «Добавь фаску», «Сделай легче». ИИ понимает контекст и меняет модель без разрушения параметрики.",
                },
                {
                  icon: "📐",
                  title: "Parametric Design",
                  sub: "Настоящий параметрический CAD",
                  body: "Связывай размеры формулами. Меняешь одно значение — обновляется вся сборка.",
                },
                {
                  icon: "⚙️",
                  title: "Physics & Kinematics",
                  sub: "Проверь, как это работает",
                  body: "Вращение валов, движение механизмов, видео симуляции (MuJoCo). Видишь не только форму — видишь поведение.",
                },
                {
                  icon: "📦",
                  title: "Manufacturing Ready",
                  sub: "Сразу к производству",
                  body: "BOM (масса, стоимость), детали отдельно, STEP / STL экспорт. Без ручной подготовки.",
                },
                {
                  icon: "📑",
                  title: "Assembly Instructions",
                  sub: "Авто PDF",
                  body: "Пошаговая сборка по графу mates, таблица деталей — как будто рядом техписатель.",
                },
                {
                  icon: "🧪",
                  title: "Engineering Diagnostics",
                  sub: "ИИ страхует от ошибок",
                  body: "Пересечения, тонкие стенки, риски для печати. AI не только рисует — подсвечивает проблемы.",
                },
              ].map((f) => (
                <div
                  key={f.title}
                  className="rounded-xl border border-neutral-800 bg-neutral-950/40 p-5"
                >
                  <div className="text-2xl">{f.icon}</div>
                  <h3 className="mt-2 font-semibold text-neutral-100">{f.title}</h3>
                  <p className="mt-0.5 text-xs text-sky-400/80">{f.sub}</p>
                  <p className="mt-2 text-sm leading-relaxed text-neutral-400">
                    {f.body}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Differentiation */}
        <section className="border-t border-neutral-800 bg-neutral-900/20 py-16 md:py-20">
          <div className="mx-auto max-w-5xl px-4">
            <h2 className="text-center text-2xl font-bold md:text-3xl">
              Это не просто CAD
            </h2>
            <div className="mt-8 overflow-x-auto rounded-xl border border-neutral-800">
              <table className="w-full min-w-[560px] text-left text-sm">
                <thead>
                  <tr className="border-b border-neutral-800 bg-neutral-900/90">
                    <th className="px-4 py-3 font-medium text-neutral-400">
                      Характеристика
                    </th>
                    <th className="px-4 py-3 font-medium text-sky-300">AI-Forge</th>
                    <th className="px-4 py-3 font-medium text-neutral-500">
                      Классический CAD
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-800">
                  <tr>
                    <td className="px-4 py-3 text-neutral-300">Создание</td>
                    <td className="px-4 py-3 text-neutral-100">
                      Пишешь текст → получаешь модель
                    </td>
                    <td className="px-4 py-3 text-neutral-500">Рисуешь вручную</td>
                  </tr>
                  <tr>
                    <td className="px-4 py-3 text-neutral-300">BOM и PDF</td>
                    <td className="px-4 py-3 text-neutral-100">
                      Авто-BOM и PDF
                    </td>
                    <td className="px-4 py-3 text-neutral-500">Всё вручную</td>
                  </tr>
                  <tr>
                    <td className="px-4 py-3 text-neutral-300">Ассистент</td>
                    <td className="px-4 py-3 text-neutral-100">AI-Copilot</td>
                    <td className="px-4 py-3 text-neutral-500">Нет</td>
                  </tr>
                  <tr>
                    <td className="px-4 py-3 text-neutral-300">Симуляция</td>
                    <td className="px-4 py-3 text-neutral-100">
                      Симуляция из коробки
                    </td>
                    <td className="px-4 py-3 text-neutral-500">
                      Настраивается отдельно
                    </td>
                  </tr>
                  <tr>
                    <td className="px-4 py-3 text-neutral-300">Скорость</td>
                    <td className="px-4 py-3 text-neutral-100">
                      Минуты вместо часов
                    </td>
                    <td className="px-4 py-3 text-neutral-500">Часы и дни</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="mt-8 text-center text-base font-medium text-neutral-300 md:text-lg">
              CAD, который работает со скоростью мысли.
            </p>
          </div>
        </section>

        {/* Demo CTA */}
        <section className="py-16 md:py-20">
          <div className="mx-auto max-w-2xl px-4 text-center">
            <h2 className="text-2xl font-bold md:text-3xl">
              Посмотри, как это работает
            </h2>
            <p className="mt-3 text-sm text-neutral-400">
              Без регистрации. Откроется прямо в редакторе.
            </p>
            <Link
              href={demoHref}
              onClick={() => {
                track("live_demo_opened", {
                  surface: "landing_demo_section",
                });
                try {
                  sessionStorage.setItem("jti_live_demo_from_landing", "1");
                } catch {
                  /* ignore */
                }
              }}
              className="mt-6 inline-flex items-center justify-center rounded-xl border border-sky-500/50 bg-sky-950/40 px-8 py-4 text-base font-semibold text-sky-100 transition hover:bg-sky-900/50"
            >
              👉 ▶️ Открыть демо проект
            </Link>
            <p className="mt-4 text-xs text-neutral-500">
              Сборка: плита, вал, подшипник, шкив, болты — только{" "}
              <code className="text-neutral-400">assembly_mates</code>, без ручных
              координат крепежа.
            </p>
          </div>
        </section>

        {/* Final CTA */}
        <section className="border-t border-neutral-800 bg-gradient-to-b from-neutral-900/40 to-neutral-950 py-16 md:py-20">
          <div className="mx-auto max-w-2xl px-4 text-center">
            <h2 className="text-2xl font-bold md:text-3xl">
              Начни проектировать прямо сейчас
            </h2>
            <p className="mt-3 text-neutral-400">
              Создай свой первый механизм за минуту. ИИ сделает остальное.
            </p>
            <button
              type="button"
              onClick={onStartFree}
              disabled={!ready}
              className="mt-8 rounded-xl bg-sky-600 px-10 py-4 text-base font-semibold text-white shadow-lg shadow-sky-900/40 transition hover:bg-sky-500 disabled:opacity-50"
            >
              🚀 Начать бесплатно
            </button>
          </div>
        </section>

        <LeadWaitlistSection />
      </main>

      <footer className="border-t border-neutral-800 py-10">
        <div className="mx-auto flex max-w-5xl flex-col items-center justify-between gap-6 px-4 md:flex-row">
          <div className="text-sm font-semibold">AI-Forge</div>
          <div className="flex flex-wrap justify-center gap-6 text-sm text-neutral-500">
            <a
              href="https://github.com/131say/jti"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-neutral-300"
            >
              GitHub
            </a>
            <a
              href="https://github.com/131say/jti#readme"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-neutral-300"
            >
              Documentation
            </a>
            <span className="text-neutral-600" title="Soon">
              Terms of Service
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
