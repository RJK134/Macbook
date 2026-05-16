-- ============================================================
-- schema v5 — Maieus past-paper-ref upstream
--
-- Extends education_resources with the metadata fields the Maieus
-- (RJK134/Maieus2) datalake importer needs to land a row in its
-- ExamPaperRef table. METADATA ONLY: no column here ever holds
-- question text, answer text, or mark-scheme text. The Maieus side
-- enforces this with FORBIDDEN_IMPORT_COLUMNS in
-- packages/shared/src/datalake/exam-paper-ref-importer.ts and rejects
-- a row outright if such a column is present in the CSV header.
--
-- All ALTERs use IF NOT EXISTS so this file is idempotent and the
-- install_v2.sh runner can replay it on already-migrated databases.
-- ============================================================

ALTER TABLE education_resources ADD COLUMN IF NOT EXISTS paper_code text;
ALTER TABLE education_resources ADD COLUMN IF NOT EXISTS paper_name text;
ALTER TABLE education_resources ADD COLUMN IF NOT EXISTS duration_minutes int;
ALTER TABLE education_resources ADD COLUMN IF NOT EXISTS total_marks int;
ALTER TABLE education_resources ADD COLUMN IF NOT EXISTS licence text;
ALTER TABLE education_resources ADD COLUMN IF NOT EXISTS official_pdf_url text;
ALTER TABLE education_resources ADD COLUMN IF NOT EXISTS aggregator_urls text[] DEFAULT ARRAY[]::text[];

CREATE INDEX IF NOT EXISTS idx_education_paper_code ON education_resources(exam_board, paper_code, year);
