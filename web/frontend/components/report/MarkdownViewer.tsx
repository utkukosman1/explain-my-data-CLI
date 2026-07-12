"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { motion } from "framer-motion";
import { Download } from "lucide-react";

interface Props {
  markdown: string;
  downloadHref: string;
  filename: string;
}

export function MarkdownViewer({ markdown, downloadHref, filename }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.25, 0.46, 0.45, 0.94] }}
      className="rounded-2xl overflow-hidden"
      style={{ border: "1px solid rgba(28,28,46,0.7)", background: "rgba(10,10,20,0.9)" }}
    >
      {/* Toolbar */}
      <div
        className="flex items-center justify-between px-5 py-3 sticky top-0 z-10"
        style={{
          background: "rgba(9,9,17,0.97)",
          borderBottom: "1px solid rgba(28,28,46,0.6)",
          backdropFilter: "blur(8px)",
        }}
      >
        <div className="flex items-center gap-2">
          <div
            className="w-2 h-2 rounded-full"
            style={{ background: "rgba(34,211,238,0.5)" }}
          />
          <span className="text-xs font-mono" style={{ color: "#475569" }}>
            {filename.replace(/\.[^.]+$/, "")}_report.md
          </span>
        </div>
        <a
          href={downloadHref}
          download
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-all hover:bg-white/[0.04] active:scale-95"
          style={{ color: "#475569", border: "1px solid rgba(28,28,46,0.8)" }}
        >
          <Download size={10} />
          Download
        </a>
      </div>

      {/* Markdown content */}
      <div className="px-8 py-8 markdown-body overflow-x-auto">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {markdown}
        </ReactMarkdown>
      </div>

      <style>{`
        .markdown-body { color: #94a3b8; font-size: 13.5px; line-height: 1.75; }

        .markdown-body h1 {
          font-size: 1.4rem; font-weight: 700; color: #f1f5f9;
          margin: 0 0 0.5rem; padding-bottom: 0.5rem;
          border-bottom: 1px solid rgba(28,28,46,0.8);
        }
        .markdown-body h2 {
          font-size: 1.05rem; font-weight: 600; color: #e2e8f0;
          margin: 2.2rem 0 0.8rem; padding-bottom: 0.4rem;
          border-bottom: 1px solid rgba(28,28,46,0.5);
        }
        .markdown-body h3 {
          font-size: 0.9rem; font-weight: 600; color: #cbd5e1;
          margin: 1.5rem 0 0.5rem;
        }
        .markdown-body h4 {
          font-size: 0.85rem; font-weight: 600; color: #94a3b8;
          margin: 1.2rem 0 0.4rem;
        }

        .markdown-body p { margin: 0.6rem 0; }

        .markdown-body strong { color: #e2e8f0; font-weight: 600; }

        .markdown-body blockquote {
          margin: 0.8rem 0; padding: 0.6rem 1rem;
          border-left: 3px solid rgba(34,211,238,0.4);
          background: rgba(34,211,238,0.04);
          border-radius: 0 8px 8px 0;
          color: #64748b;
        }
        .markdown-body blockquote strong { color: #22d3ee; }

        .markdown-body table {
          width: 100%; border-collapse: collapse;
          font-size: 12px; margin: 1rem 0;
          font-variant-numeric: tabular-nums;
        }
        .markdown-body thead tr {
          background: rgba(28,28,46,0.8);
        }
        .markdown-body th {
          padding: 8px 12px; text-align: left;
          color: #475569; font-weight: 600; font-size: 11px;
          text-transform: uppercase; letter-spacing: 0.04em;
          border-bottom: 1px solid rgba(42,42,64,0.8);
        }
        .markdown-body td {
          padding: 7px 12px; color: #64748b;
          border-bottom: 1px solid rgba(28,28,46,0.4);
          font-family: ui-monospace, monospace;
        }
        .markdown-body tr:last-child td { border-bottom: none; }
        .markdown-body tr:hover td { background: rgba(255,255,255,0.015); }
        .markdown-body td:first-child { color: #94a3b8; font-family: inherit; }

        .markdown-body code {
          font-family: ui-monospace, monospace;
          font-size: 11.5px; padding: 1px 5px;
          background: rgba(28,28,46,0.8);
          border: 1px solid rgba(42,42,64,0.6);
          border-radius: 4px; color: #22d3ee;
        }
        .markdown-body pre {
          background: rgba(13,13,24,0.9);
          border: 1px solid rgba(28,28,46,0.8);
          border-radius: 10px; padding: 1rem 1.2rem;
          overflow-x: auto; margin: 1rem 0;
        }
        .markdown-body pre code {
          background: none; border: none;
          padding: 0; color: #94a3b8; font-size: 12px;
        }

        .markdown-body hr {
          border: none; border-top: 1px solid rgba(28,28,46,0.6);
          margin: 1.5rem 0;
        }

        .markdown-body ul, .markdown-body ol {
          padding-left: 1.4rem; margin: 0.5rem 0;
        }
        .markdown-body li { margin: 0.2rem 0; color: #64748b; }
        .markdown-body li strong { color: #94a3b8; }

        /* Numbered section headers get a cyan left accent */
        .markdown-body h2::before {
          content: '';
          display: inline-block;
          width: 3px; height: 1em;
          background: rgba(34,211,238,0.4);
          border-radius: 2px;
          margin-right: 10px;
          vertical-align: middle;
        }
      `}</style>
    </motion.div>
  );
}
