"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import { supabase } from "@/lib/supabase";
import { dashboardApi, journalApi } from "@/lib/api";
import type { InsightsResponse, JournalEntryResponse, TrendDataPoint } from "@/lib/api";
import MoodTrendChart, { scoreToMeta } from "./components/MoodTrendChart";
import EmotionBreakdown from "./components/EmotionBreakdown";
import MoodHeatmap from "./components/MoodHeatmap";
import NudgesWidget from "@/components/NudgesWidget";
import Navbar from "@/components/Navbar";
import styles from "./dashboard.module.css";

// ── Helpers ────────────────────────────────────────────────────

function timeAgo(iso: string): string {
  const diff  = Date.now() - new Date(iso).getTime();
  const mins  = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days  = Math.floor(diff / 86400000);
  if (mins < 2)   return "just now";
  if (mins < 60)  return `${mins}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days === 1) return "yesterday";
  return `${days}d ago`;
}

function computeStreak(dates: string[]): number {
  const set   = new Set(dates);
  const today = new Date();
  let streak  = 0;
  for (let i = 0; i < 90; i++) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    if (set.has(d.toISOString().slice(0, 10))) streak++;
    else if (i > 0) break;
  }
  return streak;
}

/**
 * analysis.py sets entry.status = "COMPLETED" (uppercase string),
 * but the AnalysisStatus enum expects "completed" (lowercase).
 * Handle both defensively until that bug is fixed in analysis.py.
 */
function isDone(status: string): boolean {
  return status === "completed" || status === "COMPLETED";
}
function isFailed(status: string): boolean {
  return status === "failed" || status === "FAILED";
}

// ── Shimmer skeleton ───────────────────────────────────────────

function Shimmer({ className = "" }: { className?: string }) {
  return <div className={`${styles.shimmer} ${className}`} />;
}

// ── Stat cell ──────────────────────────────────────────────────

interface StatCellProps {
  label: string;
  loading: boolean;
  value: string;
  sub: string;
  valueColor?: string;
  barWidth?: number;   // 0–100
  barColor?: string;
}

function StatCell({ label, loading, value, sub, valueColor, barWidth, barColor }: StatCellProps) {
  return (
    <div className={`bg-[#0e0d0b] px-5 py-[1.4rem] transition-colors duration-200 ${styles.statCell}`}>
      <p className="text-[10px] tracking-[0.12em] uppercase text-[#7d7568] mb-2">{label}</p>
      {loading ? (
        <Shimmer className="h-[22px] w-20 mt-1" />
      ) : (
        <>
          <p className="font-['Lora'] text-[22px] leading-none" style={{ color: valueColor ?? "#e8e4dc" }}>
            {value}
          </p>
          <p className="text-[11px] text-[#8a8070] font-light mt-1">{sub}</p>
          {barWidth !== undefined && (
            <div className="h-[2px] bg-[#1a1815] rounded-sm mt-2 overflow-hidden w-full">
              <div
                className={styles.scoreBarFill}
                style={{ width: `${barWidth}%`, background: barColor ?? "#c8a96e" }}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Emotion colour map (matches EmotionBreakdown.tsx) ──────────
// Keys capitalised to match insights.py's .capitalize() output

const EMOTION_COLORS: Record<string, string> = {
  Joy: "#c8a96e", Love: "#c87a8a", Optimism: "#8aad6e",
  Sadness: "#5c7a9e", Anger: "#b85c4a", Fear: "#7a6e9e",
  Disgust: "#5c7a5c", Surprise: "#9e8a5c", Neutral: "#5a5550",
};

// ── Page ───────────────────────────────────────────────────────

export default function DashboardPage() {
  const [insights,     setInsights]     = useState<InsightsResponse | null>(null);
  const [entries,      setEntries]      = useState<JournalEntryResponse[]>([]);
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState<string | null>(null);
  const [justFinished, setJustFinished] = useState(false);
  // null = still loading, true/false = fetched
  const [consentGiven, setConsentGiven] = useState<boolean | null>(null);

  // Single backend round-trip: insights + recent entries via /dashboard/summary.
  async function loadData() {
    const summary = await dashboardApi.summary();
    setInsights(summary.insights);
    setEntries(summary.recent_entries);
  }

  useEffect(() => {
    // Load dashboard data and consent status in parallel.
    dashboardApi.summary()
      .then((summary) => {
        setInsights(summary.insights);
        setEntries(summary.recent_entries);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load dashboard"))
      .finally(() => setLoading(false));

    (async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return;
        const res = await fetch('/api/v1/account/consent', {
          headers: { Authorization: `Bearer ${session.access_token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setConsentGiven(data.consent_given ?? false);
        }
      } catch {
        // Non-fatal — banner simply won't show if fetch fails
      }
    })();
  }, []);

  // ── Poll while the latest entry is still being analysed ─────────
  // SSE is not used because Next.js rewrites buffer streaming responses,
  // preventing server-sent events from reaching the browser. Polling the
  // analysis-status endpoint every 3 s is simpler and reliably works.
  const pendingEntry =
    entries[0] && !isDone(entries[0].status) && !isFailed(entries[0].status)
      ? entries[0]
      : null;

  useEffect(() => {
    if (!pendingEntry) return;
    const entryId = pendingEntry.id;
    let cancelled = false;

    (async () => {
      while (!cancelled) {
        await new Promise<void>((r) => setTimeout(r, 3000));
        if (cancelled) break;
        try {
          const { status } = await journalApi.getAnalysisStatus(entryId);
          if (isDone(status) || isFailed(status)) {
            await loadData();
            if (isDone(status)) {
              setJustFinished(true);
              setTimeout(() => setJustFinished(false), 4000);
            }
            break;
          }
        } catch {
          // transient network error — keep polling
        }
      }
    })();

    return () => { cancelled = true; };
  }, [pendingEntry?.id]);  // eslint-disable-line react-hooks/exhaustive-deps

  // ── Derived stats ──────────────────────────────────────────────
  // "Right now" uses the most recent completed entry's individual score
  // and dominant emotion, not the aggregated daily average from trend_data.
  const latestCompletedEntry = entries.find(e => isDone(e.status));
  const latestScore = latestCompletedEntry?.mood_scores?.fused_score
    ?? insights?.trend_data?.at(-1)?.score
    ?? null;
  const latestDominantEmotion = latestCompletedEntry?.mood_scores?.dominant_emotion ?? null;
  const latestMeta  = scoreToMeta(latestScore);

  // Fix 4: explicit types on reduce so TypeScript doesn't infer `any`
  const avgScore = insights?.trend_data?.length
    ? insights.trend_data.reduce((s: number, d: TrendDataPoint) => s + d.score, 0)
      / insights.trend_data.length
    : null;
  const avgMeta = scoreToMeta(avgScore);

  const streak          = insights
    ? computeStreak(insights.trend_data.map((d: TrendDataPoint) => d.date))
    : 0;
  const dominantEmotion = insights?.emotion_breakdown?.[0] ?? null;

  return (
    <div className="min-h-screen bg-[#0e0d0b] text-[#e8e4dc]" style={{ fontFamily: "var(--font-dm-sans), sans-serif" }}>
      <Navbar />
      <div className="grid px-5" style={{ gridTemplateColumns: "1fr min(1040px, 100%) 1fr" }}>
        <div className="col-start-2 py-12 pb-24">

          {/* ── Header ── */}
          <motion.div
            className="flex items-end justify-between flex-wrap gap-4 mb-12"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45 }}
          >
            <div>
              <p className="text-[11px] tracking-[0.12em] uppercase text-[#6b6357] font-light mb-2">
                {new Date().toLocaleDateString("en-GB", {
                  weekday: "long", day: "numeric", month: "long", year: "numeric",
                })}
              </p>
              <h1 style={{ fontFamily: "var(--font-lora), serif" }}
                className="text-[clamp(26px,4vw,38px)] font-normal text-[#f0ece2] leading-tight">
                Your <em className="text-[#c8a96e] italic">emotional</em> map
              </h1>
            </div>
            <Link
              href="/journal/new"
              className="inline-flex items-center gap-2 px-6 py-3 border border-[#2a2720] rounded-full text-[#a09080] text-[13px] no-underline transition-all duration-200 hover:border-[#c8a96e] hover:text-[#c8a96e]"
            >
              <span className="text-lg leading-none">+</span> New entry
            </Link>
          </motion.div>

          {/* Amber accent line */}
          <div className="w-10 h-px bg-[#c8a96e] opacity-40 mb-10" />

          {/* ── Error banner ── */}
          <AnimatePresence>
            {error && (
              <motion.div
                className="bg-[#1a0f0f] border border-[#4a1b1b] rounded-lg px-4 py-3 text-[13px] text-[#e24b4a] mb-8"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              >
                {error}
              </motion.div>
            )}
          </AnimatePresence>

          {/* ── Consent banner ── */}
          <AnimatePresence>
            {consentGiven === false && (
              <motion.div
                className="flex items-start justify-between gap-4 rounded-xl border border-[#c8a96e]/25 bg-[#0c0b09] px-5 py-4 mb-8"
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.3 }}
              >
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 shrink-0 text-[#c8a96e] text-[15px]">⚠</span>
                  <div>
                    <p className="text-[13px] text-[#c8bfb0] font-light leading-relaxed">
                      <span className="font-normal">Data processing consent not given.</span>{" "}
                      MoodMap needs your consent to analyse journal entries and generate mood insights.
                      Without it, new entries cannot be processed.
                    </p>
                  </div>
                </div>
                <Link
                  href="/account"
                  className="shrink-0 self-center rounded-lg border border-[#c8a96e]/40 px-3.5 py-1.5 text-[12px] text-[#c8a96e] no-underline transition-all hover:border-[#c8a96e] hover:bg-[#c8a96e]/10 whitespace-nowrap"
                >
                  Give consent →
                </Link>
              </motion.div>
            )}
          </AnimatePresence>

          {/* ── Analysis status banner ── */}
          <AnimatePresence>
            {pendingEntry && (
              <motion.div
                key="analysing"
                className="flex items-center gap-3 rounded-xl border border-[#c8a96e]/30 bg-[#0c0b09] px-5 py-3.5 mb-8"
                initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.3 }}
              >
                <div className="relative flex h-2.5 w-2.5 shrink-0">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#c8a96e] opacity-60" />
                  <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-[#c8a96e]" />
                </div>
                <p className="text-[13px] text-[#c8bfb0] font-light">
                  Analysing your latest entry — your mood scores will update automatically.
                </p>
              </motion.div>
            )}
            {justFinished && !pendingEntry && (
              <motion.div
                key="done"
                className="flex items-center gap-3 rounded-xl border border-[#3a5a30]/60 bg-[#0c0b09] px-5 py-3.5 mb-8"
                initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
              >
                <span className="text-[13px] text-[#6a9a60]">Analysis complete — your dashboard has been updated.</span>
              </motion.div>
            )}
          </AnimatePresence>

          {/* ── Nudges Widget ── */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05, duration: 0.4 }}
            className="mb-12"
          >
            <NudgesWidget />
          </motion.div>

          {/* ── Stat strip ── */}
          <motion.div
            className="grid grid-cols-4 max-sm:grid-cols-2 gap-px bg-[#1a1815] border border-[#1a1815] rounded-xl overflow-hidden mb-12"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.4 }}
          >
            <StatCell
              label="Right now"
              loading={loading}
              value={latestDominantEmotion ?? latestMeta.label}
              sub={latestScore !== null ? `Score ${latestScore > 0 ? "+" : ""}${latestScore.toFixed(2)}` : "No entries yet"}
              valueColor={latestDominantEmotion ? (EMOTION_COLORS[latestDominantEmotion] ?? latestMeta.color) : latestMeta.color}
              barWidth={latestScore !== null ? ((latestScore + 1) / 2) * 100 : 50}
              barColor={latestMeta.color}
            />
            <StatCell
              label="30-day average"
              loading={loading}
              value={avgMeta.label}
              sub={avgScore !== null ? `Avg ${avgScore > 0 ? "+" : ""}${avgScore.toFixed(2)}` : "No data yet"}
              valueColor={avgMeta.color}
              barWidth={avgScore !== null ? ((avgScore + 1) / 2) * 100 : 50}
              barColor={avgMeta.color}
            />
            <StatCell
              label="Logging streak"
              loading={loading}
              value={String(streak)}
              sub={`${streak === 1 ? "day" : "days"} in a row`}
            />
            <StatCell
              label="Most felt"
              loading={loading}
              value={dominantEmotion?.name ?? "—"}
              sub="this month"
              valueColor={dominantEmotion ? EMOTION_COLORS[dominantEmotion.name] ?? "#c8a96e" : "#6b6357"}
            />
          </motion.div>

          {/* ── Trend + Pie ── */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.4 }}
          >
            <p className={`text-[10px] tracking-[0.14em] uppercase text-[#6b6357] mb-5 flex items-center gap-3 ${styles.sectionTitle}`}>
              30-day mood landscape
            </p>
            <div className="grid gap-6 mb-12 grid-cols-[1fr_340px] max-[860px]:grid-cols-1">
              <MoodTrendChart data={insights?.trend_data ?? []} loading={loading} />
              <EmotionBreakdown data={insights?.emotion_breakdown ?? []} loading={loading} />
            </div>
          </motion.div>

          {/* ── Heatmap ── */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.28, duration: 0.4 }}
          >
            <p className={`text-[10px] tracking-[0.14em] uppercase text-[#6b6357] mb-5 flex items-center gap-3 ${styles.sectionTitle}`}>
              Pattern over time
            </p>
            <div className="mb-12">
              <MoodHeatmap data={insights?.calendar_data ?? []} loading={loading} />
            </div>
          </motion.div>

          {/* ── Recent entries ── */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35, duration: 0.4 }}
          >
            <p className={`text-[10px] tracking-[0.14em] uppercase text-[#6b6357] mb-5 flex items-center gap-3 ${styles.sectionTitle}`}>
              Recent entries
            </p>

            <div className="flex flex-col">
              {loading ? (
                [0, 1, 2].map((i) => (
                  <div key={i} className="py-5 border-b border-[#141210]">
                    <Shimmer className="h-[14px] w-3/5 mb-2" />
                    <Shimmer className="h-[11px] w-2/5" />
                  </div>
                ))
              ) : entries.length === 0 ? (
                <div className="py-12 flex flex-col items-center gap-2">
                  <div className="w-9 h-9 rounded-full border border-[#2a2720] flex items-center justify-center text-[#6b6357] text-sm">◌</div>
                  <p className="text-[13px] text-[#6b6357] font-light">No entries yet</p>
                  <Link href="/journal/new" className="text-[12px] text-[#c8a96e] hover:underline no-underline">
                    Start your first entry →
                  </Link>
                </div>
              ) : (
                entries.map((entry, i) => {
                  const d      = new Date(entry.created_at);
                  const score  = entry.mood_scores?.fused_score ?? null;
                  const meta   = scoreToMeta(score);
                  const done   = isDone(entry.status);
                  const failed = isFailed(entry.status);

                  return (
                    <motion.div
                      key={entry.id}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.4 + i * 0.07 }}
                    >
                      <Link href={`/journal/${entry.id}`} className="no-underline block">
                        <div className={`grid items-start py-5 border-b border-[#141210] last:border-none ${styles.entryRow}`}
                          style={{ gridTemplateColumns: "3rem 1fr auto", gap: "0 1.25rem" }}
                        >
                          {/* Date column */}
                          <div className="text-center pt-0.5">
                            <p style={{ fontFamily: "var(--font-lora), serif" }}
                              className="text-[20px] font-normal text-[#c8bfb0] leading-none">
                              {d.getDate()}
                            </p>
                            <p className="text-[9px] uppercase tracking-wider text-[#6b6357] mt-1">
                              {d.toLocaleDateString("en-GB", { month: "short" })}
                            </p>
                          </div>

                          {/* Body */}
                          <div>
                            <p style={{ fontFamily: "var(--font-lora), serif" }}
                              className="text-[15px] text-[#8a8070] leading-relaxed line-clamp-2">
                              {entry.text}
                            </p>
                            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                              <span className="text-[11px] text-[#6b6357] font-light">
                                {timeAgo(entry.created_at)}
                              </span>
                              {/* Fix 3: explicit : string type */}
                              {entry.mood_tags?.slice(0, 2).map((tag: string) => (
                                <span key={tag}
                                  className="text-[10px] px-2 py-0.5 rounded-full border border-[#1a1815] text-[#5a5550]">
                                  {tag}
                                </span>
                              ))}
                              {entry.audio_key && (
                                <span className="text-[10px] px-2 py-0.5 rounded-full border border-[#1a1815] text-[#5a5550]">
                                  🎙 voice
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Status pill */}
                          {done && score !== null ? (
                            <div className="self-center text-[11px] px-3 py-1 rounded-full border border-[#1a1815] font-light whitespace-nowrap"
                              style={{ color: meta.color }}>
                              {meta.label}
                            </div>
                          ) : (
                            <div className="self-center text-[10px] px-3 py-1 rounded-full border border-[#1a1815] text-[#6b6357] font-light whitespace-nowrap">
                              {failed ? "Failed" : "Analysing…"}
                            </div>
                          )}
                        </div>
                      </Link>
                    </motion.div>
                  );
                })
              )}
            </div>

            {entries.length > 0 && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.62 }}
                className="mt-6"
              >
                <Link href="/journal"
                  className="text-[12px] text-[#6b6357] no-underline tracking-wider transition-colors duration-150 hover:text-[#c8a96e]">
                  View all entries →
                </Link>
              </motion.div>
            )}
          </motion.div>

        </div>
      </div>
    </div>
  );
}