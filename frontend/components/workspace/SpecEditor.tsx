"use client";

import Editor, { type OnMount } from "@monaco-editor/react";

const OPTIONS = {
  minimap: { enabled: false },
  fontSize: 13,
  fontFamily: "var(--font-mono), JetBrains Mono, ui-monospace, monospace",
  lineHeight: 20,
  padding: { top: 12, bottom: 16 },
  scrollBeyondLastLine: false,
  renderLineHighlight: "line" as const,
  overviewRulerLanes: 0,
  hideCursorInOverviewRuler: true,
  scrollbar: { verticalScrollbarSize: 8, horizontalScrollbarSize: 8 },
  smoothScrolling: true,
  wordWrap: "on" as const,
  tabSize: 2,
  automaticLayout: true,
};

export function SpecEditor({ value, onChange }: { value: string; onChange: (next: string) => void }) {
  const handleMount: OnMount = (editor, monaco) => {
    monaco.editor.defineTheme("forge", {
      base: "vs-dark",
      inherit: true,
      rules: [
        { token: "comment", foreground: "52525b" },
        { token: "keyword", foreground: "a1a1aa" },
        { token: "string", foreground: "d4d4d8" },
        { token: "number", foreground: "e4e4e7" },
      ],
      colors: {
        "editor.background": "#09090b",
        "editor.foreground": "#d4d4d8",
        "editorLineNumber.foreground": "#3f3f46",
        "editorLineNumber.activeForeground": "#a1a1aa",
        "editor.selectionBackground": "#27272a",
        "editor.lineHighlightBackground": "#18181b",
        "editorCursor.foreground": "#fafafa",
        "editorIndentGuide.background": "#1c1c1f",
        "editorWidget.background": "#09090b",
        "editorGutter.background": "#09090b",
      },
    });
    monaco.editor.setTheme("forge");
    editor.focus();
  };

  return (
    <Editor
      height="100%"
      defaultLanguage="markdown"
      value={value}
      onChange={(next) => onChange(next ?? "")}
      onMount={handleMount}
      options={OPTIONS}
      theme="vs-dark"
    />
  );
}
