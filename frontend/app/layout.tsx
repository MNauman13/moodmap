import type { Metadata, Viewport } from "next";
import { Lora, DM_Sans } from "next/font/google";
import "./globals.css";
import AuthProvider from "@/components/AuthProvider";

// Loading the brand fonts here (rather than via runtime <style>@import</style>
// inside individual pages) eliminates the render-blocking network request
// and makes 'Lora' / 'DM Sans' available to the global Navbar + Logo.
const lora = Lora({
  variable: "--font-lora",
  subsets: ["latin"],
  weight: ["400", "500"],
  style: ["normal", "italic"],
  display: "swap",
});

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
  weight: ["300", "400", "500"],
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
