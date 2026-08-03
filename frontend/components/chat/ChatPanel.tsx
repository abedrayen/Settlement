"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { chatStream, listConversations, type ConversationSummary } from "@/lib/api";
import { useRole } from "@/components/AuthProvider";
import { AssistantMessage } from "./AssistantMessage";
import { UserMessage } from "./UserMessage";
import type { ChatMessage } from "./types";
import { Button } from "@/components/ui/Button";
import { IconChat, IconSparkle } from "@/components/icons";

const TOOL_LABELS: Record<string, string> = {
  borrower_lookup: "Looking up borrower profile",
  offer_grid: "Retrieving offer grid comparison",
  offer_optimization: "Running MILP optimizer",
  explainability: "Analyzing model drivers",
  portfolio_analytics: "Fetching portfolio KPIs",
  monitoring: "Checking model health",
  frontier_analysis: "Running frontier analysis",
  installment_comparison: "Comparing installment scenarios",
  document_rag: "Searching policy documents",
  model_score: "Running model scorer",
  payment_history: "Fetching payment history",
  human_handoff: "Creating human handoff",
  exception_request: "Logging exception request",
};

const STARTER_PROMPTS = [
  { label: "Recommend by name+code", q: "Recommend a settlement for the first borrower — use their legal name and customer code." },
  { label: "Portfolio EV vs actual", q: "What is the current 3L EV vs actual? How has realisation rate moved this month?" },
  { label: "Frontier · RR cap 50%", q: "What happens to total EV if we cap RR at 50%? Show the efficient frontier." },
  { label: "Optimize portfolio MILP", q: "Optimize portfolio with RR capped at 50%." },
];

export function ChatPanel({ fullWidth }: { fullWidth?: boolean }) {
  const { role } = useRole();
  const [collapsed, setCollapsed] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [statusText, setStatusText] = useState<string>();
  const [conversationId, setConversationId] = useState<string>();
  const [history, setHistory] = useState<ConversationSummary[]>([]);
  const [historyQuery, setHistoryQuery] = useState("");
  const [showHistory, setShowHistory] = useState(fullWidth);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController>();

  const send = useCallback(async (text: string) => {
    if (!text.trim() || loading) return;
    setCollapsed(false);
    const userIdx = messages.length;
    setMessages((m) => [...m, { role: "user", content: text }]);
    setInput("");
    setLoading(true);
    setStatusText("Analyzing your question...");
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const assistantIdx = userIdx + 1;
    setMessages((m) => [...m, { role: "assistant", content: "", tool_calls: [] }]);

    try {
      const res = await chatStream(text, role, conversationId, (event) => {
        if (event.type === "status") setStatusText(event.message);
        else if (event.type === "tool_start") setStatusText(TOOL_LABELS[event.tool] || `Running ${event.tool}...`);
        else if (event.type === "answer") {
          setMessages((m) => {
            const copy = [...m];
            if (copy[assistantIdx]) copy[assistantIdx] = { ...copy[assistantIdx], content: event.content };
            return copy;
          });
          setStatusText(undefined);
        } else if (event.type === "done") {
          setConversationId(event.conversation_id);
          setMessages((m) => {
            const copy = [...m];
            if (copy[assistantIdx]) {
              copy[assistantIdx] = {
                role: "assistant",
                content: event.answer,
                intent: event.intent,
                tool_calls: event.tool_calls,
                recommendation: event.recommendation,
                guardrails: event.guardrails,
                workflow: event.workflow,
              };
            }
            return copy;
          });
        }
      }, controller.signal);
      setConversationId(res.conversation_id);
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setMessages((m) => {
          const copy = [...m];
          if (copy[assistantIdx]) copy[assistantIdx] = { role: "assistant", content: "Sorry, something went wrong." };
          return copy;
        });
      }
    } finally {
      setLoading(false);
      setStatusText(undefined);
    }
  }, [loading, messages.length, conversationId, role]);

  useEffect(() => {
    listConversations(role, historyQuery).then(setHistory).catch(() => {});
  }, [role, historyQuery, conversationId]);

  useEffect(() => {
    const handler = (e: Event) => {
      const q = (e as CustomEvent<{ question: string }>).detail?.question;
      if (q) send(q);
    };
    window.addEventListener("ask-agent", handler);
    return () => window.removeEventListener("ask-agent", handler);
  }, [send]);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("q");
    if (q && fullWidth) send(q);
  }, [fullWidth]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, statusText]);

  if (collapsed && !fullWidth) {
    return (
      <button
        onClick={() => setCollapsed(false)}
        className="w-10 border-l border-slate-200 bg-white flex items-center justify-center hover:bg-slate-50"
        aria-label="Expand chat"
      >
        <IconChat className="w-4 h-4 text-slate-500" />
      </button>
    );
  }

  return (
    <aside
      className={clsx(
        "border-l border-slate-200 bg-white flex flex-col shrink-0",
        fullWidth ? "flex-1 min-w-0" : "w-[380px]",
      )}
    >
      <div className="px-3 py-2.5 border-b border-slate-100 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <IconSparkle className="w-4 h-4 text-blue-600 shrink-0" />
          <span className="text-sm font-semibold text-slate-900">Agent</span>
        </div>
        <div className="flex gap-1 shrink-0">
          <button
            type="button"
            onClick={() => setShowHistory((s) => !s)}
            className="text-xs text-slate-500 hover:text-slate-800 px-2 py-1 rounded-md hover:bg-slate-50"
          >
            History
          </button>
          {messages.length > 0 && (
            <button
              type="button"
              onClick={() => {
                abortRef.current?.abort();
                setMessages([]);
                setConversationId(undefined);
              }}
              className="text-xs text-slate-500 hover:text-slate-800 px-2 py-1 rounded-md hover:bg-slate-50"
            >
              New
            </button>
          )}
          {!fullWidth && (
            <button
              type="button"
              onClick={() => setCollapsed(true)}
              className="text-xs text-slate-400 hover:text-slate-700 px-2 py-1 rounded-md hover:bg-slate-50"
              aria-label="Collapse chat"
            >
              ×
            </button>
          )}
        </div>
      </div>

      {showHistory && (
        <div className="border-b border-slate-100 p-2 max-h-36 overflow-y-auto bg-slate-50/50">
          <input
            value={historyQuery}
            onChange={(e) => setHistoryQuery(e.target.value)}
            placeholder="Search chats..."
            className="input-field text-xs mb-2"
          />
          {history.length === 0 && (
            <p className="text-[11px] text-slate-400 px-2 py-1">No saved chats yet.</p>
          )}
          {history.map((c) => (
            <button
              key={c.conversation_id}
              onClick={() => { setConversationId(c.conversation_id); setShowHistory(false); }}
              className="block w-full text-left text-xs p-2 rounded-md hover:bg-white truncate text-slate-600"
            >
              {c.preview || "Untitled chat"}
            </button>
          ))}
        </div>
      )}

      <div className="flex-1 flex flex-col overflow-hidden min-h-0">
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && !loading && (
            <div className={clsx("py-6", fullWidth ? "max-w-xl mx-auto" : "")}>
              <p className="text-sm font-medium text-slate-800 text-center">Ask the settlement portfolio agent</p>
              <p className="text-xs text-slate-500 text-center mt-1 mb-4 leading-relaxed">
                Optimal offers, EV vs actual, frontier constraints, and policy answers — grounded in models and guardrails.
              </p>
              <div className="flex flex-wrap gap-2 justify-center">
                {STARTER_PROMPTS.map((p) => (
                  <button key={p.q} type="button" className="chip-quiet" onClick={() => send(p.q)}>
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((msg, i) =>
            msg.role === "user" ? (
              <UserMessage key={i} content={msg.content} roleLabel={role} />
            ) : (
              <AssistantMessage key={i} message={msg} onFollowUp={send} />
            ),
          )}
          {loading && statusText && (
            <div className="flex items-center gap-2 px-2 text-xs text-slate-500">
              <span className="inline-flex gap-0.5">
                <span className="typing-dot w-1 h-1 rounded-full bg-blue-500" />
                <span className="typing-dot w-1 h-1 rounded-full bg-blue-500" />
                <span className="typing-dot w-1 h-1 rounded-full bg-blue-500" />
              </span>
              <span>{statusText}</span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
        <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="p-3 border-t border-slate-100 flex gap-2 bg-white">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question…"
            className="input-field flex-1 text-sm"
            disabled={loading}
          />
          <Button type="submit" size="sm" disabled={loading || !input.trim()}>Send</Button>
        </form>
      </div>
    </aside>
  );
}
