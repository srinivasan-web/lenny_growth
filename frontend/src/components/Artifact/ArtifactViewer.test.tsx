import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { detectArtifact } from "./ArtifactViewer";
import { SandboxedIframe, sanitizeArtifactHtml } from "./SandboxedIframe";

describe("artifact isolation", () => {
  it("detects fenced Markdown and HTML artifacts", () => {
    expect(detectArtifact("```markdown\n# Checklist\n" + "```")?.type).toBe("markdown");
    expect(detectArtifact("```html\n<div>Preview</div>\n" + "```")?.type).toBe("html");
  });

  it("sanitizes XSS payloads before setting srcDoc", () => {
    const dirty = '<img src=x onerror="parent.document.body.innerHTML=\'x\'"><script>parent.localStorage.clear()</script>';
    const clean = sanitizeArtifactHtml(dirty);
    expect(clean).not.toContain("onerror");
    expect(clean).not.toContain("<script");
  });

  it("uses an opaque-origin sandbox without allow-same-origin", () => {
    render(<SandboxedIframe html="<h1>Safe preview</h1>" />);
    const frame = screen.getByTitle("Generated artifact");
    expect(frame.getAttribute("sandbox")).toBe("allow-scripts");
    expect(frame.getAttribute("sandbox")).not.toContain("allow-same-origin");
    expect(frame.getAttribute("srcdoc")).toContain("Safe preview");
  });
});
