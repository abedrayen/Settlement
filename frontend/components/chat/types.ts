export type ToolCall = {
  tool: string;
  input?: unknown;
  output?: unknown;
  duration_ms?: number;
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  intent?: string;
  tool_calls?: ToolCall[];
  recommendation?: Record<string, unknown>;
  guardrails?: Record<string, unknown>;
  workflow?: Record<string, unknown>;
};

export type GuardrailData = {
  status?: string;
  checks?: string[];
  reason?: string | null;
  workflow_type?: string | null;
};

export type WorkflowData = {
  type?: string;
  status?: string;
  reason?: string;
  queue?: string;
  risk_tier?: string;
  task_id?: string;
};
