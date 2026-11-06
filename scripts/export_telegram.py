#!/usr/bin/env python3
"""Export public channel messages for diagnosing/reviewing an import, never session data."""

import argparse
import asyncio
import json
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl import functions, types

from sync_telegram import env


async def export(output: Path) -> None:
    messages = []
    async with TelegramClient(
        StringSession(env('TELEGRAM_STRING_SESSION', required=True)),
        int(env('TELEGRAM_API_ID', required=True)), env('TELEGRAM_API_HASH', required=True),
    ) as client:
        entity = await client.get_entity(env('TELEGRAM_CHANNEL', default='phys_math_dev'))
        async for message in client.iter_messages(entity, reverse=True):
            if not isinstance(message, types.Message):
                continue
            rich = getattr(message, 'rich_message', None)
            if rich and rich.part:
                message.rich_message = await client(functions.messages.GetRichMessageRequest(entity, message.id))
            data = json.loads(message.to_json())
            messages.append({key: data.get(key) for key in (
                'id', 'date', 'edit_date', 'message', 'entities', 'media', 'rich_message',
                'grouped_id', 'reactions',
            )})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(messages, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Exported {len(messages)} public messages to {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    asyncio.run(export(parser.parse_args().output))
