"use client";

import { useEffect, useState, use } from "react";
import { motion } from "framer-motion";
import { ArrowLeft } from "lucide-react";
import { getJobStatus, type DriftResult } from "@/lib/api";
import { DriftReport } from "@/components/compare/DriftReport";

interface Props {
  params: Promise<{ jobId: string }>;
}

export default function CompareResultPage({ params }: Props) {
  const { jobId } = use(params);
  const [result, setResult] = useState<DriftResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      while (!cancelled) {
        try {
          const job = await getJobStatus(jobId);
          if (job.status === "done" && job.result) {
            if (!cancelled) setResult(job.result as unknown as DriftResult);
            return;
          }
          if (job.status === "failed") {
            if (!cancelled) setError(job.error ?? "Comparison failed");
            return;
          }
        } catch {
          if (!cancelled) setError("Could not reach server");
          return;
        }
        await new Promise((r) => setTimeout(r, 800));
      }
    };
    poll();
    return () => { cancelled = true; };
  }, [jobId]);

  if (error) {
    return (
      <div className="min-h-dvh flex items-center justify-center">
        <div
          className="text-sm px-5 py-3 rounded-xl"
          style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)", color: "#f43f5e" }}
        >
          {error}
        </div>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="min-h-dvh flex items-center justify-center">
        <motion.div
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{ repeat: Infinity, duration: 1.5 }}
          className="text-sm"
          style={{ color: "#475569" }}
        >
          Loading results…
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-dvh" style={{ zIndex: 1, position: "relative" }}>
      {/* Top bar */}
      <div
        className="sticky top-0 px-6 py-3 flex items-center gap-3 z-10"
        style={{
          background: "rgba(6,6,13,0.9)",
          borderBottom: "1px solid rgba(28,28,46,0.5)",
          backdropFilter: "blur(12px)",
        }}
      >
        <a
          href="/compare"
          className="flex items-center gap-1.5 text-xs transition-colors hover:text-slate-300"
          style={{ color: "#475569" }}
        >
          <ArrowLeft size={12} /> New comparison
        </a>
        <div
          className="w-px h-4 ml-1"
          style={{ background: "rgba(28,28,46,0.8)" }}
        />
        <span className="text-xs font-mono truncate" style={{ color: "#334155" }}>
          {result.ref_name} → {result.cur_name}
        </span>
      </div>

      {/* Content */}
      <main className="max-w-4xl mx-auto px-6 py-8">
        <DriftReport result={result} />
      </main>
    </div>
  );
}
