#!/usr/bin/env python3
"""Post a message (optionally with a photo) to the channel via the Telegram user session.

This is how a navigational post (or any post) gets published with formatting + a collage.
Run it in a normal terminal — a sandbox may cap outbound connections.

    uv run --with telethon python scripts/post_telegram.py TEXT.md [IMAGE]

TEXT.md  - the post text (markdown). Links may be written [label](<url>) or [label](url);
           the angle brackets are stripped for Telegram.
IMAGE    - optional photo; sent as ONE message with TEXT.md as the caption.

Env (the same credentials the daily sync uses):
    TELEGRAM_API_ID, TELEGRAM_API_HASH   - https://my.telegram.org -> API development tools
    TELEGRAM_STRING_SESSION              - scripts/generate_string_session.py --qr
    TELEGRAM_CHANNEL                     - the channel handle (e.g. phys_math_dev)
"""
import asyncio, os, re, sys

from telethon import TelegramClient
from telethon.sessions import StringSession


def need(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        sys.exit(f"Missing env var {name} (same creds as the daily sync; see this script's docstring).")
    return v


def utf16_units(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


async def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: post_telegram.py TEXT.md [IMAGE]")
    text = open(sys.argv[1], encoding="utf-8").read().strip()
    text = re.sub(r"\(<([^>]+)>\)", r"(\1)", text)  # [label](<url>) -> [label](url)
    image = sys.argv[2] if len(sys.argv) > 2 else None

    if image:
        visible = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)  # links count only their label
        if utf16_units(visible) > 1024:
            sys.exit(f"Caption is {utf16_units(visible)} UTF-16 units (>1024). "
                     "Send the text as a separate message, or split it.")

    api_id = int(need("TELEGRAM_API_ID"))
    api_hash = need("TELEGRAM_API_HASH")
    session = need("TELEGRAM_STRING_SESSION")
    channel = need("TELEGRAM_CHANNEL")

    async with TelegramClient(StringSession(session), api_id, api_hash) as client:
        if image:
            if not os.path.exists(image):
                sys.exit(f"Image not found: {image}")
            await client.send_file(channel, image, caption=text, parse_mode="md")
        else:
            await client.send_message(channel, text, parse_mode="md", link_preview=False)
    print(f"Posted to @{channel}")


if __name__ == "__main__":
    asyncio.run(main())
