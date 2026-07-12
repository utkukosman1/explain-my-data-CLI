"use client";

import { useState, Fragment } from "react";
import { motion } from "framer-motion";
import type { Correlation } from "@/lib/api";
import { SectionTitle } from "./QualitySection";

interface Props {
  correlation: Correlation;
}

export function CorrelationSection({ correlation }: Props) {
  const [view, setView] = useState<"pearson" | "spearman">("pearson");
  const matrix = view === "pearson" ? correlation.pearson : correlation.spearman;
  const cols = view === "pearson" ? correlation.pearson_columns : correlation.spearman_columns;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <SectionTitle>Correlation Analysis</SectionTitle>
        <div
          className="flex rounded-lg p-0.5 text-xs"
          style={{ background: "rgba(13,13,24,0.8)", border: "1px solid rgba(28,28,46,0.6)" }}
        >
          {(["pearson", "spearman"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className="px-3 py-1.5 rounded-md transition-all capitalize"
              style={{
                background: view === v ? "rgba(129,140,248,0.1)" : "transparent",
                color: view === v ? "#818cf8" : "#475569",
                border: view === v ? "1px solid rgba(129,140,248,0.2)" : "1px solid transparent",
              }}
            >
              {v}
            </button>
          ))}
        </div>
      </div>

      {/* Heatmap */}
      {matrix && cols.length > 0 && (
        <HeatmapGrid cells={matrix} columns={cols} />
      )}

      {/* Strong pairs */}
      {correlation.strong_pairs.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-xs font-medium" style={{ color: "#475569" }}>
            Strong correlations (|r| ≥ 0.7)
          </p>
          <div className="flex flex-col gap-1.5">
            {correlation.strong_pairs.map((pair, i) => (
              <motion.div
                key={`${pair.col_a}-${pair.col_b}`}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
                className="flex items-center gap-3 px-4 py-2.5 rounded-lg text-xs"
                style={{
                  background: "rgba(13,13,24,0.8)",
                  border: "1px solid rgba(28,28,46,0.6)",
                }}
              >
                <span className="font-mono" style={{ color: "#94a3b8" }}>{pair.col_a}</span>
                <span style={{ color: "#334155" }}>↔</span>
                <span className="font-mono" style={{ color: "#94a3b8" }}>{pair.col_b}</span>
                <div className="ml-auto flex items-center gap-2">
                  <span
                    className="font-mono tabular font-semibold"
                    style={{ color: pair.r > 0 ? "#34d399" : "#f43f5e" }}
                  >
                    {pair.r.toFixed(3)}
                  </span>
                  <span style={{ color: "#334155" }}>
                    {pair.label}
                  </span>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* VIF */}
      {correlation.vif && Object.keys(correlation.vif).length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-xs font-medium" style={{ color: "#475569" }}>
            Variance Inflation Factors (VIF)
          </p>
          <div className="grid grid-cols-2 gap-1.5">
            {Object.entries(correlation.vif)
              .filter(([, vif]) => vif != null)
              .sort(([, a], [, b]) => (b ?? 0) - (a ?? 0))
              .map(([col, vif]) => (
                <div
                  key={col}
                  className="flex items-center justify-between px-3 py-2 rounded-lg text-xs"
                  style={{
                    background: "rgba(13,13,24,0.8)",
                    border: `1px solid ${(vif ?? 0) > 10 ? "rgba(244,63,94,0.2)" : "rgba(28,28,46,0.6)"}`,
                  }}
                >
                  <span className="font-mono truncate" style={{ color: "#94a3b8" }}>{col}</span>
                  <span
                    className="tabular font-semibold ml-2 shrink-0"
                    style={{ color: (vif ?? 0) > 10 ? "#f43f5e" : (vif ?? 0) > 5 ? "#fbbf24" : "#34d399" }}
                  >
                    {(vif as number).toFixed(1)}
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

function HeatmapGrid({
  cells,
  columns,
}: {
  cells: { row: string; col: string; value: number | null }[];
  columns: string[];
}) {
  const [hovered, setHovered] = useState<string | null>(null);
  const size = columns.length;
  if (size === 0) return null;

  const cellSize = Math.min(44, Math.floor(580 / size));

  const valueColor = (v: number | null) => {
    if (v == null) return "rgba(28,28,46,0.4)";
    const abs = Math.abs(v);
    if (v > 0) return `rgba(34,211,238,${0.1 + abs * 0.85})`;
    return `rgba(244,63,94,${0.1 + abs * 0.85})`;
  };

  return (
    <div
      className="rounded-xl p-4 overflow-x-auto"
      style={{
        background: "rgba(13,13,24,0.8)",
        border: "1px solid rgba(28,28,46,0.6)",
      }}
    >
      <div style={{ display: "grid", gridTemplateColumns: `${cellSize}px repeat(${size}, ${cellSize}px)`, gap: 2 }}>
        {/* Top-left empty */}
        <div />
        {/* Column labels */}
        {columns.map((col) => (
          <div
            key={col}
            className="text-center"
            style={{ height: cellSize, display: "flex", alignItems: "flex-end", justifyContent: "center", paddingBottom: 4 }}
          >
            <span
              className="text-xs font-mono"
              style={{
                color: "#334155",
                fontSize: Math.max(9, Math.min(11, cellSize * 0.25)),
                writingMode: size > 6 ? "vertical-rl" : "horizontal-tb",
                transform: size > 6 ? "rotate(180deg)" : undefined,
                whiteSpace: "nowrap",
                overflow: "hidden",
                maxWidth: cellSize,
                textOverflow: "ellipsis",
              }}
            >
              {col.length > 8 ? col.slice(0, 8) + "…" : col}
            </span>
          </div>
        ))}

        {/* Rows */}
        {columns.map((rowCol) => (
          <Fragment key={rowCol}>
            {/* Row label */}
            <div
              style={{ height: cellSize, display: "flex", alignItems: "center", justifyContent: "flex-end", paddingRight: 6 }}
            >
              <span
                className="font-mono"
                style={{
                  color: "#334155",
                  fontSize: Math.max(9, Math.min(11, cellSize * 0.25)),
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  maxWidth: cellSize * 2,
                  textOverflow: "ellipsis",
                }}
              >
                {rowCol.length > 8 ? rowCol.slice(0, 8) + "…" : rowCol}
              </span>
            </div>

            {/* Cells */}
            {columns.map((colCol) => {
              const cell = cells.find((c) => c.row === rowCol && c.col === colCol);
              const v = cell?.value ?? null;
              const key = `${rowCol}-${colCol}`;

              return (
                <motion.div
                  key={key}
                  onMouseEnter={() => setHovered(key)}
                  onMouseLeave={() => setHovered(null)}
                  title={v != null ? `${rowCol} × ${colCol}: ${v.toFixed(3)}` : ""}
                  style={{
                    width: cellSize,
                    height: cellSize,
                    background: valueColor(v),
                    borderRadius: 4,
                    cursor: "default",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    border: hovered === key ? "1px solid rgba(255,255,255,0.2)" : "1px solid transparent",
                  }}
                  whileHover={{ scale: 1.15 }}
                  transition={{ duration: 0.1 }}
                >
                  {cellSize >= 36 && v != null && (
                    <span style={{ fontSize: 9, color: "rgba(255,255,255,0.7)", fontFamily: "monospace" }}>
                      {v.toFixed(2)}
                    </span>
                  )}
                </motion.div>
              );
            })}
          </Fragment>
        ))}
      </div>
    </div>
  );
}
