"use client";
import { useState } from "react";
import { GroundedResponse, Provider, Source, streamChat } from "@/lib/api";

export function useChatStream() {
  const [streamingText, setStreamingText] = useState(""); const [sources, setSources] = useState<Source[]>([]); const [loading, setLoading] = useState(false); const [error, setError] = useState<string | null>(null);
  const send = async (sessionId: string, message: string, provider: Provider): Promise<GroundedResponse | null> => { setLoading(true); setError(null); setStreamingText(""); setSources([]); let done: GroundedResponse | null = null; let streamError = false; let timeoutId: ReturnType<typeof setTimeout> | undefined; try { const timeout = new Promise<never>((_, reject) => { timeoutId = setTimeout(() => reject(new Error("The response took too long. Check the backend logs and try again.")), 90_000); }); await Promise.race([streamChat(sessionId, message, provider, (event, data) => { if (event === "token") setStreamingText((current) => current + (data as { text: string }).text); if (event === "source") setSources((current) => [...current, data as Source]); if (event === "done") done = data as GroundedResponse; if (event === "error") { streamError = true; setError((data as { message: string }).message); } }), timeout]); if (!done && !streamError) setError("The backend closed the stream without a completed answer."); return done; } catch (reason) { setError(reason instanceof Error ? reason.message : "Chat failed."); return null; } finally { if (timeoutId) clearTimeout(timeoutId); setLoading(false); } };
  return { streamingText, sources, loading, error, send };
}
