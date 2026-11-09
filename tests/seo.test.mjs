import assert from 'node:assert/strict';
import test from 'node:test';
import { hasReadableBody, markdownText, prepareBody } from '../src/lib/html.ts';

const resolvePost = (id, locale) => id === 86 ? `/${locale}/post/86-mapreduce-in-the-farmer-was-replaced/` : undefined;

test('only pages with readable body content are eligible for search', () => {
  assert.equal(hasReadableBody('<p><a href="https://example.com">\u2060</a></p>'), false);
  assert.equal(hasReadableBody('<img src="photo.jpg" alt="A descriptive photograph">'), false);
  assert.equal(hasReadableBody('<p>Short but meaningful.</p>'), true);
  assert.equal(hasReadableBody('<p>Короткая заметка.</p>'), true);
});

test('metadata uses visible text rather than Markdown and hidden math markup', () => {
  assert.equal(markdownText('[**An article**](<https://example.com>)'), 'An article');
  assert.equal(markdownText('[\u2060](<https://example.com>)'), '');
});

test('rich heading is rendered once even after a cover image, with code and math retained', () => {
  const body = '<p><img src="cover.jpg"></p><h1>Pascal triangle</h1><pre><code>if (x &lt; 3) {}</code></pre><div class="katex">x²</div><h1>Another section</h1>';
  const result = prepareBody(body, 'Short title', resolvePost);
  assert.equal(result.heading, 'Pascal triangle');
  assert.equal(result.html.includes('<h1>'), false);
  assert.match(result.html, /<h2>Another section<\/h2>/);
  assert.match(result.html, /if \(x &lt; 3\)/);
  assert.match(result.html, /class="katex">x²/);
});

test('imported links resolve to domains and canonical post slugs without changing other sites', () => {
  const body = '<a href="Vocabulary.com">Vocabulary</a><a href="fonts.google.com">Fonts</a><a href="gbdte.md">gbdte.md</a><a href="https://phys-math.dev/ru/post/86-old/?q=a#proof">Article</a><a href="https://example.org/ru/post/86-old/">External</a>';
  const { html } = prepareBody(body, 'Title', resolvePost);
  assert.match(html, /href="https:\/\/Vocabulary.com"/);
  assert.match(html, /href="https:\/\/fonts.google.com"/);
  assert.match(html, /<code>gbdte.md<\/code>/);
  assert.match(html, /href="\/ru\/post\/86-mapreduce-in-the-farmer-was-replaced\/\?q=a#proof"/);
  assert.match(html, /href="https:\/\/example.org\/ru\/post\/86-old\/"/);
});

test('a missing post keeps its URL and fragment intact', () => {
  const { html } = prepareBody('<a href="/en/post/999-unknown/?q=a#proof">Missing</a>', 'Title', resolvePost);
  assert.match(html, /href="\/en\/post\/999-unknown\/\?q=a#proof"/);
});

test('invisible source links receive an accessible label in each language', () => {
  for (const [locale, label] of [['en', 'Read the original article'], ['ru', 'Открыть исходную статью']]) {
    const { html } = prepareBody('<p><a href="https://t.me/iv?url=example">\u2060</a></p>', 'Title', resolvePost, locale);
    assert.ok(markdownText(html).includes(label));
  }
});

test('linked media is retained when its anchor has no text', () => {
  const { html } = prepareBody('<a href="https://example.com"><img src="figure.jpg" alt="A diagram"></a>', 'Title', resolvePost);
  assert.match(html, /<img src="figure.jpg" alt="A diagram">/);
});
