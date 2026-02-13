export type Locale = 'en' | 'ru';

export type TranslationStatus = 'draft' | 'reviewed' | 'needs_review' | 'locked';

export type MediaKind = 'photo' | 'video' | 'file';

export interface Reaction {
  emoji: string;
  count: number;
}

export interface MediaItem {
  kind: MediaKind;
  url: string;
  fileName?: string;
  mimeType?: string;
  size?: number;
  width?: number;
  height?: number;
}

export interface PostFrontmatter {
  id: number;
  slug: string;
  title: string;
  summary: string;
  date: string;
  edited_at?: string | null;
  channel: string;
  source_url: string;
  source_hash: string;
  deleted?: boolean;
  album_id?: string | null;
  reactions?: Reaction[];
  media?: MediaItem[];
  translation_status?: TranslationStatus;
  en_source_hash?: string;
  updated_at?: string;
}

export interface PostRecord extends PostFrontmatter {
  locale: Locale;
  bodyMarkdown: string;
  bodyHtml: string;
  pathSlug: string;
  path: string;
}

export interface SiteText {
  title: string;
  subtitle: string;
  bodyMarkdown: string;
  bodyHtml: string;
}
