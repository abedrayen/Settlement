"use client";

import { ReactNode, useMemo } from "react";
import { Button } from "./Button";

function toCsv(columns: string[], rows: Record<string, unknown>[]): string {
  const escape = (v: unknown) => {
    const s = String(v ?? "");
    return s.includes(",") || s.includes('"') ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [columns.join(",")];
  for (const row of rows) {
    lines.push(columns.map((c) => escape(row[c])).join(","));
  }
  return lines.join("\n");
}

export function DownloadableTable({
  columns,
  rows,
  exportFilename = "export.csv",
  askQuestion,
  children,
}: {
  columns: { key: string; label: string }[];
  rows: Record<string, unknown>[];
  exportFilename?: string;
  askQuestion?: string;
  children: ReactNode;
}) {
  const csv = useMemo(
    () => toCsv(columns.map((c) => c.key), rows),
    [columns, rows],
  );

  const download = () => {
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = exportFilename;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-2">
      <div className="flex justify-end gap-2">
        {askQuestion && <AskAgentBridge question={askQuestion} />}
        <Button variant="outline" size="sm" onClick={download}>Download CSV</Button>
      </div>
      {children}
    </div>
  );
}

export function AskAgentBridge({ question, label = "Ask the agent" }: { question: string; label?: string }) {
  const openChat = () => {
    window.dispatchEvent(new CustomEvent("ask-agent", { detail: { question } }));
  };
  return (
    <Button variant="outline" size="sm" onClick={openChat}>{label}</Button>
  );
}
