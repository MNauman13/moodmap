"use client";

import { useMemo } from "react";
import type { TrendDataPoint } from "@/lib/api";
import styles from "../dashboard.module.css";

// ── Score → colour ─────────────────────────────────────────────

function scoreToColor(score: number): string {
  if (score > 0.4)  return "#4a7a3a";
  if (score > 0.1)  return "#c8a96e";
  if (score > -0.1) return "#3a3428";
  if (score > -0.4) return "#7a4a30";
  return                   "#8a2a2a";
}

function scoreToLabel(score: number): string {
  if (score > 0.4)  return "Thriving";
  if (score > 0.1)  return "Doing well";
  if (score > -0.1) return "Neutral";
  if (score > -0.4) return "Low";
  return "Struggling";
}

// ── Build 13-week grid ending today ───────────────────────────

interface DayCell {
  date: string;        // "YYYY-MM-DD"
  score: number | null;
  isCurrentMonth: boolean;
  isFuture: boolean;
}

function buildGrid(data: TrendDataPoint[]): DayCell[][] {
  // MoodScore.time is set to entry.created_at in analysis.py,
  // so the dates in calendar_data are the journal entry dates — correct.
  const scoreMap = new Map(data.map((d) => [d.date, d.score]));
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  // Start from the most recent Sunday, go back 7 weeks
  const startDay = new Date(today);
  startDay.setDate(today.getDate() - today.getDay() - 7 * 7);

  const weeks: DayCell[][] = [];
  for (let w = 0; w < 8; w++) {
    const week: DayCell[] = [];
    for (let d = 0; d < 7; d++) {
      const date = new Date(startDay);
      date.setDate(startDay.getDate() + w * 7 + d);
      const iso = date.toISOString().slice(0, 10);
      week.push({
        date: iso,
        score: scoreMap.get(iso) ?? null,
        isCurrentMonth: date.getMonth() === today.getMonth(),
        isFuture: date > today,
      });
    }
    weeks.push(week);
  }
  return weeks;
}

// ── Month labels ───────────────────────────────────────────────

function getMonthLabels(weeks: DayCell[][]): { label: string; col: number }[] {
  const seen = new Set<string>();
  const out: { label: string; col: number }[] = [];
  weeks.forEach((week, i) => {
    const d = new Date(week[0].date);
    const key = `${d.getFullYear()}-${d.getMonth()}`;
    if (!seen.has(key)) {
      seen.add(key);
      out.push({ label: d.toLocaleDateString("en-GB", { month: "short" }), col: i });
    }
  });
  return out;
}

const DOW = ["S","M","T","W","T","F","S"];

// ── Component ──────────────────────────────────────────────────

interface Props {
  data: TrendDataPoint[];
  loading: boolean;
}

export default function MoodHeatmap({ data, loading }: Props) {
  const weeks       = useMemo(() => buildGrid(data), [data]);
  const monthLabels = useMemo(() => getMonthLabels(weeks), [weeks]);

  return (
    <div className="bg-[#0c0b09] border border-[#1a1815] rounded-xl p-6">
      <p className="font-['Lora'] text-[15px] text-[#c8bfb0] mb-1">8-week calendar</p>
      <p className="text-[12px] text-[#6b6357] font-light mb-5">
        Each square is one day — hover to see your score
      </p>

      {loading ? (
        <div className={`${styles.shimmer} h-[120px] w-full rounded-lg`} />
      ) : data.length === 0 ? (
        <div className="h-[100px] flex items-center justify-center">
          <p className="text-[13px] text-[#6b6357] font-light">
            Start journalling to fill your calendar
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto pb-1">
          <div style={{ minWidth: 320 }}>

            {/* Month labels row */}
            <div className="flex mb-1 ml-6">
              {weeks.map((_, i) => {
                const lbl = monthLabels.find((m) => m.col === i);
                return (
                  <div key={i} className="flex-1">
                    {lbl && (
                      <span className="text-[10px] text-[#6b6357] uppercase tracking-wider">
                        {lbl.label}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="flex gap-0.5">
              {/* Day-of-week labels */}
              <div className="flex flex-col gap-0.5 mr-1">
                {DOW.map((d, i) => (
                  <div key={i} className="w-4 h-4 flex items-center justify-center text-[9px] text-[#3a3428]">
                    {i % 2 === 1 ? d : ""}
                  </div>
                ))}
              </div>

              {/* Week columns */}
              {weeks.map((week, wi) => (
                <div key={wi} className="flex flex-col gap-0.5 flex-1">
                  {week.map((day) => (
                    <div
                      key={day.date}
                      title={
                        day.isFuture ? "" :
                        day.score !== null
                          ? `${day.date} — ${scoreToLabel(day.score)} (${day.score > 0 ? "+" : ""}${day.score.toFixed(2)})`
                          : `${day.date} — no entry`
                      }
                      className="w-full aspect-square rounded-[3px] transition-all duration-150 cursor-default"
                      style={{
                        background: day.isFuture ? "transparent" :
                          day.score !== null ? scoreToColor(day.score) : "#1a1815",
                        opacity: day.isFuture ? 0 : 1,
                        outline: day.isCurrentMonth && day.score !== null
                          ? "1px solid rgba(200,169,110,0.15)" : "none",
                      }}
                    />
                  ))}
                </div>
              ))}
            </div>

            {/* Legend */}
            <div className="flex items-center gap-3 mt-3 ml-6">
              <span className="text-[10px] text-[#3a3428]">Less</span>
              {([-0.7, -0.25, 0, 0.25, 0.7] as const).map((s, i) => (
                <div
                  key={i}
                  title={scoreToLabel(s)}
                  className="w-3 h-3 rounded-[2px] cursor-default"
                  style={{ background: scoreToColor(s) }}
                />
              ))}
              <span className="text-[10px] text-[#3a3428]">More</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}