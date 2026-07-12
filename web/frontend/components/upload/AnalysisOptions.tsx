"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, Zap, SlidersHorizontal } from "lucide-react";
import type { AnalyzeOptions } from "@/lib/api";

interface Props {
  file: File;
  onSubmit: (options: AnalyzeOptions) => void;
  loading?: boolean;
}

export function AnalysisOptions({ file, onSubmit, loading }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [target, setTarget] = useState("");
  const [skipCorrelation, setSkipCorrelation] = useState(false);
  const [skipOutlier, setSkipOutlier] = useState(false);
  const [sampleSize, setSampleSize] = useState("");

  const handleSubmit = () => {
    onSubmit({
      skipCorrelation,
      skipOutlier,
      target: target.trim() || undefined,
      sampleSize: sampleSize ? parseInt(sampleSize) : undefined,
    });
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
      className="rounded-2xl overflow-hidden"
      style={{
        background: "rgba(13,13,24,0.8)",
        border: "1px solid rgba(28,28,46,0.8)",
        backdropFilter: "blur(12px)",
      }}
    >
      {/* File pill */}
      <div
        className="px-5 py-3 flex items-center gap-3"
        style={{ borderBottom: "1px solid rgba(28,28,46,0.6)" }}
      >
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
          style={{ background: "rgba(52,211,153,0.1)", border: "1px solid rgba(52,211,153,0.2)" }}
        >
          <span style={{ color: "#34d399", fontSize: 12 }}>✓</span>
        </div>
        <span className="text-sm font-medium truncate" style={{ color: "#94a3b8" }}>
          {file.name}
        </span>
        <span
          className="ml-auto text-xs shrink-0 font-mono"
          style={{ color: "#475569" }}
        >
          {(file.size / 1024).toFixed(0)} KB
        </span>
      </div>

      {/* Advanced toggle */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-5 py-3 flex items-center gap-2 text-xs transition-colors hover:bg-white/[0.02]"
        style={{ color: "#475569" }}
      >
        <SlidersHorizontal size={13} />
        Advanced options
        <motion.span
          animate={{ rotate: expanded ? 180 : 0 }}
          transition={{ duration: 0.2 }}
          className="ml-auto"
        >
          <ChevronDown size={13} />
        </motion.span>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div
              className="px-5 pb-4 flex flex-col gap-4"
              style={{ borderBottom: "1px solid rgba(28,28,46,0.6)" }}
            >
              {/* Target column */}
              <div className="flex flex-col gap-1.5">
                <label className="text-xs" style={{ color: "#64748b" }}>
                  Target column{" "}
                  <span style={{ color: "#334155" }}>(optional — for feature importance)</span>
                </label>
                <input
                  type="text"
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                  placeholder="e.g. survived, price, label"
                  className="w-full text-sm px-3 py-2 rounded-lg outline-none transition-colors font-mono placeholder:text-[#334155]"
                  style={{
                    background: "rgba(28,28,46,0.5)",
                    border: "1px solid rgba(42,42,64,0.6)",
                    color: "#e2e8f0",
                  }}
                  onFocus={(e) =>
                    (e.currentTarget.style.borderColor = "rgba(34,211,238,0.4)")
                  }
                  onBlur={(e) =>
                    (e.currentTarget.style.borderColor = "rgba(42,42,64,0.6)")
                  }
                />
              </div>

              {/* Sample size */}
              <div className="flex flex-col gap-1.5">
                <label className="text-xs" style={{ color: "#64748b" }}>
                  Sample size{" "}
                  <span style={{ color: "#334155" }}>(leave empty for full dataset)</span>
                </label>
                <input
                  type="number"
                  value={sampleSize}
                  onChange={(e) => setSampleSize(e.target.value)}
                  placeholder="e.g. 10000"
                  className="w-full text-sm px-3 py-2 rounded-lg outline-none transition-colors font-mono placeholder:text-[#334155]"
                  style={{
                    background: "rgba(28,28,46,0.5)",
                    border: "1px solid rgba(42,42,64,0.6)",
                    color: "#e2e8f0",
                  }}
                  onFocus={(e) =>
                    (e.currentTarget.style.borderColor = "rgba(34,211,238,0.4)")
                  }
                  onBlur={(e) =>
                    (e.currentTarget.style.borderColor = "rgba(42,42,64,0.6)")
                  }
                />
              </div>

              {/* Toggles */}
              <div className="flex gap-3">
                <Toggle
                  label="Skip correlation"
                  value={skipCorrelation}
                  onChange={setSkipCorrelation}
                />
                <Toggle
                  label="Skip outlier"
                  value={skipOutlier}
                  onChange={setSkipOutlier}
                />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* CTA */}
      <div className="px-5 py-4">
        <button
          onClick={handleSubmit}
          disabled={loading}
          className="w-full flex items-center justify-center gap-2.5 py-3 rounded-xl text-sm font-semibold transition-all active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
          style={{
            background: loading
              ? "rgba(34,211,238,0.15)"
              : "linear-gradient(135deg, rgba(34,211,238,0.9) 0%, rgba(129,140,248,0.9) 100%)",
            color: loading ? "#22d3ee" : "#06060d",
            boxShadow: loading ? "none" : "0 0 24px rgba(34,211,238,0.2)",
          }}
        >
          {loading ? (
            <>
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
                className="w-4 h-4 rounded-full"
                style={{ borderWidth: 2, borderStyle: "solid", borderColor: "transparent", borderTopColor: "#22d3ee" }}
              />
              Analyzing…
            </>
          ) : (
            <>
              <Zap size={15} strokeWidth={2.5} />
              Analyze
            </>
          )}
        </button>
      </div>
    </motion.div>
  );
}

function Toggle({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      onClick={() => onChange(!value)}
      className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs transition-all flex-1 justify-center"
      style={{
        background: value ? "rgba(34,211,238,0.08)" : "rgba(28,28,46,0.5)",
        border: `1px solid ${value ? "rgba(34,211,238,0.25)" : "rgba(42,42,64,0.5)"}`,
        color: value ? "#22d3ee" : "#475569",
      }}
    >
      <div
        className="w-3.5 h-3.5 rounded-sm border flex items-center justify-center transition-all"
        style={{
          borderColor: value ? "#22d3ee" : "#334155",
          background: value ? "#22d3ee" : "transparent",
        }}
      >
        {value && <span style={{ fontSize: 8, color: "#06060d", fontWeight: 900 }}>✓</span>}
      </div>
      {label}
    </button>
  );
}
