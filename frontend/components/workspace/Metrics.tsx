"use client";

import { Separator } from "@/components/ui/separator";

export function Metrics({
  cases,
  coverage,
  durationMs,
  heals,
}: {
  cases: number;
  coverage: number;
  durationMs: number;
  heals: number;
}) {
  return (
    <div className="flex items-center gap-0 h-8">
      <Metric label="cases" value={cases.toString().padStart(2, "0")} />
      <Separator orientation="vertical" className="mx-3 h-4" />
      <Metric label="coverage" value={`${coverage.toFixed(1)}%`} />
      <Separator orientation="vertical" className="mx-3 h-4" />
      <Metric label="duration" value={formatDuration(durationMs)} />
      <Separator orientation="vertical" className="mx-3 h-4" />
      <Metric label="heals" value={String(heals)} />
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-[10px] uppercase tracking-label text-zinc-500">{label}</span>
      <span className="font-mono text-[13px] text-zinc-100 tabular-nums">{value}</span>
    </div>
  );
}

function formatDuration(ms: number): string {
  if (!ms) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}
