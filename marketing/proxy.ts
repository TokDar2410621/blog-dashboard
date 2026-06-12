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
 * This proxy restores the old behavior for everything EXCEPT the
 * paths proxied to Django, which must keep their trailing slashes intact.
 */
const PROXIED_PREFIXES = ["/api/", "/admin/", "/accounts/"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (
    pathname.length > 1 &&
    pathname.endsWith("/") &&
    !PROXIED_PREFIXES.some((p) => pathname.startsWith(p))
  ) {
    // Clone keeps protocol/host/search; only the pathname changes.
    const url = request.nextUrl.clone();
    url.pathname = pathname.replace(/\/+$/, "");
    return NextResponse.redirect(url, 308);
  }

  return NextResponse.next();
}

export const config = {
  // Skip Next internals and static assets entirely.
  matcher: ["/((?!_next/|favicon|icons/|brand/).*)"],
};
