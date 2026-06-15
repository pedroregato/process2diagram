-- Migration: add communication_noise_json column to meetings
-- Run via psycopg2 (local only) or Supabase SQL editor
-- Date: 2026-06-15

ALTER TABLE meetings
    ADD COLUMN IF NOT EXISTS communication_noise_json TEXT;

COMMENT ON COLUMN meetings.communication_noise_json IS
    'JSON serialization of CommunicationNoiseModel — ambiguities, gaps, noise_score, summary';
