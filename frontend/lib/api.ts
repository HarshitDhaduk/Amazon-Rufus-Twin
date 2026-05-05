import { AnalyzeRequest, AnalyzeResponse, MarketEstimate, PersonaContext, ReportCard, SSEEvent } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function analyzeProducts(req: AnalyzeRequest): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail ?? `HTTP ${res.status}`);
  }

  return res.json();
}

/**
 * Stream analysis via SSE.
 * Events: persona → market_estimate → token (many) → report_card → [DONE]
 */
export async function streamAnalysis(
  req: AnalyzeRequest,
  callbacks: {
    onPersona?: (persona: PersonaContext) => void;
    onQueryPlan?: (plan: { query_type: string; routing: Record<string, unknown> }) => void;
    onToken: (token: string) => void;
    onReportCard: (report: ReportCard) => void;
    onMarketEstimate: (estimate: MarketEstimate) => void;
    onError: (err: Error) => void;
    onDone: () => void;
  }
): Promise<void> {
  try {
    const res = await fetch(`${API_BASE}/analyze/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: "Unknown error" }));
      throw new Error(error.detail ?? `HTTP ${res.status}`);
    }

    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() ?? "";

      for (const chunk of lines) {
        const line = chunk.trim();
        if (!line || !line.startsWith("data: ")) continue;
        const data = line.slice(6).trim();
        if (data === "[DONE]") {
          callbacks.onDone();
          return;
        }

        try {
          const event: SSEEvent = JSON.parse(data);
          if (event.type === "persona") {
            callbacks.onPersona?.(event.content);
          } else if (event.type === "query_plan") {
            callbacks.onQueryPlan?.(event.content);
          } else if (event.type === "token") {
            callbacks.onToken(event.content);
          } else if (event.type === "report_card") {
            callbacks.onReportCard(event.content);
          } else if (event.type === "market_estimate") {
            callbacks.onMarketEstimate(event.content);
          } else if (event.type === "error") {
            callbacks.onError(new Error(event.content));
            return;
          }
        } catch {
          // skip malformed chunk
        }
      }
    }
    callbacks.onDone();
  } catch (err) {
    callbacks.onError(err instanceof Error ? err : new Error(String(err)));
  }
}
