"use client";

import type { Overview } from "@/lib/api";
import { SectionTitle } from "./QualitySection";

interface Props {
  overview: Overview;
}

export function OverviewSection({ overview }: Props) {
  const numericCols = overview.columns.filter((c) =>
    ["int64", "float64", "int32", "float32"].some((t) => c.dtype.includes(t))
  );
  const catCols = overview.columns.filter((c) => c.dtype === "object" || c.dtype === "category");
  const colsWithMissing = overview.columns.filter((c) => c.null_pct > 0);

  return (
    <div className="flex flex-col gap-5">
      <SectionTitle>Dataset Overview</SectionTitle>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-3">
        <StatCard label="Rows" value={overview.rows.toLocaleString()} accent="#22d3ee" />
        <StatCard label="Columns" value={String(overview.cols)} accent="#818cf8" />
        <StatCard label="Numeric" value={String(numericCols.length)} accent="#34d399" />
        <StatCard label="Memory" value={`${overview.memory_kb} KB`} accent="#fbbf24" />
      </div>

      {/* Column table */}
      <div
        className="rounded-xl overflow-hidden"
        style={{ border: "1px solid rgba(28,28,46,0.6)" }}
      >
        {/* Header */}
        <div
          className="grid text-xs font-medium px-4 py-2.5"
          style={{
            gridTemplateColumns: "2fr 1fr 1fr 1fr",
            background: "rgba(13,13,24,0.8)",
            borderBottom: "1px solid rgba(28,28,46,0.6)",
            color: "#475569",
          }}
        >
          <span>Column</span>
          <span>Type</span>
          <span>Non-null</span>
          <span>Missing</span>
        </div>

        {/* Rows */}
        {overview.columns.map((col, i) => (
          <div
            key={col.name}
            className="grid items-center px-4 py-2.5 text-xs transition-colors hover:bg-white/[0.015]"
            style={{
              gridTemplateColumns: "2fr 1fr 1fr 1fr",
              borderBottom:
                i < overview.columns.length - 1
                  ? "1px solid rgba(28,28,46,0.4)"
                  : "none",
            }}
          >
            <span
              className="font-mono font-medium truncate"
              style={{ color: "#e2e8f0" }}
            >
              {col.name}
            </span>
            <span
              className="font-mono text-xs px-2 py-0.5 rounded w-fit"
              style={{
                background: "rgba(28,28,46,0.6)",
                color: dtypeColor(col.dtype),
                border: "1px solid rgba(42,42,64,0.4)",
              }}
            >
              {shortDtype(col.dtype)}
            </span>
            <span className="tabular" style={{ color: "#64748b" }}>
              {col.non_null.toLocaleString()}
            </span>
            <div className="flex items-center gap-2">
              {col.null_pct > 0 ? (
                <>
                  <div
                    className="h-1 rounded-full flex-1 max-w-12"
                    style={{ background: "rgba(28,28,46,0.8)" }}
                  >
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${col.null_pct}%`,
                        background: col.null_pct > 30 ? "#f43f5e" : "#fbbf24",
                      }}
                    />
                  </div>
                  <span className="tabular" style={{ color: "#fbbf24" }}>
                    {col.null_pct.toFixed(1)}%
                  </span>
                </>
              ) : (
                <span style={{ color: "#334155" }}>—</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent: string;
}) {
  return (
    <div
      className="flex flex-col gap-1.5 px-4 py-3 rounded-xl"
      style={{
        background: "rgba(13,13,24,0.8)",
        border: "1px solid rgba(28,28,46,0.6)",
      }}
    >
      <span className="text-xs" style={{ color: "#475569" }}>
        {label}
      </span>
      <span
        className="text-xl font-semibold tabular"
        style={{ color: accent }}
      >
        {value}
      </span>
    </div>
  );
}

function shortDtype(dtype: string): string {
  if (dtype.includes("float")) return "float";
  if (dtype.includes("int")) return "int";
  if (dtype === "object") return "str";
  if (dtype === "bool") return "bool";
  if (dtype.includes("datetime")) return "date";
  return dtype.slice(0, 6);
}

function dtypeColor(dtype: string): string {
  if (dtype.includes("float") || dtype.includes("int")) return "#22d3ee";
  if (dtype === "object") return "#818cf8";
  if (dtype === "bool") return "#34d399";
  if (dtype.includes("datetime")) return "#fbbf24";
  return "#64748b";
}
