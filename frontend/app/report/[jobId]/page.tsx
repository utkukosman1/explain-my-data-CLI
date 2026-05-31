"use client";

import { useEffect, useState, use } from "react";
import { motion } from "framer-motion";
import { getJobStatus, type AnalysisResult } from "@/lib/api";
import { ReportLayout } from "@/components/report/ReportLayout";

interface Props {
  params: Promise<{ jobId: string }>;
}

export default function ReportPage({ params }: Props) {
  const { jobId } = use(params);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      while (!cancelled) {
        try {
          const job = await getJobStatus(jobId);
          if (job.status === "done" && job.result) {
            if (!cancelled) setResult(job.result);
            return;
          }
          if (job.status === "failed") {
            if (!cancelled) setError(job.error ?? "Analysis failed");
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

  return <ReportLayout result={result} jobId={jobId} />;
}
