# Yandex Indexing Diagnostic Report for https://phys-math.dev

Generated: 2026-02-26 UTC

## 1) Stack and deploy target (from repo)

- OS/runtime on diagnostic machine:
  - Linux (Ubuntu kernel 6.8), Node `v18.20.8`, npm `10.8.2`.
  - Evidence: `diag_yandex/raw/env_info.txt`
- App stack:
  - Astro static site (`astro` 5.x), TypeScript, Node build scripts.
  - Evidence: `diag_yandex/raw/package_json.txt`, `astro.config.mjs` in `diag_yandex/raw/key_file_snapshots.txt`
- Deploy target:
  - Cloudflare Pages (`wrangler.toml` has `pages_build_output_dir = "dist"`).
  - `_redirects` present (`/ /en/ 302`).
  - Evidence: `diag_yandex/raw/key_file_snapshots.txt`, `diag_yandex/raw/dist_redirects_snapshot.txt`
- Site generation behavior:
  - `astro.config.mjs` sets `output: 'static'` and `trailingSlash: 'always'`.

## 2) Repo scan for indexing blockers (noindex/robots/redirects)

Raw scans requested are saved in:
- `diag_yandex/raw/grep_noindex.txt`
- `diag_yandex/raw/grep_x_robots_tag.txt`
- `diag_yandex/raw/grep_meta_robots.txt`
- `diag_yandex/raw/grep_robots_txt_refs.txt`
- `diag_yandex/raw/grep_sitemap.txt`
- `diag_yandex/raw/grep_redirect.txt`
- `diag_yandex/raw/grep_308.txt`
- `diag_yandex/raw/grep_pretty.txt`

Focused scan summary:
- `src/layouts/BaseLayout.astro` only adds `<meta name="robots" ...>` when `noIndex` prop is true.
- Intentional noindex pages exist:
  - `/` redirect page (`src/pages/index.astro`) has `noindex,follow`.
  - `/{locale}/archive/` redirect page has `noindex,follow`.
  - 404 pages are noindex.
  - Some RU fallback post pages are noindex and canonically point to EN equivalents.
- `robots.txt` route exists and allows crawling (`Allow: /`) with sitemap line.
- `sitemap.xml` route exists and emits real URL list.
- Evidence: `diag_yandex/raw/src_indexing_signals.txt`, `diag_yandex/raw/key_file_snapshots.txt`

## 3) Live-site crawlability (normal UA vs YandexBot UA)

Raw full logs:
- `diag_yandex/raw/http_checks.txt`
- Parsed status summary: `diag_yandex/raw/http_checks_summary.txt`
- Extra check for verification URL with GET (without `-I`): `diag_yandex/raw/yandex_verification_get_no_follow.txt`

### Status/redirect matrix

| URL | Normal (HEAD / follow) | YandexBot (HEAD / follow) | Notes |
|---|---|---|---|
| `https://phys-math.dev/` | `302 -> /en/` / `302 -> 200` | `302 -> /en/` / `302 -> 200` | Same behavior for bot and normal UA |
| `https://phys-math.dev/en/` | `200` / `200` | `200` / `200` | Crawlable |
| `https://phys-math.dev/en/archive/1/` | `200` / `200` | `200` / `200` | Crawlable |
| `https://phys-math.dev/en/post/149-reality-check/` | `200` / `200` | `200` / `200` | Crawlable |
| `https://phys-math.dev/robots.txt` | `200` / `200` | `200` / `200` | Contains `Allow: /` and `Sitemap: https://phys-math.dev/sitemap.xml` |
| `https://phys-math.dev/sitemap.xml` | `200` / `200` | `200` / `200` | Valid XML with many real URLs |
| `https://phys-math.dev/sitemap_index.xml` | `404` / `404` | `404` / `404` | Broken key file |
| `https://phys-math.dev/yandex_b2fb10ca15940053.html` | `HEAD: 308` / `follow: 200` | `HEAD: 308` / `follow: 200` | GET without `-I` is `200` for both UAs |
| `https://phys-math.dev/yandex_b2fb10ca15940053` | `200` / `200` | `200` / `200` | Verification body served |

### Robots/noindex/canonical/JS rendering signals from fetched HTML

- `X-Robots-Tag`: not present on tested crawlable pages.
- `<meta name="robots">` on tested content pages:
  - `/en/`, `/en/archive/1/`, `/en/post/149-reality-check/`: **none** (indexable).
  - `/sitemap_index.xml` returns 404 HTML with `noindex,nofollow` (as expected for 404).
- Canonical tags:
  - `/en/` canonical = `https://phys-math.dev/en/`
  - `/en/archive/1/` canonical = same URL
  - `/en/post/149-reality-check/` canonical = same URL
- Rendering mode:
  - Server HTML includes meaningful text and post content (not JS-only shell).
  - Tiny crawl simulation text lengths: `/en/` = 3683, `/en/archive/1/` = 5653.
  - Evidence: `diag_yandex/raw/tiny_crawl_simulation.txt`

## 4) Diagnosis

### Primary most likely blocker (category 4: key files broken)

`https://phys-math.dev/sitemap_index.xml` returns **404** for both normal and YandexBot UAs.

Why this is likely critical:
- In Yandex Webmaster, many users submit `sitemap_index.xml` by habit.
- If this is the submitted sitemap URL, Yandex gets 404 and discovers nothing from it.
- This cleanly explains a persistent “0 pages in search” state despite crawlable pages.

Evidence:
- `diag_yandex/raw/http_checks_summary.txt` (`sitemap_index.xml` is 404 for both UAs)
- `diag_yandex/raw/http_checks.txt` (full headers and HTML body for that 404)

### Secondary issues (not primary blockers)

1. Verification URL nuance:
- `HEAD` to `/yandex_b2fb10ca15940053.html` returns `308`, while GET returns `200`.
- May confuse diagnostics/tools that rely on HEAD.
- Evidence: `diag_yandex/raw/http_checks.txt`, `diag_yandex/raw/yandex_verification_get_no_follow.txt`

2. Root URL is a redirect (`/` -> `/en/`), which is normal here but adds one hop.

3. Some RU fallback pages are intentionally `noindex` and canonicalized to EN pages. This reduces duplicate indexing and is expected.

## 5) Minimal concrete fix

### Proposed smallest code fix

Create `src/pages/sitemap_index.xml.ts` so `/sitemap_index.xml` returns 200 and references existing `/sitemap.xml`.

Patch file created:
- `diag_yandex/suggested_fix.patch`

### After applying/deploying

1. Re-check:
- `https://phys-math.dev/sitemap_index.xml` must be `200`.

2. In Yandex Webmaster:
- Add/re-add sitemap URL(s):
  - `https://phys-math.dev/sitemap.xml`
  - optionally `https://phys-math.dev/sitemap_index.xml`

3. Request recrawl/reindex for `/en/` and one post URL.

## 6) What was not found

- No bot-specific Cloudflare challenge/403 for YandexBot in tested URLs.
- No global noindex or X-Robots-Tag blocking content pages.
- No JS-only rendering issue; HTML includes substantial server-side content.

## 7) Artifact index

- Main report: `diag_yandex/yandex_indexing_report.md`
- Raw outputs folder: `diag_yandex/raw/`
- Suggested patch: `diag_yandex/suggested_fix.patch`
