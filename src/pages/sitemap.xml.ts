import { getEnPostMap, getLocalePosts, getRuPostMap } from '@/lib/content';

type UrlNode = {
  loc: string;
  lastmod?: string;
  alternates?: string[];
};

function xmlEscape(input: string): string {
  return input
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;');
}

export function GET() {
  const site = 'https://phys-math.dev';
  const urls: UrlNode[] = [];

  const enPosts = Array.from(getEnPostMap({ includeDeleted: false }).values());
  const ruMap = getRuPostMap({ includeDeleted: false, includeDraft: false });

  urls.push({
    loc: `${site}/en/`,
    alternates: [`${site}/en/`, `${site}/ru/`]
  });
  urls.push({
    loc: `${site}/ru/`,
    alternates: [`${site}/en/`, `${site}/ru/`]
  });

  const enPages = Math.max(1, Math.ceil(getLocalePosts('en').length / 20));
  const ruPages = Math.max(1, Math.ceil(getLocalePosts('ru').length / 20));

  for (let page = 1; page <= enPages; page += 1) {
    const ruPage = page <= ruPages ? `${site}/ru/archive/${page}/` : `${site}/ru/archive/1/`;
    urls.push({
      loc: `${site}/en/archive/${page}/`,
      alternates: [`${site}/en/archive/${page}/`, ruPage]
    });
  }

  for (let page = 1; page <= ruPages; page += 1) {
    const enPage = page <= enPages ? `${site}/en/archive/${page}/` : `${site}/en/archive/1/`;
    urls.push({
      loc: `${site}/ru/archive/${page}/`,
      alternates: [enPage, `${site}/ru/archive/${page}/`]
    });
  }

  for (const enPost of enPosts) {
    const enLoc = `${site}${enPost.path}`;
    const ruPost = ruMap.get(enPost.id);

    if (ruPost) {
      const ruLoc = `${site}${ruPost.path}`;
      urls.push({
        loc: enLoc,
        lastmod: enPost.edited_at || enPost.updated_at || enPost.date,
        alternates: [enLoc, ruLoc]
      });
      urls.push({
        loc: ruLoc,
        lastmod: ruPost.edited_at || ruPost.updated_at || ruPost.date,
        alternates: [enLoc, ruLoc]
      });
    } else {
      urls.push({
        loc: enLoc,
        lastmod: enPost.edited_at || enPost.updated_at || enPost.date,
        alternates: [enLoc]
      });
    }
  }

  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
${urls
  .map((node) => {
    const alternates = (node.alternates || [])
      .map((alt) => {
        const lang = alt.includes('/ru/') ? 'ru' : 'en';
        return `    <xhtml:link rel="alternate" hreflang="${lang}" href="${xmlEscape(alt)}" />`;
      })
      .join('\n');

    const xDefault = node.alternates?.some((x) => x.includes('/en/'))
      ? `\n    <xhtml:link rel="alternate" hreflang="x-default" href="${xmlEscape(node.alternates.find((x) => x.includes('/en/')) || `${site}/en/`)}" />`
      : '';

    return `  <url>
    <loc>${xmlEscape(node.loc)}</loc>
${node.lastmod ? `    <lastmod>${xmlEscape(new Date(node.lastmod).toISOString())}</lastmod>\n` : ''}${alternates}${xDefault}
  </url>`;
  })
  .join('\n')}
</urlset>`;

  return new Response(body, {
    headers: {
      'Content-Type': 'application/xml; charset=utf-8'
    }
  });
}
