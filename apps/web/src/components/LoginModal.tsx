"use client";

import { GoogleLogin } from "@react-oauth/google";
import { X } from "lucide-react";

import { useAuth } from "@/context/AuthContext";

export function LoginModal({
  open,
  onClose,
  onLoggedIn,
}: {
  open: boolean;
  onClose: () => void;
  onLoggedIn?: () => void;
}) {
  const { loginWithGoogleCredential } = useAuth();
  const hasGoogle = Boolean(process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="login-modal-title"
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
          id="login-modal-title"
          className="text-lg font-semibold text-neutral-100"
        >
          Вход в AI-Forge
        </h2>
        <p className="mt-2 text-sm text-neutral-400">
          Войдите через Google, чтобы сохранять проекты в облаке и управлять
          доступом (приватно / публично).
        </p>
        <div className="mt-6 flex flex-col items-center justify-center gap-3">
          {hasGoogle ? (
            <GoogleLogin
              onSuccess={async (cred) => {
                const c = cred.credential;
                if (!c) return;
                await loginWithGoogleCredential(c);
                onLoggedIn?.();
                onClose();
              }}
              onError={() => {
                /* noop */
              }}
              useOneTap={false}
            />
          ) : (
            <p className="text-center text-xs text-amber-200/90">
              Задайте{" "}
              <code className="text-neutral-300">NEXT_PUBLIC_GOOGLE_CLIENT_ID</code>{" "}
              и{" "}
              <code className="text-neutral-300">
                GOOGLE_CLIENT_ID / JWT_SECRET
              </code>{" "}
              на API.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
