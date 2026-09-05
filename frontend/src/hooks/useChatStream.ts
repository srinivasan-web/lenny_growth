"use client";
import { useState } from "react";
import { GroundedResponse, Provider, Source, streamChat } from "@/lib/api";

export function useChatStream() {
  const [streamingText, setStreamingText] = useState(""); const [sources, setSources] = useState<Source[]>([]); const [loading, setLoading] = useState(false); const [error, setError] = useState<string | null>(null);
  const send = async (sessionId: string, message: string, provider: Provider): Promise<GroundedResponse | null> => { setLoading(true); setError(null); setStreamingText(""); setSources([]); let done: GroundedResponse | null = null; try { await streamChat(sessionId, message, provider, (event, data) => { if (event === "token") setStreamingText((current) => current + (data as { text: string }).text); if (event === "source") setSources((current) => [...current, data as Source]); if (event === "done") done = data as GroundedResponse; if (event === "error") setError((data as { message: string }).message); }); return done; } catch (reason) { setError(reason instanceof Error ? reason.message : "Chat failed."); return null; } finally { setLoading(false); } };
  return { streamingText, sources, loading, error, send };
}
