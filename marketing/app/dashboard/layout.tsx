import { AuthGuard } from "@/components/AuthGuard";

/**
 * Wraps every /dashboard/* route. Just enforces auth - the per-site layout
 * at /dashboard/[siteId]/layout.tsx adds the sidebar shell on top of this.
 */
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AuthGuard>{children}</AuthGuard>;
}
