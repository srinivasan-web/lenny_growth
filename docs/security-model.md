# Artifact Security Model

Generated artifacts are untrusted. The application never inserts generated HTML into the parent React DOM.

## Rendering boundary

Markdown is rendered as text through `react-markdown` with `remark-gfm`; it is not injected using `dangerouslySetInnerHTML`.

HTML/CSS artifacts are processed by DOMPurify before becoming an iframe `srcDoc`. The sanitizer removes executable script elements, event-handler attributes, and high-risk embedding/navigation elements. The iframe has exactly `sandbox="allow-scripts"`; it never receives `allow-same-origin`.

This means an artifact executes, if executable content survives a future sanitizer-policy change, in an opaque origin. It cannot read the parent document, parent local/session storage, or parent cookies through same-origin browser APIs. The parent and artifact have no message channel in this implementation.

## Limits and verification

DOMPurify prevents known unsafe markup but is not the sole boundary; the iframe sandbox is defense in depth. Tests assert XSS payload removal and the absence of `allow-same-origin`. Browser enforcement of cross-origin DOM/storage access must be manually verified in a running browser before release. Do not add `allow-same-origin`, `allow-top-navigation`, or parent-window message handlers without security review.
