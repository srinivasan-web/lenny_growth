export type Source = { source_id: string; episode: string; guest: string | null; timestamp: string | null; topic: string | null; source_url: string; similarity_score: number };
export type Message = { id: string; role: "user" | "assistant" | "system"; content: string; provider: string | null; model: string | null; source_metadata: { sources?: Source[] } | null; created_at: string };
export type Session = { id: string; title: string | null; created_at: string; updated_at: string; messages: Message[] };
export type GroundedResponse = { answer: string; sources: Source[]; retrieval_metadata: { provider: string | null; model: string | null } };
const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> { const response = await fetch(`${apiBase}${path}`, { ...init, headers: { "Content-Type": "application/json", ...init?.headers } }); if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? `Request failed (${response.status})`); return response.json() as Promise<T>; }
export const createSession = (title?: string) => request<Session>("/sessions", { method: "POST", body: JSON.stringify({ title }) });
export const getSession = (id: string) => request<Session>(`/sessions/${id}`);

export type Provider = "openai" | "cloud" | "ollama";
export async function streamChat(sessionId: string, message: string, provider: Provider, onEvent: (event: string, data: unknown) => void): Promise<void> {
  const response = await fetch(`${apiBase}/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: sessionId, message, provider }) });
  if (!response.ok || !response.body) throw new Error(`Chat request failed (${response.status})`);
  const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = "";
  const processFrames = (flush = false) => { const frames = buffer.split("\n\n"); buffer = flush ? "" : (frames.pop() ?? ""); for (const frame of frames) { const event = frame.match(/^event: (.+)$/m)?.[1]; const raw = frame.match(/^data: (.+)$/m)?.[1]; if (!event || !raw) continue; try { onEvent(event, JSON.parse(raw)); } catch { throw new Error("The backend returned malformed stream data."); } } };
  while (true) { const { value, done } = await reader.read(); buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done }); processFrames(done); if (done) break; }
}
