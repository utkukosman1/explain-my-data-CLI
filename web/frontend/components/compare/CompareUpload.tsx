"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { motion, AnimatePresence } from "framer-motion";
import { FileSpreadsheet, Upload, X, ArrowRight } from "lucide-react";

const ACCEPTED = {
  "text/csv": [".csv"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "application/vnd.ms-excel": [".xls"],
};

interface SlotProps {
  label: string;
  sublabel: string;
  color: string;
  file: File | null;
  onFile: (f: File) => void;
  onClear: () => void;
}

function FileSlot({ label, sublabel, color, file, onFile, onClear }: SlotProps) {
  const onDrop = useCallback((accepted: File[]) => {
    if (accepted[0]) onFile(accepted[0]);
  }, [onFile]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED,
    maxFiles: 1,
  });

  return (
    <div {...getRootProps()} className="outline-none cursor-pointer flex-1">
      <input {...getInputProps()} />
      <motion.div
        animate={{
          borderColor: isDragActive
            ? color
            : file
            ? `${color}55`
            : "rgba(28,28,46,0.8)",
          boxShadow: isDragActive
            ? `0 0 0 1px ${color}33, inset 0 0 40px ${color}08`
            : file
            ? `0 0 0 1px ${color}22`
            : "none",
        }}
        transition={{ duration: 0.2 }}
        className="h-full min-h-36 rounded-2xl border-2 border-dashed flex flex-col items-center justify-center gap-3 p-5 transition-colors"
        style={{ background: "rgba(13,13,24,0.7)" }}
      >
        {file ? (
          <div className="flex flex-col items-center gap-2 text-center">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: `${color}15`, border: `1px solid ${color}30` }}
            >
              <FileSpreadsheet size={18} style={{ color }} />
            </div>
            <div>
              <p className="text-xs font-medium truncate max-w-32" style={{ color: "#e2e8f0" }}>
                {file.name}
              </p>
              <p className="text-xs mt-0.5" style={{ color: "#475569" }}>
                {(file.size / 1024).toFixed(0)} KB
              </p>
            </div>
            <button
              onClick={(e) => { e.stopPropagation(); onClear(); }}
              className="flex items-center gap-1 text-xs px-2 py-1 rounded-full hover:bg-white/5"
              style={{ color: "#475569", border: "1px solid rgba(28,28,46,0.8)" }}
            >
              <X size={10} /> clear
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 text-center">
            <motion.div
              animate={isDragActive ? { y: [-2, 2, -2] } : { y: 0 }}
              transition={{ repeat: isDragActive ? Infinity : 0, duration: 0.8 }}
              className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: "rgba(28,28,46,0.8)", border: "1px solid rgba(42,42,64,0.6)" }}
            >
              <Upload size={16} style={{ color: "#475569" }} />
            </motion.div>
            <div>
              <p className="text-xs font-semibold" style={{ color }}>
                {label}
              </p>
              <p className="text-xs mt-0.5" style={{ color: "#334155" }}>
                {sublabel}
              </p>
            </div>
          </div>
        )}
      </motion.div>
    </div>
  );
}

interface Props {
  onSubmit: (ref: File, cur: File, threshold: number) => void;
  loading?: boolean;
}

export function CompareUpload({ onSubmit, loading }: Props) {
  const [refFile, setRefFile] = useState<File | null>(null);
  const [curFile, setCurFile] = useState<File | null>(null);
  const [threshold, setThreshold] = useState("0.2");

  const ready = refFile && curFile;

  return (
    <div className="flex flex-col gap-4">
      {/* Slots */}
      <div className="flex gap-3 items-stretch">
        <FileSlot
          label="Reference"
          sublabel="training / baseline"
          color="#22d3ee"
          file={refFile}
          onFile={setRefFile}
          onClear={() => setRefFile(null)}
        />

        <div className="flex items-center self-center shrink-0">
          <div
            className="w-7 h-7 rounded-full flex items-center justify-center"
            style={{ background: "rgba(28,28,46,0.8)", border: "1px solid rgba(42,42,64,0.6)" }}
          >
            <ArrowRight size={13} style={{ color: "#334155" }} />
          </div>
        </div>

        <FileSlot
          label="Current"
          sublabel="test / production"
          color="#818cf8"
          file={curFile}
          onFile={setCurFile}
          onClear={() => setCurFile(null)}
        />
      </div>

      {/* Threshold */}
      <div
        className="flex items-center gap-3 px-4 py-3 rounded-xl"
        style={{ background: "rgba(13,13,24,0.8)", border: "1px solid rgba(28,28,46,0.6)" }}
      >
        <span className="text-xs" style={{ color: "#475569" }}>PSI threshold</span>
        <input
          type="number"
          step="0.05"
          min="0.05"
          max="0.5"
          value={threshold}
          onChange={(e) => setThreshold(e.target.value)}
          className="w-16 text-xs px-2 py-1 rounded-lg outline-none font-mono text-center"
          style={{
            background: "rgba(28,28,46,0.6)",
            border: "1px solid rgba(42,42,64,0.5)",
            color: "#e2e8f0",
          }}
        />
        <span className="text-xs" style={{ color: "#334155" }}>
          &lt; 0.1 stable · 0.1–0.2 moderate · &gt; 0.2 high
        </span>
      </div>

      {/* CTA */}
      <button
        disabled={!ready || loading}
        onClick={() => ready && onSubmit(refFile, curFile, parseFloat(threshold) || 0.2)}
        className="w-full py-3 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 transition-all active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed"
        style={{
          background: ready && !loading
            ? "linear-gradient(135deg, rgba(34,211,238,0.85), rgba(129,140,248,0.85))"
            : "rgba(28,28,46,0.6)",
          color: ready && !loading ? "#06060d" : "#334155",
          boxShadow: ready && !loading ? "0 0 24px rgba(34,211,238,0.15)" : "none",
        }}
      >
        {loading ? (
          <>
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
              className="w-4 h-4 rounded-full"
              style={{ borderWidth: 2, borderStyle: "solid", borderColor: "transparent", borderTopColor: "#22d3ee" }}
            />
            Comparing…
          </>
        ) : (
          "Compare datasets"
        )}
      </button>
    </div>
  );
}
