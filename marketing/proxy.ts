import { NextRequest, NextResponse } from "next/server";

/**
 * Trailing-slash normalization for PAGE routes only (Next 16 "proxy" file,
 * the renamed middleware convention).
 *
 * next.config.ts sets skipTrailingSlashRedirect: true because the
 * automatic 308 (slashed -> slashless) ran before the /api rewrite and
 * ping-ponged with Django's APPEND_SLASH 301 (slashless -> slashed),
 * producing ERR_TOO_MANY_REDIRECTS on every API call.
 *
 * This proxy restores the old behavior for everything EXCEPT the paths
 * proxied to Django, which must keep their trailing slashes intact.
 *
 * Gotcha: request.nextUrl.pathname strips the trailing slash and keeps it
 * as internal state, so detection MUST read the raw request.url instead.
 */
const PROXIED_PREFIXES = ["/api/", "/admin/", "/accounts/"];

export function proxy(request: NextRequest) {
  // Raw pathname, slash included - nextUrl.pathname would hide it.
  const rawPath = new URL(request.url).pathname;

  if (
    rawPath.length > 1 &&
    rawPath.endsWith("/") &&
    !PROXIED_PREFIXES.some((p) => rawPath.startsWith(p))
  ) {
    const target = new URL(request.url);
    target.pathname = rawPath.replace(/\/+$/, "");
    return NextResponse.redirect(target, 308);
  }

  return NextResponse.next();
}

export const config = {
  // Skip Next internals and static assets entirely.
  matcher: ["/((?!_next/|favicon|icons/|brand/).*)"],
};
