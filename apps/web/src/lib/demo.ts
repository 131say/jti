/**
 * Публичные демо без API: `?project=<slug>` загружает JSON из `/public/<slug>.json`.
 */

export const LIVE_DEMO_SLUGS = [
  "demo-constraints-v3.5",
  "demo-gearbox-v4.3",
  "demo-mates-v3",
] as const;

export type LiveDemoSlug = (typeof LIVE_DEMO_SLUGS)[number];

/** Демо по умолчанию (лендинг, CTA): Constraint Assembly v3.5. */
export const LIVE_DEMO_PROJECT_SLUG: LiveDemoSlug = "demo-constraints-v3.5";

/** Прежнее демо редуктора (snap_to_operation) — для ссылок «как раньше». */
export const MATES_V3_LIVE_DEMO_SLUG: LiveDemoSlug = "demo-mates-v3";

const LIVE_DEMO_CONFIG: Record<
  LiveDemoSlug,
  { jsonPath: string; displayName: string }
> = {
  "demo-constraints-v3.5": {
    jsonPath: "/demo-constraints-v3.5.json",
    displayName: "Сборка (Constraints v3.5)",
  },
  "demo-gearbox-v4.3": {
    jsonPath: "/demo-gearbox-v4.3.json",
    displayName: "Редуктор (генератор v4.3)",
  },
  "demo-mates-v3": {
    jsonPath: "/demo-mates-v3.json",
    displayName: "Редуктор (mates v3)",
  },
};

export function isLiveDemoSlug(
  id: string | null | undefined,
): id is LiveDemoSlug {
  return (
    id === "demo-constraints-v3.5" ||
    id === "demo-gearbox-v4.3" ||
    id === "demo-mates-v3"
  );
}

export function getLiveDemoJsonPath(slug: LiveDemoSlug): string {
  return LIVE_DEMO_CONFIG[slug].jsonPath;
}

export function getLiveDemoDisplayName(slug: LiveDemoSlug): string {
  return LIVE_DEMO_CONFIG[slug].displayName;
}
