"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiPost } from "@/lib/api";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { IconDoc } from "@/components/icons";
import { MarkdownContent } from "@/components/chat/MarkdownContent";

const PRESET_QUERIES = [
  "What is the max recovery rate?",
  "How do we handle deceased borrowers?",
  "What is the corporate collections process?",
  "What are the PoA model key features?",
  "How should we handle vulnerable borrowers?",
];

export default function DocumentsPage() {
  const [question, setQuestion] = useState("What is the max recovery rate?");
  const [result, setResult] = useState<{ sources: Array<{ document_name: string; content: string; score: number }> } | null>(null);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const query = async (q?: string) => {
    const text = q || question;
    setQuestion(text);
    setLoading(true);
    try {
      const res = await apiPost<{ sources: Array<{ document_name: string; content: string; score: number }> }>("/api/documents/query", { question: text });
      setResult(res);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container">
      <PageHeader
        title="Document Intelligence"
        actions={
          <Button variant="outline" size="sm" onClick={() => router.push(`/assistant?q=${encodeURIComponent(question)}`)}>
            Ask in Chat
          </Button>
        }
      />

      <Card>
        <div className="flex gap-2 flex-wrap mb-4">
          {PRESET_QUERIES.map((q) => (
            <button
              key={q}
              onClick={() => query(q)}
              className="text-xs px-3 py-1.5 rounded-full border border-slate-200 text-slate-600 hover:border-brand-500 hover:text-brand-600 hover:bg-brand-50 transition-all"
            >
              {q}
            </button>
          ))}
        </div>
        <div className="flex gap-3">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && query()}
            className="input-field flex-1"
            placeholder="Ask about policies, model cards, compliance rules..."
          />
          <Button onClick={() => query()} disabled={loading}>
            {loading ? "Searching..." : "Query"}
          </Button>
        </div>
      </Card>

      {result?.sources?.map((s, i) => (
        <Card key={i} hover>
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-lg bg-blue-50 text-brand-600 shrink-0">
              <IconDoc className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <p className="font-semibold text-slate-900">{s.document_name}</p>
                <span className="text-xs text-slate-400">relevance {s.score}</span>
              </div>
              <div className="text-sm text-slate-600 mt-2 leading-relaxed">
                <MarkdownContent content={s.content} />
              </div>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}
