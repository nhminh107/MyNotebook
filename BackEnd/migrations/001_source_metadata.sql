-- Additive migration. Existing rows retain unknown locations as NULL.
BEGIN;
ALTER TABLE public.chunks ADD COLUMN IF NOT EXISTS page integer;
ALTER TABLE public.chunks ADD COLUMN IF NOT EXISTS chunk_index integer;
ALTER TABLE public.chunks ADD COLUMN IF NOT EXISTS ocr_used boolean;
COMMIT;
-- chat_history.conversation must support JSON objects with additional fields.
-- No existing chunks, Qdrant points, or conversations are rewritten here.
