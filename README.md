# phys-math.dev Mirror

Bilingual static mirror for `https://t.me/s/phys_math_dev` with:

- `/en/...` and `/ru/...` routes
- daily EN incremental sync from Telegram API
- RU workflow with draft/review statuses and non-destructive updates
- SEO-focused static pages for Google and Yandex
- deploy from GitHub Actions to Cloudflare Pages via Wrangler

## Stack

- Astro (static site)
- Python + Telethon (Telegram sync)
- Cloudflare Pages + R2 + Web Analytics

## Project policies

- Keep analytics counters enabled on all HTML pages:
  - Google tag ID: `G-KW8VXVXW7N`
  - Yandex.Metrika counter ID: `106989967`
- Source of truth for counters:
  - `src/layouts/BaseLayout.astro` (all regular EN/RU content pages)
  - `src/pages/index.astro` (root redirect page)
- Any new standalone page that does not use `BaseLayout` must include both counters manually.
- Do not remove or replace these counters without explicit approval from the project owner.
- RU translation review must follow a manual checklist workflow:
  - create a full list of target messages/files first
  - process one message at a time (EN source + RU translation)
  - fix translation only for the current item
  - mark this item as done in the checklist
  - repeat in an agent loop until all items are done
- Do not implement programmable/batch loops for RU translation review or fixes.

## Local setup

1. Install dependencies:

```bash
npm install
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Create `.env` from `.env.example` and fill all required variables.

3. Run EN sync:

```bash
npm run sync:en
```

4. Prepare RU drafts/review queue:

```bash
npm run translate:ru
```

5. Start site:

```bash
npm run dev
```

## Content model

- EN posts: `content/en/posts/{id}.md`
- RU posts: `content/ru/posts/{id}.md`
- Site descriptions:
  - `content/site/en.md`
  - `content/site/ru.md`
- Sync state: `data/state/en_sync_state.json`

RU status values:

- `draft`: hidden from RU public pages (redirect to EN equivalent)
- `reviewed`: public/indexable
- `needs_review`: public/indexable after EN changed
- `locked`: public/indexable, never auto-modified

## Cloudflare + GitHub secrets

Configure these repository secrets:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`
- `CF_PAGES_PROJECT_NAME`
- `R2_ENDPOINT`
- `R2_BUCKET`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_PUBLIC_BASE_URL`
- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `TELEGRAM_STRING_SESSION`
- `PUBLIC_CF_ANALYTICS_TOKEN` (optional, for analytics)

## Daily automation

Workflow `.github/workflows/daily-sync-deploy.yml` runs daily at `18:00 UTC` (21:00 Moscow):

1. sync EN content incrementally
2. commit content changes to `main` (if any)
3. build Astro site
4. deploy to Cloudflare Pages via Wrangler

## Generating Telegram StringSession

Run once locally with your dedicated Telegram account:

```bash
python3 scripts/generate_string_session.py
```

Copy printed session string into GitHub secret `TELEGRAM_STRING_SESSION`.
