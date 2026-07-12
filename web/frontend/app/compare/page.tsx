"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft } from "lucide-react";
import { CompareUpload } from "@/components/compare/CompareUpload";
import { JobProgress } from "@/components/upload/JobProgress";
import { uploadAndCompare } from "@/lib/api";
import { saveDataset } from "@/lib/storage";

type Stage = "upload" | "progress" | "error";

export default function ComparePage() {
  const router = useRouter();
  const [stage, setStage] = useState<Stage>("upload");
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [fileNames, setFileNames] = useState<{ ref: string; cur: string } | null>(null);

  const handleSubmit = async (ref: File, cur: File, threshold: number) => {
    setLoading(true);
    setFileNames({ ref: ref.name, cur: cur.name });
    try {
      const { job_id } = await uploadAndCompare(ref, cur, threshold);
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
    if (jobId && fileNames) {
      saveDataset({
        type: "compare",
        label: `${fileNames.ref} vs ${fileNames.cur}`,
        jobId,
        href: `/compare/result/${jobId}`,
      });
      router.push(`/compare/result/${jobId}`);
    }
  }, [jobId, fileNames, router]);

  const handleError = useCallback((msg: string) => {
    setError(msg);
    setStage("error");
  }, []);

  return (
    <div
      className="min-h-dvh flex flex-col items-center justify-center px-4 py-16 relative"
      style={{ zIndex: 1 }}
    >
      {/* Background glow — purple tint for compare */}
      <div
        className="pointer-events-none fixed inset-0"
        style={{
          background:
            "radial-gradient(ellipse 60% 40% at 50% 0%, rgba(129,140,248,0.04) 0%, transparent 70%)",
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
                background: "linear-gradient(135deg, rgba(34,211,238,0.15), rgba(129,140,248,0.2))",
                border: "1px solid rgba(129,140,248,0.25)",
              }}
            >
              <span style={{ fontSize: 14 }}>⇄</span>
            </div>
            <div>
              <h1 className="text-lg font-semibold" style={{ color: "#f1f5f9" }}>
                Drift Compare
              </h1>
              <p className="text-xs" style={{ color: "#475569" }}>
                Detect statistical distribution shifts between two datasets
              </p>
            </div>
          </div>
        </motion.div>

        {/* Upload */}
        <AnimatePresence mode="wait">
          {stage === "upload" && (
            <motion.div
              key="upload"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.97 }}
              className="rounded-2xl p-5"
              style={{
                background: "rgba(13,13,24,0.8)",
                border: "1px solid rgba(28,28,46,0.8)",
                backdropFilter: "blur(12px)",
              }}
            >
              <CompareUpload onSubmit={handleSubmit} loading={loading} />
            </motion.div>
          )}

          {stage === "progress" && jobId && (
            <motion.div
              key="progress"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-2xl p-6"
              style={{
                background: "rgba(13,13,24,0.8)",
                border: "1px solid rgba(28,28,46,0.8)",
                backdropFilter: "blur(12px)",
              }}
            >
              <JobProgress jobId={jobId} onDone={handleDone} onError={handleError} />
            </motion.div>
          )}

          {stage === "error" && (
            <motion.div
              key="error"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-xl px-4 py-3 text-sm flex items-center gap-2"
              style={{
                background: "rgba(244,63,94,0.08)",
                border: "1px solid rgba(244,63,94,0.2)",
                color: "#f43f5e",
              }}
            >
              <span>⚠</span>
              {error ?? "Something went wrong"}
              <button
                onClick={() => setStage("upload")}
                className="ml-auto text-xs underline"
              >
                retry
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
