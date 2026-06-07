/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { clearTokens } from "@/lib/sites";
import { ApiError, backendLogout, fetchCurrentUser } from "@/lib/api-client";
import type { User } from "@/lib/schemas";

type AuthContextValue = {
  user: User | null;
  isLoading: boolean;
  /** True when `/auth/me/` succeeded and the user is set */
  isAuthenticated: boolean;
  logout: () => void;
  checkAuth: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    // Always probe /auth/me/. sessionStorage may be empty (tab suspended in
    // background, cross-tab restore, fresh page open) while the httpOnly
    // access_token cookie (2h) or refresh_token cookie (30d) is still valid.
    // authFetch will silently refresh on 401 using the cookie, so the
    // session is restored without bouncing the user to /login.
    setIsLoading(true);
    try {
      const userData = await fetchCurrentUser();
      setUser(userData);
    } catch (err) {
      // Real expiry: both access AND refresh cookies are gone/invalid.
      // Anything else (network, CORS) -> stay silent, don't wipe storage.
      const expired = err instanceof ApiError && err.code === "SESSION_EXPIRED";
      if (expired) {
        clearTokens();
      } else {
        console.warn(
          "[Auth] Session check failed:",
          err instanceof Error ? err.message : err
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
    // Clear local state immediately so the UI flips right away.
    clearTokens();
    setUser(null);
    // Fire-and-forget the backend cookie wipe. A failure here is non-blocking:
    // the local clearTokens() already broke the SPA's auth context, and the
    // server-side cookies will expire on their own anyway (2h access / 7d
    // refresh TTL).
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
    [user, isLoading, logout, checkAuth]
  );

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
