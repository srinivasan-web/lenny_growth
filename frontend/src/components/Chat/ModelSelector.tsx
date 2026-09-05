"use client";

import { Provider } from "@/lib/api";

export function ModelSelector({ value, onChange }: { value: Provider; onChange: (provider: Provider) => void }) {
  return <label className="provider-control"><span>Provider</span><select value={value} onChange={(event) => onChange(event.target.value as Provider)}><option value="openai">OpenAI</option><option value="ollama">Ollama</option></select><i>⌄</i></label>;
}
