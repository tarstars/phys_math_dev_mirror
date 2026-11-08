import { parse } from 'node-html-parser';
import { marked } from 'marked';

export function readableText(html: string): string {
  const root = parse(html);
  root.querySelectorAll('script, style, .katex-mathml').forEach((node) => node.remove());
  return root.structuredText.replace(/[\u200B-\u200D\u2060\uFEFF]/g, '').replace(/\s+/g, ' ').trim();
}

export function markdownText(markdown: string): string {
  return readableText(marked.parse(markdown) as string);
}

export function hasReadableBody(html: string): boolean {
  return /[\p{L}\p{N}]/u.test(readableText(html));
}

export function excerpt(text: string, length: number): string {
  if (text.length <= length) return text;
  const cut = text.slice(0, length + 1);
  const space = cut.lastIndexOf(' ');
  return `${cut.slice(0, space > length / 2 ? space : length).trimEnd()}…`;
}

export function prepareBody(html: string, title: string, resolvePost: (id: number, locale: string) => string | undefined, locale = 'en'): { html: string; heading: string } {
  const root = parse(html);
  const first = root.firstElementChild;
  const firstHeading = root.querySelector('h1');
  const headingIndex = firstHeading ? root.childNodes.indexOf(firstHeading) : -1;
  const beforeHeading = headingIndex >= 0 ? root.childNodes.slice(0, headingIndex).map((node) => node.toString()).join('') : '';
  let heading = title;
  // Rich messages already contain the article heading. Render it once, above the date.
  if (firstHeading && !hasReadableBody(beforeHeading)) {
    heading = firstHeading.text.trim();
    firstHeading.remove();
  } else if (first?.tagName === 'P' && first.text.trim().toLocaleLowerCase() === title.toLocaleLowerCase()) {
    first.remove();
  }
  root.querySelectorAll('h1').forEach((node) => { node.tagName = 'h2'; });

  for (const anchor of root.querySelectorAll('a[href]')) {
    let href = anchor.getAttribute('href') || '';
    // Telegram sometimes turns a filename into a domain-like link. There is no
    // published download for this file; retain the filename as code.
    if (href === 'gbdte.md') {
      anchor.tagName = 'code';
      anchor.removeAttribute('href');
      continue;
    }
    if (/^(?:[a-z0-9-]+\.)+(?:com|org|net|io|dev|edu|ru)(?:[/?#]|$)/i.test(href)) {
      href = `https://${href}`;
    }
    const post = href.match(/^(?:https?:\/\/phys-math\.dev)?\/(en|ru)\/post\/(\d+)-[^/?#]+\/?([?#].*)?$/);
    if (post) {
      const path = resolvePost(Number(post[2]), post[1]);
      if (path) href = path + (post[3] || '');
    }
    anchor.setAttribute('href', href);
    if (!/[\p{L}\p{N}]/u.test(readableText(anchor.innerHTML)) && !anchor.querySelector('img, video, audio, svg')) {
      anchor.textContent = locale === 'ru' ? 'Открыть исходную статью' : 'Read the original article';
    }
  }
  return { html: root.toString(), heading };
}
