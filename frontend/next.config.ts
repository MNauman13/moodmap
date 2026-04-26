import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  compress: true,
  reactStrictMode: true,

  // React Compiler: stable in Next.js 16 — automatically memoises components
  // and eliminates unnecessary re-renders without manual useMemo/useCallback.
  //reactCompiler: true,

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
      // ── Medium-lived cache for public/ assets (images, icons) ─
      // {
      //   source: "/(:path(favicon.ico|.*\\.png|.*\\.jpg|.*\\.svg|.*\\.webp))",
      //   headers: [
      //     {
      //       key: "Cache-Control",
      //       value: "public, max-age=86400, stale-while-revalidate=604800",
      //     },
      //   ],
      // },
    ];
  },
};

export default nextConfig;
