"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  getAuthMe,
  postAuthGoogle,
  type AuthTokenResponse,
  type AuthUser,
} from "@/lib/api";
import { getStoredAccessToken, setStoredAccessToken } from "@/lib/auth-storage";

type AuthState = {
  user: AuthUser | null;
  /** false до первой проверки токена в браузере */
  ready: boolean;
  loginWithGoogleCredential: (credential: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
};

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);

  const refreshUser = useCallback(async () => {
    const t = getStoredAccessToken();
    if (!t) {
      setUser(null);
      return;
    }
    try {
      const me = await getAuthMe();
      setUser(me);
    } catch {
      setStoredAccessToken(null);
      setUser(null);
    }
  }, []);

  useEffect(() => {
    void (async () => {
      await refreshUser();
      setReady(true);
    })();
  }, [refreshUser]);

  const loginWithGoogleCredential = useCallback(async (credential: string) => {
    const r: AuthTokenResponse = await postAuthGoogle(credential);
    setStoredAccessToken(r.access_token);
    setUser(r.user);
  }, []);

  const logout = useCallback(() => {
    setStoredAccessToken(null);
    setUser(null);
  }, []);

  const value = useMemo(
    () =>
      ({
        user,
        ready,
        loginWithGoogleCredential,
        logout,
        refreshUser,
      }) satisfies AuthState,
    [user, ready, loginWithGoogleCredential, logout, refreshUser],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be used within AuthProvider");
  return v;
}
