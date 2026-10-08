-- Original files remain private in Cloudflare R2. Store keys, never API tokens.
BEGIN;
ALTER TABLE public.document
    ADD COLUMN IF NOT EXISTS storage_bucket text,
    ADD COLUMN IF NOT EXISTS storage_key text,
    ADD COLUMN IF NOT EXISTS content_type text,
    ADD COLUMN IF NOT EXISTS file_size bigint CHECK (file_size > 0),
    ADD COLUMN IF NOT EXISTS sha256 text,
    ADD COLUMN IF NOT EXISTS etag text;

CREATE UNIQUE INDEX IF NOT EXISTS document_storage_object_unique
    ON public.document (storage_bucket, storage_key)
    WHERE storage_key IS NOT NULL;

COMMENT ON COLUMN public.document.storage_key IS
    'Private R2 object key; read through the authenticated document file route.';
COMMENT ON COLUMN public.document.sha256 IS
    'SHA-256 checksum of the original uploaded bytes.';
COMMIT;

-- Reload the PostgREST schema cache after adding the columns.
NOTIFY pgrst, 'reload schema';
-- Citation schema version 2 lives inside chat_history.conversation JSON/JSONB.
-- Existing rows keep NULL storage fields; no original files are fabricated.
