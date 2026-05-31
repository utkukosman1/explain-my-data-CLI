"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { DriftResult, DriftColumn } from "@/lib/api";

interface Props {
  result: DriftResult;
}

const SEVERITY_STYLE = {
  high:     { color: "#f43f5e", bg: "rgba(244,63,94,0.08)",  border: "rgba(244,63,94,0.25)",  label: "HIGH" },
  moderate: { color: "#fbbf24", bg: "rgba(251,191,36,0.08)", border: "rgba(251,191,36,0.25)", label: "MODERATE" },
  none:     { color: "#34d399", bg: "rgba(52,211,153,0.06)", border: "rgba(52,211,153,0.15)", label: "STABLE" },
};

export function DriftReport({ result }: Props) {
  const s = result.summary;
  const hasDrift = s.overall_drift;

  return (
    <div className="flex flex-col gap-8">
      {/* Banner */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-4 px-5 py-4 rounded-2xl"
        style={{
          background: hasDrift ? "rgba(244,63,94,0.07)" : "rgba(52,211,153,0.07)",
          border: `1px solid ${hasDrift ? "rgba(244,63,94,0.25)" : "rgba(52,211,153,0.2)"}`,
        }}
      >
        <span style={{ fontSize: 24 }}>{hasDrift ? "⚡" : "✓"}</span>
        <div>
          <p className="text-sm font-semibold" style={{ color: hasDrift ? "#f43f5e" : "#34d399" }}>
            {hasDrift
              ? `Data drift detected — ${s.drifted_count} of ${s.total_columns} columns`
              : "No significant drift detected"}
          </p>
          <p className="text-xs mt-0.5" style={{ color: "#475569" }}>
            {result.ref_name} → {result.cur_name} · PSI threshold {s.psi_threshold}
          </p>
        </div>
      </motion.div>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-3">
        <SummaryCard
          label="Reference rows"
          value={s.reference_shape[0].toLocaleString()}
          color="#22d3ee"
        />
        <SummaryCard
          label="Current rows"
          value={s.current_shape[0].toLocaleString()}
          color="#818cf8"
        />
        <SummaryCard
          label="Drifted"
          value={`${s.drifted_count} / ${s.total_columns}`}
          color={s.drifted_count > 0 ? "#f43f5e" : "#34d399"}
        />
        <SummaryCard
          label="Drift fraction"
          value={`${(s.drift_fraction * 100).toFixed(1)}%`}
          color={s.drift_fraction > 0.3 ? "#f43f5e" : s.drift_fraction > 0 ? "#fbbf24" : "#34d399"}
        />
      </div>

      {/* Schema changes */}
      {(s.missing_in_current.length > 0 || s.new_in_current.length > 0) && (
        <div className="flex flex-col gap-2">
          {s.missing_in_current.length > 0 && (
            <SchemaAlert
              label="Columns removed in current"
              cols={s.missing_in_current}
              color="#f43f5e"
            />
          )}
          {s.new_in_current.length > 0 && (
            <SchemaAlert
              label="New columns in current"
              cols={s.new_in_current}
              color="#fbbf24"
            />
          )}
        </div>
      )}

      {/* Column table */}
      <div className="flex flex-col gap-2">
        <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#475569" }}>
          Column-level drift
        </p>
        <div
          className="rounded-xl overflow-hidden"
          style={{ border: "1px solid rgba(28,28,46,0.6)" }}
        >
          {/* Header */}
          <div
            className="grid text-xs font-medium px-4 py-2.5"
            style={{
              gridTemplateColumns: "2fr 80px 90px 90px 90px 80px",
              background: "rgba(13,13,24,0.9)",
              borderBottom: "1px solid rgba(28,28,46,0.6)",
              color: "#475569",
            }}
          >
            <span>Column</span>
            <span>Type</span>
            <span>PSI</span>
            <span>KS p-val</span>
            <span>Mean shift</span>
            <span>Severity</span>
          </div>

          {result.columns.map((col, i) => (
            <DriftRow
              key={col.name}
              col={col}
              hasChart={!!result.chart_data[col.name]}
              chartData={result.chart_data[col.name] ?? []}
              isLast={i === result.columns.length - 1}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function DriftRow({
  col,
  hasChart,
  chartData,
  isLast,
}: {
  col: DriftColumn;
  hasChart: boolean;
  chartData: { bin: string; x: number; reference: number; current: number }[];
  isLast: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const style = SEVERITY_STYLE[col.drift_severity];
  const fmt = (v: number | null, decimals = 3) =>
    v == null ? "—" : v.toFixed(decimals);

  return (
    <>
      <motion.div
        className="grid items-center px-4 py-2.5 text-xs cursor-pointer hover:bg-white/[0.015] transition-colors"
        style={{
          gridTemplateColumns: "2fr 80px 90px 90px 90px 80px",
          borderBottom: isLast && !expanded ? "none" : "1px solid rgba(28,28,46,0.35)",
          background: col.drift_detected ? `${style.bg}` : "transparent",
        }}
        onClick={() => hasChart && setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          <span className="font-mono font-medium truncate" style={{ color: "#e2e8f0" }}>
            {col.name}
          </span>
          {hasChart && (
            <span style={{ color: "#334155" }}>
              {expanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
            </span>
          )}
        </div>
        <span
          className="font-mono text-xs px-1.5 py-0.5 rounded w-fit"
          style={{
            background: "rgba(28,28,46,0.6)",
            border: "1px solid rgba(42,42,64,0.4)",
            color: col.col_type === "numeric" ? "#22d3ee" : "#818cf8",
          }}
        >
          {col.col_type}
        </span>
        <span className="tabular font-mono" style={{ color: col.psi != null && col.psi >= 0.2 ? "#f43f5e" : col.psi != null && col.psi >= 0.1 ? "#fbbf24" : "#64748b" }}>
          {fmt(col.psi)}
        </span>
        <span className="tabular font-mono" style={{ color: col.ks_pvalue != null && col.ks_pvalue < 0.05 ? "#fbbf24" : "#64748b" }}>
          {fmt(col.ks_pvalue)}
        </span>
        <span className="tabular font-mono" style={{ color: "#64748b" }}>
          {col.mean_shift_pct != null ? `${col.mean_shift_pct.toFixed(1)}%` : "—"}
        </span>
        <span
          className="text-xs font-semibold px-2 py-0.5 rounded-full w-fit"
          style={{ background: style.bg, color: style.color, border: `1px solid ${style.border}` }}
        >
          {style.label}
        </span>
      </motion.div>

      {/* Overlay chart */}
      <AnimatePresence>
        {expanded && hasChart && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="overflow-hidden"
            style={{ borderBottom: isLast ? "none" : "1px solid rgba(28,28,46,0.35)" }}
          >
            <div className="px-4 py-4" style={{ background: "rgba(9,9,17,0.6)" }}>
              <p className="text-xs mb-3" style={{ color: "#475569" }}>
                Distribution overlay — {col.name}
              </p>
              <div style={{ height: 160 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ left: 0, right: 0, top: 4, bottom: 0 }}>
                    <defs>
                      <linearGradient id="refGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#22d3ee" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="curGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#818cf8" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#818cf8" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis
                      dataKey="bin"
                      hide
                    />
                    <YAxis hide />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (!active || !payload?.length) return null;
                        const d = payload[0].payload;
                        return (
                          <div
                            className="text-xs px-2.5 py-2 rounded-lg flex flex-col gap-1"
                            style={{ background: "#0d0d18", border: "1px solid rgba(28,28,46,0.8)" }}
                          >
                            <span style={{ color: "#64748b" }}>{d.bin}</span>
                            <span style={{ color: "#22d3ee" }}>ref: {d.reference}</span>
                            <span style={{ color: "#818cf8" }}>cur: {d.current}</span>
                          </div>
                        );
                      }}
                    />
                    <Legend
                      wrapperStyle={{ fontSize: 10, color: "#475569" }}
                      iconType="circle"
                      iconSize={6}
                    />
                    <Area
                      type="monotone"
                      dataKey="reference"
                      stroke="#22d3ee"
                      strokeWidth={1.5}
                      fill="url(#refGrad)"
                      name="Reference"
                    />
                    <Area
                      type="monotone"
                      dataKey="current"
                      stroke="#818cf8"
                      strokeWidth={1.5}
                      fill="url(#curGrad)"
                      name="Current"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

function SummaryCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div
      className="px-4 py-3 rounded-xl flex flex-col gap-1"
      style={{ background: "rgba(13,13,24,0.8)", border: "1px solid rgba(28,28,46,0.6)" }}
    >
      <span className="text-xs" style={{ color: "#475569" }}>{label}</span>
      <span className="text-xl font-semibold tabular" style={{ color }}>{value}</span>
    </div>
  );
}

function SchemaAlert({ label, cols, color }: { label: string; cols: string[]; color: string }) {
  return (
    <div
      className="flex items-start gap-3 px-4 py-3 rounded-xl text-xs"
      style={{ background: `${color}09`, border: `1px solid ${color}25` }}
    >
      <span style={{ color }}>⚠</span>
      <div>
        <span className="font-medium" style={{ color }}>{label}: </span>
        <span className="font-mono" style={{ color: "#64748b" }}>{cols.join(", ")}</span>
      </div>
    </div>
  );
}
