#!/usr/bin/env python3
"""Prepare RU translation drafts incrementally without overwriting reviewed content."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Any

import frontmatter

ROOT = Path(__file__).resolve().parents[1]
EN_DIR = ROOT / 'content' / 'en' / 'posts'
RU_DIR = ROOT / 'content' / 'ru' / 'posts'
QUEUE_PATH = ROOT / 'data' / 'state' / 'ru_translation_queue.md'

SYNC_KEYS = [
    'slug',
    'date',
    'edited_at',
    'channel',
    'source_url',
    'summary',
    'album_id',
    'reactions',
    'media',
]


def load_post(path: Path) -> frontmatter.Post:
    return frontmatter.load(path)


def save_post(path: Path, post: frontmatter.Post) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter.dumps(post), encoding='utf-8')


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def update_ru_metadata(en_meta: dict[str, Any], ru_post: frontmatter.Post) -> tuple[bool, bool]:
    """Returns (changed, needs_review_marked)."""
    changed = False
    needs_review_marked = False

    ru_meta = ru_post.metadata

    for key in SYNC_KEYS:
        if ru_meta.get(key) != en_meta.get(key):
            ru_meta[key] = en_meta.get(key)
            changed = True

    if ru_meta.get('deleted') != en_meta.get('deleted', False):
        ru_meta['deleted'] = en_meta.get('deleted', False)
        changed = True

    status = ru_meta.get('translation_status', 'draft')
    old_en_hash = str(ru_meta.get('en_source_hash') or '')
    new_en_hash = str(en_meta.get('source_hash') or '')

    if old_en_hash and old_en_hash != new_en_hash and status in {'reviewed', 'needs_review'}:
        if status != 'needs_review':
            ru_meta['translation_status'] = 'needs_review'
            changed = True
            needs_review_marked = True

    if old_en_hash != new_en_hash:
        ru_meta['en_source_hash'] = new_en_hash
        changed = True

    ru_meta['updated_at'] = now_iso()
    return changed, needs_review_marked


def create_ru_draft(en_post: frontmatter.Post) -> frontmatter.Post:
    en_meta = en_post.metadata
    draft_content = (
        '> TODO: translate this EN post to RU and mark `translation_status: reviewed` when ready.\n\n'
        + en_post.content.strip()
        + '\n'
    )

    metadata = {
        'id': en_meta['id'],
        'slug': en_meta['slug'],
        'title': f"[DRAFT] {en_meta['title']}",
        'summary': '',
        'date': en_meta['date'],
        'edited_at': en_meta.get('edited_at'),
        'channel': en_meta.get('channel', 'phys_math_dev'),
        'source_url': en_meta['source_url'],
        'source_hash': '',
        'deleted': en_meta.get('deleted', False),
        'album_id': en_meta.get('album_id'),
        'reactions': en_meta.get('reactions', []),
        'media': en_meta.get('media', []),
        'translation_status': 'draft',
        'en_source_hash': en_meta.get('source_hash', ''),
        'updated_at': now_iso(),
    }

    return frontmatter.Post(draft_content, **metadata)


def main() -> None:
    parser = argparse.ArgumentParser(description='Prepare RU translation drafts and review queue.')
    parser.add_argument('--queue-path', default=str(QUEUE_PATH), help='Path to queue markdown output file.')
    args = parser.parse_args()

    RU_DIR.mkdir(parents=True, exist_ok=True)

    created: list[tuple[int, str, str]] = []
    needs_review: list[tuple[int, str, str]] = []
    touched = 0

    en_files = sorted(EN_DIR.glob('*.md'), key=lambda p: int(p.stem))
    for en_path in en_files:
        en_post = load_post(en_path)
        en_meta = en_post.metadata

        post_id = int(en_meta['id'])
        ru_path = RU_DIR / f'{post_id}.md'

        if not ru_path.exists():
            draft_post = create_ru_draft(en_post)
            save_post(ru_path, draft_post)
            created.append((post_id, str(en_meta.get('title', f'Post {post_id}')), str(en_meta.get('source_url', ''))))
            touched += 1
            continue

        ru_post = load_post(ru_path)
        changed, marked = update_ru_metadata(en_meta, ru_post)
        if marked:
            needs_review.append((post_id, str(en_meta.get('title', f'Post {post_id}')), str(en_meta.get('source_url', ''))))

        if changed:
            save_post(ru_path, ru_post)
            touched += 1

    queue_path = Path(args.queue_path)
    queue_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        '# RU Translation Queue',
        '',
        f'Generated: {now_iso()}',
        '',
        f'- New drafts: **{len(created)}**',
        f'- Needs review: **{len(needs_review)}**',
        '',
        '## New Drafts',
        ''
    ]

    if created:
        lines.extend([f'- `{pid}` · {title} · {url}' for pid, title, url in created])
    else:
        lines.append('- None')

    lines.extend(['', '## Needs Review', ''])
    if needs_review:
        lines.extend([f'- `{pid}` · {title} · {url}' for pid, title, url in needs_review])
    else:
        lines.append('- None')

    queue_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print(f'RU draft prep completed. Files touched: {touched}')
    print(f'New drafts: {len(created)} | Needs review: {len(needs_review)}')
    print(f'Queue file: {queue_path.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
