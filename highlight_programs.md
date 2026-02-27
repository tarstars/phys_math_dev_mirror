# Program Highlighting: Current State and Fix Plan

## What I checked

1. `content/en/posts/100.md` and `content/ru/posts/100.md`:
   - code is plain text lines, not wrapped in triple backticks.
2. Render pipeline:
   - `src/lib/content.ts` uses `marked.parse(content)` with `gfm: true` and `breaks: true`.
   - no syntax-highlighting integration is configured.
3. Styling:
   - `src/styles/global.css` has no dedicated styles for `.post-content pre` / `.post-content code`.
4. Telegram sync:
   - `scripts/sync_telegram.py` takes plain `(primary.message or '')` and normalizes lines.
   - it does not convert Telegram entities (`MessageEntityCode`, `MessageEntityPre`) back into markdown backticks/fences.
5. Built output evidence:
   - `dist/ru/post/100-walrus-operator/index.html` renders the snippet as `<p>...<br>...</p>`, not `<pre><code>`.
   - only 2 EN posts currently render `<pre><code>` (`67`, `86`), likely by accidental indentation, not by preserved backticks.

## Why highlighting is missing

Primary cause:
- code formatting from Telegram is lost at import time, so markdown code blocks are not present in source posts.

Secondary cause:
- even when `<pre><code>` exists, there is no syntax highlighter (token coloring) configured.

## Is it possible to keep program highlighting?

Yes.

There are two separate goals:

1. Keep code blocks as code blocks (structural formatting):
   - preserve Telegram `code/pre` entities as markdown backticks/triple-backtick blocks in `content/en/posts/*.md`.
2. Add syntax coloring (real highlighting):
   - integrate a highlighter in the `marked` pipeline (e.g. `marked-highlight` + `highlight.js`), plus CSS theme.

## Smallest practical fix

1. In `scripts/sync_telegram.py`, replace plain text extraction with entity-aware markdown reconstruction:
   - parse `primary.message` + `primary.entities`;
   - convert `MessageEntityCode` -> inline backticks;
   - convert `MessageEntityPre` -> fenced code block (triple backticks), preserving language if available.
2. Run EN resync (full backfill) to rewrite markdown for old posts.
3. Rebuild RU drafts from EN for affected posts (or retranslate only affected ones) so code blocks are preserved there too.
4. Add minimal code block CSS (`.post-content pre`, `.post-content code`) for clear visual separation.

Effort: medium (about 3-6 hours including validation and backfill).

## Optional upgrade: token syntax highlighting

Add:
- dependency: `marked-highlight` + `highlight.js`;
- `marked.use(markedHighlight(...))` in `src/lib/content.ts`;
- syntax theme CSS.

Extra effort: low-medium (about 1-2 hours), plus QA.

## Risk notes

- Existing translated RU posts may contain translated code literals (example in post 100: `"end"` became `"конец"`), because code was not marked as code.
- After enabling entity-aware sync, affected posts should be refreshed from EN source to avoid broken code in RU translations.

## Recommendation

Implement in this order:

1. Preserve code entities during Telegram sync.
2. Backfill EN content and refresh RU for affected posts.
3. Add syntax coloring plugin (optional but recommended).

This order gives immediate structural code rendering first, then visual highlighting.
