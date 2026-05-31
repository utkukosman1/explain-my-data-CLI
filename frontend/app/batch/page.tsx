"use client";

import { motion } from "framer-motion";
import { ArrowLeft } from "lucide-react";
import { BatchQueue } from "@/components/batch/BatchQueue";

export default function BatchPage() {
  return (
    <div
      className="min-h-dvh flex flex-col items-center justify-center px-4 py-16 relative"
      style={{ zIndex: 1 }}
    >
      <div
        className="pointer-events-none fixed inset-0"
        style={{
          background:
            "radial-gradient(ellipse 60% 40% at 50% 0%, rgba(52,211,153,0.03) 0%, transparent 70%)",
        }}
      />

      <div className="w-full max-w-lg flex flex-col gap-4">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col gap-1 mb-2"
        >
          <a
            href="/"
            className="flex items-center gap-1.5 text-xs w-fit mb-3 transition-colors hover:text-slate-300"
            style={{ color: "#475569" }}
          >
            <ArrowLeft size={12} /> Back
          </a>
          <div className="flex items-center gap-2">
            <div
              className="w-8 h-8 rounded-xl flex items-center justify-center shrink-0"
              style={{
                background: "linear-gradient(135deg, rgba(52,211,153,0.15), rgba(34,211,238,0.15))",
                border: "1px solid rgba(52,211,153,0.2)",
              }}
            >
              <span style={{ fontSize: 14 }}>⊞</span>
            </div>
            <div>
              <h1 className="text-lg font-semibold" style={{ color: "#f1f5f9" }}>
                Batch Analyze
              </h1>
              <p className="text-xs" style={{ color: "#475569" }}>
                Drop multiple files and analyze them all at once
              </p>
            </div>
          </div>
        </motion.div>

        {/* Queue */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="rounded-2xl p-5"
          style={{
            background: "rgba(13,13,24,0.8)",
            border: "1px solid rgba(28,28,46,0.8)",
            backdropFilter: "blur(12px)",
          }}
        >
          <BatchQueue />
        </motion.div>

        {/* Tip */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="text-xs text-center"
          style={{ color: "#334155" }}
        >
          Each file gets its own report — click "View" next to any completed file
        </motion.p>
      </div>
    </div>
  );
}
