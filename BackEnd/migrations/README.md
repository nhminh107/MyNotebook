# Source metadata migration

Apply `001_source_metadata.sql` in the Supabase SQL editor to also store source
metadata in SQL. Uploads remain compatible with the previous chunks schema: the
SQL adapter retries only PGRST204 errors identifying a missing optional metadata
column, omits that column, and logs a warning. Existing metadata columns are kept;
other SQL errors propagate. Qdrant and chat citation snapshots retain the metadata.
Restart the backend after applying the migration to clear cached missing columns. The migration adds nullable `page`, `chunk_index`, and
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

## Original document storage

Apply `002_document_storage.sql` before enabling R2 uploads. It adds nullable
`storage_bucket`, `storage_key`, `content_type`, `file_size`, `sha256`, and `etag`
columns to `public.document`, plus a unique index on the bucket/object pair.
It preserves existing rows and reloads the PostgREST schema cache. The backend
checks these columns before sending an original file to R2.

Original files use the private `mynotebook` bucket and keys of the form
`documents/<document_id>.<extension>`. Configure `CF_ACC_ID` and `S3_API_KEY` in
`BackEnd/.env`; the latter must be a Cloudflare R2 **API Token** with Object Read
& Write permissions for this bucket. Set `S3_API_URL` to the account's S3 endpoint
(`https://<account_id>.r2.cloudflarestorage.com`), or omit it to derive the default
endpoint from `CF_ACC_ID`. The boto3 client uses the S3 API with AWS Signature V4.
Dashboard URLs ending in `/mynotebook` are also accepted; the backend removes
that path because the S3 SDK supplies the bucket separately.
The backend verifies the API token to obtain its ID as the S3 Access Key ID and
derives the S3 Secret Access Key as the SHA-256 hash of the token value, following
Cloudflare's documented conversion. It reuses this client across requests.
Object-scoped R2 tokens support the S3 API; they do not authorize Cloudflare REST
object uploads. Install the declared `boto3` dependency in the backend environment.

Citation schema version 2 adds `document_url` to source snapshots and a structured
`citations` list to the final SSE citations event. Links are stable authenticated
backend routes, not public R2 URLs or expiring signed URLs. These fields live in
the existing `chat_history.conversation` JSON/JSONB objects and require no new
conversation columns. The original-file route checks the signed session and
document ownership before reading an object.

Existing documents keep NULL storage metadata and remain available as snippets;
the migration does not backfill original files or rewrite existing Qdrant points.
Re-upload a document to archive its original and create new citation links.
If SQL insertion or later indexing fails after a successful R2 upload, the
original is retained in R2 for recovery; it is not automatically deleted.
