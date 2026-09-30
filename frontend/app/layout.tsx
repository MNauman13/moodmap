import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import "./globals.css";
import AuthProvider from "@/components/AuthProvider";

// Self-host the Latin font files so builds don't depend on Google Fonts being
// reachable, and so every page uses the same font definitions.
const lora = localFont({
  src: [
    { path: "./fonts/lora-latin.woff2", weight: "400 500", style: "normal" },
    { path: "./fonts/lora-latin-italic.woff2", weight: "400 500", style: "italic" },
  ],
  variable: "--font-lora",
  display: "swap",
});

const dmSans = localFont({
  src: "./fonts/dm-sans-latin.woff2",
  variable: "--font-dm-sans",
  weight: "300 500",
  display: "swap",
});

export const metadata: Metadata = {
  title: "MoodMap — Your emotional map",
  description:
    "A reflective journaling companion that maps your emotional landscape over time.",
  applicationName: "MoodMap",
  // Browser-tab icon. Next.js auto-generates the <link> tags from app/icon.svg.
  // The default favicon.ico was removed so the SVG mark wins on every browser.
};

export const viewport: Viewport = {
  themeColor: "#0e0d0b",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${lora.variable} ${dmSans.variable} h-full antialiased`}
    >
      <body
        className="min-h-full flex flex-col bg-[#0e0d0b] text-[#e8e4dc]"
        style={{ fontFamily: "var(--font-dm-sans), sans-serif" }}
      >
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
