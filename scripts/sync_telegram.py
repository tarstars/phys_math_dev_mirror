#!/usr/bin/env python3
"""Incremental Telegram sync for EN mirror content.

Features:
- Full backfill on first run (or --full-backfill)
- Incremental daily updates
- Edit detection via source hash
- Deletion audit (marks posts deleted for EN and RU)
- Media upload to Cloudflare R2 (or local fallback)
- RU state update: reviewed -> needs_review when EN source changes
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import hashlib
import json
import mimetypes
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import boto3
import frontmatter
from botocore.exceptions import ClientError
from slugify import slugify
from telethon import TelegramClient
from telethon.helpers import add_surrogate, del_surrogate, within_surrogate
from telethon.sessions import StringSession
from telethon.tl.types import (
    DocumentAttributeFilename,
    Message,
    MessageEmpty,
    MessageEntityCode,
    MessageEntityPre,
    MessageEntityTextUrl,
    MessageEntityUrl,
)

ROOT = Path(__file__).resolve().parents[1]
EN_DIR = ROOT / 'content' / 'en' / 'posts'
RU_DIR = ROOT / 'content' / 'ru' / 'posts'
STATE_PATH = ROOT / 'data' / 'state' / 'en_sync_state.json'
LOCAL_MEDIA_DIR = ROOT / 'public' / 'media' / 'local'


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def env(name: str, *, default: str | None = None, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and (value is None or value == ''):
        raise RuntimeError(f'Missing required env var: {name}')
    return value or ''


@dataclass
class Config:
    api_id: int
    api_hash: str
    string_session: str
    channel: str
    recent_window: int
    max_video_bytes: int
    r2_endpoint: str
    r2_bucket: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_public_base_url: str

    @property
    def has_r2(self) -> bool:
        return all(
            [
                self.r2_endpoint,
                self.r2_bucket,
                self.r2_access_key_id,
                self.r2_secret_access_key,
                self.r2_public_base_url,
            ]
        )


class MediaStore:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.client = None
        if cfg.has_r2:
            self.client = boto3.client(
                's3',
                endpoint_url=cfg.r2_endpoint,
                aws_access_key_id=cfg.r2_access_key_id,
                aws_secret_access_key=cfg.r2_secret_access_key,
                region_name='auto',
            )

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open('rb') as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    def _ensure_r2_object(self, local_path: Path, key: str, mime_type: str) -> None:
        assert self.client is not None
        try:
            self.client.head_object(Bucket=self.cfg.r2_bucket, Key=key)
            return
        except ClientError as exc:
            code = str(exc.response.get('Error', {}).get('Code', ''))
            if code not in {'404', 'NoSuchKey', 'NotFound'}:
                raise

        with local_path.open('rb') as stream:
            self.client.put_object(
                Bucket=self.cfg.r2_bucket,
                Key=key,
                Body=stream,
                ContentType=mime_type,
                CacheControl='public, max-age=31536000, immutable',
            )

    def put(self, local_path: Path, channel: str) -> str:
        mime_type = mimetypes.guess_type(local_path.name)[0] or 'application/octet-stream'
        digest = self._sha256(local_path)

        extension = local_path.suffix
        if not extension:
            guessed = mimetypes.guess_extension(mime_type) or ''
            extension = guessed

        object_name = f'{digest}{extension}'

        if self.client is not None:
            key = f'telegram/{channel}/{object_name}'
            self._ensure_r2_object(local_path, key, mime_type)
            return f"{self.cfg.r2_public_base_url.rstrip('/')}/{key}"

        # Local fallback for development when R2 is not configured.
        LOCAL_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        local_target = LOCAL_MEDIA_DIR / object_name
        if not local_target.exists():
            shutil.copy2(local_path, local_target)
        return f'/media/local/{object_name}'


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {'last_max_id': 0, 'last_sync_at': None, 'known_ids': []}

    try:
        return json.loads(STATE_PATH.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return {'last_max_id': 0, 'last_sync_at': None, 'known_ids': []}


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def post_path(locale: str, post_id: int) -> Path:
    target = EN_DIR if locale == 'en' else RU_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target / f'{post_id}.md'


def load_post(locale: str, post_id: int) -> frontmatter.Post | None:
    path = post_path(locale, post_id)
    if not path.exists():
        return None
    return frontmatter.load(path)


def save_post(locale: str, post_id: int, post: frontmatter.Post) -> None:
    path = post_path(locale, post_id)
    path.write_text(frontmatter.dumps(post), encoding='utf-8')


def iter_existing_ids(locale: str) -> list[int]:
    base = EN_DIR if locale == 'en' else RU_DIR
    if not base.exists():
        return []
    ids: list[int] = []
    for item in base.glob('*.md'):
        if item.stem.isdigit():
            ids.append(int(item.stem))
    return sorted(ids)


def chunked(items: Sequence[int], size: int) -> Iterable[list[int]]:
    for index in range(0, len(items), size):
        yield list(items[index : index + size])


def first_non_empty_line(text: str) -> str:
    for line in text.splitlines():
        clean = line.strip()
        if clean:
            return clean
    return ''


def build_title_and_summary(text: str, post_id: int) -> tuple[str, str]:
    lead = first_non_empty_line(text)
    title = lead[:130] if lead else f'Post {post_id}'

    plain = ' '.join(part.strip() for part in text.splitlines() if part.strip())
    summary = plain[:220]
    return title, summary


def reaction_to_emoji(reaction: Any) -> str:
    if reaction is None:
        return '❔'

    emoji = getattr(reaction, 'emoticon', None)
    if emoji:
        return str(emoji)

    doc_id = getattr(reaction, 'document_id', None)
    if doc_id:
        return f'custom:{doc_id}'

    return '❔'


def extract_reactions(msg: Message) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    data = getattr(msg, 'reactions', None)
    if not data or not getattr(data, 'results', None):
        return out

    for item in data.results:
        out.append(
            {
                'emoji': reaction_to_emoji(getattr(item, 'reaction', None)),
                'count': int(getattr(item, 'count', 0)),
            }
        )

    out.sort(key=lambda row: row['count'], reverse=True)
    return out


def message_media_signature(msg: Message) -> str:
    if msg.photo:
        return f'photo:{getattr(msg.photo, "id", "")}'
    if msg.document:
        return f'document:{getattr(msg.document, "id", "")}'
    return ''


def build_source_hash(msg: Message, group_messages: list[Message], text: str, reactions: list[dict[str, Any]]) -> str:
    payload = {
        'id': msg.id,
        'grouped_id': msg.grouped_id,
        'edit_date': msg.edit_date.isoformat() if msg.edit_date else None,
        'text': text,
        'reactions': reactions,
        'media': [message_media_signature(item) for item in group_messages],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def media_kind(msg: Message) -> str:
    if msg.photo:
        return 'photo'
    if msg.video:
        return 'video'
    if msg.document:
        mime = getattr(getattr(msg, 'file', None), 'mime_type', '') or ''
        if mime.startswith('video/'):
            return 'video'
        return 'file'
    return 'file'


def media_filename(msg: Message, fallback_name: str) -> str:
    document = msg.document
    if document and getattr(document, 'attributes', None):
        for attr in document.attributes:
            if isinstance(attr, DocumentAttributeFilename) and attr.file_name:
                return attr.file_name

    file_name = getattr(getattr(msg, 'file', None), 'name', None)
    if file_name:
        return str(file_name)

    return fallback_name


async def extract_media(
    msg: Message,
    store: MediaStore,
    channel: str,
    *,
    skip_media: bool,
    max_video_bytes: int,
) -> list[dict[str, Any]]:
    if skip_media:
        return []

    if not msg.media:
        return []

    media_type = media_kind(msg)
    file_info = getattr(msg, 'file', None)
    file_size = int(getattr(file_info, 'size', 0) or 0)

    if media_type == 'video' and max_video_bytes > 0 and file_size > max_video_bytes:
        print(
            f'Skipping oversized video for message {msg.id}: '
            f'{file_size} bytes > MAX_VIDEO_BYTES={max_video_bytes}'
        )
        return []

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / f'message_{msg.id}'
        downloaded = await msg.download_media(file=str(tmp_path))
        if not downloaded:
            return []

        path = Path(downloaded)
        file_url = store.put(path, channel)

        width = int(getattr(file_info, 'width', 0) or 0) or None
        height = int(getattr(file_info, 'height', 0) or 0) or None

        mime_type = getattr(file_info, 'mime_type', None) or mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        name = media_filename(msg, path.name)

        return [
            {
                'kind': media_type,
                'url': file_url,
                'fileName': name,
                'mimeType': mime_type,
                'size': path.stat().st_size,
                'width': width,
                'height': height,
            }
        ]


def normalize_markdown(text: str) -> str:
    if not text:
        return ''
    return '\n'.join(line.rstrip() for line in text.replace('\r\n', '\n').split('\n')).strip() + '\n'


def _ranges_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def message_to_markdown(msg: Message) -> str:
    raw_text = msg.message or ''
    if not raw_text:
        return ''

    entities = getattr(msg, 'entities', None) or []
    code_entities = [entity for entity in entities if isinstance(entity, (MessageEntityCode, MessageEntityPre))]
    link_entities = [entity for entity in entities if isinstance(entity, (MessageEntityTextUrl, MessageEntityUrl))]

    if not code_entities and not link_entities:
        return raw_text

    surrogated_text = add_surrogate(raw_text)
    insertions: list[tuple[int, int, str]] = []
    code_ranges: list[tuple[int, int]] = []

    for entity in code_entities:
        start = int(getattr(entity, 'offset', 0) or 0)
        length = int(getattr(entity, 'length', 0) or 0)
        end = start + length

        if length <= 0 or start < 0 or end > len(surrogated_text):
            continue

        entity_text = del_surrogate(surrogated_text[start:end])
        code_ranges.append((start, end))

        if isinstance(entity, MessageEntityPre) or '\n' in entity_text:
            language = str(getattr(entity, 'language', '') or '').strip()
            opening = f'```{language}\n' if language else '```\n'
            closing = '\n```'

            # Keep fenced blocks detached from surrounding text when the entity is inline.
            if start > 0 and surrogated_text[start - 1] != '\n':
                opening = '\n' + opening
            if end < len(surrogated_text) and surrogated_text[end] != '\n':
                closing = closing + '\n'

            insertions.append((start, 1, opening))
            insertions.append((end, 0, closing))
            continue

        delimiter = '``' if '`' in entity_text else '`'
        insertions.append((start, 1, delimiter))
        insertions.append((end, 0, delimiter))

    for entity in link_entities:
        start = int(getattr(entity, 'offset', 0) or 0)
        length = int(getattr(entity, 'length', 0) or 0)
        end = start + length

        if length <= 0 or start < 0 or end > len(surrogated_text):
            continue

        if any(_ranges_overlap(start, end, c_start, c_end) for c_start, c_end in code_ranges):
            continue

        link_text = del_surrogate(surrogated_text[start:end])
        if not link_text:
            continue

        if isinstance(entity, MessageEntityTextUrl):
            url = str(getattr(entity, 'url', '') or '').strip()
        else:
            url = link_text.strip()

        if not url:
            continue

        safe_url = url.replace('>', '%3E')

        insertions.append((start, 1, '['))
        insertions.append((end, 0, f'](<{safe_url}>)'))

    for position, _, token in sorted(insertions, key=lambda row: (row[0], row[1]), reverse=True):
        while within_surrogate(surrogated_text, position):
            position += 1
        surrogated_text = surrogated_text[:position] + token + surrogated_text[position:]

    return del_surrogate(surrogated_text)


def channel_url(channel: str, post_id: int) -> str:
    username = channel[1:] if channel.startswith('@') else channel
    return f'https://t.me/{username}/{post_id}'


def choose_album_primary(messages: list[Message]) -> Message:
    with_caption = [msg for msg in messages if (msg.message or '').strip()]
    if with_caption:
        with_caption.sort(key=lambda msg: msg.id)
        return with_caption[0]

    messages.sort(key=lambda msg: msg.id)
    return messages[0]


def build_canonical_posts(messages: list[Message]) -> list[tuple[Message, list[Message]]]:
    grouped: dict[int, list[Message]] = {}
    singles: list[Message] = []

    for msg in messages:
        if not isinstance(msg, Message):
            continue
        if isinstance(msg, MessageEmpty):
            continue
        if not msg.id:
            continue
        if msg.grouped_id:
            grouped.setdefault(int(msg.grouped_id), []).append(msg)
        else:
            singles.append(msg)

    out: list[tuple[Message, list[Message]]] = []
    for single in singles:
        out.append((single, [single]))

    for group_messages in grouped.values():
        group_messages.sort(key=lambda msg: msg.id)
        primary = choose_album_primary(group_messages)
        out.append((primary, group_messages))

    out.sort(key=lambda item: item[0].id)
    return out


def mark_deleted_in_locale(locale: str, post_id: int) -> bool:
    post = load_post(locale, post_id)
    if not post:
        return False

    if post.metadata.get('deleted'):
        return False

    post.metadata['deleted'] = True
    post.metadata['updated_at'] = now_iso()
    save_post(locale, post_id, post)
    return True


def sync_ru_state_from_en(post_id: int, en_hash: str, deleted: bool) -> bool:
    post = load_post('ru', post_id)
    if not post:
        return False

    changed = False
    status = post.metadata.get('translation_status', 'draft')
    old_hash = str(post.metadata.get('en_source_hash') or '')

    if post.metadata.get('deleted') != deleted:
        post.metadata['deleted'] = deleted
        changed = True

    if not deleted and old_hash and old_hash != en_hash and status in {'reviewed', 'needs_review'}:
        if status != 'needs_review':
            post.metadata['translation_status'] = 'needs_review'
            changed = True

    if old_hash != en_hash:
        post.metadata['en_source_hash'] = en_hash
        changed = True

    if changed:
        post.metadata['updated_at'] = now_iso()
        save_post('ru', post_id, post)

    return changed


async def fetch_messages_incremental(client: TelegramClient, entity: Any, state: dict[str, Any], recent_window: int, full_backfill: bool) -> list[Message]:
    messages: dict[int, Message] = {}

    if full_backfill:
        async for msg in client.iter_messages(entity, reverse=True):
            if isinstance(msg, Message):
                messages[msg.id] = msg
        return sorted(messages.values(), key=lambda m: m.id)

    last_max = int(state.get('last_max_id') or 0)

    async for msg in client.iter_messages(entity, min_id=last_max, reverse=True):
        if isinstance(msg, Message):
            messages[msg.id] = msg

    async for msg in client.iter_messages(entity, limit=recent_window):
        if isinstance(msg, Message):
            messages[msg.id] = msg

    return sorted(messages.values(), key=lambda m: m.id)


async def audit_deletions(client: TelegramClient, entity: Any, known_ids: list[int]) -> list[int]:
    missing: list[int] = []

    for batch in chunked(known_ids, 100):
        fetched = await client.get_messages(entity, ids=batch)
        if not isinstance(fetched, list):
            fetched = [fetched]

        # Telethon usually preserves requested ordering for ids list.
        fetched_map: dict[int, Message | MessageEmpty | None] = {}
        for item in fetched:
            if item is None:
                continue
            fetched_map[getattr(item, 'id', -1)] = item

        for req_id in batch:
            item = fetched_map.get(req_id)
            if item is None or isinstance(item, MessageEmpty):
                missing.append(req_id)

    return sorted(set(missing))


async def run_sync(
    cfg: Config,
    full_backfill: bool,
    skip_delete_audit: bool,
    dry_run: bool,
    skip_media: bool,
) -> None:
    EN_DIR.mkdir(parents=True, exist_ok=True)
    RU_DIR.mkdir(parents=True, exist_ok=True)

    state = load_state()
    store = MediaStore(cfg)

    updated = 0
    unchanged = 0
    ru_touched = 0
    deleted_marked = 0

    async with TelegramClient(StringSession(cfg.string_session), cfg.api_id, cfg.api_hash) as client:
        entity = await client.get_entity(cfg.channel)

        messages = await fetch_messages_incremental(client, entity, state, cfg.recent_window, full_backfill)
        canonical = build_canonical_posts(messages)

        for primary, group in canonical:
            text = normalize_markdown(message_to_markdown(primary).strip())
            if not text and not any(item.media for item in group):
                continue

            reactions = extract_reactions(primary)
            source_hash = build_source_hash(primary, group, text, reactions)

            existing = load_post('en', primary.id)
            existing_hash = str(existing.metadata.get('source_hash') if existing else '')
            existing_deleted = bool(existing.metadata.get('deleted')) if existing else False

            if existing and existing_hash == source_hash and not existing_deleted:
                unchanged += 1
                continue

            title, summary = build_title_and_summary(text, primary.id)
            slug = slugify(title, max_length=90) or f'post-{primary.id}'

            media_items: list[dict[str, Any]] = []
            for item in group:
                media_items.extend(
                    await extract_media(
                        item,
                        store,
                        cfg.channel,
                        skip_media=skip_media,
                        max_video_bytes=cfg.max_video_bytes,
                    )
                )

            payload = {
                'id': primary.id,
                'slug': slug,
                'title': title,
                'summary': summary,
                'date': primary.date.isoformat() if primary.date else now_iso(),
                'edited_at': primary.edit_date.isoformat() if primary.edit_date else None,
                'channel': cfg.channel.lstrip('@'),
                'source_url': channel_url(cfg.channel, primary.id),
                'source_hash': source_hash,
                'deleted': False,
                'album_id': str(primary.grouped_id) if primary.grouped_id else None,
                'reactions': reactions,
                'media': media_items,
                'updated_at': now_iso(),
            }

            post = frontmatter.Post(text, **payload)
            if not dry_run:
                save_post('en', primary.id, post)
            updated += 1

            if sync_ru_state_from_en(primary.id, source_hash, deleted=False):
                ru_touched += 1

        latest = await client.get_messages(entity, limit=1)
        latest_id = 0
        if isinstance(latest, list) and latest:
            latest_id = int(getattr(latest[0], 'id', 0) or 0)
        elif latest:
            latest_id = int(getattr(latest, 'id', 0) or 0)

        known_ids = iter_existing_ids('en')

        if not skip_delete_audit and known_ids:
            missing_ids = await audit_deletions(client, entity, known_ids)
            for post_id in missing_ids:
                marked = False
                if mark_deleted_in_locale('en', post_id):
                    marked = True
                    deleted_marked += 1
                if mark_deleted_in_locale('ru', post_id):
                    marked = True
                if marked:
                    ru_touched += 1

        state['last_max_id'] = max(int(state.get('last_max_id') or 0), latest_id)
        state['last_sync_at'] = now_iso()
        state['known_ids'] = iter_existing_ids('en')

        if not dry_run:
            save_state(state)

    print('Sync complete')
    print(f'Updated EN posts: {updated}')
    print(f'Unchanged EN posts: {unchanged}')
    print(f'RU metadata touched: {ru_touched}')
    print(f'Marked deleted: {deleted_marked}')
    print(f'Current max message id: {state.get("last_max_id")}')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Sync Telegram channel into EN content files incrementally.')
    parser.add_argument('--full-backfill', action='store_true', help='Force full history fetch.')
    parser.add_argument('--skip-delete-audit', action='store_true', help='Skip deleted post audit.')
    parser.add_argument('--dry-run', action='store_true', help='Run without writing files.')
    parser.add_argument('--skip-media', action='store_true', help='Skip all media download/upload and keep only text metadata.')
    parser.add_argument('--recent-window', type=int, default=None, help='Override recent message scan window.')
    return parser.parse_args()


def load_config(args: argparse.Namespace) -> Config:
    api_id = int(env('TELEGRAM_API_ID', required=True))
    api_hash = env('TELEGRAM_API_HASH', required=True)
    string_session = env('TELEGRAM_STRING_SESSION', required=True)

    recent = args.recent_window if args.recent_window is not None else int(env('SYNC_RECENT_WINDOW', default='250'))
    max_video_bytes = int(env('MAX_VIDEO_BYTES', default='26214400'))
    if max_video_bytes < 0:
        raise RuntimeError('MAX_VIDEO_BYTES must be >= 0')

    return Config(
        api_id=api_id,
        api_hash=api_hash,
        string_session=string_session,
        channel=env('TELEGRAM_CHANNEL', default='phys_math_dev'),
        recent_window=recent,
        max_video_bytes=max_video_bytes,
        r2_endpoint=env('R2_ENDPOINT', default=''),
        r2_bucket=env('R2_BUCKET', default=''),
        r2_access_key_id=env('R2_ACCESS_KEY_ID', default=''),
        r2_secret_access_key=env('R2_SECRET_ACCESS_KEY', default=''),
        r2_public_base_url=env('R2_PUBLIC_BASE_URL', default=env('PUBLIC_MEDIA_BASE_URL', default='')),
    )


def main() -> None:
    args = parse_args()
    cfg = load_config(args)

    state = load_state()
    full_backfill = args.full_backfill or int(state.get('last_max_id') or 0) == 0

    asyncio.run(
        run_sync(
            cfg=cfg,
            full_backfill=full_backfill,
            skip_delete_audit=args.skip_delete_audit,
            dry_run=args.dry_run,
            skip_media=args.skip_media or args.dry_run,
        )
    )


if __name__ == '__main__':
    main()
