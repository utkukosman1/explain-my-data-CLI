"use client";

import { motion } from "framer-motion";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { Missing } from "@/lib/api";
import { SectionTitle } from "./QualitySection";

interface Props {
  missing: Missing;
}

export function MissingSection({ missing }: Props) {
  const pct = (missing.global_missing_pct * 100).toFixed(2);

  return (
    <div className="flex flex-col gap-5">
      <SectionTitle>Missing Values</SectionTitle>

      {/* Summary row */}
      <div className="grid grid-cols-3 gap-3">
        <SummaryCard
          label="Total missing"
          value={missing.total_missing.toLocaleString()}
          sub={`${pct}% of all cells`}
          color="#fbbf24"
        />
        <SummaryCard
          label="Complete rows"
          value={missing.complete_rows.toLocaleString()}
          sub={`${(missing.complete_rows_pct * 100).toFixed(1)}% of dataset`}
          color="#34d399"
        />
        <SummaryCard
          label="Affected columns"
          value={String(missing.chart_data.length)}
          sub={`out of all columns`}
          color="#818cf8"
        />
      </div>

      {missing.chart_data.length === 0 ? (
        <div
          className="px-4 py-3 rounded-xl text-sm"
          style={{
            background: "rgba(52,211,153,0.08)",
            border: "1px solid rgba(52,211,153,0.2)",
            color: "#34d399",
          }}
        >
          ✓ No missing values detected
        </div>
      ) : (
        <div
          className="rounded-xl p-4"
          style={{
            background: "rgba(13,13,24,0.8)",
            border: "1px solid rgba(28,28,46,0.6)",
          }}
        >
          <p className="text-xs mb-3" style={{ color: "#475569" }}>
            Missing % by column
          </p>
          <div style={{ height: Math.max(160, missing.chart_data.length * 28) }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={[...missing.chart_data].sort((a, b) => b.missing_pct - a.missing_pct)}
                layout="vertical"
                margin={{ left: 80, right: 40, top: 4, bottom: 4 }}
                barSize={14}
              >
                <XAxis
                  type="number"
                  domain={[0, 100]}
                  tick={{ fill: "#334155", fontSize: 10 }}
                  tickFormatter={(v) => `${v}%`}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="column"
                  width={76}
                  tick={{ fill: "#64748b", fontSize: 11, fontFamily: "monospace" }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const d = payload[0].payload;
                    return (
                      <div
                        className="text-xs px-2.5 py-1.5 rounded-lg"
                        style={{
                          background: "#0d0d18",
                          border: "1px solid rgba(28,28,46,0.8)",
                          color: "#94a3b8",
                        }}
                      >
                        <strong style={{ color: "#f1f5f9" }}>{d.column}</strong>
                        <br />
                        {d.missing_count.toLocaleString()} missing ({d.missing_pct.toFixed(2)}%)
                      </div>
                    );
                  }}
                />
                <Bar dataKey="missing_pct" radius={[0, 4, 4, 0]}>
                  {missing.chart_data.map((d) => (
                    <Cell
                      key={d.column}
                      fill={
                        d.missing_pct > 50
                          ? "#f43f5e"
                          : d.missing_pct > 20
                          ? "#fbbf24"
                          : "#818cf8"
                      }
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}

function SummaryCard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub: string;
  color: string;
}) {
  return (
    <div
      className="px-4 py-3 rounded-xl flex flex-col gap-1"
      style={{
        background: "rgba(13,13,24,0.8)",
        border: "1px solid rgba(28,28,46,0.6)",
      }}
    >
      <span className="text-xs" style={{ color: "#475569" }}>
        {label}
      </span>
      <span className="text-xl font-semibold tabular" style={{ color }}>
        {value}
      </span>
      <span className="text-xs" style={{ color: "#334155" }}>
        {sub}
      </span>
    </div>
  );
}
