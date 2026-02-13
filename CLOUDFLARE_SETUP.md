# Cloudflare + GitHub Setup Guide

This guide sets up deploy for `https://phys-math.dev` and daily sync at 21:00 Moscow time.

## 1) Create Cloudflare Pages project

1. Open Cloudflare Dashboard -> **Workers & Pages** -> **Create** -> **Pages**.
2. Create a project (for example: `phys-math-dev`).
3. Keep note of the project name; it will be used as `CF_PAGES_PROJECT_NAME` secret.

## 2) Create R2 bucket for media

1. Open **R2** -> **Create bucket**.
2. Name it (for example: `phys-math-media`).
3. Attach a public domain/custom domain (recommended `media.phys-math.dev`).
4. Copy the public base URL (used as `R2_PUBLIC_BASE_URL`).

## 3) Create R2 API credentials

1. In R2, create **Access Keys**.
2. Save:
   - Access Key ID -> `R2_ACCESS_KEY_ID`
   - Secret Access Key -> `R2_SECRET_ACCESS_KEY`
3. Get endpoint URL (S3 API endpoint) -> `R2_ENDPOINT`.
4. Bucket name -> `R2_BUCKET`.

## 4) Create Cloudflare API token for Pages deploy

1. Go to **My Profile** -> **API Tokens** -> **Create Token**.
2. Start with template "Edit Cloudflare Workers" and add permissions for Pages deploy.
3. Save token as `CLOUDFLARE_API_TOKEN`.
4. Account ID is in dashboard sidebar -> save as `CLOUDFLARE_ACCOUNT_ID`.

## 5) Create Telegram credentials

1. Create Telegram API app at `https://my.telegram.org`.
2. Save values:
   - `TELEGRAM_API_ID`
   - `TELEGRAM_API_HASH`
3. Generate StringSession locally:

```bash
python3 scripts/generate_string_session.py
```

4. Save output as `TELEGRAM_STRING_SESSION`.

Use a dedicated Telegram account for this project.

## 6) Add GitHub repository secrets

In GitHub repository -> **Settings** -> **Secrets and variables** -> **Actions**, add:

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
- `PUBLIC_CF_ANALYTICS_TOKEN` (optional)

## 7) Validate workflow

1. Push repository to GitHub.
2. Run workflow manually: **Actions** -> **Daily Sync And Deploy** -> **Run workflow**.
3. Check logs for:
   - Telegram sync completed
   - Build completed
   - `wrangler pages deploy` success

## 8) DNS

Set `phys-math.dev` and `www` to Cloudflare-managed records as needed, and bind custom domain in Pages project.
