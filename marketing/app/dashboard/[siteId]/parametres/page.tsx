import { redirect } from "next/navigation";

/**
 * /dashboard/[siteId]/parametres -> redirect to the General tab,
 * matching the SPA's index route behaviour.
 */
export default async function ParametresIndexPage({
  params,
}: {
  params: Promise<{ siteId: string }>;
}) {
  const { siteId } = await params;
  redirect(`/dashboard/${siteId}/parametres/general`);
}
