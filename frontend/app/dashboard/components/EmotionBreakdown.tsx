"use client";

import { useState } from "react";
import { PieChart, Pie, Cell, Sector, ResponsiveContainer } from "recharts";
import type { EmotionDataPoint } from "@/lib/api";
import styles from "../dashboard.module.css";

// ── Colour map ─────────────────────────────────────────────────
const EMOTION_COLORS: Record<string, string> = {
  Joy:      "#c8a96e",
  Sadness:  "#5c7a9e",
  Anger:    "#b85c4a",
  Fear:     "#7a6e9e",
  Disgust:  "#5c7a5c",
  Surprise: "#9e8a5c",
  Neutral:  "#5a5550",
};
const FALLBACK = ["#c8a96e","#5c7a9e","#b85c4a","#7a6e9e","#5c7a5c","#9e8a5c","#5a5550"];

function getColor(name: string, index: number): string {
  return EMOTION_COLORS[name] ?? FALLBACK[index % FALLBACK.length];
}

// ── Active sector shape ────────────────────────────────────────
interface SectorShapeProps {
  cx: number;
  cy: number;
  innerRadius: number;
  outerRadius: number;
  startAngle: number;
  endAngle: number;
  fill: string;
  payload: EmotionDataPoint;
  percent: number;
}

function ActiveSector(props: SectorShapeProps) {
  const { cx, cy, innerRadius, outerRadius, startAngle, endAngle, fill, payload, percent } = props;

  return (
    <g>
      <text x={cx} y={cy - 10} textAnchor="middle" className={styles.pieCenterLabel}>
        {payload.name}
      </text>
      <text x={cx} y={cy + 14} textAnchor="middle" className={styles.pieCenterPct}>
        {(percent * 100).toFixed(0)}%
      </text>
      <Sector cx={cx} cy={cy}
        innerRadius={innerRadius} outerRadius={outerRadius + 6}
        startAngle={startAngle} endAngle={endAngle}
        fill={fill}
      />
      <Sector cx={cx} cy={cy}
        innerRadius={outerRadius + 10} outerRadius={outerRadius + 12}
        startAngle={startAngle} endAngle={endAngle}
        fill={fill}
      />
    </g>
  );
}

// ── Component ──────────────────────────────────────────────────

interface Props {
  data: EmotionDataPoint[];
  loading: boolean;
}

export default function EmotionBreakdown({ data, loading }: Props) {
  const [activeIndex, setActiveIndex] = useState(0);

  return (
    <div className="bg-[#0c0b09] border border-[#1a1815] rounded-xl p-6">
      <p className="font-['Lora'] text-[15px] text-[#c8bfb0] mb-1">Emotion mix</p>
      <p className="text-[12px] text-[#4a4438] font-light mb-5">
        Dominant feelings this month
      </p>

      {loading ? (
        <div className={`${styles.shimmer} h-[160px] w-full rounded-lg`} />
      ) : data.length === 0 ? (
        <div className="h-[160px] flex flex-col items-center justify-center gap-2">
          <div className="w-9 h-9 rounded-full border border-[#2a2720] flex items-center justify-center text-[#4a4438] text-sm">◌</div>
          <p className="text-[13px] text-[#4a4438] font-light">No data yet</p>
        </div>
      ) : (
        <>
          <div className={styles.chartWrap}>
            <ResponsiveContainer width="100%" height={160}>
              <PieChart>
                <Pie
                  data={data}
                  cx="50%" cy="50%"
                  innerRadius={46} outerRadius={68}
                  dataKey="value"
                  activeShape={(props: unknown) => (
                    <ActiveSector {...(props as SectorShapeProps)} />
                  )}
                  onMouseEnter={(_, index) => setActiveIndex(index)}
                  strokeWidth={0}
                >
                  {data.map((entry, index) => (
                    <Cell
                      key={`cell-${entry.name}`}
                      fill={getColor(entry.name, index)}
                      opacity={index === activeIndex ? 1 : 0.4}
                    />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Legend */}
          <ul className="mt-4 flex flex-col gap-1.5 list-none p-0 m-0">
            {data.map((entry, index) => (
              <li
                key={entry.name}
                className="flex items-center justify-between gap-2 cursor-pointer py-0.5"
                onMouseEnter={() => setActiveIndex(index)}
              >
                <div className="flex items-center gap-2">
                  <div
                    className="w-1.5 h-1.5 rounded-full shrink-0 transition-opacity duration-150"
                    style={{
                      background: getColor(entry.name, index),
                      opacity: index === activeIndex ? 1 : 0.4,
                    }}
                  />
                  <span
                    className="text-[12px] font-light transition-colors duration-150"
                    style={{ color: index === activeIndex ? "#e8e4dc" : "#6b6357" }}
                  >
                    {entry.name}
                  </span>
                </div>
                <span className="text-[11px] text-[#4a4438] tabular-nums">{entry.value}×</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
