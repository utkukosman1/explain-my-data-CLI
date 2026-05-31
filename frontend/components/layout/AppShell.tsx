"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Plus, GitCompare, Layers, X, BarChart2 } from "lucide-react";
import { getSavedDatasets, removeDataset, type SavedDataset } from "@/lib/storage";

const TYPE_CONFIG = {
  analyze: { label: "Analysis",  color: "#22d3ee",  icon: "◈" },
  compare: { label: "Drift",     color: "#818cf8",  icon: "⇄" },
  batch:   { label: "Batch",     color: "#34d399",  icon: "⊞" },
};

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [datasets, setDatasets] = useState<SavedDataset[]>([]);

  // Load from localStorage and listen for updates
  useEffect(() => {
    const refresh = () => setDatasets(getSavedDatasets());
    refresh();
    window.addEventListener("emd_storage", refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener("emd_storage", refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);

  const navItems = [
    { icon: Plus,        label: "New Analysis", href: "/analyze",  accent: "#22d3ee" },
    { icon: GitCompare,  label: "Compare",      href: "/compare",  accent: "#818cf8" },
    { icon: Layers,      label: "Batch",        href: "/batch",    accent: "#34d399" },
  ];

  return (
    <div className="flex min-h-dvh" style={{ position: "relative", zIndex: 1 }}>
      {/* Sidebar */}
      <aside
        className="w-56 shrink-0 sticky top-0 h-dvh flex flex-col overflow-hidden"
        style={{
          background: "rgba(8,8,16,0.97)",
          borderRight: "1px solid rgba(28,28,46,0.6)",
        }}
      >
        {/* Logo */}
        <div className="px-4 pt-5 pb-4">
          <button
            onClick={() => router.push("/")}
            className="flex items-center gap-2.5 group w-full"
          >
            <div
              className="w-7 h-7 rounded-xl flex items-center justify-center shrink-0"
              style={{
                background: "linear-gradient(135deg, rgba(34,211,238,0.2), rgba(129,140,248,0.2))",
                border: "1px solid rgba(34,211,238,0.2)",
              }}
            >
              <BarChart2 size={13} style={{ color: "#22d3ee" }} />
            </div>
            <span
              className="text-xs font-bold tracking-widest"
              style={{ color: "#475569", letterSpacing: "0.12em" }}
            >
              EXPLAIN MY DATA
            </span>
          </button>
        </div>

        {/* Nav actions */}
        <div className="px-3 flex flex-col gap-1 pb-4" style={{ borderBottom: "1px solid rgba(28,28,46,0.5)" }}>
          {navItems.map(({ icon: Icon, label, href, accent }) => {
            const active = pathname === href;
            return (
              <button
                key={href}
                onClick={() => router.push(href)}
                className="relative flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all text-left w-full"
                style={{
                  background: active ? `${accent}10` : "transparent",
                  color: active ? accent : "#475569",
                  border: active ? `1px solid ${accent}20` : "1px solid transparent",
                }}
              >
                <Icon size={13} strokeWidth={active ? 2.5 : 2} />
                {label}
              </button>
            );
          })}
        </div>

        {/* Dataset list */}
        <div className="flex-1 overflow-y-auto px-3 py-3 flex flex-col gap-1">
          {datasets.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-24 gap-2">
              <p className="text-xs text-center" style={{ color: "#2a2a40" }}>
                No datasets yet.
                <br />Upload one to get started.
              </p>
            </div>
          ) : (
            <>
              <p
                className="text-xs px-2 mb-1 uppercase tracking-widest"
                style={{ color: "#2a2a40" }}
              >
                Datasets
              </p>
              {datasets.map((ds) => {
                const cfg = TYPE_CONFIG[ds.type];
                const active = pathname === ds.href || pathname.startsWith(ds.href + "/");
                return (
                  <div key={ds.id} className="group relative">
                    <button
                      onClick={() => router.push(ds.href)}
                      className="w-full flex flex-col gap-0.5 px-3 py-2.5 rounded-lg text-left transition-all"
                      style={{
                        background: active ? `${cfg.color}0c` : "transparent",
                        border: active ? `1px solid ${cfg.color}20` : "1px solid transparent",
                      }}
                    >
                      <span
                        className="text-xs font-medium font-mono truncate block max-w-[140px]"
                        style={{ color: active ? "#e2e8f0" : "#64748b" }}
                      >
                        {ds.label}
                      </span>
                      <span
                        className="text-xs flex items-center gap-1"
                        style={{ color: cfg.color, opacity: 0.8 }}
                      >
                        <span style={{ fontSize: 9 }}>{cfg.icon}</span>
                        {cfg.label}
                      </span>
                    </button>

                    {/* Remove button */}
                    <button
                      onClick={(e) => { e.stopPropagation(); removeDataset(ds.id); }}
                      className="absolute right-1.5 top-1/2 -translate-y-1/2 w-5 h-5 rounded flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                      style={{ background: "rgba(28,28,46,0.8)", color: "#334155" }}
                    >
                      <X size={9} />
                    </button>
                  </div>
                );
              })}
            </>
          )}
        </div>

        {/* Bottom version */}
        <div className="px-4 py-3" style={{ borderTop: "1px solid rgba(28,28,46,0.4)" }}>
          <p className="text-xs" style={{ color: "#1e1e2e" }}>emd v0.1.0</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto min-w-0">
        {children}
      </main>
    </div>
  );
}
