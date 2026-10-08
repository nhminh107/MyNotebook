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
4. `citations`: valid/invalid IDs, structured cited-source snapshots,
   `source_schema_version: 2`, and `saved: true`, after summary/history storage.
5. `done`: `saved: true`.

A failed retrieval, generation, summarization or history write sends `error` and
never a successful `done`. A partially delivered answer is not confirmed saved.
Citation validation checks source membership, not whether a source semantically
supports every claim. Code blocks and inline code are excluded from validation.

The UI renders recognized markers as clickable references and lists only cited
documents, grouped by document ID. The "Nguồn" section shows one filename per
document, without chunk IDs, excerpts or page rows. Archived documents in this
section and the sidebar open the original R2 file in a new tab; hovering shows
the filename and file link. Inline references open the original at the cited
page when available. Unknown IDs are noninteractive. Source content and filenames are rendered
as text, never executable HTML. Reloading a conversation uses its original source
snapshots instead of running retrieval again. Snapshots contain the exact excerpt
supplied to the model, including any context-budget truncation.

DOCX/TXT and legacy points can have unknown pages. The source viewer displays this
explicitly. New uploads preserve original PDF/DOCX/TXT bytes in the private
Cloudflare R2 `mynotebook` bucket before chunk indexing. Apply
[`002_document_storage.sql`](migrations/002_document_storage.sql) to store the R2
bucket/key, content type, file size, SHA-256 checksum and ETag in SQL. Configure
`CF_ACC_ID` and a Cloudflare R2 Object Read & Write API Token as `S3_API_KEY`.
`S3_API_URL` selects the R2 S3 endpoint; boto3 signs upload/read requests using
credentials derived from the verified API token. Object-scoped tokens are used
through the S3 API rather than the Cloudflare REST object endpoints.

New source snapshots include a `document_url`, for example
`/documents/files/<document_id>#page=3`. Chat document responses also include
`document_url` and a fresh `r2_url`, allowing old source snapshots to resolve
their originals from the current chat's document metadata without reindexing
Qdrant. With `S3_PUBLIC_URL`, the UI uses the permanent public bucket URL plus
the object's stored key, without signing or expiry. Without that setting, it
uses the direct Cloudflare S3 URL signed for GET for one hour.
Reloading the chat refreshes these links; expiring URLs are never stored in SQL
conversation snapshots or Qdrant. The stable `/documents/files/...` route checks
the signed session and SQL ownership, then returns a non-cacheable 303 redirect
to a fresh Cloudflare URL. PDF links retain the cited page fragment. The application
never publishes the bucket or exposes its API token. Temporary local upload files
are still removed after ingestion. Legacy snippets without originals remain
viewable and have a null `document_url`.

The final citations event contains only valid, cited sources. For example:

```json
{
  "turn_id": "TURN_ID",
  "source_schema_version": 2,
  "cited_source_ids": [1],
  "invalid_source_ids": [],
  "citations": [{
    "citation_id": 1,
    "chunk_id": "CHUNK_ID",
    "qdrant_point_id": "CHUNK_ID",
    "document_id": "DOCUMENT_ID",
    "file_name": "notes.pdf",
    "page": 3,
    "chunk_index": 2,
    "ocr_used": false,
    "content": "The exact excerpt supplied to the model.",
    "document_url": "/documents/files/DOCUMENT_ID#page=3"
  }],
  "saved": true
}
```

The upload response now also includes `document_id` and `document_url`. Empty
files are rejected, and the application limits each original to 300 MB.

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
