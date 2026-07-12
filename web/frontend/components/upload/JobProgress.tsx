"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { createJobSocket } from "@/lib/api";

const STEPS = [
  { label: "Loading data", pct: 5 },
  { label: "Quality check", pct: 15 },
  { label: "Distribution analysis", pct: 30 },
  { label: "Missing value analysis", pct: 45 },
  { label: "Correlation analysis", pct: 60 },
  { label: "Outlier detection", pct: 75 },
  { label: "Building response", pct: 95 },
  { label: "Done", pct: 100 },
];

interface Props {
  jobId: string;
  onDone: () => void;
  onError: (msg: string) => void;
}

export function JobProgress({ jobId, onDone, onError }: Props) {
  const [progress, setProgress] = useState(0);
  const [step, setStep] = useState("Starting…");
  const [status, setStatus] = useState<"running" | "done" | "failed">("running");

  // Use refs so the WebSocket callbacks always see the latest values
  // without being listed as effect dependencies (avoids reconnect loops).
  const onDoneRef = useRef(onDone);
  const onErrorRef = useRef(onError);
  useEffect(() => { onDoneRef.current = onDone; }, [onDone]);
  useEffect(() => { onErrorRef.current = onError; }, [onError]);

  useEffect(() => {
    let intentionallyClosed = false;
    const ws = createJobSocket(jobId);

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.progress !== undefined) setProgress(data.progress);
      if (data.step) setStep(data.step);
      if (data.status === "done") {
        setStatus("done");
        setProgress(100);
        intentionallyClosed = true;
        ws.close();
        setTimeout(() => onDoneRef.current(), 600);
      } else if (data.status === "failed") {
        setStatus("failed");
        intentionallyClosed = true;
        ws.close();
        onErrorRef.current(data.error ?? "Analysis failed");
      }
    };

    ws.onerror = () => {
      if (!intentionallyClosed) onErrorRef.current("Connection lost — is the backend running?");
    };

    return () => {
      intentionallyClosed = true;
      ws.close();
    };
  // Only re-connect when jobId actually changes, not when callbacks change.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  const activeIndex = STEPS.findIndex((s) => s.label === step);
  const resolvedIndex = activeIndex >= 0 ? activeIndex : STEPS.findIndex((s) => s.pct > progress) - 1;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
      className="flex flex-col gap-6"
    >
      {/* Progress bar */}
      <div className="relative">
        <div
          className="h-1 rounded-full overflow-hidden"
          style={{ background: "rgba(28,28,46,0.8)" }}
        >
          <motion.div
            className="h-full rounded-full"
            style={{
              background: "linear-gradient(90deg, #22d3ee, #818cf8)",
              boxShadow: "0 0 12px rgba(34,211,238,0.5)",
            }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.4, ease: "easeOut" }}
          />
        </div>
        <div
          className="flex justify-between mt-1.5 text-xs tabular"
          style={{ color: "#475569" }}
        >
          <span>{step}</span>
          <span>{progress}%</span>
        </div>
      </div>

      {/* Steps */}
      <div className="flex flex-col gap-0.5">
        {STEPS.filter((s) => s.label !== "Done").map((s, i) => {
          const done = progress >= s.pct;
          const active = resolvedIndex === i;

          return (
            <motion.div
              key={s.label}
              className="flex items-center gap-3 px-3 py-2 rounded-lg"
              animate={{
                background: active
                  ? "rgba(34,211,238,0.06)"
                  : "transparent",
              }}
              transition={{ duration: 0.2 }}
            >
              {/* Dot */}
              <div className="relative w-4 h-4 flex items-center justify-center shrink-0">
                {active ? (
                  <motion.div
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ background: "#22d3ee" }}
                    animate={{ scale: [1, 1.3, 1], opacity: [1, 0.7, 1] }}
                    transition={{ repeat: Infinity, duration: 1.2 }}
                  />
                ) : done ? (
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{ background: "rgba(52,211,153,0.8)" }}
                  />
                ) : (
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{ background: "rgba(42,42,64,0.8)" }}
                  />
                )}
              </div>

              <span
                className="text-xs font-medium transition-colors"
                style={{
                  color: active ? "#22d3ee" : done ? "#475569" : "#334155",
                  textDecoration: done && !active ? "line-through" : "none",
                }}
              >
                {s.label}
              </span>

              {done && !active && (
                <motion.span
                  initial={{ opacity: 0, x: -4 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="ml-auto text-xs"
                  style={{ color: "rgba(52,211,153,0.6)" }}
                >
                  done
                </motion.span>
              )}
            </motion.div>
          );
        })}
      </div>

      {/* Done flash */}
      <AnimatePresence>
        {status === "done" && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center justify-center gap-2 text-sm font-medium"
            style={{ color: "#34d399" }}
          >
            <span>✓</span> Analysis complete — loading results…
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
