# Document sources and retrieval traces

The web frontend requests citations with `include_sources: true` on either
`/documents/retrieval/stream` or `/documents/retrieval/agent-stream`. The previous SQL chunks schema remains supported. The optional
[source metadata migration](migrations/README.md) enables SQL storage of page,
chunk index and OCR metadata; Qdrant and citation snapshots retain these fields
even without the migration. Restart after migration to refresh schema capabilities.

## Authentication

Register or log in first. These routes set an expiring, signed, HttpOnly cookie
with SameSite=Strict. All `/documents` routes require that session and reject a
supplied user ID that differs from its signed identity. Browser requests use
same-origin credentials. Existing browser users must log in again after upgrading;
a previously cached user object does not authenticate a request.

Configure `NOTEBOOK_SESSION_SECRET` as an environment secret of at least 32
characters for persistent sessions and multiple worker processes. If absent, a
random per-process secret supports local development, and restarting the process
requires another login. HTTPS requests receive Secure cookies; configure trusted
proxy headers correctly when terminating TLS upstream. `/auth/logout` clears the
browser cookie. API clients must retain the cookie from login for document calls.

## SSE contract

Without `include_sources`, the token/error/done event contract remains unchanged.
With sources enabled, the standard retrieval stream sends:

1. `sources`: a `turn_id` and source snapshots used in the model context.
2. `retrieval_trace`: optional, separately authorized diagnostics.
3. `token`: answer text, including `[[source:N]]` markers.
4. `citations`: valid/invalid IDs and `saved: true`, after summary/history storage.
5. `done`: `saved: true`.

A failed retrieval, generation, summarization or history write sends `error` and
never a successful `done`. A partially delivered answer is not confirmed saved.
Citation validation checks source membership, not whether a source semantically
supports every claim. Code blocks and inline code are excluded from validation.

The UI renders recognized markers as clickable references and lists only cited
sources. Unknown IDs are noninteractive. Source content and filenames are rendered
as text, never executable HTML. Reloading a conversation uses its original source
snapshots instead of running retrieval again. Snapshots contain the exact excerpt
supplied to the model, including any context-budget truncation.

DOCX/TXT and legacy points can have unknown pages. The source viewer displays this
explicitly. It opens extracted snippets; original file/PDF viewing is not available
because uploaded temporary files are removed after ingestion.

## Agent mode

Document tools register sources in a request-local registry. Repeated chunks reuse
an ID within that turn, including parallel tool calls. Tool results carry backend
source labels. Web results retain ordinary URL links. Intermediate model narration
and tool calls are withheld. Each model step is buffered until its completed
message identifies whether it invokes tools; only answer steps emit text chunks.
Agent document citations use the same source snapshots and history format.

## Retrieval diagnostics

`QDrant.search_hits()` returns chunk/point/document IDs, content, metadata, native
RRF scores and fused ranks. `search()` remains a text-context wrapper. Both dense
and sparse prefetches, and the fused query, enforce user/chat scope; an optional
document filter further narrows that scope.

For standard retrieval only, enabling `include_trace: true` also requires
`include_sources: true`, a valid user session, and an `X-Retrieval-Trace-Key` header
matching the server's `NOTEBOOK_RETRIEVAL_TRACE_KEY` environment secret. If no key
is configured, trace access is disabled. Never place the trace key in frontend
code or public configuration. Agent trace requests are explicitly rejected.

Trace events contain fused hit IDs/scores/ranks, context point IDs, query settings,
and embedding/retrieval durations. They omit content and vectors. RRF scores are
ranking signals, not confidence percentages. `dense_rank` and `sparse_rank` are
null because the native fusion response does not expose its branch rankings.

No benchmark code or datasets are changed as part of this feature.
