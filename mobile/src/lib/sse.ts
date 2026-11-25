/** Server-sent events over a streamed POST response (no EventSource: /api/chat is a POST).
 * Same parser as the web app's frontend/src/lib/sse.ts. */

export interface SseEvent {
  event: string;
  data: string;
}

export async function* readSse(body: ReadableStream<Uint8Array>): AsyncGenerator<SseEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }); // a character can span two chunks
      let separator: number;
      while ((separator = buffer.indexOf("\n\n")) !== -1) {
        const parsed = parseBlock(buffer.slice(0, separator));
        buffer = buffer.slice(separator + 2);
        if (parsed) yield parsed;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export function parseBlock(block: string): SseEvent | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).trim());
  }
  return data.length ? { event, data: data.join("\n") } : null;
}
