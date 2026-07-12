"use client";

import { useCallback, useEffect, useState } from "react";
import { useDropzone } from "react-dropzone";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, X, ExternalLink, RefreshCw } from "lucide-react";
import { uploadAndAnalyze, createJobSocket } from "@/lib/api";
import { saveDataset } from "@/lib/storage";

const ACCEPTED = {
  "text/csv": [".csv"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "application/vnd.ms-excel": [".xls"],
};

type ItemStatus = "queued" | "uploading" | "running" | "done" | "failed";

interface BatchItem {
  id: string;
  file: File;
  status: ItemStatus;
  jobId: string | null;
  progress: number;
  step: string;
  error: string | null;
}

function useBatchItem(item: BatchItem, update: (id: string, patch: Partial<BatchItem>) => void) {
  useEffect(() => {
    if (!item.jobId || item.status !== "running") return;

    let intentionallyClosed = false;
    const ws = createJobSocket(item.jobId);

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.progress !== undefined) update(item.id, { progress: data.progress });
      if (data.step) update(item.id, { step: data.step });
      if (data.status === "done") {
        intentionallyClosed = true;
        ws.close();
        update(item.id, { status: "done", progress: 100 });
        saveDataset({
          type: "batch",
          label: item.file.name,
          jobId: item.jobId!,
          href: `/report/${item.jobId}`,
        });
      } else if (data.status === "failed") {
        intentionallyClosed = true;
        ws.close();
        update(item.id, { status: "failed", error: data.error ?? "Failed" });
      }
    };

    ws.onerror = () => {
      if (!intentionallyClosed) update(item.id, { status: "failed", error: "Connection lost" });
    };

    return () => { intentionallyClosed = true; ws.close(); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [item.jobId]);
}

function BatchItemRow({
  item,
  update,
}: {
  item: BatchItem;
  update: (id: string, patch: Partial<BatchItem>) => void;
}) {
  useBatchItem(item, update);

  const statusColor: Record<ItemStatus, string> = {
    queued:    "#475569",
    uploading: "#fbbf24",
    running:   "#22d3ee",
    done:      "#34d399",
    failed:    "#f43f5e",
  };

  const statusLabel: Record<ItemStatus, string> = {
    queued:    "queued",
    uploading: "uploading",
    running:   item.step || "running",
    done:      "done",
    failed:    "failed",
  };

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -12 }}
      className="flex items-center gap-3 px-4 py-3 rounded-xl"
      style={{
        background: item.status === "failed" ? "rgba(244,63,94,0.05)" : "rgba(13,13,24,0.7)",
        border: `1px solid ${item.status === "done" ? "rgba(52,211,153,0.15)" : item.status === "failed" ? "rgba(244,63,94,0.2)" : "rgba(28,28,46,0.6)"}`,
      }}
    >
      {/* Status dot / spinner */}
      <div className="w-5 h-5 flex items-center justify-center shrink-0">
        {item.status === "running" || item.status === "uploading" ? (
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
            className="w-4 h-4 rounded-full"
            style={{
              borderWidth: 2,
              borderStyle: "solid",
              borderColor: "transparent",
              borderTopColor: statusColor[item.status],
            }}
          />
        ) : (
          <div
            className="w-2 h-2 rounded-full"
            style={{ background: statusColor[item.status] }}
          />
        )}
      </div>

      {/* File name */}
      <span
        className="font-mono text-xs font-medium truncate flex-1"
        style={{ color: "#94a3b8" }}
      >
        {item.file.name}
      </span>

      {/* Progress bar (running) */}
      {(item.status === "running" || item.status === "uploading") && (
        <div
          className="w-24 h-1 rounded-full overflow-hidden shrink-0"
          style={{ background: "rgba(28,28,46,0.8)" }}
        >
          <motion.div
            className="h-full rounded-full"
            style={{ background: "linear-gradient(90deg, #22d3ee, #818cf8)" }}
            animate={{ width: `${item.progress}%` }}
            transition={{ duration: 0.3 }}
          />
        </div>
      )}

      {/* Status label */}
      <span
        className="text-xs shrink-0 truncate max-w-28"
        style={{ color: statusColor[item.status] }}
      >
        {statusLabel[item.status]}
      </span>

      {/* Action */}
      {item.status === "done" && item.jobId && (
        <a
          href={`/report/${item.jobId}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg transition-colors hover:bg-white/5 shrink-0"
          style={{ color: "#34d399", border: "1px solid rgba(52,211,153,0.2)" }}
        >
          View <ExternalLink size={10} />
        </a>
      )}

      {item.status === "failed" && (
        <span className="text-xs shrink-0" style={{ color: "#f43f5e" }} title={item.error ?? ""}>
          ⚠ {item.error?.slice(0, 24)}
        </span>
      )}
    </motion.div>
  );
}

export function BatchQueue() {
  const [items, setItems] = useState<BatchItem[]>([]);
  const [running, setRunning] = useState(false);

  const update = useCallback((id: string, patch: Partial<BatchItem>) => {
    setItems((prev) => prev.map((it) => (it.id === id ? { ...it, ...patch } : it)));
  }, []);

  const onDrop = useCallback((accepted: File[]) => {
    const newItems: BatchItem[] = accepted.map((file) => ({
      id: Math.random().toString(36).slice(2),
      file,
      status: "queued",
      jobId: null,
      progress: 0,
      step: "",
      error: null,
    }));
    setItems((prev) => [...prev, ...newItems]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED,
    multiple: true,
  });

  const removeItem = (id: string) => {
    setItems((prev) => prev.filter((it) => it.id !== id));
  };

  const runAll = async () => {
    setRunning(true);
    const queued = items.filter((it) => it.status === "queued");

    for (const item of queued) {
      update(item.id, { status: "uploading", progress: 0 });
      try {
        const { job_id } = await uploadAndAnalyze(item.file, {});
        update(item.id, { status: "running", jobId: job_id });
      } catch (e) {
        update(item.id, { status: "failed", error: String(e) });
      }
    }

    setRunning(false);
  };

  const queued = items.filter((it) => it.status === "queued").length;
  const done = items.filter((it) => it.status === "done").length;
  const failed = items.filter((it) => it.status === "failed").length;

  return (
    <div className="flex flex-col gap-4">
      {/* Drop zone */}
      <div {...getRootProps()} className="outline-none cursor-pointer">
        <input {...getInputProps()} />
        <motion.div
          animate={{
            borderColor: isDragActive ? "rgba(34,211,238,0.7)" : "rgba(28,28,46,0.8)",
            boxShadow: isDragActive
              ? "0 0 0 1px rgba(34,211,238,0.2), inset 0 0 40px rgba(34,211,238,0.04)"
              : "none",
          }}
          transition={{ duration: 0.15 }}
          className="rounded-2xl border-2 border-dashed px-6 py-8 flex flex-col items-center gap-3"
          style={{ background: "rgba(13,13,24,0.7)" }}
        >
          <motion.div
            animate={isDragActive ? { y: [-3, 3, -3] } : { y: 0 }}
            transition={{ repeat: isDragActive ? Infinity : 0, duration: 0.8 }}
            className="w-12 h-12 rounded-2xl flex items-center justify-center"
            style={{
              background: isDragActive ? "rgba(34,211,238,0.1)" : "rgba(28,28,46,0.8)",
              border: `1px solid ${isDragActive ? "rgba(34,211,238,0.3)" : "rgba(42,42,64,0.6)"}`,
            }}
          >
            <Upload size={20} style={{ color: isDragActive ? "#22d3ee" : "#475569" }} />
          </motion.div>
          <div className="text-center">
            <p className="text-sm font-medium" style={{ color: isDragActive ? "#22d3ee" : "#94a3b8" }}>
              {isDragActive ? "Drop files here" : "Drop multiple files to batch analyze"}
            </p>
            <p className="text-xs mt-1" style={{ color: "#334155" }}>
              CSV and Excel files · all analyzed in parallel
            </p>
          </div>
        </motion.div>
      </div>

      {/* Queue */}
      <AnimatePresence mode="popLayout">
        {items.map((item) => (
          <div key={item.id} className="relative group">
            <BatchItemRow item={item} update={update} />
            {item.status === "queued" && (
              <button
                onClick={() => removeItem(item.id)}
                className="absolute top-2 right-2 w-5 h-5 rounded flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                style={{ background: "rgba(244,63,94,0.1)", color: "#f43f5e" }}
              >
                <X size={10} />
              </button>
            )}
          </div>
        ))}
      </AnimatePresence>

      {/* Actions */}
      {items.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-3"
        >
          {queued > 0 && (
            <button
              onClick={runAll}
              disabled={running}
              className="flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all active:scale-[0.98] disabled:opacity-50 flex items-center justify-center gap-2"
              style={{
                background: "linear-gradient(135deg, rgba(34,211,238,0.85), rgba(129,140,248,0.85))",
                color: "#06060d",
                boxShadow: "0 0 20px rgba(34,211,238,0.15)",
              }}
            >
              {running ? (
                <>
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
                    className="w-4 h-4 rounded-full"
                    style={{ borderWidth: 2, borderStyle: "solid", borderColor: "transparent", borderTopColor: "#06060d" }}
                  />
                  Running…
                </>
              ) : (
                `Analyze ${queued} file${queued > 1 ? "s" : ""}`
              )}
            </button>
          )}

          {(done > 0 || failed > 0) && (
            <div className="flex items-center gap-2 text-xs" style={{ color: "#475569" }}>
              {done > 0 && <span style={{ color: "#34d399" }}>✓ {done} done</span>}
              {failed > 0 && <span style={{ color: "#f43f5e" }}>✗ {failed} failed</span>}
            </div>
          )}

          <button
            onClick={() => setItems([])}
            className="flex items-center gap-1.5 text-xs px-3 py-2 rounded-lg transition-colors hover:bg-white/5"
            style={{ color: "#475569", border: "1px solid rgba(28,28,46,0.6)" }}
          >
            <X size={11} /> Clear
          </button>
        </motion.div>
      )}
    </div>
  );
}
