import fs from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import markedKatex from 'marked-katex-extension';
import type { Locale, PostFrontmatter, PostRecord, SiteText, TranslationStatus } from './types';
import { excerpt, hasReadableBody, markdownText, prepareBody } from './html';

marked.setOptions({
  gfm: true,
  breaks: true
});
marked.use(markedKatex({ throwOnError: false, trust: false, nonStandard: true }));

const ROOT = process.cwd();
const postCache = new Map<string, PostRecord[]>();

function resolvePostPath(id: number, locale: string): string | undefined {
  const file = path.join(ROOT, 'content', 'en', 'posts', `${id}.md`);
  if (!fs.existsSync(file)) return undefined;
  const { data } = readMarkdownFile(file);
  return data.deleted ? undefined : `/${locale}/post/${id}-${data.slug}/`;
}

function readMarkdownFile(filePath: string): { data: Record<string, unknown>; content: string } {
  const raw = fs.readFileSync(filePath, 'utf8');
  const parsed = matter(raw);
  return { data: parsed.data, content: parsed.content.trim() };
}

function toDateString(value: unknown, fallback: string): string {
  if (!value) {
    return fallback;
  }
  const dt = new Date(String(value));
  if (Number.isNaN(dt.getTime())) {
    return fallback;
  }
  return dt.toISOString();
}

function toPost(locale: Locale, filePath: string): PostRecord {
  const fallbackDate = new Date(0).toISOString();
  const { data, content } = readMarkdownFile(filePath);

  const id = Number(data.id);
  let slug = String(data.slug ?? `post-${id}`);
  if (locale === 'ru') {
    const enPath = path.join(ROOT, 'content', 'en', 'posts', `${id}.md`);
    if (fs.existsSync(enPath)) {
      slug = String(readMarkdownFile(enPath).data.slug ?? slug);
    }
  }
  const date = toDateString(data.date, fallbackDate);
  const rawHtml = marked.parse(content) as string;
  const indexable = hasReadableBody(rawHtml);
  const sharedOn = formatDate(date, locale);
  const hasPhotos = (data.media as PostFrontmatter['media'])?.some((item) => item.kind === 'photo');
  const photoOnly = hasPhotos && !rawHtml.includes('<a ');
  const fallbackTitle = locale === 'ru'
    ? `${photoOnly ? 'Фотография' : 'Внешняя публикация'} от ${sharedOn}`
    : `${photoOnly ? 'Photo' : 'External article'} shared on ${sharedOn}`;
  const rawTitle = markdownText(String(data.title ?? ''));
  const title = !rawTitle || /^(Post|Пост|Публикация)\s+\d+$/i.test(rawTitle) ? fallbackTitle : rawTitle;
  const prepared = prepareBody(rawHtml, title, resolvePostPath, locale);
  const summary = markdownText(String(data.summary ?? '')) || markdownText(content) || fallbackTitle;

  const fm: PostFrontmatter = {
    id,
    slug,
    title,
    summary: excerpt(summary, 220),
    date,
    edited_at: data.edited_at ? String(data.edited_at) : null,
    channel: String(data.channel ?? 'phys_math_dev'),
    source_url: String(data.source_url ?? ''),
    source_hash: String(data.source_hash ?? ''),
    deleted: Boolean(data.deleted ?? false),
    album_id: data.album_id ? String(data.album_id) : null,
    reactions: (Array.isArray(data.reactions) ? data.reactions : []) as PostFrontmatter['reactions'],
    media: (Array.isArray(data.media) ? data.media : []) as PostFrontmatter['media'],
    translation_status: (data.translation_status as TranslationStatus | undefined) ?? undefined,
    en_source_hash: data.en_source_hash ? String(data.en_source_hash) : undefined,
    updated_at: data.updated_at ? String(data.updated_at) : undefined
  };

  const pathSlug = `${fm.id}-${fm.slug}`;

  return {
    ...fm,
    locale,
    bodyMarkdown: content,
    bodyHtml: prepared.html,
    heading: prepared.heading,
    indexable,
    pathSlug,
    path: `/${locale}/post/${pathSlug}/`
  };
}

function postsDir(locale: Locale): string {
  return path.join(ROOT, 'content', locale, 'posts');
}

export function getLocalePosts(locale: Locale, options?: { includeDraft?: boolean; includeDeleted?: boolean }): PostRecord[] {
  const dir = postsDir(locale);
  if (!fs.existsSync(dir)) {
    return [];
  }

  const includeDraft = options?.includeDraft ?? false;
  const includeDeleted = options?.includeDeleted ?? false;
  const cacheKey = `${locale}:${includeDraft}:${includeDeleted}`;
  if (import.meta.env.PROD && postCache.has(cacheKey)) return postCache.get(cacheKey)!;

  const files = fs
    .readdirSync(dir)
    .filter((name) => name.endsWith('.md'))
    .map((name) => path.join(dir, name));

  const posts = files
    .map((filePath) => toPost(locale, filePath))
    .filter((post) => {
      if (!includeDeleted && post.deleted) {
        return false;
      }
      if (locale === 'ru' && !includeDraft && post.translation_status === 'draft') {
        return false;
      }
      return true;
    })
    .sort((a, b) => {
      const da = new Date(a.date).getTime();
      const db = new Date(b.date).getTime();
      if (db !== da) {
        return db - da;
      }
      return b.id - a.id;
    });

  if (import.meta.env.PROD) postCache.set(cacheKey, posts);
  return posts;
}

export function getEnPostMap(options?: { includeDeleted?: boolean }): Map<number, PostRecord> {
  return new Map(getLocalePosts('en', { includeDeleted: options?.includeDeleted ?? true, includeDraft: true }).map((post) => [post.id, post]));
}

export function getRuPostMap(options?: { includeDeleted?: boolean; includeDraft?: boolean }): Map<number, PostRecord> {
  return new Map(
    getLocalePosts('ru', {
      includeDeleted: options?.includeDeleted ?? true,
      includeDraft: options?.includeDraft ?? true
    }).map((post) => [post.id, post])
  );
}

export function getSiteText(locale: Locale): SiteText {
  const filePath = path.join(ROOT, 'content', 'site', `${locale}.md`);
  if (!fs.existsSync(filePath)) {
    const fallback = locale === 'en' ? 'PhysMath Hub' : 'Хаб ФизМат';
    return {
      title: fallback,
      subtitle: fallback,
      bodyMarkdown: '',
      bodyHtml: ''
    };
  }

  const { data, content } = readMarkdownFile(filePath);
  return {
    title: String(data.title ?? 'PhysMath Hub'),
    subtitle: String(data.subtitle ?? ''),
    bodyMarkdown: content,
    bodyHtml: marked.parse(content) as string
  };
}

export function formatDate(dateIso: string, locale: Locale): string {
  const dt = new Date(dateIso);
  return new Intl.DateTimeFormat(locale === 'ru' ? 'ru-RU' : 'en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  }).format(dt);
}

export function pageTitle(base: string, locale: Locale): string {
  const clean = markdownText(base).replace(/(?:\s*·\s*PhysMath Hub)+$/, '').trim();
  return `${excerpt(clean || (locale === 'ru' ? 'Физика, математика и программирование' : 'Physics, mathematics and programming'), 85)} · PhysMath Hub`;
}
