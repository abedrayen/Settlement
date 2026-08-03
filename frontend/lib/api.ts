const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TOKEN_KEY = "access_token";
const COOKIE_NAME = "access_token";

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
  const maxAge = 60 * 60 * 8;
  document.cookie = `${COOKIE_NAME}=${encodeURIComponent(token)}; Path=/; Max-Age=${maxAge}; SameSite=Lax`;
}

export function clearAuthSession(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem("role");
  document.cookie = `${COOKIE_NAME}=; Path=/; Max-Age=0; SameSite=Lax`;
}

function authHeaders(): HeadersInit {
  const h: HeadersInit = { "Content-Type": "application/json" };
  const token = getStoredToken();
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

function handleUnauthorized(): void {
  clearAuthSession();
  if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
    window.location.href = "/login";
  }
}

async function parseError(res: Response): Promise<string> {
  try {
    return await res.text();
  } catch {
    return res.statusText;
  }
}

export async function apiGet<T>(path: string, _role?: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store", headers: authHeaders() });
  if (res.status === 401) {
    handleUnauthorized();
    throw new Error("Unauthorized");
  }
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiPost<T>(path: string, body: unknown, _role?: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (res.status === 401) {
    handleUnauthorized();
    throw new Error("Unauthorized");
  }
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiPut<T>(path: string, body: unknown, _role?: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "PUT",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (res.status === 401) {
    handleUnauthorized();
    throw new Error("Unauthorized");
  }
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiPatch<T>(path: string, body: unknown, _role?: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (res.status === 401) {
    handleUnauthorized();
    throw new Error("Unauthorized");
  }
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export type ChatResult = {
  conversation_id: string;
  answer: string;
  intent: string;
  tool_calls: Array<{ tool: string; input?: unknown; output?: unknown; duration_ms?: number }>;
  recommendation?: Record<string, unknown>;
  guardrails?: Record<string, unknown>;
  workflow?: Record<string, unknown>;
};

export type ChatStreamEvent =
  | { type: "status"; message: string }
  | { type: "tool_start"; tool: string }
  | { type: "tool_done"; tool: string; output?: unknown }
  | { type: "answer"; content: string }
  | { type: "error"; message: string }
  | ({ type: "done" } & ChatResult);

export async function chatStream(
  message: string,
  _role: string,
  conversationId: string | undefined,
  onEvent: (event: ChatStreamEvent) => void,
  signal?: AbortSignal,
): Promise<ChatResult> {
  const res = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ message, conversation_id: conversationId }),
    signal,
  });
  if (res.status === 401) {
    handleUnauthorized();
    throw new Error("Unauthorized");
  }
  if (!res.ok) throw new Error(await parseError(res));
  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: ChatResult | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      try {
        const event = JSON.parse(line.slice(6)) as ChatStreamEvent;
        if (event.type === "error") throw new Error(event.message);
        onEvent(event);
        if (event.type === "done") result = event;
      } catch (e) {
        if (e instanceof SyntaxError) continue;
        throw e;
      }
    }
  }

  if (!result) throw new Error("Stream ended without a result");
  return result;
}

export type ConversationSummary = {
  conversation_id: string;
  preview: string;
  started_at: string;
  domain?: string;
};

export async function listConversations(_role: string, q?: string): Promise<ConversationSummary[]> {
  const qs = q ? `?q=${encodeURIComponent(q)}` : "";
  return apiGet(`/api/audit/conversations${qs}`);
}

export { API_URL };
