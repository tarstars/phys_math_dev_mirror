# Rusification Plan (EN -> RU)

## Goal

Fill Russian versions for all English pages and make RU pages public/indexable.

## Current Baseline (as of 2026-02-26)

- EN posts: `127`
- RU posts: `125`
- Missing RU files: `2` (`148`, `149`)
- RU translation statuses:
  - `draft`: `125`
  - `needs_review`: `0`
  - `reviewed`: `0`
  - `locked`: `0`

## Target State

- Every EN post has a RU file in `content/ru/posts/{id}.md`.
- RU file has:
  - translated `title`
  - translated `summary`
  - translated body (no TODO marker)
  - `translation_status: reviewed` (or `locked` for finalized evergreen posts)
- No `[DRAFT]` titles remain.
- No RU public page redirects to EN because of `draft` status.

## Execution Order

1. Close structural gaps first:
   - Create RU files for missing IDs `148`, `149`.
2. Translate newest posts first (highest traffic value):
   - IDs `149` down to `120`.
3. Continue in descending ID batches until complete.
4. Move stable evergreen posts to `locked` after final editorial pass.

## Working Loop (per batch)

Batch size: `10` posts.

1. Sync metadata and queue:
   - `npm run translate:ru`
2. Pick next 10 draft IDs (newest first).
3. For each selected RU file:
   - replace `[DRAFT] ...` title with final RU title
   - write RU summary
   - replace body translation placeholder/TODO block with RU content
   - keep `slug`, `id`, `source_url`, `en_source_hash` intact
   - set `translation_status: reviewed`
4. Validate:
   - `npm run build`
   - spot-check rendered RU pages for the batch
5. Commit batch.

## Quality Rules

- Translation quality:
  - preserve technical meaning and examples
  - keep code/math notation unchanged
  - keep links/media/source_url unchanged
- Metadata quality:
  - `title` and `summary` must be natural RU text
  - `translation_status` must reflect actual state
- SEO quality:
  - avoid empty summaries on reviewed RU posts
  - no `[DRAFT]` or TODO text on reviewed pages

## Progress Tracking

- Primary operational queue: `data/state/ru_translation_queue.md`
- Optional lightweight KPI to track after each batch:
  - `draft_count`
  - `reviewed_count`
  - `missing_ru_files_count`

## Completion Criteria

- `missing_ru_files_count = 0`
- `draft_count = 0`
- `needs_review_count = 0`
- All RU pages intended for publication are `reviewed` or `locked`
- Final `npm run build` passes.
