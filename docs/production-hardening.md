# Production Hardening Audit

Audit scope: backend API, PostgreSQL/pgvector persistence, ingestion and retrieval, LLM providers, frontend streaming and artifact rendering, security controls, and observability. This is a code/configuration audit of the current repository; no production traffic or deployment telemetry was available.

## Existing Controls

- Database migrations create foreign keys, delete cascades, uniqueness constraints, role/time-range checks, transcript and session indexes, and an HNSW vector index.
- Ingestion uses one database transaction and is idempotent by source URL/content hash.
- Retrieval rejects empty queries, validates embedding dimensions, applies a similarity threshold, and sorts by similarity.
- Grounded answers refuse empty evidence and reject empty or uncited model output.
- Provider adapters normalize timeout, transport, HTTP, and malformed-output failures into `ProviderError`.
- Request schemas enforce UUIDs, bounded strings, provider choices, and required fields.
- Markdown is rendered through `react-markdown`; HTML artifacts are sanitized and rendered in an opaque-origin iframe without `allow-same-origin`.

## Risk Table

| Risk | Probability | Impact | Detection | Mitigation |
|---|---|---|---|---|
| Development database password is also the Compose default and PostgreSQL is published on host port 5432 | High in local/shared environments | High | Configuration review; secret scanning; exposed-port scan | Require a non-default secret outside local development; keep DB on the private Compose network; rotate credentials. |
| `embedding_dimensions` is configurable but the ORM and migration hard-code `Vector(384)` | Medium | High | Startup configuration check; ingestion/retrieval dimension tests | Make the dimension immutable per deployment or generate schema/config from one validated setting; fail startup on mismatch. |
| Database connectivity failures in request handlers become generic 500 responses, while only health checks classify them | Medium | High | API error-rate logs; database pool metrics | Add explicit database exception mapping, bounded pool settings, and readiness/liveness separation. |
| Chat commits the user message before generation; later provider/stream failure leaves an incomplete conversation turn | Medium | Medium | Message/provider status audit; failed stream logs | Add turn status or failure metadata, and make persistence semantics explicit for partial generations. |
| Compose runs `alembic upgrade head` as the application startup command; concurrent replicas can race migrations | Medium | High | Deployment logs; migration lock failures | Run migrations as a one-shot release job with a deployment lock, then start replicas. |
| Retrieval has a threshold but no reranker or calibrated relevance evaluation in production | Medium | High | RAG evaluation report; low citation/source acceptance rate | Run the new evaluation command in CI/release checks, calibrate threshold, and add reranking only from measured evidence. |
| Retrieval/embedding exceptions are not converted to `RAGError` before `ChatService` catches failures | Medium | High | Requests that emit `retrieving` and then terminate without an SSE error | Normalize `RetrievalError` and `EmbeddingError` at the RAG boundary and test both `answer` and `stream` paths. |
| Retrieved metadata validation checks presence but not URL scheme, finite scores, or metadata lengths | Medium | Medium | Ingestion validation logs; malformed-row tests | Validate URL schemes, numeric finiteness/ranges, and bounded metadata before persistence and citation rendering. |
| Providers have timeouts but no retry/backoff policy; OpenAI explicitly sets `max_retries=0` | Medium | Medium | Provider error counts and latency percentiles | Add bounded retries for transient failures only, with jitter and a request budget; never retry malformed output. |
| Provider construction errors and unexpected retrieval errors reach the generic exception handler | Medium | Medium | 5xx logs by route/provider | Map known dependency failures to stable 502/503 responses without exposing upstream details. |
| Streaming can fail after headers are sent; frontend JSON parsing also assumes every SSE frame is valid JSON | Medium | High | Client disconnect/error logs; stream completion counters | Emit a terminal error event for all known failures, handle malformed frames defensively, and add cancellation/backpressure tests. |
| No authentication, authorization, rate limiting, or request-size policy beyond field lengths is present | Medium for private local use, High for public deployment | High | Gateway logs; abuse/load testing | Put the API behind authenticated access and rate limits; restrict CORS and enforce body/time budgets at the edge. |
| Frontend chat creation and refresh failures are silently swallowed; stream interruption has no retry or resume behavior | Medium | Medium | Browser error monitoring; failed-request counters | Surface actionable errors, add abort/retry handling, and preserve incomplete-turn state clearly. |
| Generated HTML executes scripts inside an opaque iframe; this is isolated but still permits artifact-side computation and network requests | Low for parent compromise, Medium for abuse/privacy | Medium | Browser security tests; CSP/network review | Keep the sandbox restrictive, consider disabling scripts for ordinary previews, and add CSP/resource policy if interactive artifacts remain required. |
| External source links and generated artifact URLs are not governed by an allowlist | Medium | Medium | URL validation and browser policy tests | Allow only `https` source URLs, use `rel="noreferrer noopener"`, and define an explicit external-resource policy. |
| Logs are text-formatted and have no request IDs, latency, retrieval, or provider metrics | High | Medium/High | Observability review; inability to correlate a failed stream | Add request ID middleware, structured JSON logs, duration fields, retrieval counts/scores, provider/model labels, and error counters. |

## Release Gates

Before public deployment, require:

1. A real evaluation report from `python scripts/evaluate_rag.py` with no execution errors and reviewed case-level predictions.
2. Database migration and embedding-dimension compatibility checks against the target Postgres instance.
3. Stream failure, provider timeout, empty retrieval, malformed citation, and frontend interruption tests.
4. Secret, dependency, container, and exposed-port scans.
5. Request IDs, latency/error metrics, and alert thresholds for database, retrieval, provider, and stream failures.

The audit intentionally does not claim that these release gates have passed; this repository contains no production execution measurements.