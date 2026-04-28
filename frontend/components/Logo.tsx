'use client'

import Link from "next/link"

/**
 * MoodMap brand mark.
 *
 * Visual: a continuous gold curve that traces an "M" silhouette through two
 * soft peaks — reads as both the letter M and a mood wave / topographic
 * line. Same path shape as app/icon.svg so the favicon and the in-app
 * logo are visually identical.
 *
 * `withWordmark` toggles the "Mood<em>Map</em>" text next to the mark
 * (italic gold "Map", echoing the website's "Your <em>emotional</em> map"
 * treatment).
 */

interface LogoProps {
  size?: "sm" | "md" | "lg"
  withWordmark?: boolean
  href?: string
  className?: string
}

const SIZES = {
  sm: { mark: 22, wordmark: 15 },
  md: { mark: 28, wordmark: 18 },
  lg: { mark: 38, wordmark: 24 },
}

export default function Logo({
  size = "md",
  withWordmark = true,
  href,
  className = "",
}: LogoProps) {
  const dims = SIZES[size]

  const content = (
    <span
      className={`inline-flex items-center gap-2.5 leading-none ${className}`}
      aria-label="MoodMap"
    >
      {/* Mark: viewBox 32x32 matches the favicon. stroke uses currentColor
          so the parent can recolor it (default gold). */}
      <svg
        width={dims.mark}
        height={dims.mark}
        viewBox="0 0 32 32"
        fill="none"
        aria-hidden="true"
        className="shrink-0 text-[#c8a96e]"
      >
        <path
          d="M 5 22 Q 10 5, 14 16 T 22 16 T 27 22"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>

      {withWordmark && (
        <span
          style={{
            fontFamily: "var(--font-lora), 'Lora', Georgia, serif",
            fontSize: dims.wordmark,
            letterSpacing: "0.005em",
          }}
          className="text-[#e8e4dc] font-normal"
        >
          Mood<em className="italic text-[#c8a96e]">Map</em>
        </span>
      )}
    </span>
  )

  if (href) {
    return (
      <Link
        href={href}
        className="no-underline inline-block transition-opacity duration-200 hover:opacity-80"
      >
        {content}
      </Link>
    )
  }
  return content
}
