import { NextResponse, type NextRequest } from "next/server";

/**
 * Server-side route guard.
 *
 * Without this, route protection lived only in <AuthProvider/>, a client
 * component — anyone could request /dashboard and Next.js would serve the
 * HTML shell before any JS ran. Bots, JS-disabled clients, and link
 * previewers could see "protected" routes.
 *
 * The cookie check here verifies presence only; FastAPI still validates the
 * JWT on every API call, so a forged cookie buys nothing — it just lets the
 * page shell render before AuthProvider's runtime check redirects.
 */

const PROTECTED_PREFIXES = ["/dashboard", "/journal", "/nudges", "/reports", "/account"];
const AUTH_PREFIXES = ["/login", "/signup"];

// Supabase stores its session under `sb-<project-ref>-auth-token`
const SUPABASE_COOKIE_RE = /^sb-.+-auth-token(?:\.\d+)?$/;

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isProtected = PROTECTED_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`),
  );
  const isAuthPage = AUTH_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`),
  );

  if (!isProtected && !isAuthPage) {
    return NextResponse.next();
  }

  const hasSession = request.cookies
    .getAll()
    .some(({ name }) => SUPABASE_COOKIE_RE.test(name));

  if (isProtected && !hasSession) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (isAuthPage && hasSession) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

// Skip middleware for API routes, _next assets, favicon, and public files
export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
