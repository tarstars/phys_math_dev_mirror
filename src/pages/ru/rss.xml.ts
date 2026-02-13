import rss from '@astrojs/rss';
import { getLocalePosts } from '@/lib/content';

export function GET(context: { site: URL | undefined }) {
  const posts = getLocalePosts('ru', { includeDeleted: false, includeDraft: false });

  return rss({
    title: 'PhysMath Hub (RU)',
    description: 'Переводы и материалы про физику, математику и программирование.',
    site: context.site,
    customData: '<language>ru-ru</language>',
    items: posts.slice(0, 100).map((post) => ({
      title: post.title,
      description: post.summary,
      pubDate: new Date(post.date),
      link: post.path,
      content: `${post.bodyHtml}<p><a href="${post.source_url}">Оригинал в Telegram</a></p>`
    }))
  });
}
