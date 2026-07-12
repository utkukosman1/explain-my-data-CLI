"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { BarChart2, Link2, Minus, Activity, Target, TrendingUp, ChevronDown, ChevronUp, Download, FileText } from "lucide-react";
import { MarkdownViewer } from "./MarkdownViewer";
import type { AnalysisResult } from "@/lib/api";
import { QualitySection } from "./QualitySection";
import { OverviewSection } from "./OverviewSection";
import { DistributionSection } from "./DistributionSection";
import { CorrelationSection } from "./CorrelationSection";
import { MissingSection } from "./MissingSection";
import { OutlierSection } from "./OutlierSection";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Props {
  result: AnalysisResult;
  jobId: string;
}

type SectionId = "distribution" | "correlation" | "missing" | "outlier" | "target";

interface SectionDef {
  id: SectionId;
  label: string;
  icon: React.ElementType;
  color: string;
  available: boolean;
}

export function ReportLayout({ result, jobId }: Props) {
  const [open, setOpen] = useState<Set<SectionId>>(new Set());
  const [showReport, setShowReport] = useState(false);

  const toggle = (id: SectionId) => {
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const sections: SectionDef[] = (
    [
      { id: "distribution" as SectionId, label: "Distribution", icon: BarChart2,  color: "#22d3ee", available: true },
      { id: "correlation"  as SectionId, label: "Correlation",  icon: Link2,      color: "#818cf8", available: result.correlation !== null },
      { id: "missing"      as SectionId, label: "Missing",      icon: Minus,      color: "#fbbf24", available: result.missing.total_missing > 0 },
      { id: "outlier"      as SectionId, label: "Outliers",     icon: Activity,   color: "#f43f5e", available: result.outlier !== null },
      { id: "target"       as SectionId, label: `Target · ${result.target?.target_col ?? ""}`, icon: TrendingUp, color: "#34d399", available: result.target !== null },
    ] as SectionDef[]
  ).filter((s) => s.available);

  return (
    <div className="min-h-dvh px-6 py-8 max-w-3xl mx-auto flex flex-col gap-8" style={{ position: "relative", zIndex: 1 }}>

      {/* Always visible: Quality + Overview */}
      <FadeIn delay={0}>
        <QualitySection quality={result.quality} />
      </FadeIn>

      <FadeIn delay={0.08}>
        <OverviewSection overview={result.overview} />
      </FadeIn>

      {/* Section toggle buttons */}
      <FadeIn delay={0.15}>
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <p className="text-xs uppercase tracking-widest" style={{ color: "#2a2a40" }}>
              Deep dive
            </p>
            <button
              onClick={() => setShowReport(!showReport)}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-all hover:bg-white/[0.04] active:scale-95"
              style={{
                color: showReport ? "#22d3ee" : "#475569",
                border: `1px solid ${showReport ? "rgba(34,211,238,0.25)" : "rgba(28,28,46,0.8)"}`,
                background: showReport ? "rgba(34,211,238,0.06)" : "transparent",
              }}
            >
              <FileText size={11} />
              {showReport ? "Hide report" : "View full report"}
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {sections.map(({ id, label, icon: Icon, color }) => {
              const isOpen = open.has(id);
              return (
                <button
                  key={id}
                  onClick={() => toggle(id)}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all active:scale-[0.97]"
                  style={{
                    background: isOpen ? `${color}12` : "rgba(13,13,24,0.8)",
                    border: `1px solid ${isOpen ? `${color}35` : "rgba(28,28,46,0.7)"}`,
                    color: isOpen ? color : "#475569",
                    boxShadow: isOpen ? `0 0 16px ${color}10` : "none",
                  }}
                >
                  <Icon size={13} strokeWidth={isOpen ? 2.5 : 2} />
                  {label}
                  <motion.span
                    animate={{ rotate: isOpen ? 45 : 0 }}
                    transition={{ duration: 0.2 }}
                    className="text-xs leading-none"
                    style={{ opacity: 0.5 }}
                  >
                    +
                  </motion.span>
                </button>
              );
            })}
          </div>
        </div>
      </FadeIn>

      {/* Full markdown report viewer */}
      <AnimatePresence>
        {showReport && result._markdown && (
          <motion.div
            key="report-viewer"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.35, ease: [0.25, 0.46, 0.45, 0.94] }}
            className="overflow-hidden"
          >
            <MarkdownViewer
              markdown={result._markdown}
              downloadHref={`${BASE}/api/jobs/${jobId}/report`}
              filename={result.overview.filename}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Expandable sections */}
      <div className="flex flex-col gap-6">
        <AnimatePresence initial={false}>
          {sections
            .filter(({ id }) => open.has(id))
            .map(({ id, color }) => (
              <motion.div
                key={id}
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
                className="overflow-hidden"
              >
                <div
                  className="h-px mb-6 rounded-full"
                  style={{ background: `linear-gradient(90deg, ${color}30, transparent)` }}
                />
                <SectionContent id={id} result={result} />
              </motion.div>
            ))}
        </AnimatePresence>
      </div>
    </div>
  );
}

function TargetCard({ target }: { target: NonNullable<AnalysisResult["target"]> }) {
  const [showAll, setShowAll] = useState(false);
  const topScore = target.all_features[0]?.score ?? target.top_features[0]?.score ?? 0;
  const restFeatures = target.all_features.slice(5);

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{ border: "1px solid rgba(52,211,153,0.2)", background: "rgba(13,13,24,0.8)" }}
    >
      {/* Header */}
      <div
        className="px-5 py-3 flex items-center gap-3"
        style={{
          background: "rgba(52,211,153,0.06)",
          borderBottom: "1px solid rgba(52,211,153,0.12)",
        }}
      >
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
          style={{ background: "rgba(52,211,153,0.12)", border: "1px solid rgba(52,211,153,0.2)" }}
        >
          <TrendingUp size={14} style={{ color: "#34d399" }} />
        </div>
        <div>
          <p className="text-sm font-semibold" style={{ color: "#34d399" }}>
            Target Analysis
          </p>
          <p className="text-xs" style={{ color: "#475569" }}>
            <span className="font-mono" style={{ color: "#64748b" }}>{target.target_col}</span>
            {" · "}
            {target.target_type}
            {" · "}
            {target.all_features.length} features ranked
          </p>
        </div>
      </div>

      {/* Top 5 features */}
      <div className="px-5 py-4 flex flex-col gap-2">
        <p className="text-xs mb-1" style={{ color: "#334155" }}>Top 5 by correlation</p>
        {target.top_features.map((f, i) => (
          <FeatureRow key={f.feature} f={f} i={i} topScore={topScore} />
        ))}
      </div>

      {/* All features expandable */}
      {restFeatures.length > 0 && (
        <>
          <button
            onClick={() => setShowAll(!showAll)}
            className="w-full px-5 py-2.5 flex items-center gap-2 text-xs transition-colors hover:bg-white/[0.02]"
            style={{
              borderTop: "1px solid rgba(28,28,46,0.4)",
              color: "#475569",
            }}
          >
            {showAll ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
            {showAll ? "Hide" : `Show all ${target.all_features.length} features`}
          </button>

          <AnimatePresence>
            {showAll && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.25, ease: "easeInOut" }}
                className="overflow-hidden"
              >
                <div className="px-5 pb-4 flex flex-col gap-2">
                  {restFeatures.map((f, i) => (
                    <FeatureRow key={f.feature} f={f} i={i + 5} topScore={topScore} muted />
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </>
      )}

      {/* Warnings */}
      {target.warnings.length > 0 && (
        <div
          className="px-5 pb-4 flex flex-col gap-1"
          style={{ borderTop: "1px solid rgba(28,28,46,0.4)" }}
        >
          {target.warnings.map((w, i) => (
            <p key={i} className="text-xs pt-3" style={{ color: "#475569" }}>
              ⚠ {w}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

function FeatureRow({
  f,
  i,
  topScore,
  muted = false,
}: {
  f: { feature: string; score: number; method: string; direction: string };
  i: number;
  topScore: number;
  muted?: boolean;
}) {
  const barWidth = topScore > 0 ? (Math.abs(f.score) / topScore) * 100 : 0;
  const isPositive = f.direction !== "negative";

  return (
    <div className="flex items-center gap-3">
      <span className="text-xs w-5 shrink-0 text-right tabular" style={{ color: "#334155" }}>
        {i + 1}
      </span>
      <span
        className="font-mono text-xs font-medium w-32 shrink-0 truncate"
        style={{ color: muted ? "#64748b" : "#e2e8f0" }}
      >
        {f.feature}
      </span>
      <div
        className="flex-1 h-1.5 rounded-full overflow-hidden"
        style={{ background: "rgba(28,28,46,0.8)" }}
      >
        <motion.div
          className="h-full rounded-full"
          initial={{ width: 0 }}
          animate={{ width: `${barWidth}%` }}
          transition={{ duration: 0.4, ease: "easeOut" }}
          style={{
            background: muted
              ? "rgba(100,116,139,0.5)"
              : isPositive
              ? "linear-gradient(90deg, #34d399, #22d3ee)"
              : "linear-gradient(90deg, #f43f5e, #fbbf24)",
            opacity: muted ? 0.6 : 1,
          }}
        />
      </div>
      <span
        className="text-xs tabular font-mono w-16 shrink-0 text-right"
        style={{ color: muted ? "#475569" : isPositive ? "#34d399" : "#f43f5e" }}
      >
        {f.score.toFixed(4)}
      </span>
      <span
        className="text-xs shrink-0 hidden sm:block"
        style={{ color: "#2a2a40", width: 80 }}
      >
        {f.method}
      </span>
    </div>
  );
}

function SectionContent({ id, result }: { id: SectionId; result: AnalysisResult }) {
  switch (id) {
    case "distribution":
      return <DistributionSection distribution={result.distribution} />;
    case "correlation":
      return <CorrelationSection correlation={result.correlation!} />;
    case "missing":
      return <MissingSection missing={result.missing} />;
    case "outlier":
      return <OutlierSection outlier={result.outlier!} />;
    case "target":
      return <TargetCard target={result.target!} />;
  }
}

function FadeIn({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay, ease: [0.25, 0.46, 0.45, 0.94] }}
    >
      {children}
    </motion.div>
  );
}
