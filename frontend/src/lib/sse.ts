/** Minimal SSE-over-fetch parser for POST /api/chat (no EventSource: we need POST + bodies). */

export interface SseEvent {
  event: string;
  data: string;
}

export async function* streamSse(
  response: Response,
  signal?: AbortSignal
): AsyncGenerator<SseEvent> {
  const reader = response.body?.getReader();
  if (!reader) throw new Error("empty response body");
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      if (signal?.aborted) break;
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let separator: number;
      while ((separator = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, separator);
        buffer = buffer.slice(separator + 2);
        const parsed = parseBlock(block);
        if (parsed) yield parsed;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

function parseBlock(block: string): SseEvent | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }
  if (!dataLines.length) return null;
  return { event, data: dataLines.join("\n") };
}
