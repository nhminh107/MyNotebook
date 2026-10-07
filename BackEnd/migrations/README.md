# Source metadata migration

Apply `001_source_metadata.sql` in the Supabase SQL editor before uploading new
files with this version. The migration adds nullable `page`, `chunk_index`, and
`ocr_used` columns to `public.chunks`. It is additive and can be applied again.
Verify the target schema is `public` before applying it to another deployment.

The existing `chat_history.conversation` column must be a JSON/JSONB array. New
turns add `turn_id`, `sources`, `cited_source_ids`, `invalid_source_ids`, and
`source_schema_version` alongside the existing `user` and `chatbot` fields. No
conversation rows need backfilling. The chat-list query projects only the first
user message as `title`; the detail query returns the complete conversation.

This change does not update existing SQL rows or Qdrant points. Old Qdrant point
IDs remain distinct from SQL chunk IDs; absent pages and chunk IDs remain null.
Legacy filenames are looked up only among documents belonging to the same user
and chat. Recovering missing page numbers requires the original document; do not
infer a page from repeated text or silently reindex existing storage.

For new uploads, Qdrant point IDs equal SQL chunk IDs and payloads carry version-2
source metadata. Vector dimensions, chunking settings, native dense/BM25/RRF
fusion, and the `user_documents` collection are unchanged.

Before applying the migration, preserve the deployment's normal database backup.
No migrations are applied automatically by the application or unit tests.
