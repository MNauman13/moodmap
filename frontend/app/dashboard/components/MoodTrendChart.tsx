"use client";

import {
  LineChart, Line, XAxis, YAxis,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import Link from "next/link";
import type { TrendDataPoint } from "@/lib/api";
import styles from "../dashboard.module.css";

// ── Helpers ────────────────────────────────────────────────────

function formatAxisDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric", month: "short",
  });
}

export function scoreToMeta(score: number | null): { label: string; color: string } {
  if (score === null) return { label: "—",          color: "#5a5550" };
  if (score > 0.4)    return { label: "Thriving",   color: "#8aad6e" };
  if (score > 0.1)    return { label: "Doing well", color: "#c8a96e" };
  if (score > -0.1)   return { label: "Neutral",    color: "#7a7060" };
  if (score > -0.4)   return { label: "Low",        color: "#9e7a5c" };
  return                     { label: "Struggling", color: "#9e5c5c" };
}

// ── Custom tooltip ─────────────────────────────────────────────

function MoodTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: { value: number }[];
  label?: string;
}) {
  if (!active || !payload?.length || !label) return null;
  const score = payload[0].value;
  const meta  = scoreToMeta(score);
  return (
    <div className="bg-[#141210] border border-[#2a2720] rounded-lg px-3 py-2 shadow-none">
      <p className="text-[11px] text-[#6b6357] mb-1">{formatAxisDate(label)}</p>
      <p className="font-['Lora'] text-[15px] mb-0.5" style={{ color: meta.color }}>
        {meta.label}
      </p>
      <p className="text-[11px] text-[#4a4438] tabular-nums">
        {score > 0 ? "+" : ""}{score.toFixed(2)}
      </p>
    </div>
  );
}

// ── Dot renderer ───────────────────────────────────────────────

function renderDot(props: {
  cx?: number; cy?: number;
  payload?: TrendDataPoint;
}, lastDate: string) {
  const { cx = 0, cy = 0, payload } = props;
  if (!payload) return <g key="empty" />;
  if (payload.date === lastDate) {
    return (
      <circle key={`dot-last`} cx={cx} cy={cy} r={4}
        fill="#c8a96e" stroke="#0e0d0b" strokeWidth={2} />
    );
  }
  return (
    <circle key={`dot-${payload.date}`} cx={cx} cy={cy} r={2}
      fill="#c8a96e" fillOpacity={0.35} stroke="none" />
  );
}

// ── Component ──────────────────────────────────────────────────

interface Props {
  data: TrendDataPoint[];
  loading: boolean;
}

export default function MoodTrendChart({ data, loading }: Props) {
  const lastDate = data.at(-1)?.date ?? "";

  return (
    <div className="bg-[#0c0b09] border border-[#1a1815] rounded-xl p-6">
      <p className="font-['Lora'] text-[15px] text-[#c8bfb0] mb-1">Mood trajectory</p>
      <p className="text-[12px] text-[#4a4438] font-light mb-5">
        Daily fused score — positive is wellbeing, negative is distress
      </p>

      {loading ? (
        <div className={`${styles.shimmer} h-[200px] w-full`} />
      ) : data.length === 0 ? (
        <div className="h-[200px] flex flex-col items-center justify-center gap-2">
          <div className="w-9 h-9 rounded-full border border-[#2a2720] flex items-center justify-center text-[#4a4438] text-sm">◌</div>
          <p className="text-[13px] text-[#4a4438] font-light">No mood data yet</p>
          <Link href="/journal" className="text-[12px] text-[#c8a96e] hover:underline no-underline">
            Write your first entry →
          </Link>
        </div>
      ) : (
        <div className={styles.chartWrap}>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: -28 }}>
              <XAxis
                dataKey="date"
                tickFormatter={formatAxisDate}
                tickLine={false}
                axisLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                domain={[-1, 1]}
                tickCount={5}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) => v.toFixed(1)}
              />
              <ReferenceLine y={0} strokeDasharray="4 4" />
              <Tooltip content={<MoodTooltip />} />
              <Line
                type="monotone"
                dataKey="score"
                stroke="#c8a96e"
                strokeWidth={1.5}
                dot={(props) => renderDot(props as Parameters<typeof renderDot>[0], lastDate)}
                activeDot={{ r: 5, fill: "#c8a96e", stroke: "#0e0d0b", strokeWidth: 2 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}