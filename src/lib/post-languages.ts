import type { PostRecord } from './types';

// Navigation can fall back to English; SEO alternates must be published and indexable.
export function postLanguages(en: PostRecord, ru?: PostRecord) {
  const enPath = `/en/post/${en.id}-${en.slug}/`;
  const ruAvailable = Boolean(ru && !ru.deleted && ru.translation_status !== 'draft');
  const ruPath = ruAvailable ? `/ru/post/${en.id}-${en.slug}/` : enPath;
  const alternates: Partial<Record<'en' | 'ru' | 'x-default', string>> = {};
  if (!en.deleted && en.indexable) {
    alternates.en = enPath;
    alternates['x-default'] = enPath;
    if (ruAvailable && ru?.indexable) alternates.ru = ruPath;
  }
  return { enPath, ruPath, ruAvailable, alternates };
}
