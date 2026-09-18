import type { GenerateResponse, SampleSpec } from "./types";

const API = "";

async function parseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return body.detail || body.message || response.statusText;
  } catch {
    return response.statusText;
  }
}

export async function fetchSamples(): Promise<SampleSpec[]> {
  const response = await fetch(`${API}/api/samples`);
  if (!response.ok) return [];
  const body = await response.json();
  return body.samples ?? [];
}

export async function generateTests(spec: string): Promise<GenerateResponse> {
  const response = await fetch(`${API}/api/generate-tests`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ spec, execute: true, max_repairs: 3 }),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function runTests(runId: string, sutCode: string, pytestCode: string, sutFilename: string, testFilename: string): Promise<GenerateResponse> {
  const response = await fetch(`${API}/api/run-tests`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      run_id: runId || null,
      sut_code: sutCode,
      pytest_code: pytestCode,
      sut_filename: sutFilename,
      test_filename: testFilename,
    }),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function streamGenerate(
  spec: string,
  onEvent: (event: Record<string, unknown>) => void,
): Promise<GenerateResponse | null> {
  const response = await fetch(`${API}/api/generate-tests/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ spec, execute: true, max_repairs: 3 }),
  });
  if (!response.ok || !response.body) {
    throw new Error(await parseError(response));
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: GenerateResponse | null = null;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const line = part.split("\n").find((item) => item.startsWith("data: "));
      if (!line) continue;
      const payload = JSON.parse(line.slice(6)) as Record<string, unknown>;
      onEvent(payload);
      if (payload.type === "complete") {
        result = payload.result as GenerateResponse;
      }
    }
  }
  return result;
}
