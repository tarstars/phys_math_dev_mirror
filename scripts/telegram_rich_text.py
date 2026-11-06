"""Convert Telegram RichMessage/PageBlock content without silently dropping blocks."""

from __future__ import annotations

import html
import re
from typing import Any


def kind(value: Any) -> str:
    return type(value).__name__


def link(label: str, url: str) -> str:
    return f'[{label}](<{url.replace(">", "%3E")}>)'


def fence(text: str, language: str = '') -> str:
    longest = max((len(m.group()) for m in re.finditer(r'`+', text)), default=0)
    delimiter = '`' * max(3, longest + 1)
    return f'{delimiter}{language}\n{text}\n{delimiter}'


def rich_text(value: Any, *, plain: bool = False) -> str:
    if value is None:
        return ''
    if isinstance(value, str):
        return value if plain else re.sub(r'([\\`*_\[\]<>])', r'\\\1', value)
    name = kind(value)
    if name == 'TextEmpty':
        return ''
    if name == 'TextPlain':
        return rich_text(value.text, plain=plain)
    if name == 'TextConcat':
        return ''.join(rich_text(item, plain=plain) for item in value.texts)
    if name == 'TextCustomEmoji':
        return value.alt
    if name == 'TextMath':
        return value.source if plain else f'${value.source}$'
    if name == 'TextImage':
        return '' if plain else f'![Inline image](<tg-media:document:{value.document_id}>)'
    if not hasattr(value, 'text'):
        raise ValueError(f'Unsupported Telegram rich text: {name}')
    text = rich_text(value.text, plain=plain)
    if plain:
        return text
    wrappers = {
        'TextBold': ('**', '**'), 'TextItalic': ('*', '*'),
        'TextStrike': ('~~', '~~'), 'TextUnderline': ('<u>', '</u>'),
        'TextSubscript': ('<sub>', '</sub>'), 'TextSuperscript': ('<sup>', '</sup>'),
        'TextMarked': ('<mark>', '</mark>'), 'TextSpoiler': ('<span class="spoiler">', '</span>'),
    }
    if name in wrappers:
        before, after = wrappers[name]
        return before + text + after
    if name == 'TextFixed':
        raw = rich_text(value.text, plain=True)
        delimiter = '`' * (max((len(m.group()) for m in re.finditer(r'`+', raw)), default=0) + 1)
        return f'{delimiter} {raw} {delimiter}'
    if name == 'TextUrl':
        return link(text, value.url)
    if name == 'TextEmail':
        return link(text, 'mailto:' + value.email)
    if name == 'TextPhone':
        return link(text, 'tel:' + value.phone)
    if name == 'TextAnchor':
        return f'<span id="{html.escape(value.name, quote=True)}"></span>{text}'
    if name == 'TextDiff':
        return '~~' + rich_text(value.old_text) + '~~ ' + text
    if name == 'TextButton':
        button = value.type
        return link(text, button.url) if hasattr(button, 'url') else text
    if name in {
        'TextAutoEmail', 'TextAutoPhone', 'TextAutoUrl', 'TextBankCard', 'TextBotCommand',
        'TextCashtag', 'TextDate', 'TextHashtag', 'TextMention', 'TextMentionName',
    }:
        return text
    raise ValueError(f'Unsupported Telegram rich text: {name}')


def caption(value: Any) -> str:
    return '\n\n'.join(filter(None, (rich_text(value.text), rich_text(value.credit))))


def blocks_markdown(blocks: list[Any]) -> str:
    return '\n\n'.join(filter(None, (block_markdown(block) for block in blocks)))


def block_markdown(block: Any) -> str:
    name = kind(block)
    headings = {
        'PageBlockTitle': 1, 'PageBlockHeader': 2, 'PageBlockSubheader': 3,
        **{f'PageBlockHeading{n}': n for n in range(1, 7)},
    }
    if name in headings:
        return '#' * headings[name] + ' ' + rich_text(block.text)
    if name in {'PageBlockParagraph', 'PageBlockSubtitle', 'PageBlockFooter', 'PageBlockKicker', 'PageBlockThinking'}:
        return rich_text(block.text)
    if name == 'PageBlockMath':
        return f'$$\n{block.source}\n$$'
    if name == 'PageBlockPreformatted':
        return fence(rich_text(block.text, plain=True), block.language)
    if name == 'PageBlockDivider':
        return '---'
    if name == 'PageBlockAnchor':
        return f'<span id="{html.escape(block.name, quote=True)}"></span>'
    if name == 'PageBlockAuthorDate':
        return rich_text(block.author)
    if name in {'PageBlockBlockquote', 'PageBlockPullquote', 'PageBlockBlockquoteBlocks'}:
        body = blocks_markdown(block.blocks) if hasattr(block, 'blocks') else rich_text(block.text)
        body = '\n\n'.join(filter(None, (body, rich_text(block.caption))))
        return '\n'.join('> ' + line for line in body.splitlines())
    if name == 'PageBlockCover':
        return block_markdown(block.cover)
    if name in {'PageBlockCollage', 'PageBlockSlideshow'}:
        return '\n\n'.join(filter(None, (blocks_markdown(block.items), caption(block.caption))))
    if name == 'PageBlockDetails':
        return rich_text(block.title) + '\n\n' + blocks_markdown(block.blocks)
    if name in {'PageBlockList', 'PageBlockOrderedList'}:
        lines = []
        for index, item in enumerate(block.items, start=getattr(block, 'start', None) or 1):
            content = blocks_markdown(item.blocks) if hasattr(item, 'blocks') else rich_text(item.text)
            prefix = f'{getattr(item, "value", None) or index}. ' if name == 'PageBlockOrderedList' else '- '
            if getattr(item, 'checkbox', False):
                prefix += '[x] ' if getattr(item, 'checked', False) else '[ ] '
            lines.append(prefix + content.replace('\n', '\n' + ' ' * len(prefix)))
        return '\n'.join(lines)
    if name == 'PageBlockTable':
        rows = [[rich_text(cell.text).replace('|', '\\|').replace('\n', '<br>') for cell in row.cells] for row in block.rows]
        if not rows:
            return rich_text(block.title)
        width = max(map(len, rows))
        rows = [row + [''] * (width - len(row)) for row in rows]
        rows.insert(1, ['---'] * width)
        return rich_text(block.title) + '\n\n' + '\n'.join('| ' + ' | '.join(row) + ' |' for row in rows)
    media_fields = {
        'PageBlockPhoto': ('photo', 'photo_id'), 'PageBlockVideo': ('document', 'video_id'),
        'PageBlockAudio': ('document', 'audio_id'), 'PageBlockDocument': ('document', 'document_id'),
    }
    if name in media_fields:
        media_kind, field = media_fields[name]
        url = f'tg-media:{media_kind}:{getattr(block, field)}'
        if name == 'PageBlockPhoto':
            item = f'![Post image](<{url}>)'
        elif name in {'PageBlockVideo', 'PageBlockAudio'}:
            tag = 'video' if name == 'PageBlockVideo' else 'audio'
            item = f'<{tag} controls preload="metadata" src="{url}"></{tag}>'
        else:
            item = link('Download attachment', url)
        return '\n\n'.join(filter(None, (item, caption(block.caption))))
    if name == 'PageBlockEmbed':
        if block.url:
            return link('Embedded content', block.url) + '\n\n' + caption(block.caption)
        raise ValueError('Telegram embedded HTML has no source URL; refusing to drop it')
    if name == 'PageBlockEmbedPost':
        return '\n\n'.join(filter(None, (link(block.author or 'Source', block.url), blocks_markdown(block.blocks), caption(block.caption))))
    if name == 'PageBlockMap':
        url = f'https://www.openstreetmap.org/?mlat={block.geo.lat}&mlon={block.geo.long}'
        return link('Map', url) + '\n\n' + caption(block.caption)
    if name == 'PageBlockChannel':
        username = getattr(block.channel, 'username', None)
        return link(block.channel.title, f'https://t.me/{username}') if username else block.channel.title
    if name == 'PageBlockRelatedArticles':
        return rich_text(block.title) + '\n\n' + '\n'.join('- ' + link(item.title or item.url, item.url) for item in block.articles)
    if name == 'PageBlockButtonRow':
        labels = []
        for button in block.buttons:
            label = rich_text(button.text)
            labels.append(link(label, button.type.url) if hasattr(button.type, 'url') else label)
        return ' · '.join(labels)
    raise ValueError(f'Unsupported Telegram content block: {name}')
