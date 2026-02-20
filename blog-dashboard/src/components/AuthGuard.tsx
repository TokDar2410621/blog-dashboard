import { type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { getActiveSite } from "@/lib/sites";

export function AuthGuard({ children }: { children: ReactNode }) {
  const site = getActiveSite();

  if (!site?.token) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
