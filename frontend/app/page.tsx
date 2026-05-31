"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Plus, GitCompare, Layers, ArrowRight } from "lucide-react";
import { getSavedDatasets, type SavedDataset } from "@/lib/storage";

export default function HomePage() {
  const router = useRouter();
  const [datasets, setDatasets] = useState<SavedDataset[]>([]);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setDatasets(getSavedDatasets());
    const refresh = () => setDatasets(getSavedDatasets());
    window.addEventListener("emd_storage", refresh);
    return () => window.removeEventListener("emd_storage", refresh);
  }, []);

  const actions = [
    {
      icon: Plus,
      title: "New Analysis",
      desc: "Upload a CSV or Excel file for full EDA",
      href: "/analyze",
      color: "#22d3ee",
      bg: "rgba(34,211,238,0.06)",
      border: "rgba(34,211,238,0.15)",
    },
    {
      icon: GitCompare,
      title: "Drift Compare",
      desc: "Detect distribution shifts between two datasets",
      href: "/compare",
      color: "#818cf8",
      bg: "rgba(129,140,248,0.06)",
      border: "rgba(129,140,248,0.15)",
    },
    {
      icon: Layers,
      title: "Batch Analyze",
      desc: "Analyze multiple files at once",
      href: "/batch",
      color: "#34d399",
      bg: "rgba(52,211,153,0.06)",
      border: "rgba(52,211,153,0.15)",
    },
  ];

  return (
    <div className="min-h-dvh flex flex-col items-center justify-center px-6 py-16" style={{ zIndex: 1, position: "relative" }}>
      {/* Background glow */}
      <div
        className="pointer-events-none fixed inset-0"
        style={{ background: "radial-gradient(ellipse 60% 50% at 50% 0%, rgba(34,211,238,0.03) 0%, transparent 70%)" }}
      />

      <div className="w-full max-w-xl flex flex-col gap-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center"
        >
          <h1 className="text-2xl font-semibold" style={{ color: "#f1f5f9" }}>
            {mounted && datasets.length > 0 ? `${datasets.length} dataset${datasets.length > 1 ? "s" : ""} analyzed` : "Welcome"}
          </h1>
          <p className="text-sm mt-1.5" style={{ color: "#475569" }}>
            {mounted && datasets.length > 0
              ? "Select a dataset from the sidebar or start a new analysis"
              : "Upload a dataset to get started with automated EDA"}
          </p>
        </motion.div>

        {/* Quick action cards */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="flex flex-col gap-3"
        >
          {actions.map(({ icon: Icon, title, desc, href, color, bg, border }, i) => (
            <motion.button
              key={href}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1 + i * 0.06 }}
              onClick={() => router.push(href)}
              className="flex items-center gap-4 px-5 py-4 rounded-2xl text-left transition-all active:scale-[0.99] group"
              style={{ background: bg, border: `1px solid ${border}` }}
              whileHover={{ scale: 1.01 }}
            >
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
                style={{ background: `${color}15`, border: `1px solid ${color}25` }}
              >
                <Icon size={18} style={{ color }} />
              </div>
              <div className="flex-1">
                <p className="text-sm font-semibold" style={{ color: "#e2e8f0" }}>{title}</p>
                <p className="text-xs mt-0.5" style={{ color: "#475569" }}>{desc}</p>
              </div>
              <ArrowRight
                size={15}
                style={{ color: "#334155", transition: "transform 0.2s" }}
                className="group-hover:translate-x-0.5"
              />
            </motion.button>
          ))}
        </motion.div>

        {/* Recent datasets preview */}
        {mounted && datasets.length > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="flex flex-col gap-2"
          >
            <p className="text-xs uppercase tracking-widest" style={{ color: "#2a2a40" }}>Recent</p>
            {datasets.slice(0, 3).map((ds) => (
              <button
                key={ds.id}
                onClick={() => router.push(ds.href)}
                className="flex items-center gap-3 px-4 py-2.5 rounded-xl text-left transition-colors hover:bg-white/[0.02]"
                style={{ border: "1px solid rgba(28,28,46,0.5)" }}
              >
                <span className="text-xs font-mono truncate flex-1" style={{ color: "#64748b" }}>
                  {ds.label}
                </span>
                <span
                  className="text-xs px-2 py-0.5 rounded-full"
                  style={{
                    background: ds.type === "analyze" ? "rgba(34,211,238,0.08)" : ds.type === "compare" ? "rgba(129,140,248,0.08)" : "rgba(52,211,153,0.08)",
                    color: ds.type === "analyze" ? "#22d3ee" : ds.type === "compare" ? "#818cf8" : "#34d399",
                    border: `1px solid ${ds.type === "analyze" ? "rgba(34,211,238,0.2)" : ds.type === "compare" ? "rgba(129,140,248,0.2)" : "rgba(52,211,153,0.2)"}`,
                  }}
                >
                  {ds.type}
                </span>
              </button>
            ))}
          </motion.div>
        )}
      </div>
    </div>
  );
}
