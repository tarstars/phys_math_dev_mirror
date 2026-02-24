#!/usr/bin/env python3
"""Generate Telethon StringSession for CI use."""

from __future__ import annotations

import asyncio
import argparse
import getpass
import os
import urllib.parse

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SendCodeUnavailableError,
    SessionPasswordNeededError,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Generate Telethon StringSession for CI.')
    parser.add_argument(
        '--force-sms',
        action='store_true',
        help='Request login code via SMS when possible.',
    )
    parser.add_argument(
        '--qr',
        action='store_true',
        help='Authorize via QR login instead of code-based login.',
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    api_id = os.getenv('TELEGRAM_API_ID') or input('TELEGRAM_API_ID: ').strip()
    api_hash = os.getenv('TELEGRAM_API_HASH') or input('TELEGRAM_API_HASH: ').strip()

    if not api_id or not api_hash:
        raise SystemExit('Both TELEGRAM_API_ID and TELEGRAM_API_HASH are required.')

    client = TelegramClient(StringSession(), int(api_id), api_hash)
    await client.connect()

    if await client.is_user_authorized():
        session = client.session.save()
        print('\nSession is already authorized on this machine.\n')
        print(session)
        print('\nStore this value in GitHub secret TELEGRAM_STRING_SESSION.\n')
        await client.disconnect()
        return

    if args.qr:
        qr = await client.qr_login()
        print('\nQR login requested.')
        print('On your phone: Telegram -> Settings -> Devices -> Link Desktop Device -> scan QR below.\n')

        try:
            import qrcode

            qr_code = qrcode.QRCode(border=1)
            qr_code.add_data(qr.url)
            qr_code.make(fit=True)
            qr_code.print_ascii(invert=True)
            print()
        except Exception:
            qr_image_url = (
                'https://api.qrserver.com/v1/create-qr-code/?size=400x400&data='
                + urllib.parse.quote(qr.url, safe='')
            )
            print('Could not render terminal QR.')
            print(f'QR URL: {qr.url}')
            print(f'Open this in browser to display QR image: {qr_image_url}\n')

        try:
            await qr.wait(timeout=300)
        except SessionPasswordNeededError:
            password = getpass.getpass('Please enter your Telegram 2FA password: ')
            await client.sign_in(password=password)
        except TimeoutError:
            raise SystemExit('QR login timed out after 300 seconds. Run again.')
    else:
        phone = os.getenv('TELEGRAM_PHONE') or input('TELEGRAM_PHONE (e.g. +12345678900): ').strip()
        if not phone:
            raise SystemExit('TELEGRAM_PHONE is required for login.')

        sent = await client.send_code_request(phone, force_sms=args.force_sms)
        sent_type = type(getattr(sent, 'type', None)).__name__
        print(f'\nCode was sent. Delivery type: {sent_type}')
        print("Use the newest numeric code only (do not use my.telegram.org alphanumeric code).")
        print("If no app code arrives, type 'sms' to request SMS fallback.\n")

        while True:
            code = input("Please enter numeric login code (or 'sms'): ").strip()
            if not code:
                continue

            if code.lower() == 'sms':
                try:
                    sent = await client.send_code_request(phone, force_sms=True)
                    sent_type = type(getattr(sent, 'type', None)).__name__
                    print(f'New code requested. Delivery type: {sent_type}')
                except SendCodeUnavailableError:
                    print('SMS resend unavailable now. Wait and try again later.')
                continue

            try:
                await client.sign_in(phone=phone, code=code, phone_code_hash=sent.phone_code_hash)
                break
            except PhoneCodeInvalidError:
                print('Invalid code. Try newest numeric code or type sms.')
                continue
            except PhoneCodeExpiredError:
                print('Code expired. Requesting a new one...')
                sent = await client.send_code_request(phone, force_sms=args.force_sms)
                sent_type = type(getattr(sent, 'type', None)).__name__
                print(f'New code requested. Delivery type: {sent_type}')
                continue
            except SessionPasswordNeededError:
                password = getpass.getpass('Please enter your Telegram 2FA password: ')
                await client.sign_in(password=password)
                break

    session = client.session.save()

    print('\nStringSession generated successfully.\n')
    print(session)
    print('\nStore this value in GitHub secret TELEGRAM_STRING_SESSION.\n')

    await client.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
