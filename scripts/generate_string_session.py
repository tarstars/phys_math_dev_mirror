#!/usr/bin/env python3
"""Generate Telethon StringSession for CI use."""

from __future__ import annotations

import asyncio
import os

from telethon import TelegramClient
from telethon.sessions import StringSession


async def main() -> None:
    api_id = os.getenv('TELEGRAM_API_ID') or input('TELEGRAM_API_ID: ').strip()
    api_hash = os.getenv('TELEGRAM_API_HASH') or input('TELEGRAM_API_HASH: ').strip()

    if not api_id or not api_hash:
        raise SystemExit('Both TELEGRAM_API_ID and TELEGRAM_API_HASH are required.')

    client = TelegramClient(StringSession(), int(api_id), api_hash)
    await client.start()
    session = client.session.save()

    print('\nStringSession generated successfully.\n')
    print(session)
    print('\nStore this value in GitHub secret TELEGRAM_STRING_SESSION.\n')

    await client.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
