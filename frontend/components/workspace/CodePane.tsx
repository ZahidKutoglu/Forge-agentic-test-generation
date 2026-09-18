"use client";

import { Highlight, themes } from "prism-react-renderer";
import { Check, Copy } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

type FileTab = "pytest" | "sut";

export function CodePane({
  pytestCode,
  sutCode,
  testFilename,
  sutFilename,
}: {
  pytestCode: string;
  sutCode: string;
  testFilename: string;
  sutFilename: string;
}) {
  const [tab, setTab] = useState<FileTab>("pytest");
  const [copied, setCopied] = useState(false);
  const code = tab === "pytest" ? pytestCode : sutCode;
  const filename = tab === "pytest" ? testFilename : sutFilename;
  const empty = !code.trim();

  const theme = useMemo(
    () => ({
      ...themes.vsDark,
      plain: { ...themes.vsDark.plain, backgroundColor: "#09090b", color: "#d4d4d8" },
    }),
    [],
  );

  async function copy() {
    if (!code) return;
    await navigator.clipboard.writeText(code);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="h-9 px-2 border-b border-zinc-800 flex items-center gap-1">
        <FileButton active={tab === "pytest"} onClick={() => setTab("pytest")}>
          {testFilename || "test_generated.py"}
        </FileButton>
        <FileButton active={tab === "sut"} onClick={() => setTab("sut")}>
          {sutFilename || "sut.py"}
        </FileButton>
        <div className="ml-auto">
          <Button variant="ghost" size="sm" onClick={copy} disabled={empty}>
            {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? "Copied" : "Copy"}
          </Button>
        </div>
      </div>
      <ScrollArea className="flex-1 min-h-0 bg-canvas">
        {empty ? (
          <div className="h-full flex items-center justify-center px-8">
            <p className="max-w-sm text-center text-[13px] leading-6 text-zinc-500">
              Generated PyTest will land here after the engineer agent compiles the suite.
            </p>
          </div>
        ) : (
          <Highlight theme={theme} code={code.replace(/\n$/, "")} language="python">
            {({ className, style, tokens, getLineProps, getTokenProps }) => (
              <pre className={cn(className, "font-mono text-[12px] leading-5 p-4 m-0")} style={{ ...style, background: "transparent" }}>
                {tokens.map((line, i) => (
                  <div key={i} {...getLineProps({ line })}>
                    <span className="inline-block w-10 pr-4 text-right text-zinc-700 select-none">{i + 1}</span>
                    {line.map((token, key) => (
                      <span key={key} {...getTokenProps({ token })} />
                    ))}
                  </div>
                ))}
              </pre>
            )}
          </Highlight>
        )}
      </ScrollArea>
      <span className="sr-only">{filename}</span>
    </div>
  );
}

function FileButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "h-7 px-2 rounded-sm font-mono text-[11px] transition-colors",
        active ? "bg-zinc-900 text-zinc-100 border border-zinc-800" : "text-zinc-500 hover:text-zinc-300",
      )}
    >
      {children}
    </button>
  );
}
