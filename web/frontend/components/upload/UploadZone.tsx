"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, FileSpreadsheet, X, CheckCircle2 } from "lucide-react";

interface Props {
  onFileAccepted: (file: File) => void;
}

const ACCEPTED = {
  "text/csv": [".csv"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "application/vnd.ms-excel": [".xls"],
};

export function UploadZone({ onFileAccepted }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [rejected, setRejected] = useState(false);

  const onDrop = useCallback(
    (accepted: File[]) => {
      setRejected(false);
      if (accepted[0]) {
        setFile(accepted[0]);
        onFileAccepted(accepted[0]);
      }
    },
    [onFileAccepted]
  );

  const onDropRejected = useCallback(() => {
    setRejected(true);
    setTimeout(() => setRejected(false), 2000);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    onDropRejected,
    accept: ACCEPTED,
    maxFiles: 1,
    maxSize: 100 * 1024 * 1024,
  });

  const clear = (e: React.MouseEvent) => {
    e.stopPropagation();
    setFile(null);
  };

  return (
    <div {...getRootProps()} className="cursor-pointer outline-none">
      <input {...getInputProps()} />

      <motion.div
        animate={{
          borderColor: rejected
            ? "rgba(244,63,94,0.7)"
            : isDragActive
            ? "rgba(34,211,238,0.7)"
            : file
            ? "rgba(52,211,153,0.5)"
            : "rgba(28,28,46,0.8)",
          boxShadow: rejected
            ? "0 0 0 1px rgba(244,63,94,0.2), inset 0 0 60px rgba(244,63,94,0.03)"
            : isDragActive
            ? "0 0 0 1px rgba(34,211,238,0.3), inset 0 0 80px rgba(34,211,238,0.04), 0 0 40px rgba(34,211,238,0.08)"
            : file
            ? "0 0 0 1px rgba(52,211,153,0.2), inset 0 0 60px rgba(52,211,153,0.03)"
            : "0 0 0 1px rgba(28,28,46,0.5)",
        }}
        transition={{ duration: 0.2 }}
        className="relative rounded-2xl border-2 border-dashed p-12 flex flex-col items-center gap-5 transition-colors"
        style={{ background: "rgba(13,13,24,0.6)", backdropFilter: "blur(12px)" }}
      >
        {/* Animated icon area */}
        <AnimatePresence mode="wait">
          {file ? (
            <motion.div
              key="file"
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.8, opacity: 0 }}
              className="flex flex-col items-center gap-3"
            >
              <div className="relative">
                <div
                  className="w-16 h-16 rounded-2xl flex items-center justify-center"
                  style={{ background: "rgba(52,211,153,0.1)", border: "1px solid rgba(52,211,153,0.2)" }}
                >
                  <FileSpreadsheet size={28} style={{ color: "#34d399" }} />
                </div>
                <div
                  className="absolute -top-1 -right-1 w-5 h-5 rounded-full flex items-center justify-center"
                  style={{ background: "#34d399" }}
                >
                  <CheckCircle2 size={12} color="#06060d" strokeWidth={3} />
                </div>
              </div>

              <div className="text-center">
                <p className="font-medium text-sm" style={{ color: "#f1f5f9" }}>
                  {file.name}
                </p>
                <p className="text-xs mt-0.5" style={{ color: "#475569" }}>
                  {(file.size / 1024).toFixed(1)} KB
                </p>
              </div>

              <button
                onClick={clear}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full transition-colors hover:bg-white/5"
                style={{ color: "#475569", border: "1px solid rgba(28,28,46,0.8)" }}
              >
                <X size={11} />
                Change file
              </button>
            </motion.div>
          ) : isDragActive ? (
            <motion.div
              key="drag"
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="flex flex-col items-center gap-3"
            >
              <motion.div
                animate={{ y: [-4, 4, -4] }}
                transition={{ repeat: Infinity, duration: 1, ease: "easeInOut" }}
                className="w-16 h-16 rounded-2xl flex items-center justify-center"
                style={{ background: "rgba(34,211,238,0.1)", border: "1px solid rgba(34,211,238,0.3)" }}
              >
                <Upload size={28} style={{ color: "#22d3ee" }} />
              </motion.div>
              <p className="text-sm font-medium" style={{ color: "#22d3ee" }}>
                Drop it here
              </p>
            </motion.div>
          ) : (
            <motion.div
              key="idle"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center gap-4"
            >
              <div
                className="w-16 h-16 rounded-2xl flex items-center justify-center"
                style={{ background: "rgba(28,28,46,0.8)", border: "1px solid rgba(42,42,64,0.8)" }}
              >
                <Upload size={26} style={{ color: "#475569" }} />
              </div>

              <div className="text-center">
                <p className="text-sm font-medium" style={{ color: "#94a3b8" }}>
                  Drop your CSV or Excel file here
                </p>
                <p className="text-xs mt-1" style={{ color: "#475569" }}>
                  or{" "}
                  <span style={{ color: "#22d3ee" }} className="cursor-pointer hover:underline">
                    browse files
                  </span>{" "}
                  · up to 100 MB
                </p>
              </div>

              <div className="flex items-center gap-2">
                {[".csv", ".xlsx", ".xls"].map((ext) => (
                  <span
                    key={ext}
                    className="text-xs px-2 py-0.5 rounded-md font-mono"
                    style={{
                      background: "rgba(28,28,46,0.8)",
                      border: "1px solid rgba(42,42,64,0.6)",
                      color: "#475569",
                    }}
                  >
                    {ext}
                  </span>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Reject flash */}
        <AnimatePresence>
          {rejected && (
            <motion.p
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="absolute bottom-4 text-xs"
              style={{ color: "#f43f5e" }}
            >
              Only CSV and Excel files are accepted
            </motion.p>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}
