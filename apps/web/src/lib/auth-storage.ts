const TOKEN = "aiforge_access_token";

/** Клиентский токен API (после POST /auth/google). */
export function getStoredAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN);
}

export function setStoredAccessToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem(TOKEN, token);
  else localStorage.removeItem(TOKEN);
}
