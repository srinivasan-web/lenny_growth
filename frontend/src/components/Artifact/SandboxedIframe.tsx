"use client";

import React from "react";
import DOMPurify from "dompurify";

export function sanitizeArtifactHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    FORBID_TAGS: ["base", "embed", "link", "meta", "object", "script"],
    FORBID_ATTR: ["srcdoc"],
    ALLOW_UNKNOWN_PROTOCOLS: false,
  });
}

export function SandboxedIframe({ html }: { html: string }) {
  return <iframe title="Generated artifact" className="h-full w-full border-0" sandbox="allow-scripts" srcDoc={sanitizeArtifactHtml(html)} />;
}
