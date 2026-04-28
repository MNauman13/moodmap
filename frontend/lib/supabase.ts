import { createClient, type SupportedStorage } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

/**
 * Cookie-backed storage so the Supabase session is sent to the server on every
 * request — Next.js middleware can then enforce route protection without JS
 * having to run on the client first.
 *
 * Default supabase-js storage is localStorage, which is browser-only and
 * invisible to middleware/Edge — that gap let unauthenticated users see the
 * page shell of /dashboard etc. before AuthProvider redirected them.
 */
const cookieStorage: SupportedStorage = {
  getItem(key: string): string | null {
    if (typeof document === "undefined") return null;
    const escaped = key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${escaped}=([^;]*)`));
    return match ? decodeURIComponent(match[1]) : null;
  },
  setItem(key: string, value: string): void {
    if (typeof document === "undefined") return;
    const secure = window.location.protocol === "https:" ? "; Secure" : "";
    // 7 days — Supabase refreshes its own access token internally
    document.cookie =
      `${key}=${encodeURIComponent(value)}; path=/; max-age=604800; SameSite=Lax${secure}`;
  },
  removeItem(key: string): void {
    if (typeof document === "undefined") return;
    document.cookie = `${key}=; path=/; max-age=0; SameSite=Lax`;
  },
};

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    storage: cookieStorage,
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});
