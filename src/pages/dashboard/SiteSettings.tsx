import { Navigate, useParams } from "react-router-dom";

/**
 * Legacy thin redirect.
 *
 * The settings page used to be a single fat Tabs component lived here. It has
 * been split into routed sub-pages under `/dashboard/:siteId/parametres/*`
 * (see `settings/SettingsLayout.tsx`). This file stays as a redirect so any
 * deep link or external bookmark hitting `/parametres` lands on `/general`.
 */
export default function SiteSettings() {
  const { siteId } = useParams<{ siteId: string }>();
  return (
    <Navigate
      to={`/dashboard/${siteId}/parametres/general`}
      replace
    />
  );
}
