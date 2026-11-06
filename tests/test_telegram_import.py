import asyncio
import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import frontmatter
from telethon.tl import types
import sync_telegram as sync
from prepare_ru_drafts import update_ru_metadata
from telegram_rich_text import blocks_markdown, fence


def message(**kwargs):
    return types.Message(id=306, peer_id=types.PeerChannel(1), date=dt.datetime.now(dt.timezone.utc), **kwargs)


class TelegramImportTests(unittest.TestCase):
    def test_rich_article_keeps_text_code_math_links_and_media_positions(self):
        rich = types.RichMessage(blocks=[
            types.PageBlockHeading1(types.TextPlain('Pascal triangle')),
            types.PageBlockParagraph(types.TextConcat([
                types.TextPlain('See '), types.TextUrl(types.TextBold(types.TextPlain('proof')), 'https://example.org/proof', 0),
                types.TextPlain(' and '), types.TextMath(r'\binom{n}{k}'),
            ])),
            types.PageBlockPreformatted(types.TextPlain('if x < 3:\n    print("```")'), 'python'),
            types.PageBlockPhoto(42, types.PageCaption(types.TextPlain('Diagram'), types.TextEmpty())),
            types.PageBlockMath(r'F_n = F_{n-1} + F_{n-2}'),
        ], photos=[], documents=[])
        result = sync.message_to_markdown(message(message='', rich_message=rich))
        self.assertIn('# Pascal triangle', result)
        self.assertIn('[**proof**](<https://example.org/proof>)', result)
        self.assertIn(r'$\binom{n}{k}$', result)
        self.assertIn('````python\nif x < 3:', result)
        self.assertIn('tg-media:photo:42', result)
        self.assertIn('Diagram', result)
        self.assertIn('$$\nF_n = F_{n-1} + F_{n-2}\n$$', result)

    def test_poll_question_options_and_count_are_not_empty(self):
        poll = types.Poll(id=1, hash=0, question=types.TextWithEntities('Choose a path', []), answers=[
            types.PollAnswer(types.TextWithEntities('Right', []), b'a'),
            types.PollAnswer(types.TextWithEntities('Down', []), b'b'),
        ])
        media = types.MessageMediaPoll(poll, types.PollResults(total_voters=7))
        text = sync.message_to_markdown(message(message='', media=media))
        self.assertIn('Choose a path', text)
        self.assertIn('- Right\n- Down', text)
        self.assertIn('Votes: 7', text)

    def test_unknown_or_partial_content_fails_instead_of_truncating(self):
        with self.assertRaisesRegex(ValueError, 'unsupported Telegram media'):
            sync.message_to_markdown(message(message='', media=types.MessageMediaUnsupported()))
        with self.assertRaisesRegex(ValueError, 'partial rich message'):
            sync.message_to_markdown(message(message='', rich_message=types.RichMessage([], [], [], part=True)))
        with self.assertRaisesRegex(ValueError, 'Unsupported Telegram content block'):
            blocks_markdown([types.PageBlockUnsupported()])

    def test_embedded_resource_urls_resolve_and_skipped_files_keep_source_link(self):
        text = '![a](<tg-media:photo:42>) [movie](<tg-media:document:9>)'
        result = sync.resolve_embedded_media(text, [{'telegram_media_key': 'tg-media:photo:42', 'url': 'https://cdn.example/a.jpg'}], 'https://t.me/example/306')
        self.assertIn('https://cdn.example/a.jpg', result)
        self.assertIn('https://t.me/example/306', result)
        self.assertNotIn('tg-media:', result)

    def test_rich_title_uses_heading_after_cover_photo(self):
        title, summary = sync.build_title_and_summary('![Post image](<tg-media:photo:42>)\n\n# Pascal triangle\n\nAn explanation.', 306)
        self.assertEqual(title, 'Pascal triangle')
        self.assertNotIn('tg-media:', summary)

    def test_skipped_embedded_video_becomes_source_link(self):
        text = '<video controls src="tg-media:document:1"></video>'
        result = sync.resolve_embedded_media(text, [], 'https://t.me/example/306')
        self.assertNotIn('<video', result)
        self.assertIn('[View media on Telegram]', result)

    def test_draft_metadata_preserves_russian_summary_and_locked_post(self):
        ru = frontmatter.Post('Русский текст', summary='Русское описание', translation_status='reviewed', en_source_hash='old')
        changed, marked = update_ru_metadata({'id': 1, 'summary': 'English', 'source_hash': 'new'}, ru)
        self.assertTrue(changed and marked)
        self.assertEqual(ru['summary'], 'Русское описание')
        locked = frontmatter.Post('Текст', translation_status='locked', summary='Описание')
        before = frontmatter.dumps(locked)
        self.assertEqual(update_ru_metadata({'source_hash': 'new'}, locked), (False, False))
        self.assertEqual(frontmatter.dumps(locked), before)

    def test_dry_run_does_not_modify_content_translations_or_state(self):
        class Client:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def get_entity(self, channel): return channel
            async def get_messages(self, *args, **kwargs): return [message(message='Updated article')]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            en, ru, state = root / 'en', root / 'ru', root / 'state.json'
            ru.mkdir()
            ru_file = ru / '306.md'
            ru_file.write_text(frontmatter.dumps(frontmatter.Post('Русский', id=306, translation_status='reviewed', en_source_hash='old')))
            before = ru_file.read_bytes()
            cfg = sync.Config(1, 'hash', '', 'example', 250, 0, '', '', '', '', '')
            with patch.multiple(sync, EN_DIR=en, RU_DIR=ru, STATE_PATH=state), \
                 patch.object(sync, 'TelegramClient', return_value=Client()), \
                 patch.object(sync, 'fetch_messages_incremental', new=AsyncMock(return_value=[message(message='Updated article')])):
                asyncio.run(sync.run_sync(cfg, False, False, True, True))
            self.assertFalse(en.exists())
            self.assertFalse(state.exists())
            self.assertEqual(ru_file.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
