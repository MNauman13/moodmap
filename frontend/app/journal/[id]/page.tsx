'use client'

import { useEffect, useState } from "react"
import { useRouter, useParams } from "next/navigation"
import Link from "next/link"
import { motion } from "framer-motion"
import { journalApi, type JournalEntryResponse, type MoodScores } from "@/lib/api"

// ── Helpers ────────────────────────────────────────────────────

function isDone(status: string) {
  return status === "completed" || status === "COMPLETED"
}
function isFailed(status: string) {
  return status === "failed" || status === "FAILED"
}

function scoreToColor(score: number | null): string {
  if (score === null) return "#6b6357"
  if (score >= 0.4) return "#c8a96e"
  if (score >= 0.1) return "#9e8a5c"
  if (score >= -0.1) return "#8a8070"
  if (score >= -0.4) return "#5c7a9e"
  return "#b85c4a"
}

function scoreToLabel(score: number | null): string {
  if (score === null) return "—"
  if (score >= 0.4) return "Positive"
  if (score >= 0.1) return "Slightly Positive"
  if (score >= -0.1) return "Neutral"
  if (score >= -0.4) return "Slightly Negative"
  return "Negative"
}

const EMOTION_COLORS: Record<string, string> = {
  joy: "#c8a96e",
  sadness: "#5c7a9e",
  anger: "#b85c4a",
  fear: "#7a6e9e",
  disgust: "#5c7a5c",
  surprise: "#9e8a5c",
  neutral: "#5a5550",
}

// ── Emotion bar ────────────────────────────────────────────────

function EmotionBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-16 text-[11px] text-[#6b6357] capitalize">{label}</span>
      <div className="flex-1 h-[3px] bg-[#1a1815] rounded-full overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ background: color }}
          initial={{ width: 0 }}
          animate={{ width: `${Math.round(value * 100)}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />
      </div>
      <span className="w-8 text-right text-[10px] text-[#4a4438]">
        {Math.round(value * 100)}%
      </span>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────

export default function JournalEntryPage() {
  const router = useRouter()
  const params = useParams<{ id: string }>()
  const id = params.id

  const [entry, setEntry] = useState<JournalEntryResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    journalApi.get(id)
      .then(setEntry)
      .catch((e) => setError(e.message ?? "Failed to load entry"))
      .finally(() => setLoading(false))
  }, [id])

  const handleDelete = async () => {
    if (!confirm("Delete this entry? This cannot be undone.")) return
    setDeleting(true)
    try {
      await journalApi.delete(id)
      router.push("/dashboard")
    } catch {
      setDeleting(false)
      alert("Failed to delete entry.")
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0e0d0b]">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-[#1a1815] border-t-[#c8a96e]" />
      </div>
    )
  }

  if (error || !entry) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[#0e0d0b] text-[#e8e4dc]">
        <p className="text-[#b85c4a]">{error ?? "Entry not found"}</p>
        <Link href="/dashboard" className="text-[12px] text-[#c8a96e] hover:underline">
          ← Back to dashboard
        </Link>
      </div>
    )
  }

  const ms: MoodScores | null = entry.mood_scores ?? null
  const fusedScore = ms?.fused_score ?? null
  const scoreColor = scoreToColor(fusedScore)
  const scoreLabel = scoreToLabel(fusedScore)
  const done = isDone(entry.status)
  const failed = isFailed(entry.status)

  const emotions: Array<{ key: keyof MoodScores & string; label: string }> = [
    { key: "text_joy", label: "joy" },
    { key: "text_sadness", label: "sadness" },
    { key: "text_anger", label: "anger" },
    { key: "text_fear", label: "fear" },
    { key: "text_disgust", label: "disgust" },
    { key: "text_surprise", label: "surprise" },
    { key: "text_neutral", label: "neutral" },
  ]

  const d = new Date(entry.created_at)

  return (
    <div className="min-h-screen bg-[#0e0d0b] text-[#e8e4dc]" style={{ fontFamily: "'DM Sans', sans-serif" }}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;1,400&family=DM+Sans:wght@300;400;500&display=swap');`}</style>

      <div className="grid px-5" style={{ gridTemplateColumns: "1fr min(720px, 100%) 1fr" }}>
        <div className="col-start-2 py-12 pb-24">

          {/* Nav */}
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-10 flex items-center justify-between"
          >
            <Link
              href="/dashboard"
              className="text-[12px] text-[#4a4438] no-underline hover:text-[#c8a96e] transition-colors"
            >
              ← Dashboard
            </Link>
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="text-[12px] text-[#4a4438] hover:text-[#b85c4a] transition-colors disabled:opacity-50"
            >
              {deleting ? "Deleting…" : "Delete entry"}
            </button>
          </motion.div>

          {/* Date header */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="mb-8"
          >
            <p className="text-[11px] tracking-[0.12em] uppercase text-[#6b6357] mb-2">
              {d.toLocaleDateString("en-GB", {
                weekday: "long", day: "numeric", month: "long", year: "numeric",
              })}
            </p>
            <div className="flex items-center gap-3 flex-wrap">
              <div className="w-8 h-px bg-[#c8a96e] opacity-40" />
              {entry.mood_tags?.map((tag) => (
                <span
                  key={tag}
                  className="text-[10px] px-2 py-0.5 rounded-full border border-[#1a1815] text-[#5a5550]"
                >
                  {tag}
                </span>
              ))}
              {entry.audio_key && (
                <span className="text-[10px] px-2 py-0.5 rounded-full border border-[#1a1815] text-[#5a5550]">
                  voice memo
                </span>
              )}
            </div>
          </motion.div>

          {/* Journal text */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="mb-10"
          >
            <div
              className="rounded-xl border border-[#1a1815] bg-[#0c0b09] px-8 py-8"
              style={{ fontFamily: "'Lora', serif" }}
            >
              <p className="text-[16px] leading-[1.85] text-[#c8bfb0] whitespace-pre-wrap">
                {entry.text}
              </p>
              <p className="mt-5 text-[11px] text-[#4a4438] font-light" style={{ fontFamily: "'DM Sans', sans-serif" }}>
                {entry.word_count} words
              </p>
            </div>
          </motion.div>

          {/* Audio player */}
          {entry.audio_url && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15 }}
              className="mb-10"
            >
              <p className="text-[10px] tracking-[0.12em] uppercase text-[#6b6357] mb-3">
                Voice memo
              </p>
              <div className="rounded-xl border border-[#1a1815] bg-[#0c0b09] p-5">
                <audio
                  controls
                  src={entry.audio_url}
                  className="w-full"
                  style={{ accentColor: "#c8a96e" }}
                />
              </div>
            </motion.div>
          )}

          {/* Analysis section */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <p className="text-[10px] tracking-[0.12em] uppercase text-[#6b6357] mb-4">
              Emotional analysis
            </p>

            {!done && !failed && (
              <div className="flex items-center gap-3 rounded-xl border border-[#1a1815] bg-[#0c0b09] px-6 py-5 text-[13px] text-[#6b6357]">
                <div className="h-3 w-3 animate-spin rounded-full border border-[#1a1815] border-t-[#c8a96e]" />
                Analysing your entry…
              </div>
            )}

            {failed && (
              <div className="rounded-xl border border-[#2a1515] bg-[#0c0b09] px-6 py-5 text-[13px] text-[#b85c4a]">
                Analysis failed. Please try submitting a new entry.
              </div>
            )}

            {done && ms && (
              <div className="rounded-xl border border-[#1a1815] bg-[#0c0b09] px-6 py-7 space-y-7">

                {/* Fused score */}
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-[#4a4438] mb-1">Overall mood</p>
                    <p
                      className="font-['Lora'] text-[28px] leading-none"
                      style={{ color: scoreColor }}
                    >
                      {scoreLabel}
                    </p>
                  </div>
                  {fusedScore !== null && (
                    <div
                      className="flex h-14 w-14 items-center justify-center rounded-full border text-[15px] font-medium"
                      style={{ borderColor: `${scoreColor}40`, color: scoreColor }}
                    >
                      {fusedScore > 0 ? "+" : ""}{fusedScore.toFixed(2)}
                    </div>
                  )}
                </div>

                {/* Dominant emotion */}
                {ms.dominant_emotion && (
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-[#4a4438] mb-1">Dominant emotion</p>
                    <span
                      className="text-[13px] capitalize font-medium"
                      style={{ color: EMOTION_COLORS[ms.dominant_emotion] ?? "#c8a96e" }}
                    >
                      {ms.dominant_emotion}
                    </span>
                    {ms.confidence !== null && ms.confidence !== undefined && (
                      <span className="ml-2 text-[11px] text-[#4a4438]">
                        ({Math.round(ms.confidence * 100)}% confidence)
                      </span>
                    )}
                  </div>
                )}

                {/* Emotion bars */}
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-[#4a4438] mb-4">Emotion breakdown</p>
                  <div className="space-y-3">
                    {emotions.map(({ key, label }) => {
                      const val = ms[key as keyof MoodScores] as number | null
                      if (val === null || val === undefined) return null
                      return (
                        <EmotionBar
                          key={key}
                          label={label}
                          value={val}
                          color={EMOTION_COLORS[label] ?? "#6b6357"}
                        />
                      )
                    })}
                  </div>
                </div>

                {/* Voice data */}
                {ms.voice_valence !== null && ms.voice_valence !== undefined && (
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-[#4a4438] mb-4">Voice analysis</p>
                    <div className="grid grid-cols-3 gap-4">
                      {[
                        { label: "Valence", value: ms.voice_valence },
                        { label: "Arousal", value: ms.voice_arousal },
                        { label: "Energy", value: ms.voice_energy },
                      ].map(({ label, value }) => (
                        value !== null && value !== undefined ? (
                          <div key={label} className="rounded-lg border border-[#141210] bg-[#0e0d0b] px-4 py-3">
                            <p className="text-[10px] uppercase tracking-wider text-[#4a4438] mb-1">{label}</p>
                            <p className="text-[18px] font-light text-[#8a8070]">
                              {value > 0 ? "+" : ""}{value.toFixed(2)}
                            </p>
                          </div>
                        ) : null
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </motion.div>

        </div>
      </div>
    </div>
  )
}
