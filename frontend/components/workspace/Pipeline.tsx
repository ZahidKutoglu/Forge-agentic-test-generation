"use client";

import { Check, Circle, Loader2 } from "lucide-react";

import type { AgentStatus, PipelineStep } from "@/lib/types";
import { cn } from "@/lib/utils";

export function Pipeline({
  steps,
  healIterations,
  maxHeals = 3,
}: {
  steps: PipelineStep[];
  healIterations: number;
  maxHeals?: number;
}) {
  return (
    <div className="h-full flex flex-col bg-canvas">
      <div className="h-9 px-3 border-b border-zinc-800 flex items-center justify-between">
        <span className="text-[10px] font-medium uppercase tracking-label text-zinc-500">Agent pipeline</span>
        <span className="font-mono text-[10px] text-zinc-500">
          heal {healIterations}/{maxHeals}
        </span>
      </div>
      <ol className="flex-1 overflow-auto px-3 py-3">
        {steps.map((step, index) => (
          <li key={step.id} className="relative pl-7 pb-4 last:pb-0">
            {index < steps.length - 1 ? (
              <span className="absolute left-[11px] top-5 bottom-0 w-px bg-zinc-800" />
            ) : null}
            <StatusDot status={step.status} />
            <div className="flex items-baseline justify-between gap-3">
              <p className="text-[13px] text-zinc-200 tracking-tight">{step.label}</p>
              <StatusLabel status={step.status} />
            </div>
            <p className="mt-1 text-[12px] leading-5 text-zinc-500">{step.message || "Waiting"}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}

function StatusDot({ status }: { status: AgentStatus }) {
  return (
    <span
      className={cn(
        "absolute left-0 top-1 flex h-[22px] w-[22px] items-center justify-center rounded-full border",
        status === "running" && "border-amber-700/80 bg-amber-950 text-amber-400",
        status === "complete" && "border-emerald-800 bg-emerald-950 text-emerald-400",
        status === "error" && "border-red-800 bg-red-950 text-red-400",
        status === "idle" && "border-zinc-800 bg-zinc-950 text-zinc-600",
        status === "skipped" && "border-zinc-800 bg-zinc-950 text-zinc-600",
      )}
    >
      {status === "running" ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
      {status === "complete" ? <Check className="h-3 w-3" /> : null}
      {status === "idle" || status === "skipped" ? <Circle className="h-2 w-2 fill-current" /> : null}
      {status === "error" ? <Circle className="h-2 w-2 fill-current" /> : null}
    </span>
  );
}

function StatusLabel({ status }: { status: AgentStatus }) {
  const label = status === "complete" ? "done" : status;
  return <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-600">{label}</span>;
}
