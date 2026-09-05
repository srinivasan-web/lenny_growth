"use client";

import { FormEvent, useEffect, useState } from "react";
import { Artifact, ArtifactViewer, detectArtifact } from "@/components/Artifact/ArtifactViewer";
import { ModelSelector } from "@/components/Chat/ModelSelector";
import { createSession, getSession, Message, Provider, Session, Source } from "@/lib/api";
import { useChatStream } from "@/hooks/useChatStream";

function SourceList({ sources }: { sources: Source[] }) {
  if (!sources.length) return null;
  return (
    <div className="source-stack">
      <div className="source-heading"><span className="source-rule" /> Evidence used</div>
      <ul>{sources.map((source) => <li key={source.source_id}>
        <a href={source.source_url} target="_blank" rel="noreferrer"><span className="source-badge">{source.source_id}</span>{source.episode}</a>
        {source.guest && <span>{source.guest}</span>}{source.timestamp && <span>{source.timestamp}</span>}
      </li>)}</ul>
    </div>
  );
}

function MessageCard({ message }: { message: Message }) {
  const isUser = message.role === "user";
  return (
    <article className={`message-card ${isUser ? "message-user" : "message-assistant"}`}>
      <div className="message-meta"><span className={`role-mark ${isUser ? "role-user" : "role-assistant"}`}>{isUser ? "You" : "Lenny AI"}</span>{!isUser && message.provider && <span className="model-note">{message.provider}</span>}</div>
      <div className="message-content">{message.content}</div>
      {!isUser && <SourceList sources={message.source_metadata?.sources ?? []} />}
    </article>
  );
}

function EmptyConversation() {
  return <div className="empty-conversation"><div className="signal-mark"><span /><span /><span /></div><p className="eyebrow">Grounded research workspace</p><h2>Ask better questions.<br /><em>Find the signal.</em></h2><p className="empty-copy">Explore product, growth, and startup lessons from Lenny&apos;s podcast archive.</p></div>;
}

export default function Home() {
  const [session, setSession] = useState<Session | null>(null);
  const [input, setInput] = useState("");
  const [provider, setProvider] = useState<Provider>("ollama");
  const [artifactOpen, setArtifactOpen] = useState(true);
  const [artifact, setArtifact] = useState<Artifact | null>(null);
  const { streamingText, sources, loading, error, send } = useChatStream();

  const start = () => createSession("New conversation").then(setSession).catch(() => undefined);
  useEffect(() => { start(); }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!session || !input.trim() || loading) return;
    const content = input.trim();
    setInput("");
    const user: Message = { id: crypto.randomUUID(), role: "user", content, provider: null, model: null, source_metadata: null, created_at: new Date().toISOString() };
    setSession({ ...session, messages: [...session.messages, user] });
    const response = await send(session.id, content, provider);
    if (response) {
      setArtifact(detectArtifact(response.answer));
      setSession((current) => current ? { ...current, messages: [...current.messages, { id: crypto.randomUUID(), role: "assistant", content: response.answer, provider: response.retrieval_metadata.provider, model: response.retrieval_metadata.model, source_metadata: { sources: response.sources }, created_at: new Date().toISOString() }] } : current);
    }
  };

  if (!session) return <main className="loading-screen"><div className="loading-orbit" />Preparing your workspace</main>;
  return (
    <main className="app-shell">
      <header className="topbar"><div className="brand-lockup"><div className="brand-icon"><span /><span /><span /></div><div><div className="brand-name">Lenny<span>+</span></div><div className="brand-subtitle">Growth intelligence</div></div></div><div className="topbar-status"><span className="status-dot" /> Archive connected <span className="status-divider" /> <span className="topbar-date">Research mode</span></div></header>
      <div className="workspace">
        <section className="chat-panel">
          <div className="panel-heading"><div><p className="eyebrow">Conversation</p><h1>Ask the archive</h1></div><div className="panel-actions"><button className="quiet-button" onClick={start}><span className="button-symbol">+</span> New</button><button className="icon-button" onClick={() => getSession(session.id).then(setSession).catch(() => undefined)} aria-label="Refresh conversation" title="Refresh conversation">↻</button></div></div>
          <div className="conversation-scroll">{!session.messages.length && !loading ? <EmptyConversation /> : session.messages.map((message) => <MessageCard key={message.id} message={message} />)}{loading && <article className="message-card message-assistant message-loading"><div className="message-meta"><span className="role-mark role-assistant">Lenny AI</span><span className="model-note">researching</span></div><div className="typing-line"><span /><span /><span /></div>{sources.length > 0 && <SourceList sources={sources} />}{streamingText && <div className="message-content streaming-copy">{streamingText}</div>}</article>}</div>
          {error && <div className="error-banner" role="alert"><span>!</span>{error}</div>}
          <form className="composer" onSubmit={submit}><div className="composer-input"><textarea value={input} onChange={(event) => setInput(event.target.value)} placeholder="Ask about product, growth, or strategy..." aria-label="Ask the archive" /><div className="composer-footer"><span>Grounded answers with source evidence</span><span className="shortcut">Enter to send</span></div></div><button className="send-button" disabled={loading || !input.trim()} aria-label="Send question"><span>Send</span><b>↗</b></button></form>
        </section>
        <aside className={`artifact-panel ${artifactOpen ? "" : "artifact-collapsed"}`}><div className="artifact-heading"><div><p className="eyebrow">Output</p><h2>Artifact canvas</h2></div><button className="icon-button" onClick={() => setArtifactOpen((open) => !open)} aria-label={artifactOpen ? "Hide artifact canvas" : "Show artifact canvas"} title={artifactOpen ? "Hide artifact canvas" : "Show artifact canvas"}>{artifactOpen ? "−" : "+"}</button></div>{artifactOpen && <div className="artifact-body"><div className="artifact-toolbar"><span className="canvas-dot" /> Live preview <span className="toolbar-divider" /> {artifact ? artifact.type.toUpperCase() : "WAITING"}</div><div className="artifact-content"><ArtifactViewer artifact={artifact} /></div></div>}</aside>
      </div>
      <footer className="app-footer"><span>LENNY+ / ARCHIVE WORKSPACE</span><span>Evidence first <span className="footer-dot">·</span> Claims grounded in transcript sources</span></footer>
    </main>
  );
}
