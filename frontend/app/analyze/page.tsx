"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { UploadZone } from "@/components/upload/UploadZone";
import { AnalysisOptions } from "@/components/upload/AnalysisOptions";
import { JobProgress } from "@/components/upload/JobProgress";
import { uploadAndAnalyze, type AnalyzeOptions } from "@/lib/api";
import { saveDataset } from "@/lib/storage";

type Stage = "idle" | "options" | "progress" | "error";

export default function AnalyzePage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [stage, setStage] = useState<Stage>("idle");
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleFileAccepted = useCallback((f: File) => {
    setFile(f);
    setStage("options");
  }, []);

  const handleSubmit = async (options: AnalyzeOptions) => {
    if (!file) return;
    setLoading(true);
    try {
      const { job_id } = await uploadAndAnalyze(file, options);
      setJobId(job_id);
      setStage("progress");
    } catch (e) {
      setError(String(e));
      setStage("error");
    } finally {
      setLoading(false);
    }
  };

  const handleDone = useCallback(() => {
    if (jobId && file) {
      saveDataset({
        type: "analyze",
        label: file.name,
        jobId,
        href: `/report/${jobId}`,
      });
      router.push(`/report/${jobId}`);
    }
  }, [jobId, file, router]);

  const handleError = useCallback((msg: string) => {
    setError(msg);
    setStage("error");
  }, []);

  return (
    <div className="min-h-dvh flex flex-col items-center justify-center px-4 py-16 relative" style={{ zIndex: 1 }}>
      <div className="pointer-events-none fixed inset-0" style={{ background: "radial-gradient(ellipse 60% 40% at 50% 0%, rgba(34,211,238,0.04) 0%, transparent 70%)" }} />

      <div className="w-full max-w-md flex flex-col gap-3">
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="text-center mb-6">
          <div className="flex items-center justify-center gap-2 mb-3">
            <div className="w-8 h-8 rounded-xl flex items-center justify-center" style={{ background: "linear-gradient(135deg, rgba(34,211,238,0.2), rgba(129,140,248,0.2))", border: "1px solid rgba(34,211,238,0.2)" }}>
              <span style={{ fontSize: 14 }}>◈</span>
            </div>
            <span className="text-sm font-semibold tracking-wide" style={{ color: "#94a3b8", letterSpacing: "0.08em" }}>NEW ANALYSIS</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight" style={{ color: "#f1f5f9" }}>Upload your dataset</h1>
          <p className="text-sm mt-1.5" style={{ color: "#475569" }}>Get instant EDA — distributions, correlations, outliers and more</p>
        </motion.div>

        <AnimatePresence>
          {stage !== "progress" && (
            <motion.div key="upload" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, scale: 0.97 }} transition={{ duration: 0.25 }}>
              <UploadZone onFileAccepted={handleFileAccepted} />
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {stage === "options" && file && (
            <AnalysisOptions key="options" file={file} onSubmit={handleSubmit} loading={loading} />
          )}
        </AnimatePresence>

        <AnimatePresence>
          {stage === "progress" && jobId && (
            <motion.div key="progress" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="rounded-2xl p-6" style={{ background: "rgba(13,13,24,0.8)", border: "1px solid rgba(28,28,46,0.8)", backdropFilter: "blur(12px)" }}>
              <JobProgress jobId={jobId} onDone={handleDone} onError={handleError} />
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {stage === "error" && (
            <motion.div key="error" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="rounded-xl px-4 py-3 text-sm flex items-center gap-2" style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)", color: "#f43f5e" }}>
              <span>⚠</span>
              {error ?? "Something went wrong"}
              <button onClick={() => setStage(file ? "options" : "idle")} className="ml-auto text-xs underline">retry</button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
