"use client";

import { Fragment } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useSite } from "@/hooks/useDashboard";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

type Crumb = { label: string; href?: string };

/**
 * PageBreadcrumb - "Tableau de bord > [siteName] > ...trail".
 *
 * Each item in `trail` is rendered after the site root crumb. The last item
 * becomes the current page (non-clickable). `siteName` comes from the
 * useSite() hook so we always show the right site label even on a deep link.
 */
export function PageBreadcrumb({ trail }: { trail: Crumb[] }) {
  const params = useParams<{ siteId: string }>();
  const siteId = params?.siteId;
  const { data: site } = useSite();
  const siteName = site?.name || site?.domain || "Site";
  const base = `/dashboard/${siteId}`;

  return (
    <Breadcrumb className="mb-4">
      <BreadcrumbList>
        <BreadcrumbItem>
          <BreadcrumbLink asChild>
            <Link href="/dashboard/overview">Tableau de bord</Link>
          </BreadcrumbLink>
        </BreadcrumbItem>
        <BreadcrumbSeparator />
        <BreadcrumbItem>
          <BreadcrumbLink asChild>
            <Link
              href={base}
              className="inline-block max-w-[40vw] truncate align-bottom sm:max-w-none"
            >
              {siteName}
            </Link>
          </BreadcrumbLink>
        </BreadcrumbItem>
        {trail.map((crumb, i) => {
          const isLast = i === trail.length - 1;
          return (
            <Fragment key={`${crumb.label}-${i}`}>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                {isLast || !crumb.href ? (
                  <BreadcrumbPage>{crumb.label}</BreadcrumbPage>
                ) : (
                  <BreadcrumbLink asChild>
                    <Link href={crumb.href}>{crumb.label}</Link>
                  </BreadcrumbLink>
                )}
              </BreadcrumbItem>
            </Fragment>
          );
        })}
      </BreadcrumbList>
    </Breadcrumb>
  );
}
