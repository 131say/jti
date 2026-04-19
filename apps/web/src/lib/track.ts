/**
 * Продуктовая аналитика (MVP): в dev — console; в prod — опционально POST на endpoint
 * или window.posthog (если задан NEXT_PUBLIC_POSTHOG_KEY — загрузка snippet не делаем,
 * только capture через глобальную заглушку; для полного PostHog подключите snippet в layout).
 */

export type AnalyticsPayload = Record<string, unknown>;

const isDev =
  typeof process !== "undefined" && process.env.NODE_ENV === "development";

function analyticsEndpoint(): string | null {
  const u =
    typeof process !== "undefined"
      ? process.env.NEXT_PUBLIC_ANALYTICS_ENDPOINT?.trim()
      : "";
  return u && u.length > 0 ? u : null;
}

function shouldLogToConsole(): boolean {
  if (typeof process !== "undefined" && process.env.NEXT_PUBLIC_ANALYTICS_DEBUG === "1") {
    return true;
  }
  return Boolean(isDev);
}

/**
 * Отправка события воронки / продукта.
 * Идентификаторы событий согласованы с инкрементом v4.1 (funnel).
 */
export function track(event: string, payload?: AnalyticsPayload): void {
  const body = {
    event,
    payload: payload ?? {},
    ts: Date.now(),
    path:
      typeof window !== "undefined" ? window.location.pathname : undefined,
  };

  if (shouldLogToConsole()) {
    // eslint-disable-next-line no-console
    console.log("[track]", event, body.payload);
  }

  const url = analyticsEndpoint();
  if (url && typeof window !== "undefined") {
    const json = JSON.stringify(body);
    try {
      if (navigator.sendBeacon) {
        const blob = new Blob([json], { type: "application/json" });
        navigator.sendBeacon(url, blob);
      } else {
        void fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: json,
          keepalive: true,
        }).catch(() => {});
      }
    } catch {
      /* ignore */
    }
  }

  const ph = typeof window !== "undefined" ? (window as unknown as { posthog?: { capture?: (e: string, p?: object) => void } }).posthog : undefined;
  if (ph?.capture) {
    try {
      ph.capture(event, payload ?? {});
    } catch {
      /* ignore */
    }
  }
}
