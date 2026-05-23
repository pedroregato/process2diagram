-- Migration: Document Reference Date fields (v4.25)
-- Run once in Supabase SQL Editor.
-- Adds doc_date and doc_date_estimated to meeting_documents.

ALTER TABLE meeting_documents
    ADD COLUMN IF NOT EXISTS doc_date           DATE,
    ADD COLUMN IF NOT EXISTS doc_date_estimated TEXT;

COMMENT ON COLUMN meeting_documents.doc_date IS
  'Reference date of the document (e.g. publication date). Nullable.';
COMMENT ON COLUMN meeting_documents.doc_date_estimated IS
  'Free-text estimated date when exact date is unknown (e.g. "Meados de 2023"). Nullable.';
