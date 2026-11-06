#!/usr/bin/env python3
"""Create initial, unpublished RU drafts with Telegram translation. Review each manually."""

from __future__ import annotations

import asyncio
import copy
import re

from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from telethon.tl import functions, types

from prepare_ru_drafts import create_ru_draft
from sync_telegram import EN_DIR, env, load_post, message_to_markdown, resolve_embedded_media, save_post


async def translate_new_drafts() -> None:
    created = failed = 0
    async with TelegramClient(
        StringSession(env('TELEGRAM_STRING_SESSION', required=True)),
        int(env('TELEGRAM_API_ID', required=True)), env('TELEGRAM_API_HASH', required=True),
    ) as client:
        entity = await client.get_entity(env('TELEGRAM_CHANNEL', default='phys_math_dev'))
        for en_path in sorted(EN_DIR.glob('*.md'), key=lambda p: int(p.stem)):
            post_id = int(en_path.stem)
            en = load_post('en', post_id)
            if not en or en.get('deleted') or load_post('ru', post_id):
                continue
            draft = create_ru_draft(en)
            try:
                source = await client.get_messages(entity, ids=post_id)
                translated = copy.copy(source)
                if source.rich_message:
                    result = await client(functions.messages.TranslateRichMessageRequest(to_lang='ru', peer=entity, id=[post_id]))
                    translated.rich_message = result.result[0]
                    content = message_to_markdown(translated)
                elif source.poll:
                    text = message_to_markdown(source)
                    result = await client(functions.messages.TranslateTextRequest(to_lang='ru', text=[types.TextWithEntities(text, [])]))
                    content = result.result[0].text
                elif source.message:
                    result = await client(functions.messages.TranslateTextRequest(to_lang='ru', peer=entity, id=[post_id]))
                    translated.message = result.result[0].text
                    translated.entities = result.result[0].entities
                    content = message_to_markdown(translated)
                else:
                    content = ''
                draft.content = resolve_embedded_media(content, en.get('media', []), en['source_url'])
                lead = next((line.strip() for line in draft.content.splitlines() if line.strip()), '')
                draft['title'] = re.sub(r'^[#*\s]+|\*+$', '', lead)[:130] if lead else f'Публикация {post_id}'
                draft['summary'] = ' '.join(draft.content.split())[:220]
                draft['translation_provider'] = 'telegram'
            except errors.FloodWaitError as exc:
                # Leave remaining items for a later run; never mark a failed translation reviewed.
                print(f'Translation rate limit at {post_id}: wait {exc.seconds}s before retrying')
                break
            except Exception as exc:
                failed += 1
                print(f'Draft {post_id} requires manual translation: {type(exc).__name__}: {exc}')
            save_post('ru', post_id, draft)
            created += 1
            print(f'Created unreviewed RU draft {post_id}')
            await asyncio.sleep(0.5)
    print(f'Created drafts: {created}; manual translation required: {failed}')


if __name__ == '__main__':
    asyncio.run(translate_new_drafts())
