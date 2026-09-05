"use client";

import { Provider } from "@/lib/api";

export function ModelSelector({ value, onChange }: { value: Provider; onChange: (provider: Provider) => void }) {
  return <label className="text-xs text-slate-400">Provider <select value={value} onChange={(event) => onChange(event.target.value as Provider)} className="ml-1 rounded bg-slate-800 p-1 text-slate-100"><option value="openai">OpenAI</option><option value="ollama">Ollama</option></select></label>;
}
