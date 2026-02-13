import type { Locale } from './types';

export const LOCALES: Locale[] = ['en', 'ru'];

export const DEFAULT_LOCALE: Locale = 'en';

export const UI: Record<
  Locale,
  {
    home: string;
    archive: string;
    latestPosts: string;
    readMore: string;
    source: string;
    allPosts: string;
    page: string;
    previous: string;
    next: string;
    translationPending: string;
    themeLabel: string;
    languageLabel: string;
    notFound: string;
    backHome: string;
  }
> = {
  en: {
    home: 'Home',
    archive: 'Archive',
    latestPosts: 'Latest posts',
    readMore: 'Read',
    source: 'Original Telegram post',
    allPosts: 'Browse all posts',
    page: 'Page',
    previous: 'Previous',
    next: 'Next',
    translationPending: 'Russian translation is not published yet. Redirecting to English.',
    themeLabel: 'Switch theme',
    languageLabel: 'Language',
    notFound: 'Page not found',
    backHome: 'Go to homepage'
  },
  ru: {
    home: 'Главная',
    archive: 'Архив',
    latestPosts: 'Последние публикации',
    readMore: 'Читать',
    source: 'Оригинал в Telegram',
    allPosts: 'Открыть архив',
    page: 'Страница',
    previous: 'Назад',
    next: 'Вперёд',
    translationPending: 'Русский перевод пока не опубликован. Выполняется переход на английскую версию.',
    themeLabel: 'Сменить тему',
    languageLabel: 'Язык',
    notFound: 'Страница не найдена',
    backHome: 'На главную'
  }
};

export function oppositeLocale(locale: Locale): Locale {
  return locale === 'en' ? 'ru' : 'en';
}
