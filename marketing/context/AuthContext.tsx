"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { clearTokens } from "@/lib/auth-storage";
import { ApiError, backendLogout, fetchCurrentUser } from "@/lib/api-client";
import type { User } from "@/lib/schemas";

type AuthContextValue = {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  logout: () => void;
  checkAuth: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    // Always probe /auth/me/. sessionStorage may be empty (tab suspended,
    // first visit, browser restored a stale tab) while the httpOnly
    // access_token (2h) / refresh_token (30d) cookies are still valid.
    // authFetch sends credentials and silently refreshes on 401, so the
    // session is restored on landing without bouncing the user.
    setIsLoading(true);
    try {
      const userData = await fetchCurrentUser();
      setUser(userData);
    } catch (err) {
      const expired =
        err instanceof ApiError && err.code === "SESSION_EXPIRED";
      if (expired) {
        clearTokens();
      } else {
        console.warn(
          "[Auth] Session check failed:",
          err instanceof Error ? err.message : err,
        );
      }
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void checkAuth();
  }, [checkAuth]);

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
    void backendLogout();
  }, []);

  const value = useMemo(
    () => ({
      user,
      isLoading,
      isAuthenticated: !!user,
      logout,
      checkAuth,
    }),
    [user, isLoading, logout, checkAuth],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
