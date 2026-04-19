/**
 * Продуктовая аналитика: в dev — console; события шлются на first-party
 * POST /api/v1/telemetry (тот же хост, что и API — минимум потерь из-за AdBlock/CORS).
 * Опционально: window.posthog.capture при подключённом PostHog.
 */

import { apiBaseUrl } from "@/lib/api";

export type AnalyticsPayload = Record<string, unknown>;

const isDev =
  typeof process !== "undefined" && process.env.NODE_ENV === "development";

function shouldLogToConsole(): boolean {
  if (
    typeof process !== "undefined" &&
    process.env.NEXT_PUBLIC_ANALYTICS_DEBUG === "1"
  ) {
    return true;
  }
  return Boolean(isDev);
}

function sendTelemetryFirstParty(body: Record<string, unknown>): void {
  if (typeof window === "undefined") return;
  const url = `${apiBaseUrl()}/api/v1/telemetry`;
  const json = JSON.stringify(body);
  try {
    void fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: json,
      keepalive: true,
      mode: "cors",
    }).catch(() => {});
  } catch {
    /* ignore */
  }
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

  sendTelemetryFirstParty(body);

  const ph =
    typeof window !== "undefined"
      ? (
          window as unknown as {
            posthog?: { capture?: (e: string, p?: object) => void };
          }
        ).posthog
      : undefined;
  if (ph?.capture) {
    try {
      ph.capture(event, payload ?? {});
    } catch {
      /* ignore */
    }
  }
}
