"use client";

import { motion } from "framer-motion";
import { ShieldCheck, ShieldAlert, ShieldX } from "lucide-react";
import type { Quality } from "@/lib/api";

interface Props {
  quality: Quality;
}

const SEVERITY_COLOR: Record<string, string> = {
  FATAL: "#f43f5e",
  WARNING: "#fbbf24",
  INFO: "#818cf8",
};

export function QualitySection({ quality }: Props) {
  const status = quality.passed
    ? quality.has_warnings
      ? "warnings"
      : "passed"
    : "failed";

  const statusConfig = {
    passed: {
      icon: ShieldCheck,
      label: "PASSED",
      color: "#34d399",
      bg: "rgba(52,211,153,0.08)",
      border: "rgba(52,211,153,0.2)",
    },
    warnings: {
      icon: ShieldAlert,
      label: "PASSED WITH WARNINGS",
      color: "#fbbf24",
      bg: "rgba(251,191,36,0.08)",
      border: "rgba(251,191,36,0.2)",
    },
    failed: {
      icon: ShieldX,
      label: "FAILED",
      color: "#f43f5e",
      bg: "rgba(244,63,94,0.08)",
      border: "rgba(244,63,94,0.2)",
    },
  }[status];

  const Icon = statusConfig.icon;

  return (
    <div className="flex flex-col gap-4">
      <SectionTitle>Data Quality</SectionTitle>

      {/* Status banner */}
      <div
        className="flex items-center gap-3 px-4 py-3 rounded-xl"
        style={{
          background: statusConfig.bg,
          border: `1px solid ${statusConfig.border}`,
        }}
      >
        <Icon size={18} style={{ color: statusConfig.color }} />
        <span className="text-sm font-semibold" style={{ color: statusConfig.color }}>
          {statusConfig.label}
        </span>
        {quality.issues.length === 0 && (
          <span className="ml-auto text-xs" style={{ color: "#475569" }}>
            No issues detected
          </span>
        )}
      </div>

      {/* Issues */}
      {quality.issues.length > 0 && (
        <div className="flex flex-col gap-2">
          {quality.issues.map((issue, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="flex gap-3 px-4 py-3 rounded-xl"
              style={{
                background: "rgba(13,13,24,0.8)",
                border: "1px solid rgba(28,28,46,0.6)",
              }}
            >
              <div
                className="w-1.5 h-1.5 rounded-full shrink-0 mt-1.5"
                style={{ background: SEVERITY_COLOR[issue.severity] ?? "#475569" }}
              />
              <div className="flex flex-col gap-0.5 min-w-0">
                <div className="flex items-center gap-2">
                  <span
                    className="text-xs font-mono uppercase tracking-wide"
                    style={{ color: SEVERITY_COLOR[issue.severity] ?? "#475569" }}
                  >
                    {issue.severity}
                  </span>
                  <span className="text-xs font-medium truncate" style={{ color: "#94a3b8" }}>
                    {issue.check}
                  </span>
                </div>
                <p className="text-xs" style={{ color: "#64748b" }}>
                  {issue.result}
                </p>
                <p className="text-xs" style={{ color: "#475569" }}>
                  → {issue.recommendation}
                </p>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}

export function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#475569" }}>
      {children}
    </h2>
  );
}
