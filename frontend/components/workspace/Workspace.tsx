"use client";

import dynamic from "next/dynamic";
import { Hexagon, Play, RotateCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { CodePane } from "@/components/workspace/CodePane";
import { Metrics } from "@/components/workspace/Metrics";
import { Pipeline } from "@/components/workspace/Pipeline";
import { TerminalPane } from "@/components/workspace/TerminalPane";
import { fetchSamples, generateTests, runTests, streamGenerate } from "@/lib/api";
import { FALLBACK_SAMPLES } from "@/lib/samples";
import type { AgentName, AgentStatus, GenerateResponse, PipelineStep, SampleSpec } from "@/lib/types";
import { cn } from "@/lib/utils";

const SpecEditor = dynamic(() => import("./SpecEditor").then((mod) => mod.SpecEditor), {
  ssr: false,
  loading: () => <div className="h-full bg-canvas" />,
});

const INITIAL_STEPS: PipelineStep[] = [
  { id: "architect", label: "Test Architect", status: "idle", message: "Ingest specification, enumerate cases." },
  { id: "engineer", label: "Test Engineer", status: "idle", message: "Compile fixtures, mocks, assertions." },
  { id: "executor", label: "Execution", status: "idle", message: "Run PyTest in an isolated subprocess." },
  { id: "healer", label: "Self-Healing", status: "idle", message: "Route tracebacks back to the engineer." },
];

export function Workspace() {
  const [samples, setSamples] = useState<SampleSpec[]>(FALLBACK_SAMPLES);
  const [sampleId, setSampleId] = useState(FALLBACK_SAMPLES[0].id);
  const [spec, setSpec] = useState(FALLBACK_SAMPLES[0].spec);
  const [steps, setSteps] = useState<PipelineStep[]>(INITIAL_STEPS);
  const [logs, setLogs] = useState<string[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [leftWidth, setLeftWidth] = useState(42);
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const [pytestCode, setPytestCode] = useState("");
  const [sutCode, setSutCode] = useState("");
  const [testFilename, setTestFilename] = useState("test_generated.py");
  const [sutFilename, setSutFilename] = useState("sut.py");
  const [healIterations, setHealIterations] = useState(0);
  const [coverage, setCoverage] = useState(0);
  const [durationMs, setDurationMs] = useState(0);
  const [caseCount, setCaseCount] = useState(0);
  const [splitV, setSplitV] = useState(58);

  useEffect(() => {
    fetchSamples()
      .then((items) => {
        if (items.length) {
          setSamples(items);
          setSampleId(items[0].id);
          setSpec(items[0].spec);
        }
      })
      .catch(() => undefined);
  }, []);

  const suiteStatus = useMemo(() => {
    if (running) return "run";
    if (result?.execution.failed_count || result?.execution.error_count) return "fail";
    if (result?.execution.passed) return "pass";
    return "idle";
  }, [running, result]);

  function resetPipeline() {
    setSteps(INITIAL_STEPS);
    setLogs([]);
    setError("");
    setHealIterations(0);
  }

  function applyResult(payload: GenerateResponse) {
    setResult(payload);
    setPytestCode(payload.pytest_code);
    setSutCode(payload.sut_code);
    setTestFilename(payload.test_filename);
    setSutFilename(payload.sut_filename);
    setHealIterations(payload.heal_iterations);
    setCoverage(payload.coverage_score);
    setDurationMs(payload.execution.duration_ms || payload.duration_ms);
    setCaseCount(payload.test_cases.length || payload.execution.total);
    setLogs(payload.logs.map((line) => line.replace(/^\[pytest\]\s*/, "")));
    setSteps((current) =>
      current.map((step) => {
        const match = payload.events.filter((event) => event.agent === step.id).at(-1);
        if (!match) {
          if (step.id === "healer" && payload.heal_iterations === 0) {
            return { ...step, status: "skipped", message: "No repair loop required." };
          }
          return { ...step, status: payload.status === "passed" ? "complete" : step.status };
        }
        const status = (match.status === "log" ? "complete" : match.status) as AgentStatus;
        return { ...step, status: status === "skipped" ? "skipped" : status, message: match.message };
      }),
    );
  }

  async function onGenerate() {
    if (running) return;
    setRunning(true);
    resetPipeline();
    setSteps((current) => current.map((step) => (step.id === "architect" ? { ...step, status: "running" } : step)));
    try {
      const streamed = await streamGenerate(spec, (event) => {
        if (event.type === "agent" && typeof event.agent === "string") {
          const agent = event.agent as AgentName;
          setSteps((current) =>
            current.map((step) =>
              step.id === agent
                ? {
                    ...step,
                    status: (event.status as AgentStatus) === "coded" || event.status === "architected" ? "complete" : mapStatus(String(event.status)),
                    message: String(event.message || step.message),
                  }
                : step.id === nextAgent(agent) && event.status !== "error"
                  ? { ...step, status: step.status === "idle" ? "running" : step.status }
                  : step,
            ),
          );
          if (agent === "healer") {
            const detail = event.detail as { heal_iterations?: number } | undefined;
            if (detail?.heal_iterations) setHealIterations(detail.heal_iterations);
          }
        }
        if (event.type === "log" && typeof event.line === "string") {
          setLogs((current) => [...current, event.line as string]);
        }
        if (event.type === "code") {
          if (typeof event.pytest_code === "string") setPytestCode(event.pytest_code);
          if (typeof event.sut_code === "string") setSutCode(event.sut_code);
          if (typeof event.test_filename === "string") setTestFilename(event.test_filename);
          if (typeof event.sut_filename === "string") setSutFilename(event.sut_filename);
        }
        if (event.type === "complete" && event.result) {
          applyResult(event.result as GenerateResponse);
        }
      });
      if (streamed) applyResult(streamed);
    } catch {
      try {
        const fallback = await generateTests(spec);
        applyResult(fallback);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Generation failed");
        setSteps((current) => current.map((step) => (step.status === "running" ? { ...step, status: "error" } : step)));
      }
    } finally {
      setRunning(false);
    }
  }

  async function onRerun() {
    if (running || !pytestCode) return;
    setRunning(true);
    setError("");
    setSteps((current) =>
      current.map((step) => (step.id === "executor" ? { ...step, status: "running", message: "Re-running isolated PyTest." } : step)),
    );
    try {
      const payload = await runTests(result?.run_id || "", sutCode, pytestCode, sutFilename, testFilename);
      applyResult(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Run failed");
    } finally {
      setRunning(false);
    }
  }

  function onSample(id: string) {
    const sample = samples.find((item) => item.id === id);
    if (!sample) return;
    setSampleId(id);
    setSpec(sample.spec);
  }

  function onDrag(event: React.MouseEvent<HTMLDivElement>, axis: "h" | "v") {
    event.preventDefault();
    const start = axis === "h" ? event.clientX : event.clientY;
    const origin = axis === "h" ? leftWidth : splitV;
    function move(ev: MouseEvent) {
      if (axis === "h") {
        const delta = ((ev.clientX - start) / window.innerWidth) * 100;
        setLeftWidth(Math.min(62, Math.max(28, origin + delta)));
      } else {
        const delta = ((ev.clientY - start) / window.innerHeight) * 100;
        setSplitV(Math.min(78, Math.max(32, origin + delta)));
      }
    }
    function up() {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    }
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  }

  return (
    <div className="h-screen flex flex-col bg-canvas text-zinc-200">
      <header className="min-h-12 shrink-0 border-b border-zinc-800 flex flex-wrap items-center px-3 gap-x-3 gap-y-2 py-1.5">
        <div className="flex items-center gap-2 pr-3 border-r border-zinc-800">
          <Hexagon className="h-4 w-4 text-zinc-100" strokeWidth={1.6} />
          <div className="leading-tight">
            <p className="text-[13px] font-medium tracking-tight">Forge</p>
            <p className="font-mono text-[10px] text-zinc-500">agentic pytest</p>
          </div>
        </div>
        <div className="flex-1 min-w-0 overflow-x-auto">
          <Metrics cases={caseCount} coverage={coverage} durationMs={durationMs} heals={healIterations} />
        </div>
        <div className="flex items-center gap-2 ml-auto">
          <select
            value={sampleId}
            onChange={(event) => onSample(event.target.value)}
            className="h-8 rounded-md border border-zinc-800 bg-zinc-950 px-2 font-mono text-[11px] text-zinc-300 outline-none hover:border-zinc-700"
          >
            {samples.map((sample) => (
              <option key={sample.id} value={sample.id}>
                {sample.title}
              </option>
            ))}
          </select>
          <Button variant="outline" size="sm" onClick={onRerun} disabled={running || !pytestCode}>
            <RotateCw className={cn("h-3.5 w-3.5", running && "animate-spin")} />
            Re-run
          </Button>
          <Button onClick={onGenerate} disabled={running || spec.trim().length < 20}>
            <Play className="h-3.5 w-3.5" />
            {running ? "Running" : "Generate suite"}
          </Button>
        </div>
      </header>

      <div className="flex-1 flex min-h-0">
        <section className="flex flex-col min-w-0 min-h-0 border-r border-zinc-800" style={{ width: `${leftWidth}%` }}>
          <div className="h-9 px-3 border-b border-zinc-800 flex items-center justify-between">
            <span className="text-[10px] font-medium uppercase tracking-label text-zinc-500">Requirement specification</span>
            <span className="font-mono text-[10px] text-zinc-600">{spec.split(/\s+/).filter(Boolean).length} words</span>
          </div>
          <div className="flex-1 min-h-0" style={{ flex: "1 1 58%" }}>
            <SpecEditor value={spec} onChange={setSpec} />
          </div>
          <div className="h-px bg-zinc-800" />
          <div className="min-h-[220px] h-[38%] shrink-0">
            <Pipeline steps={steps} healIterations={healIterations} />
          </div>
        </section>

        <div
          role="separator"
          onMouseDown={(event) => onDrag(event, "h")}
          className="w-1 cursor-col-resize hover:bg-zinc-700/80 bg-transparent"
        />

        <section className="flex-1 flex flex-col min-w-0 min-h-0">
          <div style={{ height: `${splitV}%` }} className="min-h-0">
            <CodePane
              pytestCode={pytestCode}
              sutCode={sutCode}
              testFilename={testFilename}
              sutFilename={sutFilename}
            />
          </div>
          <div role="separator" onMouseDown={(event) => onDrag(event, "v")} className="h-1 cursor-row-resize hover:bg-zinc-700/80" />
          <div className="flex-1 min-h-0">
            <TerminalPane lines={logs} running={running} />
          </div>
        </section>
      </div>

      <footer className="h-8 shrink-0 border-t border-zinc-800 flex items-center px-3 gap-3 text-[11px] text-zinc-500">
        <Badge variant={suiteStatus === "pass" ? "pass" : suiteStatus === "fail" ? "fail" : suiteStatus === "run" ? "run" : "idle"}>
          {suiteStatus === "pass" ? "passing" : suiteStatus === "fail" ? "failing" : suiteStatus === "run" ? "running" : "idle"}
        </Badge>
        <span className="font-mono">
          {result ? `${result.execution.passed_count}/${result.execution.total || caseCount} tests` : "no run"}
        </span>
        {result?.run_id ? <span className="font-mono text-zinc-600">run {result.run_id}</span> : null}
        {result?.provider ? <span className="font-mono text-zinc-600">agent:{result.provider}</span> : null}
        {error ? <span className="text-red-400 truncate">{error}</span> : null}
        <span className="ml-auto font-mono text-zinc-600">Architect → Engineer → Executor → Heal</span>
      </footer>
    </div>
  );
}

function mapStatus(status: string): AgentStatus {
  if (status === "running" || status === "healing" || status === "coded" || status === "architected") {
    return status === "running" || status === "healing" ? "running" : "complete";
  }
  if (status === "complete" || status === "passed") return "complete";
  if (status === "error" || status === "failed") return "error";
  if (status === "skipped") return "skipped";
  if (status === "idle") return "idle";
  return "running";
}

function nextAgent(agent: AgentName): AgentName | null {
  if (agent === "architect") return "engineer";
  if (agent === "engineer") return "executor";
  if (agent === "healer") return "engineer";
  return null;
}
