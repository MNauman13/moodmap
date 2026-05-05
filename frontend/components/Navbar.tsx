'use client'

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { supabase } from "@/lib/supabase"
import Logo from "./Logo"

/**
 * Top navigation chrome for authenticated pages.
 *
 * Sticky, hairline-bottom-bordered, very thin — the design language stays
 * out of the user's way. Logo on the left, three primary destinations in
 * the middle, sign-out on the right.
 */

const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/journal",   label: "Journal" },
  { href: "/nudges",    label: "Insights" },
  { href: "/account",   label: "Account" },
]

export default function Navbar() {
  const pathname = usePathname()
  const router = useRouter()

  const handleSignOut = async () => {
    await supabase.auth.signOut()
    window.location.href = "/login"
  }

  return (
    <nav
      className="sticky top-0 z-40 w-full border-b border-[#1a1815] bg-[#0e0d0b]/85 backdrop-blur-md"
      style={{ fontFamily: "var(--font-dm-sans), 'DM Sans', system-ui, sans-serif" }}
    >
      <div className="mx-auto flex max-w-[1080px] items-center justify-between gap-6 px-5 py-3.5">
        <Logo size="sm" href="/dashboard" />

        <ul className="hidden items-center gap-1 md:flex">
          {NAV_LINKS.map(({ href, label }) => {
            const active =
              pathname === href || pathname.startsWith(`${href}/`)
            return (
              <li key={href}>
                <Link
                  href={href}
                  className={`rounded-full px-3.5 py-1.5 text-[13px] tracking-wide no-underline transition-colors duration-150 ${
                    active
                      ? "bg-[#1e1c18]/70 text-[#c8a96e]"
                      : "text-[#8a8070] hover:text-[#c8bfb0]"
                  }`}
                >
                  {label}
                </Link>
              </li>
            )
          })}
        </ul>

        <button
          type="button"
          onClick={handleSignOut}
          className="text-[12px] tracking-wide text-[#6b6357] transition-colors duration-150 hover:text-[#c8a96e]"
        >
          Sign out
        </button>
      </div>
    </nav>
  )
}
