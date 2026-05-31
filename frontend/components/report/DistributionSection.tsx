"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { ChevronDown, ChevronUp, AlertCircle } from "lucide-react";
import type { Distribution, NumericCol, CategoricalCol } from "@/lib/api";
import { SectionTitle } from "./QualitySection";

interface Props {
  distribution: Distribution;
}

export function DistributionSection({ distribution }: Props) {
  const [tab, setTab] = useState<"numeric" | "categorical">("numeric");

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <SectionTitle>Distribution Analysis</SectionTitle>
        <div
          className="flex rounded-lg p-0.5 text-xs"
          style={{ background: "rgba(13,13,24,0.8)", border: "1px solid rgba(28,28,46,0.6)" }}
        >
          {(["numeric", "categorical"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className="px-3 py-1.5 rounded-md transition-all capitalize"
              style={{
                background: tab === t ? "rgba(34,211,238,0.1)" : "transparent",
                color: tab === t ? "#22d3ee" : "#475569",
                border: tab === t ? "1px solid rgba(34,211,238,0.2)" : "1px solid transparent",
              }}
            >
              {t} ({t === "numeric" ? distribution.numeric.length : distribution.categorical.length})
            </button>
          ))}
        </div>
      </div>

      <AnimatePresence mode="wait">
        {tab === "numeric" ? (
          <motion.div
            key="numeric"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 8 }}
            transition={{ duration: 0.2 }}
            className="grid gap-3 sm:grid-cols-2"
          >
            {distribution.numeric.map((col) => (
              <NumericCard key={col.name} col={col} />
            ))}
          </motion.div>
        ) : (
          <motion.div
            key="categorical"
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
            transition={{ duration: 0.2 }}
            className="grid gap-3 sm:grid-cols-2"
          >
            {distribution.categorical.map((col) => (
              <CategoricalCard key={col.name} col={col} />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function NumericCard({ col }: { col: NumericCol }) {
  const [open, setOpen] = useState(false);
  const hasAssumptions = col.assumptions.length > 0;

  const fmt = (v: number | null) =>
    v == null ? "—" : Math.abs(v) > 999 || (Math.abs(v) < 0.001 && v !== 0)
      ? v.toExponential(2)
      : v.toPrecision(4).replace(/\.?0+$/, "");

  return (
    <div
      className="rounded-xl overflow-hidden flex flex-col"
      style={{
        background: "rgba(13,13,24,0.8)",
        border: "1px solid rgba(28,28,46,0.6)",
      }}
    >
      {/* Header */}
      <div
        className="px-4 pt-3 pb-2 flex items-start justify-between"
        style={{ borderBottom: "1px solid rgba(28,28,46,0.4)" }}
      >
        <div>
          <p className="text-sm font-medium font-mono" style={{ color: "#e2e8f0" }}>
            {col.name}
          </p>
          <p className="text-xs mt-0.5" style={{ color: "#475569" }}>
            {col.count.toLocaleString()} values · {col.null_pct.toFixed(1)}% missing
          </p>
        </div>
        {hasAssumptions && (
          <AlertCircle size={13} style={{ color: "#fbbf24", flexShrink: 0 }} />
        )}
      </div>

      {/* Histogram */}
      <div className="px-2 pt-3 pb-1" style={{ height: 100 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={col.chart_data} barCategoryGap={1}>
            <Bar dataKey="count" radius={[2, 2, 0, 0]}>
              {col.chart_data.map((_, i) => (
                <Cell
                  key={i}
                  fill={`rgba(34,211,238,${0.3 + (i / col.chart_data.length) * 0.5})`}
                />
              ))}
            </Bar>
            <XAxis hide />
            <YAxis hide />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0].payload;
                return (
                  <div
                    className="text-xs px-2 py-1.5 rounded-lg"
                    style={{
                      background: "#0d0d18",
                      border: "1px solid rgba(28,28,46,0.8)",
                      color: "#94a3b8",
                    }}
                  >
                    <span style={{ color: "#22d3ee" }}>{d.bin}</span>
                    <br />
                    count: <strong style={{ color: "#f1f5f9" }}>{d.count}</strong>
                  </div>
                );
              }}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Stats row */}
      <div className="px-4 pb-3 grid grid-cols-4 gap-2 text-center">
        {[
          { l: "mean", v: fmt(col.mean) },
          { l: "std", v: fmt(col.std) },
          { l: "skew", v: fmt(col.skewness) },
          { l: "kurt", v: fmt(col.excess_kurtosis) },
        ].map(({ l, v }) => (
          <div key={l}>
            <p className="text-xs" style={{ color: "#334155" }}>{l}</p>
            <p className="text-xs font-mono tabular" style={{ color: "#94a3b8" }}>{v}</p>
          </div>
        ))}
      </div>

      {/* Assumptions expandable */}
      {hasAssumptions && (
        <>
          <button
            onClick={() => setOpen(!open)}
            className="px-4 py-2 flex items-center gap-1.5 text-xs transition-colors hover:bg-white/[0.02] w-full"
            style={{
              borderTop: "1px solid rgba(28,28,46,0.4)",
              color: "#fbbf24",
            }}
          >
            {open ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
            {col.assumptions.length} assumption note{col.assumptions.length > 1 ? "s" : ""}
          </button>
          <AnimatePresence>
            {open && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden"
              >
                <div className="px-4 pb-3 flex flex-col gap-2">
                  {col.assumptions.map((note, i) => (
                    <p
                      key={i}
                      className="text-xs leading-relaxed"
                      style={{ color: "#64748b" }}
                    >
                      {note}
                    </p>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </>
      )}
    </div>
  );
}

function CategoricalCard({ col }: { col: CategoricalCol }) {
  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{
        background: "rgba(13,13,24,0.8)",
        border: "1px solid rgba(28,28,46,0.6)",
      }}
    >
      <div
        className="px-4 pt-3 pb-2"
        style={{ borderBottom: "1px solid rgba(28,28,46,0.4)" }}
      >
        <p className="text-sm font-medium font-mono" style={{ color: "#e2e8f0" }}>
          {col.name}
        </p>
        <p className="text-xs mt-0.5" style={{ color: "#475569" }}>
          {col.unique_count} unique · entropy {col.entropy.toFixed(2)}
        </p>
      </div>

      {/* Horizontal bar chart */}
      <div className="px-4 py-3 flex flex-col gap-1.5">
        {col.chart_data.slice(0, 6).map((bar, i) => (
          <div key={bar.value} className="flex items-center gap-2">
            <span
              className="text-xs font-mono truncate w-20 shrink-0 text-right"
              style={{ color: "#64748b" }}
            >
              {bar.value}
            </span>
            <div
              className="flex-1 h-1.5 rounded-full overflow-hidden"
              style={{ background: "rgba(28,28,46,0.6)" }}
            >
              <motion.div
                className="h-full rounded-full"
                initial={{ width: 0 }}
                animate={{ width: `${bar.pct}%` }}
                transition={{ duration: 0.5, delay: i * 0.04, ease: "easeOut" }}
                style={{
                  background: `rgba(129,140,248,${0.4 + (1 - i / 6) * 0.5})`,
                }}
              />
            </div>
            <span
              className="text-xs tabular w-10 shrink-0"
              style={{ color: "#475569" }}
            >
              {bar.pct.toFixed(1)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
