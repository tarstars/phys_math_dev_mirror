"""Check the generated site's search directives, links and image delivery."""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import sys
import json
import re
from urllib.parse import unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET

DIST = Path(__file__).resolve().parents[1] / 'dist'
ORIGIN = 'https://phys-math.dev'


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.fallbacks = []
        self.scripts = []
        self.in_script = False
        self.canonical = None
        self.alternates = {}
        self.robots = ''
        self.h1 = 0
        self.links = []
        self.images = []
        self.article = False
        self.article_depth = 0
        self.lang = None
        self.social = {}
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'data-translation-fallback' in attrs:
            self.fallbacks.append(attrs['data-translation-fallback'])
        if tag == 'script':
            self.in_script = True
            self.scripts.append('')
        if tag == 'html':
            self.lang = attrs.get('lang')
        if tag == 'article' and 'post-page' in attrs.get('class', '').split():
            self.article = True
            self.article_depth += 1
        if tag == 'h1':
            self.h1 += 1
        if tag == 'meta':
            if attrs.get('name') == 'robots':
                self.robots = attrs.get('content', '')
            if attrs.get('property', '').startswith('og:'):
                self.social[attrs['property']] = attrs.get('content')
        if tag == 'link':
            if attrs.get('rel') == 'canonical':
                self.canonical = attrs.get('href')
            if attrs.get('hreflang'):
                self.alternates[attrs['hreflang']] = attrs.get('href')
        if tag == 'a' and attrs.get('href'):
            self.links.append(attrs['href'])
        if tag == 'img' and self.article_depth:
            self.images.append(attrs)

    def handle_data(self, data):
        if self.in_script:
            self.scripts[-1] += data

    def handle_endtag(self, tag):
        if tag == 'script':
            self.in_script = False
        if tag == 'article' and self.article_depth:
            self.article_depth -= 1


def check_translation_fallback(page, path, listed, target, require):
    """Validate the narrow RU-to-EN fallback contract, never a generic noindex exemption."""
    expected = '/en/' + path.removeprefix('/ru/')
    require(bool(re.fullmatch(r'/ru/post/\d+-[^/]+/', path)), f'Invalid fallback route: {path}')
    require(page.fallbacks == [expected], f'Invalid fallback target: {path}')
    require(page.canonical == ORIGIN + expected, f'Fallback canonical mismatch: {path}')
    directives = {part.strip() for part in page.robots.split(',')}
    require('noindex' in directives and 'follow' in directives and 'nofollow' not in directives,
            f'Fallback must be noindex,follow: {path}')
    require(ORIGIN + path not in listed, f'Fallback in sitemap: {path}')
    require(expected in page.links, f'Fallback link missing: {path}')
    require(not page.article, f'Fallback contains article: {path}')
    require(target(expected).is_file(), f'Fallback destination missing: {path}')
    if target(expected).is_file():
        destination = Page(target(expected).read_text())
        require(destination.canonical == ORIGIN + expected and not destination.fallbacks,
                f'Fallback destination is not canonical content: {path}')
    # Astro define:vars must serialize a concrete destination and execute the replacement.
    redirect_scripts = [script for script in page.scripts if 'window.location.replace' in script]
    valid_script = False
    if len(redirect_scripts) == 1:
        script = redirect_scripts[0].strip()
        # Astro wraps define:vars scripts in an IIFE.
        wrapper = re.fullmatch(r'\(function\(\)\{(.*)\}\)\(\);', script, re.DOTALL)
        if wrapper:
            script = wrapper[1]
        match = re.fullmatch(r'\s*(?:const|let|var) redirectTarget = ("[^"\n]*");\s*window\.location\.replace\(redirectTarget\);\s*', script)
        if match:
            try:
                valid_script = json.loads(match[1]) == expected
            except ValueError:
                pass
    require(valid_script, f'Invalid fallback JavaScript: {path}')


def check(dist=DIST):
    errors = []
    def require(condition, message):
        if not condition:
            errors.append(message)

    def target(url):
        path = unquote(urlsplit(url).path).lstrip('/')
        file = dist / path
        return file / 'index.html' if not file.suffix or path.endswith('/') else file

    ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9', 'x': 'http://www.w3.org/1999/xhtml'}
    sitemap = ET.parse(dist / 'sitemap.xml')
    listed = {}
    for node in sitemap.findall('s:url', ns):
        url = node.findtext('s:loc', namespaces=ns)
        require(url not in listed, f'Duplicate sitemap URL: {url}')
        listed[url] = {a.attrib['hreflang']: a.attrib['href'] for a in node.findall('x:link', ns)}
    redirects = {}
    for line in (dist / '_redirects').read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            source, destination, status = line.split()
            redirects[source] = destination
            require(status in ('301', '308'), f'Nonpermanent redirect: {source}')
    require(redirects.get('/') == '/en/', 'Root redirect missing')

    pages = {}
    counts = Counter()
    for file in sorted(dist.rglob('*.html')):
        relative = file.relative_to(dist).as_posix()
        # Verification documents are not site content pages.
        if not (relative.startswith(('en/', 'ru/')) or relative in ('index.html', '404.html')):
            continue
        path = '/' + relative.removesuffix('index.html')
        url = ORIGIN + path
        text = file.read_text()
        page = Page(text)
        pages[url] = page
        counts['html_pages'] += 1
        require('G-KW8VXVXW7N' in text and '106989967' in text, f'Analytics counter missing: {path}')
        if path in redirects:
            continue
        fallback = bool(page.fallbacks)
        if fallback:
            check_translation_fallback(page, path, listed, target, require)
            counts['translation_fallbacks'] += 1
        require(fallback or page.h1 == 1, f'Expected one main heading: {path} ({page.h1})')
        if relative == '404.html':
            continue
        require(fallback or page.canonical == url, f'Canonical mismatch: {path}: {page.canonical}')
        require(page.lang == path.split('/')[1], f'HTML language mismatch: {path}')
        require(bool(page.social.get('og:image')), f'Social image missing: {path}')
        if '/post/' in path:
            counts['posts'] += 1
            if 'noindex' in page.robots:
                counts['nonindexable_posts'] += 1
                require('follow' in page.robots and 'nofollow' not in page.robots, f'Nonindexable post blocks links: {path}')
                require(url not in listed, f'Nonindexable page in sitemap: {path}')
            else:
                require(url in listed, f'Indexable post missing from sitemap: {path}')
            require('JSON.stringify(redirectTarget)' not in text, f'Unexpanded redirect JavaScript: {path}')
        for i, image in enumerate(page.images):
            counts['article_images'] += 1
            require(bool(image.get('alt', '').strip()), f'Image lacks alternative text: {path}')
            require(all(str(image.get(key, '')).isdigit() and int(image[key]) > 0 for key in ('width', 'height')), f'Image dimensions missing: {path}')
            require(bool(image.get('srcset')) and bool(image.get('sizes')), f'Responsive image missing: {path}')
            require(image.get('loading') == ('eager' if i == 0 else 'lazy'), f'Image loading priority incorrect: {path}')
            require(image.get('fetchpriority') == ('high' if i == 0 else 'auto'), f'Image fetch priority incorrect: {path}')
            sources = [image.get('src', '')] + [s.strip().split()[0] for s in image.get('srcset', '').split(',') if s.strip()]
            for src in sources:
                require(src.startswith('/_astro/') and src.endswith('.webp'), f'Image not optimized locally: {path}: {src}')
                require(target(src).is_file(), f'Generated image missing: {path}: {src}')

    for url, page in pages.items():
        for href in page.links:
            resolved = urljoin(url, href)
            parts = urlsplit(resolved)
            if parts.scheme not in ('http', 'https') or parts.netloc != 'phys-math.dev':
                continue
            require(parts.path in redirects or target(resolved).is_file(), f'Broken local link: {url}: {href}')
        if url in listed:
            require('noindex' not in page.robots, f'Sitemap page is noindex: {url}')
            require(listed[url] == page.alternates, f'HTML/sitemap language links differ: {url}')
            for alternate in page.alternates.values():
                require(alternate in pages, f'Language target missing: {url}: {alternate}')
                if alternate in pages:
                    require(pages[alternate].alternates == page.alternates, f'Language links not reciprocal: {url}')
    for url in listed:
        require(url in pages, f'Sitemap target missing: {url}')
    for source, destination in redirects.items():
        if destination.startswith('/'):
            require(target(destination).is_file(), f'Redirect target missing: {source}: {destination}')

    print(f'Site checks: {dict(counts)}, sitemap URLs: {len(listed)}, redirects: {len(redirects)}')
    for error in errors[:40]:
        print(error, file=sys.stderr)
    if errors:
        raise SystemExit(f'{len(errors)} site checks failed')
    print('All generated-site checks passed.')


if __name__ == '__main__':
    check()
