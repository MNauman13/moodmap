"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { journalApi } from "@/lib/api";
import type { JournalEntryResponse } from "@/lib/api";
import Navbar from "@/components/Navbar";
import { scoreToMeta } from "@/app/dashboard/components/MoodTrendChart";

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

function isDone(status: string): boolean {
  return status === "completed" || status === "COMPLETED";
}
function isFailed(status: string): boolean {
  return status === "failed" || status === "FAILED";
}

const PAGE_SIZE = 20;

export default function JournalListPage() {
  const [entries, setEntries]   = useState<JournalEntryResponse[]>([]);
  const [loading, setLoading]   = useState(true);
  const [page, setPage]         = useState(1);
  const [hasMore, setHasMore]   = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  const fetchEntries = useCallback(async (pageNum: number, append: boolean) => {
    try {
      const data = await journalApi.list(pageNum, PAGE_SIZE);
      setEntries(prev => append ? [...prev, ...data.entries] : data.entries);
      setHasMore(data.has_more);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, []);

  useEffect(() => {
    fetchEntries(1, false);
  }, [fetchEntries]);

  const loadMore = () => {
    const next = page + 1;
    setPage(next);
    setLoadingMore(true);
    fetchEntries(next, true);
  };

  return (
    <>
      <style>{`
        body {
          background: #0e0d0b;
          color: #e8e4dc;
          font-family: var(--font-dm-sans), 'DM Sans', system-ui, sans-serif;
          min-height: 100vh;
        }
        .page-wrap {
          min-height: 100vh;
          display: grid;
          grid-template-columns: 1fr min(680px, 100%) 1fr;
          padding: 0 1rem;
        }
        .page-content {
          grid-column: 2;
          padding: 3rem 0 6rem;
        }
      `}</style>

      <Navbar />

      <div className="page-wrap">
        <div className="page-content">

          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45 }}
            className="flex items-end justify-between mb-10"
          >
            <div>
              <p className="text-[10px] tracking-[0.14em] uppercase text-[#6b6357] mb-2">
                Your entries
              </p>
              <h1
                style={{ fontFamily: "var(--font-lora), 'Lora', serif" }}
                className="text-[32px] font-normal text-[#f0ece2] leading-tight"
              >
                Journal
              </h1>
            </div>
            <Link
              href="/journal/new"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-[#c8a96e] text-[#0e0d0b] text-[13px] font-medium no-underline transition-all duration-200 hover:bg-[#dbb97e] hover:-translate-y-px"
            >
              New entry
            </Link>
          </motion.div>

          {/* Entry list */}
          {loading ? (
            <div className="flex flex-col">
              {[0, 1, 2, 4, 5].map((i) => (
                <div key={i} className="py-5 border-b border-[#141210]">
                  <div className="h-[14px] w-3/5 mb-2 rounded bg-[#1a1815] animate-pulse" />
                  <div className="h-[11px] w-2/5 rounded bg-[#1a1815] animate-pulse" />
                </div>
              ))}
            </div>
          ) : entries.length === 0 ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="py-24 flex flex-col items-center gap-3"
            >
              <div className="w-10 h-10 rounded-full border border-[#2a2720] flex items-center justify-center text-[#6b6357]">
                ◌
              </div>
              <p className="text-[13px] text-[#6b6357] font-light">No entries yet</p>
              <Link href="/journal/new" className="text-[13px] text-[#c8a96e] hover:underline no-underline">
                Write your first entry →
              </Link>
            </motion.div>
          ) : (
            <div className="flex flex-col">
              {entries.map((entry, i) => {
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
                    transition={{ delay: Math.min(i * 0.04, 0.4) }}
                  >
                    <Link href={`/journal/${entry.id}`} className="no-underline block">
                      <div
                        className="grid items-start py-5 border-b border-[#141210] last:border-none hover:bg-[#0f0e0c] transition-colors duration-150 rounded-sm -mx-2 px-2"
                        style={{ gridTemplateColumns: "3rem 1fr auto", gap: "0 1.25rem" }}
                      >
                        {/* Date column */}
                        <div className="text-center pt-0.5">
                          <p
                            style={{ fontFamily: "var(--font-lora), serif" }}
                            className="text-[20px] font-normal text-[#c8bfb0] leading-none"
                          >
                            {d.getDate()}
                          </p>
                          <p className="text-[9px] uppercase tracking-wider text-[#6b6357] mt-1">
                            {d.toLocaleDateString("en-GB", { month: "short" })}
                          </p>
                          <p className="text-[9px] text-[#4a4540] mt-0.5">
                            {d.toLocaleDateString("en-GB", { year: "numeric" })}
                          </p>
                        </div>

                        {/* Body */}
                        <div>
                          <p
                            style={{ fontFamily: "var(--font-lora), serif" }}
                            className="text-[15px] text-[#8a8070] leading-relaxed line-clamp-2"
                          >
                            {entry.text}
                          </p>
                          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                            <span className="text-[11px] text-[#6b6357] font-light">
                              {timeAgo(entry.created_at)}
                            </span>
                            {entry.mood_tags?.slice(0, 3).map((tag: string) => (
                              <span
                                key={tag}
                                className="text-[10px] px-2 py-0.5 rounded-full border border-[#1a1815] text-[#5a5550]"
                              >
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
                          <div
                            className="self-center text-[11px] px-3 py-1 rounded-full border border-[#1a1815] font-light whitespace-nowrap"
                            style={{ color: meta.color }}
                          >
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
              })}

              {hasMore && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="mt-8 flex justify-center"
                >
                  <button
                    onClick={loadMore}
                    disabled={loadingMore}
                    className="text-[12px] text-[#6b6357] tracking-wider border border-[#1a1815] rounded-full px-6 py-2 hover:text-[#c8a96e] hover:border-[#2a2720] transition-colors duration-150 disabled:opacity-40"
                  >
                    {loadingMore ? "Loading…" : "Load more"}
                  </button>
                </motion.div>
              )}
            </div>
          )}

        </div>
      </div>
    </>
  );
}
