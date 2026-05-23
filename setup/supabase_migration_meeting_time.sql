-- Migration: Meeting Duration & Speaker Talk Time (v4.25)
-- Run once in Supabase SQL Editor.
-- Adds duration_minutes and speaker_times columns to the meetings table.

ALTER TABLE meetings ADD COLUMN IF NOT EXISTS duration_minutes INTEGER;
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS speaker_times    JSONB DEFAULT '{}';

COMMENT ON COLUMN meetings.duration_minutes IS
  'Total meeting duration in minutes, extracted from transcript timestamps. NULL when timestamps are absent.';
COMMENT ON COLUMN meetings.speaker_times IS
  'Per-speaker talk time in seconds: {"Speaker Name": 120, ...}. '
  'Computed by transcript_time_parser. Empty object when no timestamps detected (estimated from word count).';
