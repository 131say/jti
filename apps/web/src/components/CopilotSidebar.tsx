"use client";

import { Loader2, Send } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

export type ChatMessage = {
  role: "user" | "assistant" | "system";
  content: string;
  warnings?: string[];
};

type CopilotSidebarProps = {
  messages: ChatMessage[];
  aiMode: boolean;
  /** submitting | polling — блокировка ввода (MVP) */
  pending: boolean;
  hasBlueprintContext: boolean;
  onSend: (text: string) => void;
};

export function CopilotSidebar({
  messages,
  aiMode,
  pending,
  hasBlueprintContext,
  onSend,
}: CopilotSidebarProps) {
  const [draft, setDraft] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, pending, scrollToBottom]);

  const submit = () => {
    const t = draft.trim();
    if (!t || pending || !aiMode) return;
    onSend(t);
    setDraft("");
  };

  const inputDisabled = !aiMode || pending;

  return (
    <aside className="flex h-full min-h-0 w-full flex-col border-t border-neutral-800 bg-neutral-950 md:w-[380px] md:border-l md:border-t-0">
      <div className="border-b border-neutral-800 px-3 py-2">
        <h2 className="text-sm font-semibold text-neutral-100">AI Copilot</h2>
        <p className="mt-0.5 text-[11px] text-neutral-500">
          Диалог с Gemini: запросы редактируют Blueprint (Raw, в т.ч.{" "}
          <code className="text-neutral-400">global_variables</code>).
        </p>
      </div>

      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-3 py-2">
        {messages.length === 0 ? (
          <p className="text-[11px] text-neutral-600">
            Напишите, что изменить в модели. Контекст JSON прикрепляется автоматически,
            если редактор содержит валидный Blueprint.
          </p>
        ) : null}
        {messages.map((m, i) => (
          <div
            key={`${i}-${m.role}-${m.content.slice(0, 24)}`}
            className={`rounded-md px-2.5 py-2 text-xs leading-snug ${
              m.role === "user"
                ? "ml-4 bg-neutral-800 text-neutral-100"
                : m.role === "system"
                  ? "border border-neutral-800/80 bg-neutral-900/50 text-neutral-500 italic"
                  : "mr-4 border border-neutral-700/80 bg-neutral-900 text-neutral-200"
            }`}
          >
            <div className="whitespace-pre-wrap">{m.content}</div>
            {m.warnings && m.warnings.length > 0 ? (
              <ul className="mt-2 list-inside list-disc space-y-0.5 border-t border-amber-900/50 pt-2 text-[11px] text-amber-100/90">
                {m.warnings.map((w, wi) => (
                  <li key={`${wi}-${w.slice(0, 40)}`}>{w}</li>
                ))}
              </ul>
            ) : null}
          </div>
        ))}
        {pending ? (
          <div className="mr-4 flex items-center gap-2 rounded-md border border-neutral-700/80 bg-neutral-900 px-2.5 py-2 text-xs text-neutral-400">
            <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" aria-hidden />
            AI думает / генерирует…
          </div>
        ) : null}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="border-t border-neutral-800 p-3"
      >
        {!aiMode ? (
          <p className="mb-2 text-[11px] text-neutral-500">
            Включите режим <span className="text-neutral-300">AI</span> слева, чтобы
            вести диалог.
          </p>
        ) : hasBlueprintContext ? (
          <p className="mb-2 text-[11px] text-neutral-500">
            К запросу прикладывается текущий Blueprint (редактирование).
          </p>
        ) : (
          <p className="mb-2 text-[11px] text-amber-700/90">
            Нет валидного JSON в редакторе — запрос уйдёт без контекста модели.
          </p>
        )}
        <textarea
          className="mb-2 min-h-[80px] w-full resize-y rounded border border-neutral-800 bg-neutral-950 p-2.5 font-sans text-xs text-neutral-100 placeholder:text-neutral-600 disabled:cursor-not-allowed disabled:opacity-50"
          spellCheck={false}
          placeholder="Например: уменьши высоту на 5 мм, добавь фаску 1 мм на верхней кромке…"
          value={draft}
          disabled={inputDisabled}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
        />
        <button
          type="submit"
          disabled={inputDisabled || !draft.trim()}
          className="inline-flex w-full items-center justify-center gap-2 rounded bg-neutral-100 px-3 py-2 text-sm font-medium text-neutral-900 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {pending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              Ожидание…
            </>
          ) : (
            <>
              <Send className="h-4 w-4 shrink-0" aria-hidden />
              Отправить в AI
            </>
          )}
        </button>
      </form>
    </aside>
  );
}
