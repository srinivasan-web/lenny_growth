"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { SandboxedIframe } from "./SandboxedIframe";

export type Artifact = { type: "markdown" | "html"; content: string; title?: string };

const fencedArtifact = /^```(?<type>html|css|markdown|md)[ \t]*\r?\n(?<content>[\s\S]*?)\r?\n```$/i;

export function detectArtifact(content: string): Artifact | null {
  const fenced = content.match(fencedArtifact);
  if (fenced?.groups?.content) {
    const type = fenced.groups.type;
    if (type === "css") return { type: "html", content: `<style>${fenced.groups.content}</style><div class="artifact-preview"></div>` };
    return { type: type === "html" ? "html" : "markdown", content: fenced.groups.content };
  }
  if (/^\s*<!doctype html|^\s*<html[\s>]/i.test(content)) return { type: "html", content };
  return null;
}

export function ArtifactViewer({ artifact }: { artifact: Artifact | null }) {
  if (!artifact) return <div className="artifact-empty"><div className="empty-grid"><span /><span /><span /><span /></div><p>Generated outputs will appear here</p><small>Ask a question to create a research artifact.</small></div>;
  if (artifact.type === "html") return <SandboxedIframe html={artifact.content} />;
  return <div className="artifact-markdown prose prose-invert max-w-none"><ReactMarkdown remarkPlugins={[remarkGfm]}>{artifact.content}</ReactMarkdown></div>;
}
