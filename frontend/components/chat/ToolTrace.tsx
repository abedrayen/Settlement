"use client";

import { useState } from "react";
import type { ToolCall } from "./types";

const TOOL_LABELS: Record<string, string> = {
  borrower_lookup: "Borrower Lookup",
  offer_optimization: "Offer Optimization (MILP)",
  explainability: "SHAP Explainability",
  portfolio_analytics: "Portfolio Analytics",
  monitoring: "Model Monitoring",
  frontier_analysis: "Efficient Frontier",
  installment_comparison: "Installment Comparison",
  document_rag: "Document RAG",
  model_score: "Model Scorer",
  payment_history: "Payment History",
  human_handoff: "Human Handoff",
  exception_request: "Exception Request",
  offer_grid: "Offer Grid",
};

export function ToolTrace({ toolCalls }: { toolCalls: ToolCall[] }) {
  const [open, setOpen] = useState(false);

  if (!toolCalls.length) return null;

  return (
    <div className="max-w-2xl">
      <button
        onClick={() => setOpen(!open)}
        className="text-xs text-slate-400 hover:text-slate-600 font-medium flex items-center gap-1.5"
      >
        <span>{open ? "▾" : "▸"}</span>
        Tool trace ({toolCalls.length})
      </button>

      {open && (
        <div className="mt-2 space-y-2">
          {toolCalls.map((tc, i) => (
            <div key={i} className="rounded-lg border border-slate-200 bg-white overflow-hidden">
              <div className="flex items-center justify-between px-3 py-2 bg-slate-50 border-b border-slate-100">
                <span className="text-xs font-medium text-slate-700">
                  {TOOL_LABELS[tc.tool] || tc.tool}
                </span>
                {tc.duration_ms != null && (
                  <span className="text-xs text-slate-400 font-mono">{tc.duration_ms}ms</span>
                )}
              </div>
              <details className="group">
                <summary className="px-3 py-1.5 text-xs text-slate-500 cursor-pointer hover:text-slate-700 select-none">
                  Raw output
                </summary>
                <pre className="p-3 bg-slate-900 text-emerald-400 text-xs overflow-x-auto font-mono max-h-48">
                  {JSON.stringify(tc.output ?? tc.input, null, 2)}
                </pre>
              </details>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
