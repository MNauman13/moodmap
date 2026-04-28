import type { NextConfig } from "next";

/**
 * BACKEND_URL is the host:port FastAPI listens on.
 *   - dev:  http://127.0.0.1:8000
 *   - prod: set in the deploy environment (e.g. http://api:8000 inside docker compose)
 *
 * Specific route handlers under app/api/v1/* take priority over the rewrite,
 * so the existing journal/insights handlers keep working untouched. Every
 * other /api/v1/* path (nudges, dashboard, reports, …) is proxied straight
 * to FastAPI — that closes the gap where /api/v1/nudges had no handler and
 * was 404-ing silently.
 */
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  compress: true,
  reactStrictMode: true,

  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${BACKEND_URL}/api/v1/:path*`,
      },
    ];
  },

  async headers() {
    return [
      // ── Security headers (all routes) ────────────────────────
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-XSS-Protection", value: "1; mode=block" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
      // ── Long-lived cache for content-hashed static assets ────
      // Next.js appends a hash to every /_next/static/* filename,
      // so max-age=1y + immutable is safe: stale files are never served.
      {
        source: "/_next/static/:path*",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=31536000, immutable",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
