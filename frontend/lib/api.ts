import type { GenerateResponse } from "./types";
import { generateTests as runLocal, runTests as rerunLocal, streamGenerate as streamLocal } from "./engine/pipeline";

export async function generateTests(spec: string): Promise<GenerateResponse> {
  return runLocal(spec);
}

export async function runTests(
  runId: string,
  sutCode: string,
  pytestCode: string,
  sutFilename: string,
  testFilename: string,
): Promise<GenerateResponse> {
  return rerunLocal(runId, sutCode, pytestCode, sutFilename, testFilename);
}

export async function streamGenerate(
  spec: string,
  onEvent: (event: Record<string, unknown>) => void,
): Promise<GenerateResponse | null> {
  return streamLocal(spec, onEvent);
}
