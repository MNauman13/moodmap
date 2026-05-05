'use client'

import { useEffect, useRef, useState } from 'react'
import { motion, useScroll, useTransform } from 'framer-motion'
import Link from 'next/link'
import { useAuth } from '@/components/AuthProvider'
import { supabase } from '@/lib/supabase'
import Logo from '@/components/Logo'

// ── Count-up hook ──────────────────────────────────────────────
function useCountUp(end: number, duration = 2200, active = false): number {
  const [val, setVal] = useState(0)
  useEffect(() => {
    if (!active) return
    const t0 = performance.now()
    let raf: number
    const tick = (now: number) => {
      const p = Math.min((now - t0) / duration, 1)
      const eased = 1 - Math.pow(1 - p, 3)
      setVal(Math.round(eased * end))
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [end, duration, active])
  return val
}

// ── Intersection trigger ───────────────────────────────────────
function useInViewOnce(threshold = 0.3) {
  const ref = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setVisible(true); obs.disconnect() } },
      { threshold }
    )
    if (ref.current) obs.observe(ref.current)
    return () => obs.disconnect()
  }, [threshold])
  return { ref, visible }
}

// ── Animation variants ─────────────────────────────────────────
const fadeUp = {
  hidden: { opacity: 0, y: 32 },
  show:   { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] as [number, number, number, number] } },
}
const stagger = {
  hidden: {},
  show:   { transition: { staggerChildren: 0.12 } },
}

// ── Data ───────────────────────────────────────────────────────
const STATS = [
  { value: 25,   suffix: '%', label: 'of people in England experience a mental health problem each year', source: 'Mind UK / NHS' },
  { value: 74,   suffix: '%', label: 'felt so stressed last year they felt overwhelmed or unable to cope', source: 'Mental Health Foundation, 2023' },
  { value: 118,  suffix: 'bn', prefix: '£', label: 'lost annually to the UK economy due to mental ill-health', source: 'Mental Health Foundation, 2022' },
  { value: 1,    suffix: ' in 3', label: 'people with mental health problems actually receive the treatment they need', source: 'Mental Health Foundation' },
]

const FEATURES = [
  {
    icon: '🎙',
    title: 'Voice + Text Journaling',
    desc: 'Capture your thoughts however feels right — type freely or speak your mind. Audio is understood alongside your words.',
  },
  {
    icon: '🧠',
    title: '9-Emotion Recognition',
    desc: 'Our emotion AI detects joy, love, optimism, sadness, anger, fear, disgust, surprise, and neutrality — not just "good" or "bad".',
  },
  {
    icon: '📊',
    title: 'Mood Trends & Heatmaps',
    desc: "An 8-week calendar and 30-day trend chart reveal patterns you'd never spot day-to-day.",
  },
  {
    icon: '💌',
    title: 'Personalised Nudges',
    desc: 'When your mood dips, MoodMap sends personalised suggestions — breathing exercises, reflective prompts, or social activities — based on what has helped you before.',
  },
  {
    icon: '🚨',
    title: 'Crisis Support',
    desc: 'If your entries show signs of distress, an immediate support message is sent with UK helplines — no waiting until the next check.',
  },
  {
    icon: '🔒',
    title: 'Privacy First',
    desc: 'Audio goes directly to encrypted storage. Your entries are never used for training. Only you hold the key to your story.',
  },
]

const STEPS = [
  { n: '01', title: 'Write or speak', desc: 'Open the journal and capture whatever is on your mind — text, audio, or both. No judgment, no structure required.' },
  { n: '02', title: 'AI analyses your emotions', desc: 'MoodMap listens to both your words and the tone of your voice to build a picture of how you are really feeling.' },
  { n: '03', title: 'Understand and grow', desc: 'Your dashboard updates with trends, patterns, and personalised nudges that adapt to your history over time.' },
]

const MARQUEE_ITEMS = [
  'Voice journaling', 'Emotion tracking', 'Mood heatmap', 'Crisis support',
  'Personalised nudges', 'Trend charts', 'Daily check-ins', 'Secure storage',
  'UK helplines', 'Smart insights', 'Voice + text', 'Privacy first',
]

// ── Sub-components ─────────────────────────────────────────────

function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const { session } = useAuth()

  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 24)
    window.addEventListener('scroll', fn, { passive: true })
    return () => window.removeEventListener('scroll', fn)
  }, [])

  const handleSignOut = async () => {
    await supabase.auth.signOut()
    window.location.href = '/login'
  }

  const userInitial = session?.user?.email?.[0]?.toUpperCase() ?? '?'

  return (
    <nav
      className="fixed top-0 left-0 right-0 z-50 transition-all duration-300"
      style={{
        background: scrolled ? 'rgba(14,13,11,0.85)' : 'transparent',
        backdropFilter: scrolled ? 'blur(12px)' : 'none',
        borderBottom: scrolled ? '1px solid rgba(255,255,255,0.05)' : 'none',
      }}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Logo size="md" href="/" />

        <div className="flex items-center gap-3">
          {session ? (
            <>
              {/* User avatar + email */}
              <div className="flex items-center gap-2.5">
                <div className="h-7 w-7 rounded-full bg-[#1e1c18] border border-[#2a2720] flex items-center justify-center text-[11px] font-medium text-[#c8a96e]">
                  {userInitial}
                </div>
                <span className="hidden text-[12px] font-light text-[#6b6357] sm:block max-w-[160px] truncate">
                  {session.user.email}
                </span>
              </div>
              <button
                onClick={handleSignOut}
                className="rounded-full px-4 py-2 text-[12px] font-light text-[#6b6357] transition-colors hover:text-[#c8a96e]"
              >
                Sign out
              </button>
              <Link
                href="/dashboard"
                className="rounded-full bg-[#c8a96e] px-5 py-2 text-[13px] font-medium text-[#0e0d0b] transition-all hover:bg-[#d4b87a]"
              >
                Dashboard →
              </Link>
            </>
          ) : (
            <>
              <Link
                href="/login"
                className="rounded-full px-5 py-2 text-[13px] font-light text-[#c8bfb0] transition-colors hover:text-[#e8e4dc]"
              >
                Sign in
              </Link>
              <Link
                href="/signup"
                className="rounded-full bg-[#c8a96e] px-5 py-2 text-[13px] font-medium text-[#0e0d0b] transition-all hover:bg-[#d4b87a]"
              >
                Get started
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  )
}

function BackgroundOrbs() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      <div
        className="absolute rounded-full opacity-20 blur-[120px]"
        style={{
          width: 600, height: 600,
          top: '-10%', left: '-5%',
          background: 'radial-gradient(circle, #c8a96e 0%, transparent 70%)',
          animation: 'orb1 18s ease-in-out infinite',
        }}
      />
      <div
        className="absolute rounded-full opacity-15 blur-[100px]"
        style={{
          width: 500, height: 500,
          top: '20%', right: '-5%',
          background: 'radial-gradient(circle, #5c7a9e 0%, transparent 70%)',
          animation: 'orb2 22s ease-in-out infinite',
        }}
      />
      <div
        className="absolute rounded-full opacity-10 blur-[140px]"
        style={{
          width: 400, height: 400,
          bottom: '10%', left: '30%',
          background: 'radial-gradient(circle, #9e8a5c 0%, transparent 70%)',
          animation: 'orb3 26s ease-in-out infinite',
        }}
      />
      {/* Subtle grain overlay */}
      <div
        className="absolute inset-0 opacity-[0.025]"
        style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 256 256\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'noise\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.9\' numOctaves=\'4\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23noise)\' opacity=\'1\'/%3E%3C/svg%3E")', backgroundSize: '128px' }}
      />
    </div>
  )
}

function StatCard({ value, suffix, prefix = '', label, source, active }: {
  value: number; suffix: string; prefix?: string; label: string; source: string; active: boolean
}) {
  const count = useCountUp(value, 2000, active)
  return (
    <motion.div
      variants={fadeUp}
      className="group relative overflow-hidden rounded-2xl border border-[#252220] bg-[#0c0b09] p-7 transition-all duration-300 hover:border-[#c8a96e]/30"
    >
      <div className="absolute inset-0 opacity-0 transition-opacity duration-500 group-hover:opacity-100"
        style={{ background: 'radial-gradient(ellipse at 50% 0%, rgba(200,169,110,0.06) 0%, transparent 70%)' }} />
      <p className="font-['Lora'] text-[40px] font-medium leading-none text-[#c8a96e] tabular-nums">
        {prefix}{count}{suffix}
      </p>
      <p className="mt-3 text-[14px] font-light leading-relaxed text-[#8a8070]">{label}</p>
      <p className="mt-3 text-[10px] uppercase tracking-wider text-[#3a3428]">{source}</p>
    </motion.div>
  )
}

function FeatureCard({ icon, title, desc }: { icon: string; title: string; desc: string }) {
  const ref = useRef<HTMLDivElement>(null)

  const handleMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = ref.current
    if (!el) return
    const { left, top, width, height } = el.getBoundingClientRect()
    const x = (e.clientX - left - width / 2) / (width / 2)
    const y = (e.clientY - top - height / 2) / (height / 2)
    el.style.transform = `perspective(600px) rotateY(${x * 4}deg) rotateX(${-y * 4}deg) translateZ(4px)`
  }
  const handleLeave = () => {
    if (ref.current) ref.current.style.transform = 'perspective(600px) rotateY(0) rotateX(0) translateZ(0)'
  }

  return (
    <motion.div
      ref={ref}
      variants={fadeUp}
      onMouseMove={handleMove}
      onMouseLeave={handleLeave}
      className="group cursor-default rounded-2xl border border-[#252220] bg-[#0c0b09] p-7 transition-all duration-200"
      style={{ transformStyle: 'preserve-3d', willChange: 'transform' }}
    >
      <div className="mb-5 flex h-11 w-11 items-center justify-center rounded-xl border border-[#2a2720] bg-[#141210] text-[22px] transition-all duration-300 group-hover:border-[#c8a96e]/40">
        {icon}
      </div>
      <h3 className="font-['Lora'] text-[17px] font-medium text-[#c8bfb0] mb-2">{title}</h3>
      <p className="text-[13px] font-light leading-relaxed text-[#6b6357]">{desc}</p>
    </motion.div>
  )
}

function MockDashboard() {
  // SVG path for a sample mood trend line
  const points = [
    [0, 60], [40, 50], [80, 55], [120, 30], [160, 20], [200, 35], [240, 15], [280, 25], [320, 10],
  ]
  const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`).join(' ')

  // Sample heatmap squares
  const heatData = Array.from({ length: 56 }, (_, i) => {
    const vals = [null, null, 0.3, -0.2, 0.6, null, 0.1, -0.4, 0.5, 0.2, null, null, -0.3, 0.7, 0.4, null, 0.2, -0.1, 0.8, null, null, 0.3, -0.5, null, 0.6, 0.1, null, -0.2, 0.4, 0.3, null, null, 0.5, 0.2, -0.3, null, 0.7, 0.4, null, null, -0.1, 0.6, 0.3, null, 0.5, null, -0.2, 0.4, null, null, 0.3, 0.7, -0.1, 0.5, 0.2, null]
    return vals[i % vals.length]
  })

  const heatColor = (v: number | null) => {
    if (v === null) return '#1a1815'
    if (v > 0.4) return '#4a7a3a'
    if (v > 0.1) return '#c8a96e'
    if (v > -0.1) return '#3a3428'
    if (v > -0.4) return '#7a4a30'
    return '#8a2a2a'
  }

  const entries = [
    { text: 'Today was genuinely good. I noticed something shift…', ago: '2h ago', score: '+0.61', color: '#c8a96e' },
    { text: 'Still finding mornings hard, but I pushed through…', ago: '1d ago', score: '-0.18', color: '#8a8070' },
    { text: 'Called Mum for the first time in weeks. It helped.', ago: '2d ago', score: '+0.45', color: '#9e8a5c' },
  ]

  return (
    <div
      className="relative mx-auto w-full max-w-2xl rounded-2xl border border-[#1a1815] bg-[#0c0b09] p-6 shadow-[0_40px_120px_rgba(0,0,0,0.8)]"
      style={{ transform: 'perspective(1200px) rotateX(4deg) rotateY(-3deg)' }}
    >
      {/* Fake title bar */}
      <div className="mb-5 flex items-center gap-1.5">
        <div className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
        <div className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
        <div className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
        <span className="ml-3 text-[11px] text-[#3a3428] font-light">dashboard — moodmap</span>
      </div>

      {/* Stat strip */}
      <div className="mb-5 grid grid-cols-4 gap-2">
        {[
          { label: 'Right now', val: 'Positive', color: '#c8a96e' },
          { label: '30-day avg', val: 'Neutral', color: '#8a8070' },
          { label: 'Streak', val: '5 days', color: '#e8e4dc' },
          { label: 'Most felt', val: 'Joy', color: '#c8a96e' },
        ].map((s) => (
          <div key={s.label} className="rounded-lg bg-[#0e0d0b] px-3 py-3 border border-[#141210]">
            <p className="text-[9px] uppercase tracking-wider text-[#3a3428] mb-1">{s.label}</p>
            <p className="font-['Lora'] text-[14px]" style={{ color: s.color }}>{s.val}</p>
          </div>
        ))}
      </div>

      {/* Mood trend chart */}
      <div className="mb-5 rounded-xl border border-[#141210] bg-[#0e0d0b] p-4">
        <p className="text-[10px] uppercase tracking-wider text-[#3a3428] mb-3">30-day mood trend</p>
        <svg viewBox="0 0 320 80" className="w-full overflow-visible" preserveAspectRatio="none">
          <defs>
            <linearGradient id="line-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#c8a96e" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#c8a96e" stopOpacity="0" />
            </linearGradient>
          </defs>
          {/* Fill */}
          <path d={`${pathD} L 320 80 L 0 80 Z`} fill="url(#line-grad)" />
          {/* Line */}
          <path d={pathD} fill="none" stroke="#c8a96e" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          {/* Dots */}
          {points.map(([x, y], i) => (
            <circle key={i} cx={x} cy={y} r="2.5" fill="#c8a96e" />
          ))}
        </svg>
      </div>

      {/* Heatmap */}
      <div className="mb-5 rounded-xl border border-[#141210] bg-[#0e0d0b] p-4">
        <p className="text-[10px] uppercase tracking-wider text-[#3a3428] mb-3">8-week pattern</p>
        <div className="flex gap-0.5">
          {Array.from({ length: 8 }, (_, week) => (
            <div key={week} className="flex flex-col gap-0.5 flex-1">
              {Array.from({ length: 7 }, (_, day) => {
                const v = heatData[week * 7 + day]
                return (
                  <div key={day} className="w-full aspect-square rounded-[2px]" style={{ background: heatColor(v) }} />
                )
              })}
            </div>
          ))}
        </div>
      </div>

      {/* Recent entries */}
      <div>
        <p className="text-[10px] uppercase tracking-wider text-[#3a3428] mb-3">Recent entries</p>
        {entries.map((e, i) => (
          <div key={i} className="flex items-center justify-between py-2.5 border-b border-[#141210] last:border-0">
            <div>
              <p className="font-['Lora'] text-[12px] text-[#8a8070] truncate max-w-[260px]">{e.text}</p>
              <p className="text-[10px] text-[#3a3428] mt-0.5">{e.ago}</p>
            </div>
            <span className="text-[11px] font-medium" style={{ color: e.color }}>{e.score}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────

export default function LandingPage() {
  const { session } = useAuth()
  const { ref: statsRef, visible: statsVisible } = useInViewOnce(0.2)
  const heroRef = useRef<HTMLElement>(null)
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ['start start', 'end start'] })
  const heroY = useTransform(scrollYProgress, [0, 1], ['0%', '25%'])
  const heroOpacity = useTransform(scrollYProgress, [0, 0.7], [1, 0])

  return (
    <div className="min-h-screen bg-[#0e0d0b] text-[#e8e4dc]" style={{ fontFamily: "var(--font-dm-sans), sans-serif" }}>
      <style>{`
        @keyframes orb1 { 0%,100% { transform: translate(0,0) scale(1); } 33% { transform: translate(60px,-40px) scale(1.08); } 66% { transform: translate(-30px,50px) scale(0.94); } }
        @keyframes orb2 { 0%,100% { transform: translate(0,0) scale(1); } 33% { transform: translate(-50px,30px) scale(0.92); } 66% { transform: translate(40px,-60px) scale(1.06); } }
        @keyframes orb3 { 0%,100% { transform: translate(0,0) scale(1); } 50% { transform: translate(30px,-30px) scale(1.04); } }
        @keyframes marquee { from { transform: translateX(0); } to { transform: translateX(-50%); } }
        .marquee-track { animation: marquee 28s linear infinite; }
      `}</style>

      <Navbar />

      {/* ── Hero ──────────────────────────────────────────────── */}
      <section ref={heroRef} className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden text-center">
        <BackgroundOrbs />

        <motion.div
          className="relative z-10 max-w-3xl px-6"
          style={{ y: heroY, opacity: heroOpacity }}
        >
          {/* Badge */}
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="mb-8 inline-flex items-center gap-2 rounded-full border border-[#c8a96e]/30 bg-[#c8a96e]/10 px-4 py-1.5"
          >
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#c8a96e] opacity-75" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[#c8a96e]" />
            </span>
            <span className="text-[12px] font-medium uppercase tracking-[0.1em] text-[#c8a96e]">
              Mental wellness, reimagined
            </span>
          </motion.div>

          {/* Headline */}
          <motion.h1
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="font-['Lora'] text-[clamp(42px,7vw,80px)] font-normal leading-[1.1] tracking-tight text-[#f0ece2]"
          >
            Your emotions,{' '}
            <em
              className="not-italic"
              style={{
                background: 'linear-gradient(135deg, #c8a96e 0%, #e8d4a0 50%, #c8a96e 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundSize: '200% auto',
                animation: 'gradient-shift 4s linear infinite',
              }}
            >
              mapped.
            </em>
          </motion.h1>

          <style>{`@keyframes gradient-shift { 0% { background-position: 0% center; } 100% { background-position: 200% center; } }`}</style>

          {/* Subtitle */}
          <motion.p
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="mx-auto mt-6 max-w-xl text-[18px] font-light leading-relaxed text-[#8a8070]"
          >
            AI-powered mood journaling that understands you — through text, voice, and emotional patterns you didn&apos;t know existed.
          </motion.p>

          {/* CTA */}
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.35 }}
            className="mt-10 flex flex-wrap items-center justify-center gap-4"
          >
            {session ? (
              <Link
                href="/dashboard"
                className="inline-flex items-center gap-2 rounded-full bg-[#c8a96e] px-8 py-3.5 text-[15px] font-medium text-[#0e0d0b] transition-all duration-200 hover:bg-[#d4b87a] hover:shadow-[0_0_30px_rgba(200,169,110,0.3)]"
              >
                Go to your dashboard →
              </Link>
            ) : (
              <>
                <Link
                  href="/signup"
                  className="inline-flex items-center gap-2 rounded-full bg-[#c8a96e] px-8 py-3.5 text-[15px] font-medium text-[#0e0d0b] transition-all duration-200 hover:bg-[#d4b87a] hover:shadow-[0_0_30px_rgba(200,169,110,0.3)]"
                >
                  Start journaling — it&apos;s free
                </Link>
                <Link
                  href="/login"
                  className="inline-flex items-center gap-2 rounded-full border border-[#2a2720] px-8 py-3.5 text-[15px] font-light text-[#c8bfb0] transition-all duration-200 hover:border-[#c8a96e]/50 hover:text-[#e8e4dc]"
                >
                  Sign in
                </Link>
              </>
            )}
          </motion.div>

          {/* Disclaimer */}
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.5 }}
            className="mt-6 text-[11px] text-[#6b6357]"
          >
            Not a substitute for professional mental health care. If you are in crisis, call 116 123.
          </motion.p>
        </motion.div>

      </section>

      {/* ── Marquee ───────────────────────────────────────────── */}
      <div className="overflow-hidden border-y border-[#1a1815] py-4">
        <div className="marquee-track flex gap-6 whitespace-nowrap">
          {[...MARQUEE_ITEMS, ...MARQUEE_ITEMS].map((item, i) => (
            <span key={i} className="flex items-center gap-6">
              <span className="text-[12px] font-light uppercase tracking-[0.12em] text-[#4a4438]">{item}</span>
              <span className="text-[#2a2720]">◆</span>
            </span>
          ))}
        </div>
      </div>

      {/* ── Stats ─────────────────────────────────────────────── */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <motion.div
          variants={fadeUp}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.3 }}
          className="mb-4"
        >
          <span className="text-[11px] uppercase tracking-[0.14em] text-[#6b6357]">The reality</span>
        </motion.div>
        <motion.h2
          variants={fadeUp}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.3 }}
          className="font-['Lora'] text-[clamp(28px,4vw,44px)] font-normal text-[#f0ece2] mb-12 max-w-2xl"
        >
          Mental health affects everyone.<br />
          <em className="text-[#c8a96e]">Most people suffer in silence.</em>
        </motion.h2>

        <motion.div
          ref={statsRef}
          variants={stagger}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.2 }}
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
        >
          {STATS.map((s) => (
            <StatCard key={s.label} {...s} active={statsVisible} />
          ))}
        </motion.div>
      </section>

      {/* ── How it works ──────────────────────────────────────── */}
      <section className="border-t border-[#1a1815] bg-[#0c0b09] py-20">
        <div className="mx-auto max-w-6xl px-6">
          <motion.div
            variants={fadeUp}
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, amount: 0.3 }}
          >
            <span className="text-[11px] uppercase tracking-[0.14em] text-[#6b6357]">How it works</span>
            <h2 className="font-['Lora'] mt-3 text-[clamp(28px,4vw,44px)] font-normal text-[#f0ece2] mb-12">
              Three steps to clarity.
            </h2>
          </motion.div>

          <div className="grid gap-12 md:grid-cols-3">
            {STEPS.map((step, i) => (
              <motion.div
                key={step.n}
                variants={fadeUp}
                initial="hidden"
                whileInView="show"
                viewport={{ once: true, amount: 0.3 }}
                transition={{ delay: i * 0.15 }}
                className="relative"
              >
                <span className="font-['Lora'] text-[48px] font-normal leading-none select-none" style={{ color: 'rgba(200,169,110,0.25)' }}>
                  {step.n}
                </span>
                <h3 className="font-['Lora'] text-[20px] font-medium text-[#c8bfb0] mt-4 mb-3">{step.title}</h3>
                <p className="text-[14px] font-light leading-relaxed text-[#6b6357]">{step.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ──────────────────────────────────────────── */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <motion.div
          variants={fadeUp}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.3 }}
          className="mb-12"
        >
          <span className="text-[11px] uppercase tracking-[0.14em] text-[#6b6357]">Features</span>
          <h2 className="font-['Lora'] mt-3 text-[clamp(28px,4vw,44px)] font-normal text-[#f0ece2] max-w-xl">
            Everything your emotional life deserves.
          </h2>
        </motion.div>

        <motion.div
          variants={stagger}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.1 }}
          className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
        >
          {FEATURES.map((f) => <FeatureCard key={f.title} {...f} />)}
        </motion.div>
      </section>

      {/* ── App Preview ───────────────────────────────────────── */}
      <section className="border-t border-[#1a1815] bg-[#0c0b09] py-20 overflow-hidden">
        <div className="mx-auto max-w-6xl px-6">
          <motion.div
            variants={fadeUp}
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, amount: 0.3 }}
            className="mb-12 text-center"
          >
            <span className="text-[11px] uppercase tracking-[0.14em] text-[#6b6357]">See it in action</span>
            <h2 className="font-['Lora'] mt-3 text-[clamp(28px,4vw,44px)] font-normal text-[#f0ece2]">
              Your emotional landscape, visualised.
            </h2>
            <p className="mt-4 text-[15px] font-light text-[#6b6357] max-w-lg mx-auto">
              Every entry adds a point to your story. Watch patterns emerge over days, weeks, and months.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 48 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.2 }}
            transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
          >
            <MockDashboard />
          </motion.div>
        </div>
      </section>

      {/* ── Privacy ───────────────────────────────────────────── */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <motion.div
          variants={stagger}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.3 }}
          className="grid gap-12 md:grid-cols-2 items-center"
        >
          <div>
            <motion.div variants={fadeUp}>
              <span className="text-[11px] uppercase tracking-[0.14em] text-[#6b6357]">Privacy</span>
              <h2 className="font-['Lora'] mt-3 text-[clamp(28px,4vw,40px)] font-normal text-[#f0ece2] mb-6">
                Your story.<br />
                <em className="text-[#c8a96e]">Only yours.</em>
              </h2>
              <p className="text-[15px] font-light leading-relaxed text-[#6b6357]">
                We built MoodMap on the belief that mental health data is the most sensitive data that exists.
                Everything is designed with that in mind.
              </p>
            </motion.div>
          </div>

          <motion.div variants={stagger} className="space-y-4">
            {[
              { icon: '🔐', title: 'Encrypted at rest and in transit', desc: 'Audio files go directly to encrypted R2 storage. Your entries never pass through third-party servers unprotected.' },
              { icon: '🚫', title: 'Never used for training', desc: 'Your journal entries are never fed into AI training datasets. We use your data to serve you, not to build models.' },
              { icon: '🗑', title: 'Full data deletion', desc: 'Delete any entry or your entire account at any time. No backups. No questions.' },
            ].map((p) => (
              <motion.div
                key={p.title}
                variants={fadeUp}
                className="flex gap-4 rounded-xl border border-[#252220] bg-[#0c0b09] p-5"
              >
                <span className="text-[22px] shrink-0">{p.icon}</span>
                <div>
                  <p className="font-medium text-[14px] text-[#c8bfb0] mb-1">{p.title}</p>
                  <p className="text-[13px] font-light text-[#6b6357] leading-relaxed">{p.desc}</p>
                </div>
              </motion.div>
            ))}
          </motion.div>
        </motion.div>
      </section>

      {/* ── Final CTA ─────────────────────────────────────────── */}
      <section className="relative overflow-hidden border-t border-[#1a1815] py-20 text-center">
        <div className="pointer-events-none absolute inset-0">
          <div
            className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full opacity-20 blur-[100px]"
            style={{ width: 600, height: 300, background: 'radial-gradient(ellipse, #c8a96e 0%, transparent 70%)' }}
          />
        </div>

        <motion.div
          variants={fadeUp}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.4 }}
          className="relative z-10 mx-auto max-w-xl px-6"
        >
          <h2 className="font-['Lora'] text-[clamp(32px,5vw,52px)] font-normal leading-tight text-[#f0ece2] mb-6">
            Ready to understand yourself better?
          </h2>
          <p className="text-[16px] font-light text-[#6b6357] mb-10">
            Start with a single entry. No commitment, no subscription, no pressure.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-4">
            {session ? (
              <Link
                href="/dashboard"
                className="inline-flex items-center gap-2 rounded-full bg-[#c8a96e] px-10 py-4 text-[16px] font-medium text-[#0e0d0b] transition-all duration-200 hover:bg-[#d4b87a] hover:shadow-[0_0_40px_rgba(200,169,110,0.35)]"
              >
                Open your dashboard →
              </Link>
            ) : (
              <>
                <Link
                  href="/signup"
                  className="inline-flex items-center gap-2 rounded-full bg-[#c8a96e] px-10 py-4 text-[16px] font-medium text-[#0e0d0b] transition-all duration-200 hover:bg-[#d4b87a] hover:shadow-[0_0_40px_rgba(200,169,110,0.35)]"
                >
                  Create free account
                </Link>
                <Link
                  href="/login"
                  className="text-[15px] font-light text-[#6b6357] hover:text-[#c8a96e] transition-colors"
                >
                  Already have an account →
                </Link>
              </>
            )}
          </div>

          <p className="mt-8 text-[11px] text-[#6b6357]">
            MoodMap is a wellness tool, not a medical device. Always speak to a qualified professional if you are concerned about your mental health.
          </p>
        </motion.div>
      </section>

      {/* ── Footer ────────────────────────────────────────────── */}
      <footer className="border-t border-[#1a1815] px-6 py-12">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-4 text-center sm:flex-row sm:justify-between sm:text-left">
          <Logo size="sm" href="/" />
          <p className="text-[12px] font-light text-[#6b6357]">
            Every entry is a step toward understanding yourself. You&apos;re doing better than you think. 🌱
          </p>
        </div>
      </footer>
    </div>
  )
}
