import type { NextConfig } from "next";

/**
 * BACKEND_URL is the host:port FastAPI listens on.
 *   - dev:  http://127.0.0.1:8000  (fallback — intentional for local work)
 *   - prod: must be set in the deploy environment before `next build`
 *
 * The fallback to localhost is kept deliberately so the project works
 * out-of-the-box for local development without any env setup.
 * In production the env var MUST be set — the build will log a warning
 * if it is missing so the omission is visible in CI/deploy logs.
 */
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

if (!process.env.BACKEND_URL && process.env.NODE_ENV === "production") {
  console.warn(
    "[next.config] WARNING: BACKEND_URL is not set. " +
    "All /api/v1/* requests will proxy to http://127.0.0.1:8000, " +
    "which will fail in production. Set BACKEND_URL before deploying."
  );
}

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
          { key: "X-Content-Type-Options",  value: "nosniff" },
          { key: "X-Frame-Options",          value: "DENY" },
          { key: "X-XSS-Protection",         value: "1; mode=block" },
          { key: "Referrer-Policy",          value: "strict-origin-when-cross-origin" },

          // Enforce HTTPS for 1 year, including subdomains.
          // Only effective once the site is fully on HTTPS — safe to add now.
          {
            key: "Strict-Transport-Security",
            value: "max-age=31536000; includeSubDomains; preload",
          },

          // Content-Security-Policy
          // Allows: same-origin scripts/styles, Supabase API, Google Fonts,
          // self-hosted images + data URIs (chart canvases), WebSockets for
          // Supabase realtime. Tighten further once all CDN sources are known.
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              // Scripts: self + inline (React hydration) + Supabase
              "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://*.supabase.co",
              // Styles: self + inline (Tailwind runtime) + Google Fonts
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
              // Fonts: self + Google Fonts CDN
              "font-src 'self' https://fonts.gstatic.com",
              // Images: self + data URIs (chart exports) + blob (audio waveform)
              "img-src 'self' data: blob:",
              // Connections: self + Supabase API + realtime WebSocket
              "connect-src 'self' https://*.supabase.co wss://*.supabase.co https://*.r2.cloudflarestorage.com",
              // Media: self + blob (audio recording/playback)
              "media-src 'self' blob:",
              // Workers: blob (wavesurfer web worker)
              "worker-src blob:",
              // Frames: deny everything
              "frame-src 'none'",
              // Objects: deny Flash/plugins
              "object-src 'none'",
              "base-uri 'self'",
              "form-action 'self'",
            ].join("; "),
          },

          // Disable browser features the app doesn't use.
          {
            key: "Permissions-Policy",
            value: [
              "camera=()",
              "geolocation=()",
              "payment=()",
              "usb=()",
              "gyroscope=()",
              "accelerometer=()",
              // microphone is needed for voice journalling
              "microphone=(self)",
            ].join(", "),
          },
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
