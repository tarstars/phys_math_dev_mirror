export function GET() {
  const body = `User-agent: *
Allow: /

Host: https://phys-math.dev
Sitemap: https://phys-math.dev/sitemap.xml
`;

  return new Response(body, {
    headers: {
      'Content-Type': 'text/plain; charset=utf-8'
    }
  });
}
