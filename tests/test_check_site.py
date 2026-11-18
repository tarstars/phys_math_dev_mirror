"""Generated HTML fixtures exercise the entire checker, including redirect failures."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from scripts.check_site import check, ORIGIN

EN = '/en/post/318-example/'
RU = '/ru/post/318-example/'


def page(path, body='<h1>Post</h1>', robots='index,follow', canonical=None, alternates=None):
    links = ''.join(f'<link rel="alternate" hreflang="{lang}" href="{ORIGIN}{href}">'
                    for lang, href in (alternates or {}).items())
    return (f'<html lang="{path.split("/")[1]}"><head>'
            f'<link rel="canonical" href="{ORIGIN}{canonical or path}">'
            f'<meta name="robots" content="{robots}">'
            f'<meta property="og:image" content="/social.png">{links}</head>'
            f'<body>G-KW8VXVXW7N 106989967 {body}</body></html>')


def fallback():
    return page(RU, f'<section data-translation-fallback="{EN}"><a href="{EN}">English</a></section>'
                f'<script>(function(){{const redirectTarget = "{EN}"; window.location.replace(redirectTarget);}})();</script>',
                robots='noindex,follow', canonical=EN)


class SiteChecksTest(unittest.TestCase):
    def run_site(self, ru_html=None, bilingual=False, missing_destination=False, list_fallback=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            alternates = {'en': EN, 'x-default': EN}
            if bilingual:
                alternates['ru'] = RU
            documents = {'/en/': page('/en/'), EN: page(EN, alternates=alternates),
                         RU: page(RU, alternates=alternates) if bilingual else (ru_html or fallback())}
            if missing_destination:
                del documents[EN]
            for path, html in documents.items():
                file = root / path.lstrip('/') / 'index.html'
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(html)
            (root / '_redirects').write_text('/ /en/ 301\n')
            nodes = []
            for path in ([EN, RU] if bilingual or list_fallback else [EN]):
                links = ''.join(f'<xhtml:link hreflang="{lang}" href="{ORIGIN}{href}" />'
                                for lang, href in alternates.items())
                nodes.append(f'<url><loc>{ORIGIN}{path}</loc>{links}</url>')
            (root / 'sitemap.xml').write_text('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
                                            'xmlns:xhtml="http://www.w3.org/1999/xhtml">' + ''.join(nodes) + '</urlset>')
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                check(root)

    def test_valid_translation_fallback(self):
        self.run_site()

    def test_normal_bilingual_content(self):
        self.run_site(bilingual=True)

    def test_malformed_fallbacks_fail(self):
        original = fallback()
        mutations = {
            'indexable': original.replace('noindex,follow', 'index,follow'),
            'nofollow': original.replace('noindex,follow', 'noindex,nofollow'),
            'canonical': original.replace(f'href="{ORIGIN}{EN}"', f'href="{ORIGIN}{RU}"'),
            'wrong destination': original.replace(f'data-translation-fallback="{EN}"', 'data-translation-fallback="/en/"'),
            'missing link': original.replace(f'href="{EN}"', 'href="/en/"'),
            'missing script': original.replace('window.location.replace(redirectTarget);', ''),
            'wrong script': original.replace(f'const redirectTarget = "{EN}"', 'const redirectTarget = "/en/"'),
            'unexpanded script': original.replace(f'"{EN}";', 'JSON.stringify(redirectTarget);'),
            'article': original.replace('</section>', '</section><article class="post-page"></article>'),
            'unmarked': original.replace(f'data-translation-fallback="{EN}"', ''),
        }
        for label, html in mutations.items():
            with self.subTest(label=label), self.assertRaises(SystemExit):
                self.run_site(ru_html=html)

    def test_missing_destination_fails(self):
        with self.assertRaises(SystemExit):
            self.run_site(missing_destination=True)

    def test_fallback_in_sitemap_fails(self):
        with self.assertRaises(SystemExit):
            self.run_site(list_fallback=True)

    def test_ordinary_noindex_page_still_requires_heading_and_self_canonical(self):
        for html in [page(RU, body='', robots='noindex,follow'),
                     page(RU, robots='noindex,follow', canonical=EN)]:
            with self.subTest(html=html), self.assertRaises(SystemExit):
                self.run_site(ru_html=html)
