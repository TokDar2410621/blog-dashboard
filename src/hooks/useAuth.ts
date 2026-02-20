import { useState, useCallback, useEffect } from "react";
import { getActiveSite, updateSiteTokens } from "@/lib/sites";
import { fetchCurrentUser } from "@/lib/api-client";

interface User {
  username: string;
  email: string;
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const isAuthenticated = !!getActiveSite()?.token;

  const checkAuth = useCallback(async () => {
    const site = getActiveSite();
    if (!site?.token) {
      setUser(null);
      setIsLoading(false);
      return;
    }
    try {
      const userData = await fetchCurrentUser();
      setUser(userData);
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const logout = useCallback(() => {
    const site = getActiveSite();
    if (site) {
      updateSiteTokens(site.id, "", "");
    }
    setUser(null);
  }, []);

  return { user, isAuthenticated, isLoading, logout, checkAuth };
}
