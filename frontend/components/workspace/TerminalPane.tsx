"use client";

import { useEffect, useRef } from "react";

import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

export function TerminalPane({ lines, running }: { lines: string[]; running: boolean }) {
  const endRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [lines, running]);

  return (
    <div className="h-full flex flex-col min-h-0 bg-[#070708]">
      <div className="h-9 px-3 border-b border-zinc-800 flex items-center gap-2">
        <span className="text-[10px] font-medium uppercase tracking-label text-zinc-500">Execution log</span>
        <span className="font-mono text-[10px] text-zinc-600">pytest -v --tb=short</span>
        {running ? <span className="ml-auto h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" /> : null}
      </div>
      <ScrollArea className="flex-1 min-h-0 px-3 py-2">
        <div className="font-mono text-[12px] leading-5">
          {lines.length === 0 ? (
            <p className="text-zinc-600">$ waiting for executor…</p>
          ) : (
            lines.map((line, index) => (
              <p key={`${index}-${line.slice(0, 24)}`} className={cn("whitespace-pre-wrap break-all", tone(line))}>
                {line}
              </p>
            ))
          )}
          {running ? <p className="text-zinc-500">▍</p> : null}
          <div ref={endRef} />
        </div>
      </ScrollArea>
    </div>
  );
}

function tone(line: string): string {
  if (/\bPASSED\b/.test(line) || line.includes(" passed")) return "text-emerald-400";
  if (/\bFAILED\b/.test(line) || /\bERROR\b/.test(line)) return "text-red-400";
  if (line.includes("Traceback") || line.trim().startsWith("E ")) return "text-red-300/90";
  if (line.startsWith("=") || line.startsWith("-")) return "text-zinc-500";
  if (line.startsWith("[architect]") || line.startsWith("[engineer]") || line.startsWith("[healer]")) return "text-zinc-400";
  return "text-zinc-300";
}
