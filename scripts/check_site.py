"""Check the generated site's search directives, links and image delivery."""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import sys
from urllib.parse import unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET

DIST = Path(__file__).resolve().parents[1] / 'dist'
ORIGIN = 'https://phys-math.dev'


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
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

    def handle_endtag(self, tag):
        if tag == 'article' and self.article_depth:
            self.article_depth -= 1


def check():
    errors = []
    def require(condition, message):
        if not condition:
            errors.append(message)

    def target(url):
        path = unquote(urlsplit(url).path).lstrip('/')
        file = DIST / path
        return file / 'index.html' if not file.suffix or path.endswith('/') else file

    ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9', 'x': 'http://www.w3.org/1999/xhtml'}
    sitemap = ET.parse(DIST / 'sitemap.xml')
    listed = {}
    for node in sitemap.findall('s:url', ns):
        url = node.findtext('s:loc', namespaces=ns)
        require(url not in listed, f'Duplicate sitemap URL: {url}')
        listed[url] = {a.attrib['hreflang']: a.attrib['href'] for a in node.findall('x:link', ns)}
    redirects = {}
    for line in (DIST / '_redirects').read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            source, destination, status = line.split()
            redirects[source] = destination
            require(status in ('301', '308'), f'Nonpermanent redirect: {source}')
    require(redirects.get('/') == '/en/', 'Root redirect missing')

    pages = {}
    counts = Counter()
    for file in sorted(DIST.rglob('*.html')):
        relative = file.relative_to(DIST).as_posix()
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
        require(page.h1 == 1, f'Expected one main heading: {path} ({page.h1})')
        if relative == '404.html':
            continue
        require(page.canonical == url, f'Canonical mismatch: {path}: {page.canonical}')
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
