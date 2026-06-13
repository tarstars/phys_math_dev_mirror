# phys_math_dev — channel mirror

Bilingual static mirror of the Telegram channel **phys_math_dev**, deployed to
**phys-math.dev** (Astro + Python/Telethon + Cloudflare Pages). This channel is
**English-primary** (EN posts lead; RU is the translation and may lag). Posts:
`content/en/posts/*.md` and `content/ru/posts/*.md`.

## Creating a navigational post

A *navigational post* is a curated index of one thread of related posts (see the
existing examples: **#256 "Agentic Programming — navigation"**, **#167 "The Farmer
Was Replaced — navigation"**, **#123 "GBDTE"**).

When asked **"create a navigational post for the channel"**, do this — the important
part is choosing *which* group of posts needs one most right now:

1. **Scan topics.** Tally hashtags/themes across `content/en/posts/*.md` and count the
   number of *distinct* posts per theme.
2. **Check existing coverage.** Find posts that are already navigational: title contains
   `navigation`, or the body has ≥3 internal links of the form
   `t.me/phys_math_dev/<id>`. Note which themes they already cover.
3. **Pick the target = the largest *coherent* theme with no nav post yet** (skip
   themes already covered; skip over-broad umbrellas that should be split).
4. **Draft it (EN), model on post #256:** a short personal intro; an
   `If you want to start quickly — these N posts contain most of the ideas` shortlist;
   then a `Full list` grouped into thematic sub-sections. Each entry:
   `<id> - <title> [tg](<https://t.me/phys_math_dev/<id>>) / [web](<https://phys-math.dev/en/post/<id>-<slug>/>)`.
   Build the ids, slugs, and titles from each post's frontmatter (do not hand-type
   slugs — read them from the files so the web links are exact).
5. **Output the markdown** for the user to post to the Telegram channel. Do **not**
   commit it as a content file — once posted, the daily sync imports it automatically.

## Posting a navigational post (with a collage) to Telegram

The post is authored in Telegram; the repo only mirrors it after the daily sync. To
publish the drafted text together with a collage image as **one message**:

- **Photo + caption in one message.** A photo caption is capped at **1024 UTF-16 units**
  (2048 with Telegram Premium), and only the visible link *labels* count, not the URLs.
  If the text is longer, send the photo with a short caption and the full text as a
  separate follow-up message.
- **Formatting.** Use Telethon markdown (`parse_mode="md"`): links are `[label](url)`
  with a **plain** URL — strip the `<…>` the repo stores — and no MarkdownV2 punctuation
  escaping is needed. (`HTML` parse mode is the other easy option.)
- **Credentials** (the same ones the daily sync uses; GitHub secrets are write-only, so
  re-fetch them rather than read them back):
  - `TELEGRAM_API_ID` + `TELEGRAM_API_HASH` — https://my.telegram.org → *API development
    tools* (shows your existing app's values).
  - `TELEGRAM_STRING_SESSION` — mint one with
    `uv run --with telethon --with qrcode python scripts/generate_string_session.py --qr`
    (scan via Telegram → Settings → Devices → Link Desktop Device).
  - `TELEGRAM_CHANNEL` — `phys_math_dev` (not secret).
- **Send it** (run in a normal terminal — sandboxes may cap outbound connections at ~30s):
  ```
  export TELEGRAM_API_ID=… TELEGRAM_API_HASH=… TELEGRAM_STRING_SESSION=… TELEGRAM_CHANNEL=phys_math_dev
  uv run --with telethon python scripts/post_telegram.py navpost.md collage.jpg
  ```
  `scripts/post_telegram.py` strips the `<>`, checks the caption limit, and sends the
  photo + markdown caption (or a plain message if no image is given). It posts as your
  user account, which is fine since you own the channel.
