import clsx from "clsx";
import { IconChat } from "@/components/icons";
import { Badge } from "@/components/ui/Badge";
import { MarkdownContent } from "./MarkdownContent";
import { RecommendationCard } from "./RecommendationCard";
import { GuardrailPanel } from "./GuardrailPanel";
import { WorkflowBanner } from "./WorkflowBanner";
import { ToolOutputRenderer } from "./ToolOutputRenderer";
import { ToolTrace } from "./ToolTrace";
import type { ChatMessage, GuardrailData, WorkflowData } from "./types";

const INTENT_LABELS: Record<string, string> = {
  settlement: "Settlement",
  recommendation: "Recommendation",
  restructuring: "Restructuring",
  renegotiation: "Renegotiation",
  debt_inquiry: "Debt inquiry",
  payment_history: "Payments",
  decision_explanation: "Explanation",
  policy_exception: "Exception",
  human_handoff: "Handoff",
  model_score: "Model score",
  portfolio: "Portfolio",
  strategy: "Strategy",
  document: "Policy",
  greeting: "Assistant",
};

function getFollowUps(message: ChatMessage): string[] {
  const rec = message.recommendation as {
    customer_code?: number;
    legal_name?: string;
    display_name?: string;
  } | undefined;
  const code = rec?.customer_code;
  const label = rec?.display_name || (rec?.legal_name && code ? `${rec.legal_name} ${code}` : code ? String(code) : null);
  if ((message.intent === "settlement" || message.intent === "recommendation") && label && message.recommendation) {
    return [
      `Why is acceptance probability low for ${label}?`,
      `Explain the model drivers for ${label}`,
    ];
  }
  if (message.intent === "portfolio") {
    return ["Show model monitoring alerts", "What if we cap RR at 50%?"];
  }
  if (message.intent === "document") {
    return ["What is the vulnerability policy?", "Show portfolio KPIs"];
  }
  return [];
}

export function AssistantMessage({
  message,
  onFollowUp,
}: {
  message: ChatMessage;
  onFollowUp?: (text: string) => void;
}) {
  const guardrails = message.guardrails as GuardrailData | undefined;
  const workflow = message.workflow as WorkflowData | undefined;
  const status = guardrails?.status;

  if (!message.content && !message.recommendation && !message.tool_calls?.length) {
    return null;
  }

  const bubbleBorder =
    status === "blocked"
      ? "border-red-300 bg-red-50/30"
      : status === "warning"
        ? "border-amber-300 bg-amber-50/30"
        : "border-slate-200 bg-slate-50";

  return (
    <div className="flex gap-3">
      <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-slate-100 text-slate-600">
        <IconChat className="w-4 h-4" />
      </div>
      <div className="max-w-3xl w-full space-y-3">
        {message.intent && (
          <Badge variant="info" className="text-[10px]">
            {INTENT_LABELS[message.intent] || message.intent}
          </Badge>
        )}

        <div className={clsx("px-4 py-3 rounded-2xl rounded-bl-md border text-sm", bubbleBorder)}>
          <MarkdownContent content={message.content} />
        </div>

        {workflow && <WorkflowBanner workflow={workflow} />}

        {guardrails?.status && <GuardrailPanel guardrails={guardrails} />}

        {message.recommendation && <RecommendationCard data={message.recommendation} />}

        {message.tool_calls && message.tool_calls.length > 0 && (
          <ToolOutputRenderer
            toolCalls={message.tool_calls}
            hasRecommendation={!!message.recommendation}
          />
        )}

        {message.tool_calls && message.tool_calls.length > 0 && (
          <ToolTrace toolCalls={message.tool_calls} />
        )}

        {onFollowUp && message.content && (
          (() => {
            const chips = getFollowUps(message);
            if (!chips.length) return null;
            return (
              <div className="flex gap-2 flex-wrap pt-1">
                {chips.map((chip) => (
                  <button
                    key={chip}
                    onClick={() => onFollowUp(chip)}
                    className="text-xs px-3 py-1.5 rounded-full bg-white border border-slate-200 text-slate-500 hover:border-brand-400 hover:text-brand-600 transition-all"
                  >
                    {chip}
                  </button>
                ))}
              </div>
            );
          })()
        )}
      </div>
    </div>
  );
}
