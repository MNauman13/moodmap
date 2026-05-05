'use client'

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useState } from "react"
import { supabase } from "@/lib/supabase"
import Logo from "./Logo"

const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/journal",   label: "Journal" },
  { href: "/nudges",    label: "Insights" },
  { href: "/account",   label: "Account" },
]

export default function Navbar() {
  const pathname = usePathname()
  const [menuOpen, setMenuOpen] = useState(false)

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

        {/* Desktop nav */}
        <ul className="hidden items-center gap-1 md:flex">
          {NAV_LINKS.map(({ href, label }) => {
            const active = pathname === href || pathname.startsWith(`${href}/`)
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

        {/* Desktop sign out */}
        <button
          type="button"
          onClick={handleSignOut}
          className="hidden md:block text-[12px] tracking-wide text-[#6b6357] transition-colors duration-150 hover:text-[#c8a96e]"
        >
          Sign out
        </button>

        {/* Mobile hamburger */}
        <button
          type="button"
          onClick={() => setMenuOpen(o => !o)}
          className="md:hidden flex flex-col justify-center items-center gap-[5px] w-8 h-8 shrink-0"
          aria-label="Toggle menu"
          aria-expanded={menuOpen}
        >
          <span className={`block h-px w-5 bg-[#6b6357] transition-all duration-200 origin-center ${menuOpen ? "rotate-45 translate-y-[6px]" : ""}`} />
          <span className={`block h-px w-5 bg-[#6b6357] transition-all duration-200 ${menuOpen ? "opacity-0" : ""}`} />
          <span className={`block h-px w-5 bg-[#6b6357] transition-all duration-200 origin-center ${menuOpen ? "-rotate-45 -translate-y-[6px]" : ""}`} />
        </button>
      </div>

      {/* Mobile dropdown */}
      {menuOpen && (
        <div className="md:hidden border-t border-[#1a1815] bg-[#0e0d0b] px-5 py-3">
          <ul className="flex flex-col gap-1">
            {NAV_LINKS.map(({ href, label }) => {
              const active = pathname === href || pathname.startsWith(`${href}/`)
              return (
                <li key={href}>
                  <Link
                    href={href}
                    onClick={() => setMenuOpen(false)}
                    className={`block rounded-lg px-3.5 py-2.5 text-[13px] tracking-wide no-underline transition-colors duration-150 ${
                      active
                        ? "bg-[#1e1c18] text-[#c8a96e]"
                        : "text-[#8a8070]"
                    }`}
                  >
                    {label}
                  </Link>
                </li>
              )
            })}
            <li>
              <button
                type="button"
                onClick={handleSignOut}
                className="w-full text-left rounded-lg px-3.5 py-2.5 text-[13px] tracking-wide text-[#6b6357] transition-colors duration-150 hover:text-[#c8a96e]"
              >
                Sign out
              </button>
            </li>
          </ul>
        </div>
      )}
    </nav>
  )
}
