"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { Outlier } from "@/lib/api";
import { SectionTitle } from "./QualitySection";

interface Props {
  outlier: Outlier;
}

const METHOD_COLORS: Record<string, string> = {
  IQR: "#22d3ee",
  IQR_extreme: "#818cf8",
  Z_score: "#fbbf24",
  Modified_Z: "#f43f5e",
};

export function OutlierSection({ outlier }: Props) {
  const hasOutliers = outlier.chart_data.some(
    (d) => d.IQR > 0 || d.Z_score > 0 || d.Modified_Z > 0
  );

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <SectionTitle>Outlier Detection</SectionTitle>
        <div className="flex items-center gap-2">
          {outlier.methods_used.map((m) => (
            <span
              key={m}
              className="text-xs px-2 py-0.5 rounded font-mono"
              style={{
                background: "rgba(28,28,46,0.6)",
                border: "1px solid rgba(42,42,64,0.4)",
                color: "#475569",
              }}
            >
              {m}
            </span>
          ))}
        </div>
      </div>

      {!hasOutliers ? (
        <div
          className="px-4 py-3 rounded-xl text-sm"
          style={{
            background: "rgba(52,211,153,0.08)",
            border: "1px solid rgba(52,211,153,0.2)",
            color: "#34d399",
          }}
        >
          ✓ No significant outliers detected
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
            Outlier count by column and method
          </p>
          <div style={{ height: Math.max(200, outlier.chart_data.length * 48) }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={outlier.chart_data}
                margin={{ left: 80, right: 20, top: 4, bottom: 4 }}
                layout="vertical"
                barSize={8}
                barGap={2}
              >
                <XAxis
                  type="number"
                  tick={{ fill: "#334155", fontSize: 10 }}
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
                  cursor={{ fill: "rgba(255,255,255,0.02)" }}
                  content={({ active, payload, label }) => {
                    if (!active || !payload?.length) return null;
                    return (
                      <div
                        className="text-xs px-3 py-2 rounded-lg flex flex-col gap-1"
                        style={{
                          background: "#0d0d18",
                          border: "1px solid rgba(28,28,46,0.8)",
                        }}
                      >
                        <strong style={{ color: "#f1f5f9" }}>{label}</strong>
                        {payload.map((p) => (
                          <div key={p.name} className="flex items-center gap-2">
                            <div
                              className="w-2 h-2 rounded-full"
                              style={{ background: p.fill as string }}
                            />
                            <span style={{ color: "#64748b" }}>{p.name}:</span>
                            <span style={{ color: "#f1f5f9" }}>{p.value}</span>
                          </div>
                        ))}
                      </div>
                    );
                  }}
                />
                <Legend
                  wrapperStyle={{ fontSize: 11, color: "#475569" }}
                  iconType="circle"
                  iconSize={8}
                />
                {["IQR", "Z_score", "Modified_Z"].map((method) => (
                  <Bar
                    key={method}
                    dataKey={method}
                    fill={METHOD_COLORS[method]}
                    radius={[0, 3, 3, 0]}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
