import { getImage } from 'astro:assets';
import { parse } from 'node-html-parser';
import type { MediaItem, PostRecord } from './types';

export async function postImages(post: PostRecord) {
  const root = parse(String(post.bodyHtml));
  const gallery = (post.media || []).filter((item) => !item.embedded);
  const embedded = root.querySelectorAll('img');
  const photos = [...gallery.filter((item) => item.kind === 'photo'), ...embedded];
  let number = 0;

  async function imageAttributes(src: string, media?: MediaItem, existingAlt?: string, inGallery = false) {
    number += 1;
    const first = number === 1;
    const context = post.title;
    const fallbackAlt = post.locale === 'ru'
      ? `Иллюстрация к публикации «${context}»${photos.length > 1 ? ` (${number} из ${photos.length})` : ''}`
      : `Illustration for “${context}”${photos.length > 1 ? ` (${number} of ${photos.length})` : ''}`;
    const alt = media?.alt || (existingAlt && !/^(Post image|Image|Photo)$/i.test(existingAlt) ? existingAlt : fallbackAlt);
    const originalWidth = media?.width;
    const originalHeight = media?.height;
    const width = Math.min(originalWidth || 1440, 1440);
    const height = originalWidth && originalHeight ? Math.round(width * originalHeight / originalWidth) : undefined;
    const galleryPhotos = gallery.filter((item) => item.kind === 'photo').length;
    const sizes = inGallery && galleryPhotos > 1
      ? `(max-width: 439px) calc(100vw - 4.5rem), (max-width: 628px) calc((100vw - 5.2rem) / 2), ${galleryPhotos > 2 ? 240 : 366}px`
      : '(max-width: 812px) calc(100vw - 4.5rem), 742px';
    const image = await getImage({
      src, width, ...(height ? { height } : { inferSize: true }),
      widths: [...new Set([360, 720, 1080, width].filter((size) => size <= width))].sort((a,b) => a-b),
      format: 'webp', quality: 85,
      sizes,
      alt, loading: first ? 'eager' : 'lazy', decoding: 'async',
      fetchpriority: first ? 'high' : 'auto'
    });
    return { ...image.attributes, src: image.src, srcset: image.srcSet.attribute, alt };
  }

  const media = [];
  for (const item of gallery) {
    media.push({ ...item, image: item.kind === 'photo' ? await imageAttributes(item.url, item, undefined, true) : undefined });
  }
  for (const node of embedded) {
    const src = node.getAttribute('src');
    if (!src) continue;
    const item = post.media?.find((media) => media.url === src);
    const attrs = await imageAttributes(src, item, node.getAttribute('alt'));
    for (const [key, value] of Object.entries(attrs)) {
      if (value !== undefined && value !== null) node.setAttribute(key, String(value));
    }
  }
  return { media, html: root.toString() };
}
